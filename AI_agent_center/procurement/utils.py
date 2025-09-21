import re
import json
import imaplib
import email
from email.header import decode_header
import fitz  # PyMuPDF
import io
from PIL import Image
import pytesseract
import csv 
import google.generativeai as genai
from django.conf import settings
from .models import ProcurementRequest, Supplier, Quote, Product, MasterVendor

# Try to import Excel libraries
try:
    import openpyxl # For .xlsx
    import xlrd # For .xls
    EXCEL_LIBS_INSTALLED = True
except ImportError:
    EXCEL_LIBS_INSTALLED = False
    print("WARNING: 'openpyxl' and 'xlrd' are not installed. Excel file parsing will be skipped.")


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

# ✨ NEW: Function to get a benchmark price from the AI when no other quotes are available
def get_ai_benchmark_price(product_name, specs):
    """
    Asks the AI to estimate a fair market price for a product.
    """
    if not model:
        return None

    prompt = (
        f"You are a procurement expert for the Indian market. Based on the following product details, "
        f"provide an estimated fair market price for a single unit in Indian Rupees (INR). "
        f"Your response MUST be a valid JSON object with a single key: 'estimated_price'. "
        f"The value should be a number only, without any currency symbols or text.\n\n"
        f"Product Name: '{product_name}'\n"
        f"Specifications: '{specs}'\n\n"
        f"Return ONLY the JSON object."
    )
    
    response_data = get_ai_response(prompt)
    if response_data and 'estimated_price' in response_data:
        try:
            return float(response_data['estimated_price'])
        except (ValueError, TypeError):
            return None
    return None


def process_incoming_quotes():
    """
    Independent agent function to process new incoming quotation emails.
    Updated to:
    - Handle emails with multiple line items correctly.
    - Use a single, more robust AI prompt for parsing all items.
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
        email_ids.sort(reverse=True)

        # --- STEP 4: Limit to the most recent 10 unseen emails (Optional) ---
        MAX_EMAILS = 10
        email_ids = email_ids[:MAX_EMAILS]

        print(f"Found {len(email_ids)} recent unseen emails to process.")

        processed_uids = set(Quote.objects.values_list('parsed_from_email_uid', flat=True))

        # --- STEP 5: Loop through latest unseen emails ---
        for e_id in email_ids:
            status, single_email_data = mail.fetch(e_id, '(RFC822 UID)')
            if status != 'OK':
                continue

            try:
                uid_match = re.search(r'UID\s+(\d+)', single_email_data[0][0].decode())
                if not uid_match:
                    continue
                uid = uid_match.group(1)
                if uid in processed_uids:
                    mail.store(e_id, '+FLAGS', '\\Seen')
                    continue
            except (IndexError, AttributeError):
                continue

            # --- STEP 6: Parse the email data ---
            msg = email.message_from_bytes(single_email_data[0][1])
            sender_name, sender_email = email.utils.parseaddr(msg.get("From"))
            vendor_display_name = sender_name if sender_name else sender_email.split('@')[0]

            extracted_text = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain" and part.get('Content-Disposition') is None:
                        extracted_text += part.get_payload(decode=True).decode(errors='ignore') + "\n\n"
            else:
                extracted_text += msg.get_payload(decode=True).decode(errors='ignore') + "\n\n"

            for part in msg.walk():
                if part.get_content_maintype() == 'multipart' or part.get('Content-Disposition') is None:
                    continue
                filename = part.get_filename()
                if filename:
                    try:
                        attachment_bytes = part.get_payload(decode=True)
                        extracted_text += f"\n--- ATTACHMENT: {filename} ---\n"
                        
                        if filename.lower().endswith('.pdf'):
                            with fitz.open(stream=io.BytesIO(attachment_bytes), filetype="pdf") as doc:
                                for page in doc:
                                    extracted_text += page.get_text() + "\n"
                        elif filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff')):
                            image = Image.open(io.BytesIO(attachment_bytes))
                            extracted_text += pytesseract.image_to_string(image) + "\n"
                        elif filename.lower().endswith('.xlsx') and EXCEL_LIBS_INSTALLED:
                            workbook = openpyxl.load_workbook(io.BytesIO(attachment_bytes))
                            for sheet in workbook.worksheets:
                                for row in sheet.iter_rows():
                                    row_text = [str(cell.value) for cell in row if cell.value is not None]
                                    if row_text: extracted_text += ", ".join(row_text) + "\n"
                        elif filename.lower().endswith('.xls') and EXCEL_LIBS_INSTALLED:
                            workbook = xlrd.open_workbook(file_contents=attachment_bytes)
                            for sheet in workbook.sheets():
                                for row_idx in range(sheet.nrows):
                                    row_text = [str(cell.value) for cell in sheet.row(row_idx) if cell.value is not None]
                                    if row_text: extracted_text += ", ".join(row_text) + "\n"
                        elif filename.lower().endswith('.csv'):
                            decoded_content = attachment_bytes.decode('utf-8', errors='ignore')
                            reader = csv.reader(io.StringIO(decoded_content))
                            for row in reader:
                                extracted_text += ", ".join(row) + "\n"
                        elif filename.lower().endswith('.txt'):
                            extracted_text += attachment_bytes.decode('utf-8', errors='ignore') + "\n"

                        extracted_text += f"--- END ATTACHMENT: {filename} ---\n\n"
                    except Exception as e:
                        print(f"Failed to parse attachment {filename}: {e}")

            if not extracted_text.strip():
                print(f"⚠️ No text extracted from email ID {e_id} - skipping")
                continue

            # === NEW: STEP 7 - Use a single AI prompt to extract all line items ===
            parsing_prompt = (
                f"You are an expert procurement assistant. From the following quotation text, "
                f"extract all line items. The response MUST be a valid JSON object with a single key 'quotes', "
                f"which contains a list of objects. Each object in the list represents a single quoted item and must have the following keys:\n"
                f"1. 'product_name': Extract the specific product name. Be precise.\n"
                f"2. 'price': Extract the price per unit as a number only. Remove currency symbols.\n"
                f"3. 'lead_time_days': Extract lead time as a number of days. If '2-3 weeks', return 21. If not found, return null.\n"
                f"4. 'payment_terms': Extract payment terms (e.g., 'Net 30'). If not found for a specific line item, it can be null.\n"
                f"5. 'discount': Extract any discount (e.g., '5%'). If none, return null.\n\n"
                f"If the text is not a quotation or you cannot find any line items, return an empty list: {{'quotes': []}}.\n"
                f"Return ONLY the JSON object.\n\n"
                f"Email Text:\n---\n{extracted_text[:30000]}"
            )
            parsed_data = get_ai_response(parsing_prompt)

            if not parsed_data or not parsed_data.get('quotes'):
                print(f"AI could not parse any quote items from email UID {uid}. Skipping.")
                mail.store(e_id, '+FLAGS', '\\Seen')
                continue

            # === NEW: STEP 8 - Loop through each extracted quote item and save it ===
            for item_data in parsed_data.get('quotes'):
                product_name = item_data.get('product_name')
                price = item_data.get('price')

                if not product_name or price is None:
                    print(f"Skipping an item from email UID {uid} due to missing name or price.")
                    continue

                # --- Find or create a procurement request for this specific item ---
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
                    print(f"✅ Created a new request '{product_name}' for quote from {sender_email}.")

                # --- Save the supplier and quote details to the database ---
                master_vendor, _ = MasterVendor.objects.get_or_create(
                    email=sender_email,
                    defaults={'name': vendor_display_name}
                )
                master_vendor.products.add(proc_request.product)

                supplier, _ = Supplier.objects.get_or_create(
                    procurement_request=proc_request,
                    master_vendor=master_vendor,
                    defaults={'name': master_vendor.name, 'email': sender_email}
                )

                # Use a unique UID for each quote by combining email UID and product name
                quote_uid = f"{uid}-{re.sub(r'[^a-zA-Z0-9]', '', product_name)}"

                Quote.objects.update_or_create(
                    parsed_from_email_uid=quote_uid,
                    defaults={
                        'procurement_request': proc_request,
                        'supplier': supplier,
                        'price': price,
                        'lead_time_days': item_data.get('lead_time_days'),
                        'payment_terms': item_data.get('payment_terms'),
                        'discount': item_data.get('discount'),
                        'full_email_body': extracted_text
                    }
                )
                new_quotes_found += 1

                if proc_request.status != 'quotes-received':
                    proc_request.status = 'quotes-received'
                    proc_request.save(update_fields=['status'])

                print(f"✅ Parsed and saved quote from {sender_email} for '{proc_request.title}'.")

            # Mark email as seen to prevent re-processing
            mail.store(e_id, '+FLAGS', '\\Seen')

        # --- STEP 9: Close the connection ---
        mail.close()
        mail.logout()

    except Exception as e:
        print(f"An error occurred during quote processing: {e}")

    return new_quotes_found