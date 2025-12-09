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
from django.core.mail import EmailMessage
from .models import ProcurementRequest, Supplier, Quote, Product, MasterVendor
import gspread
from google.oauth2.service_account import Credentials
from django.conf import settings
from datetime import datetime

try:
    import openpyxl
    import xlrd
    EXCEL_LIBS_INSTALLED = True
except ImportError:
    EXCEL_LIBS_INSTALLED = False
    print("WARNING: 'openpyxl' and 'xlrd' are not installed. Excel file parsing will be skipped.")

try:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
except Exception as e:
    print(f"Could not configure Gemini. Ensure GEMINI_API_KEY is set. Error: {e}")
    model = None

# ✨ NEW: Reusable function to send RFQs for a given request ID
def send_rfqs_for_request(request_id, attachment=None):
    """
    Handles the logic for sending RFQ emails for a specific procurement request.
    Returns a tuple: (success_boolean, message_string).
    """
    try:
        req = ProcurementRequest.objects.get(pk=request_id)
        suppliers = req.suppliers.all()
        if not suppliers.exists():
            # If no suppliers, move to RFQs Sent with 0 sent, so it doesn't get stuck.
            req.status = 'rfqs-sent'
            req.total_quotes_sent = 0
            req.save()
            return True, 'No suppliers were found for this request, but marking as complete.'
        
        suppliers_with_email = suppliers.filter(email__isnull=False).exclude(email__exact='')
        sent_via_email = 0
        
        if suppliers_with_email.exists():
            subject = f"Request for Quotation - {req.title} [REQ-{req.id}]"
            message_body = (
                f"Dear Supplier,\n\nWe are interested in procuring the following item:\n\n"
                f"Product: {req.title}\n"
                f"Quantity: {req.quantity}\n"
                f"Specifications: {req.specs or 'As per standard'}\n\n"
                f"Please provide your best quotation in a reply to this email.\n\n"
                f"Thank you,\nProcunova Automated System"
            )
            for supplier in suppliers_with_email:
                try:
                    email = EmailMessage(
                        subject,
                        message_body,
                        settings.DEFAULT_FROM_EMAIL,
                        [supplier.email]
                    )
                    if attachment:
                        attachment.seek(0)
                        email.attach(attachment.name, attachment.read(), attachment.content_type)
                    
                    email.send()
                    sent_via_email += 1
                except Exception as e:
                    print(f"Could not send email to {supplier.email}. Error: {e}")

        req.status = 'rfqs-sent'
        req.total_quotes_sent = req.suppliers.count()
        req.save()

        message = f'Process complete. {sent_via_email} RFQs sent via email.'
        return True, message
    except ProcurementRequest.DoesNotExist:
        return False, 'Request not found.'
    except Exception as e:
        return False, str(e)


def get_ai_response(prompt):
    if not model:
        print("AI model is not configured. Returning None.")
        return None
    try:
        response = model.generate_content(prompt, request_options={'timeout': 120})
        json_match = re.search(r'```json\s*(\{.*\}|\[.*\])\s*```', response.text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            json_text = response.text.strip()
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        raw_response = response.text if 'response' in locals() else 'N/A'
        print(f"AI Response Parsing Error: {e}\nRaw AI Response was:\n{raw_response}")
        return None
    except Exception as e:
        print(f"An unexpected AI error occurred: {e}")
        return None

def get_ai_benchmark_price(product_name, specs):
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
    new_quotes_found = 0
    if not all([settings.GMAIL_IMAP_HOST, settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD]):
        print("IMAP settings are not configured. Skipping quote processing.")
        return 0
    try:
        mail = imaplib.IMAP4_SSL(settings.GMAIL_IMAP_HOST)
        mail.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
        mail.select('inbox')
        status, data = mail.search(None, '(UNSEEN OR SUBJECT "Quotation" SUBJECT "Proforma Invoice")')
        if status != 'OK':
            print("Error searching emails.")
            return 0
        email_ids = data[0].split()
        if not email_ids:
            print("No new unseen emails found.")
            return 0
        email_ids.sort(reverse=True)
        MAX_EMAILS = 20
        email_ids = email_ids[:MAX_EMAILS]
        print(f"Found {len(email_ids)} recent unseen emails to process.")
        processed_uids = set(Quote.objects.values_list('parsed_from_email_uid', flat=True))

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

            parsing_prompt = (
                f"You are an expert procurement assistant. From the following quotation text, "
                f"extract all financial details. The response MUST be a valid JSON object with the following structure:\n"
                f"1. 'subtotal': The total value before taxes and freight. Extract as a number.\n"
                f"2. 'tax_amount': The total tax amount (e.g., GST). Extract as a number.\n"
                f"3. 'freight_charges': Any shipping or freight costs. Extract as a number.\n"
                f"4. 'total_amount': The final grand total. Extract as a number.\n"
                f"5. 'line_items': A list of objects, where each object represents a single quoted item and MUST have these keys:\n"
                f"   - 'product_name': The specific product name.\n"
                f"   - 'quantity': The quantity of the item. Extract as a number or string.\n"
                f"   - 'price': The price PER UNIT. Extract as a number.\n"
                f"   - 'lead_time_days': Lead time in days. If '7-10 days', return 10. If not found, return null.\n"
                f"   - 'payment_terms': Payment terms (e.g., '100% Advance'). If not found, return null.\n"
                f"   - 'discount': Any discount. If none, return null.\n\n"
                f"If the text is not a quotation or you cannot find line items, return {{'line_items': []}}.\n"
                f"Return ONLY the JSON object.\n\n"
                f"Email Text:\n---\n{extracted_text[:30000]}"
            )
            parsed_data = get_ai_response(parsing_prompt)

            if not parsed_data or not parsed_data.get('line_items'):
                print(f"AI could not parse any quote items from email UID {uid}. Skipping.")
                mail.store(e_id, '+FLAGS', '\\Seen')
                continue
            
            invoice_details = {
                'subtotal': parsed_data.get('subtotal'),
                'tax_amount': parsed_data.get('tax_amount'),
                'freight_charges': parsed_data.get('freight_charges'),
                'total_amount': parsed_data.get('total_amount'),
            }

            for index, item_data in enumerate(parsed_data.get('line_items')):
                product_name = item_data.get('product_name')
                price = item_data.get('price')
                quantity = item_data.get('quantity')
                if not product_name or price is None:
                    print(f"Skipping an item from email UID {uid} due to missing name or price.")
                    continue
                proc_request = ProcurementRequest.objects.filter(
                    product__name__iexact=product_name,
                    status__in=['rfqs-sent', 'quotes-received']
                ).first()
                if not proc_request:
                    product, _ = Product.objects.get_or_create(name=product_name)
                    proc_request = ProcurementRequest.objects.create(
                        title=product_name, product=product, status='quotes-received',
                        quantity=quantity or 'N/A (from email)',
                        specs=f'Automatically created from a quote received from {sender_email}.',
                        source='Manual'
                    )
                    print(f"✅ Created a new request '{product_name}' for quote from {sender_email}.")
                master_vendor, _ = MasterVendor.objects.get_or_create(
                    email=sender_email, defaults={'name': vendor_display_name}
                )
                master_vendor.products.add(proc_request.product)
                supplier, _ = Supplier.objects.get_or_create(
                    procurement_request=proc_request, master_vendor=master_vendor,
                    defaults={'name': master_vendor.name, 'email': sender_email}
                )
                quote_uid = f"{uid}-{index}"
                Quote.objects.update_or_create(
                    parsed_from_email_uid=quote_uid,
                    defaults={
                        'procurement_request': proc_request,
                        'supplier': supplier,
                        'price': price,
                        'quantity': quantity,
                        'lead_time_days': item_data.get('lead_time_days'),
                        'payment_terms': item_data.get('payment_terms'),
                        'discount': item_data.get('discount'),
                        'full_email_body': extracted_text,
                        **invoice_details
                    }
                )
                new_quotes_found += 1
                if proc_request.status != 'quotes-received':
                    proc_request.status = 'quotes-received'
                    proc_request.save(update_fields=['status'])
                print(f"✅ Parsed and saved quote from {sender_email} for '{proc_request.title}'.")
            mail.store(e_id, '+FLAGS', '\\Seen')
        mail.close()
        mail.logout()
    except Exception as e:
        print(f"An error occurred during quote processing: {e}")
    return new_quotes_found

# NEW FUNCTION TO WRITE TO GOOGLE SHEETS
def append_suppliers_to_sheet(product_name, suppliers_data):
    """
    Appends a list of supplier data to a single master worksheet in Google Sheets.
    It adds the product name in the first column for each supplier.
    """
    if not suppliers_data:
        print("   [GSHEETS] No new supplier data to append.")
        return

    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_file(settings.GOOGLE_SHEETS_CREDENTIALS_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(settings.GOOGLE_SHEET_ID)

        MASTER_SHEET_NAME = "All Suppliers Data"

        try:
            worksheet = spreadsheet.worksheet(MASTER_SHEET_NAME)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=MASTER_SHEET_NAME, rows="1000", cols="20")

        headers = ['Product Name', 'Supplier Name', 'Email', 'Phone', 'Source Link', 'Scraped At']
        existing_headers = worksheet.get('A1:F1')
        if not existing_headers or not existing_headers[0] or existing_headers[0] != headers:
            worksheet.append_row(headers)

        # This line will now work correctly
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        rows_to_append = []
        for supplier in suppliers_data:
            row = [
                product_name,
                supplier.get('name', 'N/A'),
                supplier.get('email', 'N/A'),
                supplier.get('phone', 'N/A'),
                supplier.get('source_link', 'N/A'),
                now_str
            ]
            rows_to_append.append(row)

        worksheet.append_rows(rows_to_append)
        print(f"   [GSHEETS] ✅ Successfully appended {len(rows_to_append)} rows for '{product_name}' to master sheet.")

    except Exception as e:
        print(f"   [GSHEETS] ❌ An unexpected error occurred: {e}")