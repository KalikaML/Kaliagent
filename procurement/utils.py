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

# Additional price/quote signal patterns found commonly in attachments
PRICE_SIGNAL_PATTERNS = [
    re.compile(r"\bINR\b", re.IGNORECASE),
    re.compile(r"\bRs\.?\b", re.IGNORECASE),
    re.compile(r"₹"),
    re.compile(r"\b(total|grand\s+total|subtotal|gst|tax|unit\s+price|qty|quantity|rate|amount|value)\b", re.IGNORECASE),
    # currency-like numbers (accept integers, with optional commas/decimals and '/-' suffix)
    re.compile(r"₹?\s*\b\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?\b"),
    re.compile(r"\b\d{3,}(?:,\d{3})*(?:\.\d{1,2})?\s*\/-\b")
]

# --- Product tokenization & matching helpers ---
STOPWORDS = set([
    'for','the','and','of','a','an','to','with','by','on','at','in','per',
    # Generic product descriptors that cause false matches
    'model','range','size','logo','name','approved','listed','dial','white','color',
    # Common units/containers (often appear across products)
    'mtr','roll','box'
])

def _normalize_product_tokens(name: str) -> list[str]:
    if not name:
        return []
    s = name.lower()
    # Replace common separators with spaces
    for ch in ['-', '/', '=', ',', ':', ';']:
        s = s.replace(ch, ' ')
    # Collapse multiple spaces
    s = re.sub(r"\s+", " ", s).strip()
    # Keep alphanumeric tokens like '32mm', '600m', 'cord', 'strap'
    raw_tokens = re.findall(r"[a-z0-9]+", s)
    tokens = []
    for t in raw_tokens:
        if not t:
            continue
        # Skip stopwords
        if t in STOPWORDS:
            continue
        # Skip purely numeric tokens
        if t.isdigit():
            continue
        # Skip very short alpha tokens (e.g., 'm')
        if t.isalpha() and len(t) < 3:
            continue
        tokens.append(t)
    return tokens

def _token_overlap_count(text: str, tokens: list[str]) -> int:
    if not text or not tokens:
        return 0
    low = text.lower()
    count = 0
    for t in set(tokens):
        # word boundary when token is purely alphabetic; substring for mixed like '32mm'
        if t.isalpha():
            if re.search(rf"\b{re.escape(t)}\b", low):
                count += 1
        else:
            if t in low:
                count += 1
    return count

def _alpha_overlap_count(text: str, tokens: list[str]) -> int:
    """Count overlaps considering only alphabetic tokens (e.g., 'drill','strap')."""
    if not text or not tokens:
        return 0
    low = text.lower()
    count = 0
    for t in set(tokens):
        if t.isalpha() and re.search(rf"\b{re.escape(t)}\b", low):
            count += 1
    return count

def _find_best_matching_request_by_tokens(text: str, email_date=None):
    """Return the active `ProcurementRequest` whose title/product tokens overlap the text.
    Requires overlap >= 2 to avoid false positives. Chooses the most recent RFQ among ties.
    """
    try:
        candidates = ProcurementRequest.objects.filter(
            status__in=['rfqs-sent', 'quotes-received'],
            rfq_sent_time__isnull=False
        ).select_related('product')
    except Exception:
        return None

    best = None
    best_score = 0
    for req in candidates:
        name_parts = []
        if req.title:
            name_parts.append(req.title)
        if req.product and req.product.name:
            name_parts.append(req.product.name)
        tokens = _normalize_product_tokens(' '.join(name_parts))
        score = _token_overlap_count(text, tokens)
        alpha_score = _alpha_overlap_count(text, tokens)
        # Require at least 2 overlaps, with at least 1 being alphabetic (noun-like)
        if score >= 2 and alpha_score >= 1:
            if score > best_score:
                best = req
                best_score = score
            elif score == best_score and best is not None:
                # Prefer more recent RFQ time
                prev = best.rfq_sent_time or datetime.min
                cur = req.rfq_sent_time or datetime.min
                if cur > prev:
                    best = req
                    best_score = score
    # Respect RFQ timing (reply should be after RFQ)
    if best and email_date and best.rfq_sent_time and email_date <= best.rfq_sent_time:
        return None
    return best

def _find_request_by_product_name_tokens(product_name: str, email_date=None):
    """Match an RFQ using tokens derived from the parsed 'product_name' string itself.
    Requires >=2 overlapping tokens and at least 1 alphabetic overlap to avoid numeric-only matches.
    Chooses most recent RFQ among ties and respects RFQ timing.
    """
    if not product_name:
        return None
    try:
        candidates = ProcurementRequest.objects.filter(
            status__in=['rfqs-sent', 'quotes-received'],
            rfq_sent_time__isnull=False
        ).select_related('product')
    except Exception:
        return None

    name_tokens = set(_normalize_product_tokens(product_name))
    if not name_tokens:
        return None

    best = None
    best_score = 0
    for req in candidates:
        parts = []
        if req.title:
            parts.append(req.title)
        if req.product and req.product.name:
            parts.append(req.product.name)
        req_tokens = set(_normalize_product_tokens(' '.join(parts)))
        overlap = name_tokens & req_tokens
        if len(overlap) >= 2:
            # Ensure at least one alphabetic token in overlap
            alpha_overlap = any(t.isalpha() for t in overlap)
            if not alpha_overlap:
                continue
            score = len(overlap)
            if score > best_score:
                best = req
                best_score = score
            elif score == best_score and best is not None:
                prev = best.rfq_sent_time or datetime.min
                cur = req.rfq_sent_time or datetime.min
                if cur > prev:
                    best = req
                    best_score = score
    if best and email_date and best.rfq_sent_time and email_date <= best.rfq_sent_time:
        return None
    return best

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
            text += _extract_text_from_pdf_bytes(content)
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

def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Robust PDF text extraction with OCR fallback for scanned PDFs.
    - Tries normal text extraction via PyMuPDF
    - If page text is empty/very short, renders page to image and uses Tesseract OCR
    - Gracefully skips encrypted PDFs if not decryptable
    """
    out_text = ''
    try:
        with fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf") as doc:
            # Attempt to handle simple encryption (empty password)
            if doc.is_encrypted:
                try:
                    doc.authenticate("")
                except Exception:
                    pass
            if doc.is_encrypted:
                return "[Skipped encrypted PDF]\n"

            for page in doc:
                try:
                    page_text = page.get_text() or ''
                except Exception:
                    page_text = ''

                # Heuristic: treat very short text as scanned/empty; run OCR fallback
                if len(page_text.strip()) < 20:
                    try:
                        # Render at higher DPI for better OCR (approx 300 DPI)
                        zoom = 3.0
                        mat = fitz.Matrix(zoom, zoom)
                        pix = page.get_pixmap(matrix=mat)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        ocr_text = pytesseract.image_to_string(img)
                        if ocr_text:
                            out_text += ocr_text + "\n"
                            continue
                    except Exception:
                        # If OCR fails, fall back to whatever text we have
                        pass

                out_text += page_text + "\n"
    except Exception as e:
        print(f"Failed to open/parse PDF bytes: {e}")
        out_text += "[Failed to parse PDF]\n"
    return out_text

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

def _normalize_sheet_row_to_supplier(row: dict, product_name_key: str = 'Product Name') -> dict | None:
    """Normalize a Google Sheet row (dict) into the supplier structure used by the agent.
    Expects headers like: Product Name, Supplier Name, Email, Phone, Source Link.
    Returns None if row lacks both email and phone.
    """
    try:
        name = row.get('Supplier Name') or row.get('supplier name') or row.get('Name') or row.get('name')
        email = row.get('Email') or row.get('email')
        phone = row.get('Phone') or row.get('phone') or row.get('Mobile') or row.get('mobile')
        src = row.get('Source Link') or row.get('source link') or row.get('URL') or row.get('url') or row.get('Website') or row.get('website')
        item = {'name': name or 'N/A', 'email': email, 'phone': phone, 'source_link': src}
        if item['email'] or item['phone']:
            return item
    except Exception:
        pass
    return None

def load_previous_suppliers_from_sheet(product_name: str) -> list[dict]:
    """Load historical suppliers for a product from the master Google Sheet.
    Uses settings.GOOGLE_SHEETS_CREDENTIALS_FILE and settings.GOOGLE_SHEET_ID.
    Filters rows where Product Name matches or contains the provided name (case-insensitive).
    """
    if not product_name:
        return []
    try:
        creds_path = getattr(settings, 'GOOGLE_SHEETS_CREDENTIALS_FILE', None)
        sheet_id = getattr(settings, 'GOOGLE_SHEET_ID', None)
        if not creds_path or not sheet_id:
            return []
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(sheet_id)
        MASTER_SHEET_NAME = "All Suppliers Data"
        try:
            ws = spreadsheet.worksheet(MASTER_SHEET_NAME)
        except gspread.WorksheetNotFound:
            # If the sheet doesn't exist yet, there is no historical data
            return []

        # Use explicit headers to avoid gspread duplicate/blank header errors
        EXPECTED_HEADERS = ['Product Name', 'Supplier Name', 'Email', 'Phone', 'Source Link', 'Scraped At']
        try:
            rows = ws.get_all_records(expected_headers=EXPECTED_HEADERS)
        except Exception as _e:
            # Fallback: read raw values and build minimal dicts for known columns
            values = ws.get_all_values()
            rows = []
            if values:
                header_row = values[0]
                header_map = {}
                for i, h in enumerate(header_row):
                    if h and str(h).strip():
                        header_map[str(h).strip().lower()] = i

                def _idx(*names):
                    for n in names:
                        j = header_map.get(str(n).strip().lower())
                        if j is not None:
                            return j
                    return None

                idx_product = _idx('Product Name', 'product name', 'Product', 'product')
                idx_supplier = _idx('Supplier Name', 'supplier name', 'Name', 'name')
                idx_email = _idx('Email', 'email')
                idx_phone = _idx('Phone', 'phone', 'Mobile', 'mobile')
                idx_source = _idx('Source Link', 'source link', 'URL', 'url', 'Website', 'website')

                for row in values[1:]:
                    rec = {
                        'Product Name': row[idx_product] if idx_product is not None and idx_product < len(row) else None,
                        'Supplier Name': row[idx_supplier] if idx_supplier is not None and idx_supplier < len(row) else None,
                        'Email': row[idx_email] if idx_email is not None and idx_email < len(row) else None,
                        'Phone': row[idx_phone] if idx_phone is not None and idx_phone < len(row) else None,
                        'Source Link': row[idx_source] if idx_source is not None and idx_source < len(row) else None,
                        'Scraped At': None,
                    }
                    rows.append(rec)
        target = product_name.strip().lower()
        results: list[dict] = []
        for r in rows:
            prod = r.get('Product Name') or r.get('product name') or r.get('Product') or r.get('product')
            if not prod:
                continue
            pnorm = str(prod).strip().lower()
            if pnorm == target or target in pnorm:
                item = _normalize_sheet_row_to_supplier(r)
                if item:
                    results.append(item)
        if results:
            print(f"[GSHEETS Loader] Loaded {len(results)} historical suppliers for '{product_name}' from master sheet.")
        return results
    except Exception as e:
        print(f"[GSHEETS Loader] Failed to read suppliers from Google Sheet: {e}")
        return []

def load_previous_suppliers_for_product(product_name: str) -> list[dict]:
    """Unified loader for Phase 0 historical suppliers.
    Priority: Google Sheet (master) → local CSV fallback.
    """
    # 1) Try Google Sheet
    sheet_results = load_previous_suppliers_from_sheet(product_name)
    if sheet_results:
        return sheet_results
    # 2) Fallback to local CSV
    #if not product_name:
    #    return []
    #rows = _load_previous_suppliers_csv()
    #if not rows:
    #    return []
    #target = product_name.strip().lower()
    #results = []
    #for r in rows:
    #    prod = (
    #        r.get('product') or r.get('product name') or r.get('product title') or r.get('item') or r.get('item description') or r.get('product description')
    #    )
    #    if not prod:
    #        continue
    #    pnorm = str(prod).strip().lower()
    #    if pnorm == target or target in pnorm:
    #        name = r.get('supplier') or r.get('supplier name') or r.get('name')
    #        email = r.get('email')
    #        phone = r.get('phone') or r.get('mobile') or r.get('contact')
    #        src = r.get('source') or r.get('source link') or r.get('url') or r.get('website')
    #        item = {'name': name or 'N/A', 'email': email, 'phone': phone, 'source_link': src}
    #        if item['email'] or item['phone']:
    #            results.append(item)
    #if results:
    #    print(f"[CSV Loader] Loaded {len(results)} historical suppliers for '{product_name}' from local CSV.")
    #return results

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
                content_type = (part.get_content_type() or '').lower()
                try:
                    attachment_bytes = part.get_payload(decode=True)
                except Exception:
                    attachment_bytes = None

                if not attachment_bytes:
                    continue

                # Derive a safe display name when filename is missing
                display_name = filename or {
                    'application/pdf': 'attachment.pdf',
                    'image/png': 'attachment.png',
                    'image/jpeg': 'attachment.jpg',
                    'image/tiff': 'attachment.tiff',
                    'text/plain': 'attachment.txt',
                    'text/csv': 'attachment.csv',
                    'application/vnd.ms-excel': 'attachment.xls',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'attachment.xlsx',
                }.get(content_type, 'attachment.bin')

                try:
                    extracted_text += f"\n--- ATTACHMENT: {display_name} ---\n"
                    # Primary type detection: prefer content-type, fallback to filename
                    is_pdf = (content_type == 'application/pdf') or (display_name.lower().endswith('.pdf'))
                    is_image = content_type.startswith('image/') or display_name.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff'))
                    is_xlsx = (content_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') or display_name.lower().endswith('.xlsx')
                    is_xls = (content_type in ('application/vnd.ms-excel', 'application/xls')) or display_name.lower().endswith('.xls')
                    is_csv = (content_type == 'text/csv') or display_name.lower().endswith('.csv')
                    is_txt = (content_type == 'text/plain') or display_name.lower().endswith('.txt')

                    if is_pdf:
                        extracted_text += _extract_text_from_pdf_bytes(attachment_bytes)
                    elif is_image:
                        image = Image.open(io.BytesIO(attachment_bytes))
                        extracted_text += pytesseract.image_to_string(image) + "\n"
                    elif is_xlsx and EXCEL_LIBS_INSTALLED:
                        workbook = openpyxl.load_workbook(io.BytesIO(attachment_bytes))
                        for sheet in workbook.worksheets:
                            for row in sheet.iter_rows():
                                row_text = [str(cell.value) for cell in row if cell.value is not None]
                                if row_text:
                                    extracted_text += ", ".join(row_text) + "\n"
                    elif is_xls and EXCEL_LIBS_INSTALLED:
                        workbook = xlrd.open_workbook(file_contents=attachment_bytes)
                        for sheet in workbook.sheets():
                            for row_idx in range(sheet.nrows):
                                row_text = [str(cell.value) for cell in sheet.row(row_idx) if cell.value is not None]
                                if row_text:
                                    extracted_text += ", ".join(row_text) + "\n"
                    elif is_csv:
                        decoded_content = attachment_bytes.decode('utf-8', errors='ignore')
                        reader = csv.reader(io.StringIO(decoded_content))
                        for row in reader:
                            extracted_text += ", ".join(row) + "\n"
                    elif is_txt:
                        extracted_text += attachment_bytes.decode('utf-8', errors='ignore') + "\n"
                    extracted_text += f"--- END ATTACHMENT: {display_name} ---\n\n"
                except Exception as e:
                    print(f"Failed to parse attachment {display_name}: {e}")

            if not extracted_text.strip():
                print(f"⚠️ No text extracted from email ID {e_id} - skipping")
                continue

            # Heuristic pre-filter: allow either quote keywords OR strong price signals (especially in attachments)
            combined_text = (subject_text + "\n" + extracted_text)
            has_keyword = _text_matches_any(combined_text, KEYWORD_PATTERNS)
            has_price_signal = any(p.search(extracted_text) for p in PRICE_SIGNAL_PATTERNS)
            if not (has_keyword or has_price_signal):
                # Not a candidate quote; skip without marking as seen
                continue

            # Try to capture explicit Request ID from subject like "[REQ-123]"
            req_id_int = None
            try:
                req_id_match = re.search(r"\bREQ-(\d+)\b", subject_text)
                if req_id_match:
                    req_id_int = int(req_id_match.group(1))
            except Exception:
                req_id_int = None

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
                # Get email date
                email_date_str = msg.get('Date')
                email_date = None
                if email_date_str:
                    try:
                        email_date = email.utils.parsedate_to_datetime(email_date_str)
                    except Exception:
                        pass
                # Also skip emails older than 7 days from today
                from datetime import datetime, timedelta
                now = datetime.now(email_date.tzinfo) if email_date and email_date.tzinfo else datetime.now()
                if email_date and (now - email_date).days > 7:
                    print(f"Skipping email UID {uid} for product '{product_name}' because it is older than 7 days.")
                    mail.store(e_id, '+FLAGS', '\\Seen')
                    continue
                # Try to resolve the ProcurementRequest by several strategies:
                proc_request = None
                # (A) Direct mapping via REQ-ID in subject
                if req_id_int:
                    try:
                        candidate = ProcurementRequest.objects.get(pk=req_id_int)
                        if not email_date or (candidate.rfq_sent_time and email_date > candidate.rfq_sent_time):
                            proc_request = candidate
                    except ProcurementRequest.DoesNotExist:
                        proc_request = None
                # (B) Match by product name with RFQ timing
                if not proc_request and product_name:
                    proc_requests = ProcurementRequest.objects.filter(
                        product__name__iexact=product_name,
                        status__in=['rfqs-sent', 'quotes-received'],
                        rfq_sent_time__isnull=False
                    )
                    for req in proc_requests:
                        if not email_date or (req.rfq_sent_time and email_date > req.rfq_sent_time):
                            proc_request = req
                            break
                # (B2) Token-overlap match using email/attachment text when product_name differs
                #if not proc_request:
                #    token_req = _find_best_matching_request_by_tokens(extracted_text, email_date=email_date)
                #    if token_req:
                   #     proc_request = token_req
                # (B3) Token-overlap match based on 'product_name' string itself
                if not proc_request and product_name:
                    name_token_req = _find_request_by_product_name_tokens(product_name, email_date=email_date)
                    if name_token_req:
                        proc_request = name_token_req
                # (C) Fallback: supplier reply mapping — find active RFQ sent to this sender
                if not proc_request:
                    try:
                        mv = MasterVendor.objects.filter(email=sender_email).first()
                        if mv:
                            supplier_links = Supplier.objects.filter(
                                master_vendor=mv,
                                procurement_request__rfq_sent_time__isnull=False,
                                procurement_request__status__in=['rfqs-sent','quotes-received']
                            ).order_by('-procurement_request__rfq_sent_time')
                            # Choose the supplier-linked request that also token-matches the email text
                            best_link = None
                            best_score = 0
                            for link in supplier_links:
                                req = link.procurement_request
                                name_parts = []
                                if req.title:
                                    name_parts.append(req.title)
                                if req.product and req.product.name:
                                    name_parts.append(req.product.name)
                                tokens = _normalize_product_tokens(' '.join(name_parts))
                                score = _token_overlap_count(extracted_text, tokens)
                                alpha_score = _alpha_overlap_count(extracted_text, tokens)
                                if score >= 2 and alpha_score >= 1:
                                    if score > best_score:
                                        best_link = req
                                        best_score = score
                            if best_link and (not email_date or (best_link.rfq_sent_time and email_date > best_link.rfq_sent_time)):
                                proc_request = best_link
                    except Exception:
                        pass
                # (D) Do NOT auto-create new requests from quotes; instead, skip if no match
                if not proc_request:
                    print(f"⚠️ No matching RFQ found for product '{product_name}'. Skipping quote from {sender_email}.")
                    continue
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