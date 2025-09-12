# procurement/utils.py

import re
import json
import imaplib
import email
from email.header import decode_header
import fitz  # PyMuPDF
import io
from PIL import Image
import pytesseract
import google.generativeai as genai
from django.conf import settings
from .models import ProcurementRequest, Supplier, Quote, Product, MasterVendor

# Configure the Gemini model
try:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    print(f"Could not configure Gemini. Ensure GEMINI_API_KEY is set. Error: {e}")
    model = None

def get_ai_response(prompt):
    """
    Sends a prompt to the Gemini model and returns a parsed JSON response.
    """
    if not model:
        print("AI model is not configured. Returning None.")
        return None

    try:
        # Call the Gemini API
        response = model.generate_content(prompt, request_options={'timeout': 120})
        
        # Clean up the JSON from the response
        json_match = re.search(r'```json\s*(\{.*\}|\[.*\])\s*```', response.text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            # If the ```json``` block is not found, try to parse the whole response
            json_text = response.text.strip()
        
        return json.loads(json_text)
        
    except json.JSONDecodeError as e:
        raw_response = response.text if 'response' in locals() else 'N/A'
        print(f"AI Response Parsing Error: {e}\nRaw AI Response was:\n{raw_response}")
        return None
    except Exception as e:
        print(f"An unexpected AI error occurred: {e}")
        return None

def process_incoming_quotes():
    """
    Independent agent function to process new incoming quotation emails.
    Updated to:
    - Fetch only recent unseen emails
    - Sort by newest first
    - Optionally limit to a certain number of latest emails
    """
    new_quotes_found = 0
    
    # --- STEP 0: Check IMAP configuration ---
    if not all([settings.GMAIL_IMAP_HOST, settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD]):
        print("IMAP settings are not configured. Skipping quote processing.")
        return 0

    try:
        # --- STEP 1: Connect to the IMAP server ---
        mail = imaplib.IMAP4_SSL(settings.GMAIL_IMAP_HOST)
        mail.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
        mail.select('inbox')

        # --- STEP 2: Search for unseen emails ---
        status, data = mail.search(None, '(UNSEEN OR SUBJECT "Quotation" SUBJECT "Proforma Invoice")')
        if status != 'OK':
            print("Error searching emails.")
            return 0

        email_ids = data[0].split()

        if not email_ids:
            print("No new unseen emails found.")
            return 0

        # --- STEP 3: Sort emails so latest come first ---
        email_ids.sort(reverse=True)  # Higher UID = Newer email

        # --- STEP 4: Limit to the most recent 5 unseen emails (Optional) ---
        MAX_EMAILS = 10
        email_ids = email_ids[:MAX_EMAILS]

        print(f"Found {len(email_ids)} recent unseen emails to process.")

        # Fetch already processed email UIDs to prevent duplicates
        processed_uids = set(Quote.objects.values_list('parsed_from_email_uid', flat=True))

        # --- STEP 5: Loop through latest unseen emails ---
        for e_id in email_ids:
            status, single_email_data = mail.fetch(e_id, '(RFC822 UID)')
            if status != 'OK':
                continue

            # Extract the email's UID
            try:
                uid_match = re.search(r'UID\s+(\d+)', single_email_data[0][0].decode())
                if not uid_match:
                    continue
                uid = uid_match.group(1)

                # Skip if already processed
                if uid in processed_uids:
                    mail.store(e_id, '+FLAGS', '\\Seen')  # Mark as seen
                    continue
            except (IndexError, AttributeError):
                continue

            # --- STEP 6: Parse the email data ---
            msg = email.message_from_bytes(single_email_data[0][1])
            sender_name, sender_email = email.utils.parseaddr(msg.get("From"))
            vendor_display_name = sender_name if sender_name else sender_email.split('@')[0]

            # Extract text from email body
            extracted_text = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain" and part.get('Content-Disposition') is None:
                        extracted_text += part.get_payload(decode=True).decode(errors='ignore') + "\n\n"
            else:
                extracted_text += msg.get_payload(decode=True).decode(errors='ignore') + "\n\n"

            # Extract text from attachments (PDF or images)
            for part in msg.walk():
                if part.get_content_maintype() == 'multipart' or part.get('Content-Disposition') is None:
                    continue
                filename = part.get_filename()
                if filename:
                    try:
                        attachment_bytes = part.get_payload(decode=True)
                        if filename.lower().endswith('.pdf'):
                            with fitz.open(stream=io.BytesIO(attachment_bytes), filetype="pdf") as doc:
                                for page in doc:
                                    extracted_text += page.get_text() + "\n\n"
                        elif filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff')):
                            image = Image.open(io.BytesIO(attachment_bytes))
                            extracted_text += pytesseract.image_to_string(image) + "\n\n"
                    except Exception as e:
                        print(f"Failed to parse attachment {filename}: {e}")

            if not extracted_text.strip():
                print(f"⚠️ No text extracted from email ID {e_id} - skipping")
                continue

            # --- STEP 7: Identify product name using Gemini AI ---
            product_identification_prompt = (
                f"From the following email/quotation text, identify the specific product name being quoted. "
                f"Be very precise. For example, if the text mentions '100 units of M12 High-Tensile Bolts', "
                f"the product is 'M12 High-Tensile Bolts'. "
                f"Return ONLY a valid JSON object with a single key 'product_name'. "
                f"If you cannot determine a specific product, return a value of null.\n\n"
                f"Email Text:\n---\n{extracted_text[:10000]}"  # Truncate for performance
            )
            identified_product_data = get_ai_response(product_identification_prompt)
            product_name = (
                identified_product_data.get('product_name')
                if identified_product_data and identified_product_data.get('product_name')
                else f"Unidentified Quote from {vendor_display_name}"
            )

            # --- STEP 8: Find or create a procurement request ---
            proc_request = ProcurementRequest.objects.filter(
                product__name__iexact=product_name,
                status__in=['rfqs-sent', 'quotes-received']
            ).first()

            if not proc_request:
                product, _ = Product.objects.get_or_create(name=product_name)
                proc_request = ProcurementRequest.objects.create(
                    title=product_name,
                    product=product,
                    status='quotes-received',
                    quantity='N/A (from email)',
                    specs=f'Automatically created from a quote received from {sender_email}.',
                    source='Manual'
                )
                print(f"✅ Created a new product-based request '{product_name}' for quote from {sender_email}.")

            # --- STEP 9: Extract quotation details using Gemini AI ---
            parsing_prompt = (
                f"You are an expert procurement assistant. From the following quotation text for our RFQ for '{proc_request.title}', "
                f"extract the following details precisely. The response must be a valid JSON object. "
                f"1. 'price': Extract the price per unit as a number only. Remove currency symbols like '₹' or '$'. "
                f"2. 'lead_time_days': Extract the lead time as a single number of days. If it says '2-3 weeks', return 21. "
                f"3. 'payment_terms': Extract the payment terms (e.g., 'Net 30', '50% Advance'). "
                f"4. 'discount': Extract any offered discount (e.g., '5%'). If none, return null. "
                f"Return ONLY the JSON object.\n\n"
                f"Email Text:\n---\n{extracted_text[:30000]}"  # Truncate for performance
            )
            parsed_data = get_ai_response(parsing_prompt)

            # --- STEP 10: Save data to the database ---
            if parsed_data and parsed_data.get('price'):
                master_vendor, _ = MasterVendor.objects.get_or_create(
                    email=sender_email,  # <-- Save email directly
                    defaults={
                       'name': vendor_display_name
                    }
                )
                master_vendor.products.add(proc_request.product)

                supplier, _ = Supplier.objects.get_or_create(
                    procurement_request=proc_request,
                    master_vendor=master_vendor,
                    defaults={'name': master_vendor.name, 'email': sender_email}  # <-- use sender_email
                )

                Quote.objects.create(
                    procurement_request=proc_request,
                    supplier=supplier,
                    price=parsed_data.get('price'),
                    lead_time_days=parsed_data.get('lead_time_days'),
                    payment_terms=parsed_data.get('payment_terms'),
                    discount=parsed_data.get('discount'),
                    parsed_from_email_uid=uid,
                    full_email_body=extracted_text
                )
                new_quotes_found += 1

                if proc_request.status != 'quotes-received':
                    proc_request.status = 'quotes-received'
                    proc_request.save(update_fields=['status'])

                print(f"✅ Parsed and saved quote from {sender_email} for '{proc_request.title}'.")

            # Mark email as seen to prevent re-processing
            mail.store(e_id, '+FLAGS', '\\Seen')

        # --- STEP 11: Close the connection ---
        mail.close()
        mail.logout()

    except Exception as e:
        print(f"An error occurred during quote processing: {e}")

    return new_quotes_found
