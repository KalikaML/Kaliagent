# procurement/utils.py

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
from .models import ProcurementRequest, Supplier, Quote

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

# MODIFIED: Logic updated to create separate requests for each unassigned quote's vendor.
def process_incoming_quotes():
    """
    Connects to the IMAP server, finds all emails with the keyword 'quotation',
    tries to match them to a specific request. If it fails, it creates a NEW,
    vendor-specific request for that quote.
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

        active_requests = ProcurementRequest.objects.exclude(status='finalized')
        active_titles = list(active_requests.values_list('title', flat=True))
        
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
            # Use the name part of the email if the sender name is not available
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

            # AI Step 1: Identify procurement request
            proc_request = None
            if active_titles:
                identification_prompt = (
                    f"From the following email text, identify which of our procurement requests this quotation is for. "
                    f"Here is a list of our active procurement request titles: {json.dumps(active_titles)}. "
                    f"Analyze the email content and determine the best match from the list. "
                    f"Return ONLY a valid JSON object with a single key 'request_title' whose value is the exact matching title from the provided list. "
                    f"If no clear match can be found, return a JSON object with the key 'request_title' and a value of null.\n\n"
                    f"Email Text:\n---\n{extracted_text[:10000]}"
                )
                identified_data = get_ai_response(None, identification_prompt)
                matched_title = identified_data.get('request_title') if identified_data else None

                if matched_title and matched_title in active_titles:
                    try:
                        proc_request = active_requests.get(title=matched_title)
                    except ProcurementRequest.DoesNotExist:
                        proc_request = None
            
            # --- NEW LOGIC START ---
            # If no specific request is matched, create a new one for this vendor.
            if proc_request is None:
                request_title = f"Manual Quote - {vendor_display_name}"
                proc_request, created = ProcurementRequest.objects.get_or_create(
                    title=request_title,
                    defaults={
                        'quantity': 'N/A', 
                        'specs': f'Manual quotation received from {sender_email} that was not matched to an existing request.',
                        'source': 'Manual',
                        'status': 'quotes-received' # Directly set status to quotes-received
                    }
                )
                if created:
                    print(f"Created a new dedicated request '{request_title}' for unmatched quote from {sender_email}.")
                else:
                    print(f"Found existing manual request '{request_title}' for quote from {sender_email}.")
            # --- NEW LOGIC END ---

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
                supplier, _ = Supplier.objects.get_or_create(
                    procurement_request=proc_request,
                    email__iexact=sender_email,
                    defaults={'name': vendor_display_name, 'source_link': f'mailto:{sender_email}'}
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