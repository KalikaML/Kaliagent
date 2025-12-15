import re
import os
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

# Quote detection keywords and patterns (subject/body)
QUOTE_KEYWORDS = [
    'quote', 'quotation', 'quotations', 'price', 'pricing', 'cost', 'estimate',
    'bid', 'rfq', 'request for quotation', 'purchase order', 'po',
    'proforma invoice', 'proforma'
]

def _decode_subject(msg):
    raw = msg.get('Subject', '')
    try:
        parts = decode_header(raw)
        decoded = ''
        for text, enc in parts:
            if isinstance(text, bytes):
                decoded += text.decode(enc or 'utf-8', errors='ignore')
            else:
                decoded += text or ''
        return decoded
    except Exception:
        return raw or ''

def _compile_patterns_from_keywords(keywords):
    patterns = []
    for kw in keywords:
        if kw.lower() == 'po':
            # PO as a standalone token (common shorthand for Purchase Order)
            patterns.append(re.compile(r'(?<![A-Za-z])PO(?![A-Za-z])', re.IGNORECASE))
            continue
        # word-boundary for normal tokens; allow spaces (handled by \b around ends)
        escaped = re.escape(kw)
        patterns.append(re.compile(rf"\b{escaped}\b", re.IGNORECASE))
    return patterns

KEYWORD_PATTERNS = _compile_patterns_from_keywords(QUOTE_KEYWORDS)

def _build_product_identifier_patterns():
    # Consider only active requests to focus search
    reqs = ProcurementRequest.objects.filter(
        status__in=['rfqs-sent', 'quotes-received'],
        rfq_sent_time__isnull=False
    )
    names = set()
    for r in reqs.select_related('product'):
        if r.product and r.product.name:
            names.add(r.product.name.strip())
        if r.title:
            names.add(r.title.strip())
    patterns = []
    for name in names:
        if not name:
            continue
        escaped = re.escape(name)
        patterns.append(re.compile(rf"\b{escaped}\b", re.IGNORECASE))
    return patterns

def _text_matches_any(text, patterns):
    if not text:
        return False
    for p in patterns:
        if p.search(text):
            return True
    return False

def extract_text_from_uploaded_file(django_file):
    """Extracts text from an uploaded file (pdf/images/excel/csv/txt)."""
    try:
        name = (django_file.name or '').lower()
        content = django_file.read()
        text = ''
        if name.endswith('.pdf'):
            with fitz.open(stream=io.BytesIO(content), filetype="pdf") as doc:
                for page in doc:
                    text += page.get_text() + "\n"
        elif name.endswith(('.png', '.jpg', '.jpeg', '.tiff')):
            image = Image.open(io.BytesIO(content))
            text += pytesseract.image_to_string(image) + "\n"
        elif name.endswith('.xlsx') and EXCEL_LIBS_INSTALLED:
            workbook = openpyxl.load_workbook(io.BytesIO(content))
            for sheet in workbook.worksheets:
                for row in sheet.iter_rows():
                    row_text = [str(cell.value) for cell in row if cell.value is not None]
                    if row_text: text += ", ".join(row_text) + "\n"
        elif name.endswith('.xls') and EXCEL_LIBS_INSTALLED:
            workbook = xlrd.open_workbook(file_contents=content)
            for sheet in workbook.sheets():
                for row_idx in range(sheet.nrows):
                    row_text = [str(cell.value) for cell in sheet.row(row_idx) if cell.value is not None]
                    if row_text: text += ", ".join(row_text) + "\n"
        elif name.endswith('.csv'):
            decoded_content = content.decode('utf-8', errors='ignore')
            reader = csv.reader(io.StringIO(decoded_content))
            for row in reader:
                text += ", ".join(row) + "\n"
        elif name.endswith('.txt'):
            text += content.decode('utf-8', errors='ignore') + "\n"
        return text
    except Exception as e:
        print(f"Failed to parse uploaded file {getattr(django_file, 'name', 'N/A')}: {e}")
        return ''

def parse_quote_text_to_items(extracted_text):
    """Uses AI to parse quotation text to invoice details and line items."""
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
        f"Text:\n---\n{extracted_text[:30000]}"
    )
    return get_ai_response(parsing_prompt)

# ===== Historical suppliers CSV loader =====
from functools import lru_cache

@lru_cache(maxsize=1)
def _load_previous_suppliers_csv():
    path = getattr(settings, 'PREVIOUS_SUPPLIERS_CSV', None)
    if not path:
        print("[CSV Loader] PREVIOUS_SUPPLIERS_CSV is not set; skipping historical suppliers.")
        return []
    if not os.path.exists(path):
        print(f"[CSV Loader] Historical suppliers CSV not found at: {path}")
        return []
    rows = []
    try:
        with open(path, 'rb') as f:
            raw = f.read()
        for enc in ('utf-8', 'utf-8-sig', 'latin-1', 'iso-8859-1'):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                text = None
        if text is None:
            return []
        import csv as _csv
        reader = _csv.DictReader(text.splitlines())
        for row in reader:
            # Normalize keys and strip values
            norm = {}
            for k, v in row.items():
                if k is None:
                    continue
                key = str(k).strip().lower()
                val = (v.strip() if isinstance(v, str) else ('' if v is None else v))
                norm[key] = val
            rows.append(norm)
    except Exception as e:
        print(f"Failed to load previous suppliers CSV at {path}: {e}")
        return []
    print(f"[CSV Loader] Loaded {len(rows)} rows from historical suppliers CSV: {path}")
    return rows

def load_previous_suppliers_for_product(product_name: str) -> list[dict]:
    """Return list of supplier dicts for given product from local CSV.
    Expected columns (case-insensitive, flexible): product, product name/title/description, supplier name, email, phone, source link/url/website.
    """
    if not product_name:
        return []
    rows = _load_previous_suppliers_csv()
    if not rows:
        return []
    target = product_name.strip().lower()
    results = []
    for r in rows:
        prod = (
            r.get('product') or r.get('product name') or r.get('product title') or r.get('item') or r.get('item description') or r.get('product description')
        )
        if not prod:
            continue
        pnorm = str(prod).strip().lower()
        if pnorm == target or target in pnorm:
            name = r.get('supplier') or r.get('supplier name') or r.get('name')
            email = r.get('email')
            phone = r.get('phone') or r.get('mobile') or r.get('contact')
            src = r.get('source') or r.get('source link') or r.get('url') or r.get('website')
            item = {'name': name or 'N/A', 'email': email, 'phone': phone, 'source_link': src}
            # Only include entries with at least an email or phone
            if item['email'] or item['phone']:
                results.append(item)
    return results

# ✨ NEW: Reusable function to send RFQs for a given request ID
def send_rfqs_for_request(request_id, attachment=None):
    """
    Handles the logic for sending RFQ emails for a specific procurement request.
    Returns a tuple: (success_boolean, message_string).
    """
    try:
        req = ProcurementRequest.objects.get(pk=request_id)
        # Validate SMTP configuration before attempting sends
        email_user = getattr(settings, 'EMAIL_HOST_USER', None)
        email_pass = getattr(settings, 'EMAIL_HOST_PASSWORD', None)
        email_host = getattr(settings, 'EMAIL_HOST', None)
        email_port = getattr(settings, 'EMAIL_PORT', None)
        default_from = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or email_user
        if not all([email_host, email_port, email_user, email_pass]):
            return False, (
                'Email is not configured correctly. Please set EMAIL_HOST, EMAIL_PORT, '
                'EMAIL_HOST_USER, and EMAIL_HOST_PASSWORD in environment settings.'
            )
        suppliers = req.suppliers.all()
        if not suppliers.exists():
            # If no suppliers, move to RFQs Sent with 0 sent, so it doesn't get stuck.
            req.status = 'rfqs-sent'
            req.total_quotes_sent = 0
            req.save()
            return True, 'No suppliers were found for this request, but marking as complete.'
        
        suppliers_with_email = suppliers.filter(email__isnull=False).exclude(email__exact='')
        sent_via_email = 0
        
        errors = []
        if suppliers_with_email.exists():
            subject = f"Request for Quotation - {req.title} [REQ-{req.id}]"
            message_body = (
                f"Dear Supplier,\n\n"
                f"We are seeking a quotation for the item below. Kindly provide a complete response with the requested fields so we can compare fairly.\n\n"
                f"Product Details:\n"
                f"- Product: {req.title}\n"
                f"- Quantity: {req.quantity}\n"
                f"- Specifications: {req.specs or 'As per standard'}\n\n"
                f"Required Quote Data (please fill every item):\n"
                f"Pricing:\n"
                f"- Unit Price (INR): [ ]\n"
                f"- Subtotal (INR, before taxes & freight): [ ]\n"
                f"- Tax Amount (INR, e.g., GST): [ ]\n"
                f"- Freight/Shipping Charges (INR): [ ]\n"
                f"- Grand Total (INR, after taxes & freight): [ ]\n"
                f"- Discount (% or INR, specify type): [ ]\n\n"
                f"Delivery:\n"
                f"- Lead Time (calendar days): [ ]\n\n"
                f"Payment Terms:\n"
                f"- Terms (e.g., On delivery / 50% advance / 100% advance): [ ]\n\n"
                f"Product Identification:\n"
                f"- Product Name: [ ]\n"
                f"- SKU / Model Number: [ ]\n\n"
                f"Additional Terms:\n"
                f"- Warranty (months): [ ]\n"
                f"- Return/Replacement Policy: [ ]\n\n"
                f"Supplier Information:\n"
                f"- Company Name: [ ]\n"
                f"- Contact Person: [ ]\n"
                f"- Email & Phone: [ ]\n\n"
                f"Submission Instructions:\n"
                f"- Reply to this email with the details above in the body, or attach a PDF/Excel with these fields clearly labeled.\n"
                f"- If multiple options exist (grades/specs), list each line item separately with its own unit price, lead time, and terms.\n\n"
                f"Acceptance Criteria:\n"
                f"- Complete pricing (unit, taxes, freight, total).\n"
                f"- Lead time aligned with our delivery needs.\n"
                f"- Payment terms compatible with our policies.\n"
                f"- Clear product identification (name/SKU/model).\n"
                f"- Validity and warranty stated.\n\n"
                f"Thank you,\nKalika Enterprises\n"
                f"Office Address: Plot No M-59, MIDC, Ahmednagar - 414 001 (M.S.) INDIA\n"
            )

            for supplier in suppliers_with_email:
                try:
                    email = EmailMessage(
                        subject,
                        message_body,
                        default_from,
                        [supplier.email]
                    )
                    if attachment:
                        attachment.seek(0)
                        email.attach(attachment.name, attachment.read(), attachment.content_type)
                    
                    email.send()
                    sent_via_email += 1
                except Exception as e:
                    err = f"Could not send email to {supplier.email}. Error: {e}"
                    print(err)
                    errors.append(err)

        from django.utils import timezone
        # Only mark as sent if there were no email-capable suppliers or at least one email was sent successfully
        if (not suppliers_with_email.exists()) or sent_via_email > 0:
            req.status = 'rfqs-sent'
            req.total_quotes_sent = req.suppliers.count()
            req.rfq_sent_time = timezone.now()
            req.save()
        else:
            # Keep status unchanged if sending failed for all email-capable suppliers
            if errors:
                return False, f"Failed to send RFQs to all suppliers with email. First error: {errors[0]}"

        message = f'Process complete. {sent_via_email} RFQs sent via email.'
        if errors:
            message += f" ({len(errors)} failures)"
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
        # Limit IMAP search to emails from the last 7 days
        from datetime import datetime, timedelta
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%d-%b-%Y')
        # Widen search: fetch recent emails since date, we'll filter by subject/body locally.
        # Using server-side OR with many terms is unreliable across providers.
        search_criteria = f'(SINCE "{seven_days_ago}")'
        status, data = mail.search(None, search_criteria)
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
        product_patterns = _build_product_identifier_patterns()

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
            subject_text = _decode_subject(msg)
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
                            try:
                                with fitz.open(stream=io.BytesIO(attachment_bytes), filetype="pdf") as doc:
                                    # Try to handle encrypted PDFs gracefully
                                    if doc.is_encrypted:
                                        try:
                                            doc.authenticate("")  # attempt empty password
                                        except Exception:
                                            pass
                                    if doc.is_encrypted:
                                        extracted_text += f"[Skipped encrypted PDF: {filename}]\n"
                                    else:
                                        for page in doc:
                                            extracted_text += page.get_text() + "\n"
                            except Exception as e:
                                print(f"Failed to open PDF {filename}: {e}")
                                extracted_text += f"[Failed to parse PDF: {filename}]\n"
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

            # Heuristic pre-filter: must match quote keywords and product identifiers in subject or body
            combined_text = (subject_text + "\n" + extracted_text)
            has_keyword = _text_matches_any(combined_text, KEYWORD_PATTERNS)
            has_product = _text_matches_any(combined_text, product_patterns) if product_patterns else True
            if not (has_keyword and has_product):
                # Not a candidate quote for active products; skip without marking as seen
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
                # Filter requests by product and rfq_sent_time
                proc_requests = ProcurementRequest.objects.filter(
                    product__name__iexact=product_name,
                    status__in=['rfqs-sent', 'quotes-received'],
                    rfq_sent_time__isnull=False
                )
                # Get email date
                email_date_str = msg.get('Date')
                email_date = None
                if email_date_str:
                    try:
                        email_date = email.utils.parsedate_to_datetime(email_date_str)
                    except Exception:
                        pass
                # Find matching request where email received after rfq_sent_time
                proc_request = None
                for req in proc_requests:
                    if email_date and req.rfq_sent_time and email_date > req.rfq_sent_time:
                        proc_request = req
                        break
                # Strictly skip emails before RFQ sent time (Python-side enforcement)
                # Also skip emails older than 7 days from today
                from datetime import datetime, timedelta
                now = datetime.now(email_date.tzinfo) if email_date and email_date.tzinfo else datetime.now()
                if email_date and (now - email_date).days > 7:
                    print(f"Skipping email UID {uid} for product '{product_name}' because it is older than 7 days.")
                    mail.store(e_id, '+FLAGS', '\\Seen')
                    continue
                if not proc_request:
                    print(f"Skipping email UID {uid} for product '{product_name}' because it was received before RFQ was sent or no valid RFQ found.")
                    mail.store(e_id, '+FLAGS', '\\Seen')
                    continue
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