import re
import json
import imaplib
import email
from email.header import decode_header
import fitz
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

def get_ai_response(html_content, prompt):
    """
    Sends a prompt and HTML content (optional) to the Gemini model and returns a parsed JSON response.
    """
    if not model:
        print("AI model is not configured. Returning None.")
        return None

    full_prompt = f"{prompt}\n\nHTML Content:\n{html_content}" if html_content else prompt

    try:
        response = model.generate_content(full_prompt, request_options={'timeout': 120})
        
        json_match = re.search(r'```json\s*(\{.*\}|\[.*\])\s*```', response.text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            json_text = response.text.strip()
        
        return json.loads(json_text)
        
    except (json.JSONDecodeError, IndexError) as e:
        raw_response = response.text if 'response' in locals() else 'N/A'
        print(f"AI Response Parsing Error: {e}\nRaw AI Response was:\n{raw_response}")
        return None
    except Exception as e:
        print(f"An unexpected AI error occurred: {e}")
        return None

def process_incoming_quotes():
    """
    Connects to the IMAP server, finds emails with 'quotation',
    and uses AI to identify the product. If an active request for the product exists,
    assigns the quote. Otherwise, creates a new request for that product.
    Also, it populates the MasterVendor list.
    """
    new_quotes_found = 0
    try:
        mail = imaplib.IMAP4_SSL(settings.GMAIL_IMAP_HOST)
        mail.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
        mail.select('inbox')

        status, data = mail.search(None, '(UNSEEN TEXT "quotation")')
        if status != 'OK':
            print("Error searching emails.")
            return 0
        
        email_ids = data[0].split()
        if not email_ids:
            print("No new emails with 'quotation' keyword found.")
            return 0

        processed_uids = set(Quote.objects.values_list('parsed_from_email_uid', flat=True))

        for e_id in email_ids:
            status, single_email_data = mail.fetch(e_id, '(RFC822 UID)')
            if status != 'OK': continue

            try:
                uid_match = re.search(r'UID\s+(\d+)', single_email_data[0][0].decode())
                if not uid_match or uid_match.group(1) in processed_uids: continue
                uid = uid_match.group(1)
            except (IndexError, AttributeError):
                continue
            
            msg = email.message_from_bytes(single_email_data[0][1])
            sender_name, sender_email = email.utils.parseaddr(msg.get("From"))
            vendor_display_name = sender_name if sender_name else sender_email.split('@')[0]


            extracted_text = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain" and part.get('Content-Disposition') is None:
                        extracted_text += part.get_payload(decode=True).decode(errors='ignore') + "\n\n"
            elif msg.get_content_type() == "text/plain":
                extracted_text += msg.get_payload(decode=True).decode(errors='ignore') + "\n\n"

            for part in msg.walk():
                if part.get_content_maintype() == 'multipart' or part.get('Content-Disposition') is None: continue
                filename = part.get_filename()
                if filename:
                    try:
                        attachment_bytes = part.get_payload(decode=True)
                        if filename.lower().endswith('.pdf'):
                            with fitz.open(stream=io.BytesIO(attachment_bytes), filetype="pdf") as doc:
                                for page in doc: extracted_text += page.get_text() + "\n\n"
                        elif filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff')):
                            image = Image.open(io.BytesIO(attachment_bytes))
                            extracted_text += pytesseract.image_to_string(image) + "\n\n"
                    except Exception as e:
                        print(f"Failed to parse attachment {filename}: {e}")
            
            if not extracted_text.strip(): continue

            proc_request = None
            
            # ✨ NEW: AI Step 1: Identify the PRODUCT from the email, not the request.
            product_identification_prompt = (
                f"From the following email/quotation text, identify the specific product name being quoted. "
                f"Be very precise. For example, if the text mentions 'M12 High-Tensile Bolts', the product is 'M12 High-Tensile Bolts'. "
                f"Return ONLY a valid JSON object with a single key 'product_name' and the identified product name as its value. "
                f"If you cannot determine a specific product, return a value of null.\n\n"
                f"Email Text:\n---\n{extracted_text[:10000]}"
            )
            identified_product_data = get_ai_response(None, product_identification_prompt)
            product_name = identified_product_data.get('product_name') if identified_product_data else f"Unidentified Quote from {vendor_display_name}"

            # Try to find an active request for this product
            active_request_for_product = ProcurementRequest.objects.filter(
                title__icontains=product_name,
                status__in=['new-request', 'agent-working', 'awaiting-approval', 'rfqs-sent', 'quotes-received']
            ).first()

            if active_request_for_product:
                proc_request = active_request_for_product
                print(f"Matched quote to existing request: '{proc_request.title}'")
            else:
                # If no active request, create a new one for this product.
                product, _ = Product.objects.get_or_create(name=product_name)
                proc_request, created = ProcurementRequest.objects.get_or_create(
                    title=product_name,
                    status='quotes-received',
                    defaults={
                        'product': product,
                        'quantity': 'N/A (from email)', 
                        'specs': f'Automatically created from a quote received from {sender_email}.',
                        'source': 'Manual'
                    }
                )
                if created:
                    print(f"Created a new product-based request '{product_name}' for quote from {sender_email}.")

            # AI Step 2: Extract quotation details
            parsing_prompt = (
                f"You are an expert procurement assistant. From the following quotation text for our RFQ for '{proc_request.title}', "
                f"extract the following details precisely. The response must be a valid JSON object. "
                f"1. 'price': Extract the price per unit as a number. Ignore currency symbols. "
                f"2. 'lead_time_days': Extract the lead time as a single number of days. "
                f"3. 'payment_terms': Extract the payment terms (e.g., 'Net 30', '50% Advance'). "
                f"4. 'discount': Extract any offered discount (e.g., '5%', '₹100 off per unit'). If none, return null. "
                f"Return ONLY the JSON object. Do not include any other text or explanations.\n\n"
                f"Email Text:\n---\n{extracted_text[:30000]}"
            )
            parsed_data = get_ai_response(None, parsing_prompt) or {}

            if parsed_data.get('price'):
                # ✨ NEW: Get or create a MasterVendor and link it to the product
                master_vendor, _ = MasterVendor.objects.get_or_create(
                    email__iexact=sender_email,
                    defaults={'name': vendor_display_name}
                )
                if proc_request.product:
                    master_vendor.products.add(proc_request.product)

                # Get or create a request-specific supplier entry
                supplier, _ = Supplier.objects.get_or_create(
                    procurement_request=proc_request,
                    email__iexact=sender_email,
                    defaults={'name': vendor_display_name, 'master_vendor': master_vendor}
                )
                
                Quote.objects.create(
                    procurement_request=proc_request, supplier=supplier,
                    price=parsed_data.get('price'), lead_time_days=parsed_data.get('lead_time_days'),
                    payment_terms=parsed_data.get('payment_terms'), discount=parsed_data.get('discount'),
                    parsed_from_email_uid=uid, full_email_body=extracted_text
                )
                new_quotes_found += 1
                
                if proc_request.status not in ['quotes-received', 'finalized']:
                    proc_request.status = 'quotes-received'
                    proc_request.save()
                
                print(f"✅ Parsed and saved quote from {sender_email} for '{proc_request.title}'.")

            mail.store(e_id, '+FLAGS', '\\Seen')

        mail.close()
        mail.logout()
    except Exception as e:
        print(f"An error occurred during quote processing: {e}")

    return new_quotes_found