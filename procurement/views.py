import json
import os
import re
import threading
from collections import deque
import sys
import subprocess
from decimal import Decimal
import requests
import csv
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.utils.crypto import get_random_string
from uuid import uuid4
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.mail import EmailMessage, send_mail
from django.db.models import Sum, Avg, Count
from django.contrib import messages
from django.utils import timezone
from .models import ProcurementRequest, Supplier, Quote, Product, MasterVendor
from .utils import process_incoming_quotes, get_ai_benchmark_price, get_ai_response, send_rfqs_for_request, extract_text_from_uploaded_file, parse_quote_text_to_items

# --- Quote scoring helpers ---
def _map_terms_penalty(payment_terms: str) -> int:
    if not payment_terms:
        return 100
    t = payment_terms.strip().lower()
    if 'on delivery' in t or 'on-delivery' in t:
        return 0
    if '50% advance' in t or '50 % advance' in t:
        return 50
    if '100% advance' in t or '100 % advance' in t:
        return 100
    return 50

def compute_quote_score(q, request, target_days: int = 5, per_day_penalty: int = 50, missing_field_penalty: int = 100):
    quantity = request.quantity or q.quantity or '0'
    try:
        qty_num = int(__import__('re').search(r"\d+", str(quantity)).group())
    except Exception:
        qty_num = 0

    price = float(q.price) if q.price is not None else None
    subtotal = float(q.subtotal) if q.subtotal is not None else None
    tax = float(q.tax_amount) if q.tax_amount is not None else 0.0
    freight = float(q.freight_charges) if q.freight_charges is not None else 0.0
    total = float(q.total_amount) if q.total_amount is not None else None
    discount = q.discount
    # Parse discount to a numeric value when possible
    discount_value = 0.0
    if isinstance(discount, str):
        import re
        m = re.search(r"(\d+(?:\.\d+)?)%", discount)
        if m and price is not None and qty_num:
            discount_value = (float(m.group(1)) / 100.0) * (price * qty_num)
        else:
            m2 = re.search(r"(\d+(?:\.\d+)?)", discount)
            if m2:
                discount_value = float(m2.group(1))

    if total is None:
        if subtotal is not None:
            effective_cost = subtotal + tax + freight - discount_value
        elif price is not None and qty_num:
            effective_cost = price * qty_num + tax + freight - discount_value
        else:
            effective_cost = 0.0
    else:
        effective_cost = total - discount_value

    lead_days = q.lead_time_days if q.lead_time_days is not None else None
    lead_penalty = 0
    if isinstance(lead_days, int):
        if lead_days > target_days:
            lead_penalty = (lead_days - target_days) * per_day_penalty
    else:
        lead_penalty = missing_field_penalty

    terms_penalty = _map_terms_penalty(q.payment_terms)

    missing_penalty = 0
    if price is None and total is None and subtotal is None:
        missing_penalty += missing_field_penalty
    if qty_num == 0:
        missing_penalty += missing_field_penalty

    score = effective_cost + lead_penalty + terms_penalty + missing_penalty
    breakdown = {
        'effective_cost': round(effective_cost, 2),
        'lead_penalty': lead_penalty,
        'terms_penalty': terms_penalty,
        'missing_penalty': missing_penalty,
    }
    return score, breakdown

# EXPLANATION: Yeh helper function sirf supplier scrape karta hai aur status ko 'awaiting-approval' set karta hai.
SCRAPE_QUEUE = deque()
SCRAPE_WORKER_RUNNING = False

def _agent_log_path(request_id: int) -> str:
    base_dir = getattr(settings, 'BASE_DIR', os.getcwd())
    log_dir = os.path.join(base_dir, 'runtime_logs', 'procurement')
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception:
        pass
    return os.path.join(log_dir, f"agent_request_{request_id}.log")

def _start_queue_worker():
    global SCRAPE_WORKER_RUNNING
    if SCRAPE_WORKER_RUNNING:
        return
    SCRAPE_WORKER_RUNNING = True

    def worker():
        global SCRAPE_WORKER_RUNNING
        try:
            while True:
                try:
                    request_id = SCRAPE_QUEUE.popleft()
                except IndexError:
                    # Queue is empty, exit the worker
                    break
                try:
                    _run_single_scrape(request_id)
                except Exception as e:
                    print(f"[QUEUE ERROR] Failed processing request {request_id}: {e}")
        finally:
            SCRAPE_WORKER_RUNNING = False

    threading.Thread(target=worker, daemon=True).start()

def _run_single_scrape(request_id):
    """Starts the scrape_suppliers management command for a given request ID in a background thread.
    Streams exact command output to a per-request log file so UI can reflect true logs.
    """
    try:
        req = ProcurementRequest.objects.get(pk=request_id)
        req.status = 'agent-working'
        req.save()

        log_path = _agent_log_path(request_id)
        try:
            # Truncate any previous log for a clean run
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write('')
        except Exception:
            pass

        command = [sys.executable, 'manage.py', 'scrape_suppliers', str(request_id)]
        try:
            print(f"[AGENT] Starting supplier scrape for request {request_id}...")
            # Stream stdout+stderr into the log file as the command runs
            with open(log_path, 'a', encoding='utf-8') as log_file:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                for line in process.stdout:
                    try:
                        log_file.write(line)
                        # Flush so UI sees live logs while the agent runs
                        log_file.flush()
                    except Exception:
                        # best-effort logging; ignore write failures
                        pass
                process.wait()

            if process.returncode == 0:
                print(f"[AGENT] Supplier scrape completed for request {request_id}.")
            else:
                print(f"[AGENT] Supplier scrape exited with code {process.returncode} for request {request_id}.")
                # Mark failure to avoid UI stuck; move to awaiting-approval
                req.status = 'awaiting-approval'
                req.specs = (req.specs or '') + f"\n[Scrape failed: code {process.returncode}]"
                req.save(update_fields=['status','specs'])
        except Exception as e:
            print(f"[AGENT ERROR] Failed to run supplier scrape for request {request_id}: {e}")
            req.status = 'awaiting-approval'
            req.specs = (req.specs or '') + f"\n[Scrape error: {e}]"
            req.save(update_fields=['status','specs'])
        return True
    except ProcurementRequest.DoesNotExist:
        print(f"Could not start agent for request ID {request_id}: DoesNotExist.")
        return False

def start_supplier_scraping_agent(request_id):
    """Enqueue scraping to serialize execution."""
    SCRAPE_QUEUE.append(request_id)
    _start_queue_worker()
    return True

# EXPLANATION: Yeh helper function ab bulk upload mein istemal nahi hoga.
def start_bulk_processing_agent(request_id):
    """Starts the new end-to-end management command for a given request ID in a background thread."""
    try:
        req = ProcurementRequest.objects.get(pk=request_id)
        req.status = 'agent-working'
        req.save()
        
        def run_in_thread():
            command = [sys.executable, 'manage.py', 'process_bulk_request', str(request_id)]
            subprocess.run(command)
            
        thread = threading.Thread(target=run_in_thread)
        thread.start()
        return True
    except ProcurementRequest.DoesNotExist:
        print(f"Could not start bulk processing agent for request ID {request_id}: DoesNotExist.")
        return False


def procurement_dashboard_view(request):
    total_savings = ProcurementRequest.objects.filter(status='finalized').aggregate(total=Sum('estimated_savings'))['total'] or 0
    time_saved_sourcing = ProcurementRequest.objects.filter(status__in=['awaiting-approval', 'rfqs-sent', 'quotes-received', 'finalized']).count() * 0.5
    time_saved_rfqs = ProcurementRequest.objects.filter(status__in=['rfqs-sent', 'quotes-received', 'finalized']).count() * 0.75
    time_saved_parsing = Quote.objects.count() * 0.25
    total_time_saved = time_saved_sourcing + time_saved_rfqs + time_saved_parsing
    market_alert = "Market data currently unavailable."
    try:
        response = requests.get("https://api.nbp.pl/api/cenyzlota", timeout=5)
        if response.status_code == 200:
            market_alert = f"Gold prices: PLN {response.json()[0]['cena']}/gram."
    except requests.RequestException:
        print("Could not fetch market data.")

    columns_data = [
        {'id': 'new-request', 'title': '📝 New Request', 'color': 'border-sky-500'},
        {'id': 'agent-working', 'title': '🤖 Agent Working', 'color': 'border-amber-500'},
        {'id': 'awaiting-approval', 'title': '⏳ Awaiting Approval', 'color': 'border-purple-500'},
        {'id': 'rfqs-sent', 'title': '📨 RFQs Sent', 'color': 'border-blue-500'},
        {'id': 'quotes-received', 'title': '📊 Quotes Received', 'color': 'border-green-500'},
        {'id': 'finalized', 'title': '🏆 Finalized', 'color': 'border-slate-500'}
    ]
    all_requests = ProcurementRequest.objects.all().order_by('-created_at')
    for column in columns_data:
        if column['id'] == 'quotes-received':
            products_in_stage = Product.objects.filter(
                procurementrequest__status='quotes-received'
            ).distinct().annotate(
                quote_count=Count('procurementrequest__quotes')
            )
            column['products'] = products_in_stage
            column['requests'] = []
        else:
            column['requests'] = [req for req in all_requests if req.status == column['id']]
            column['products'] = []

    context = {
        'columns': columns_data, 'total_savings': total_savings,
        'total_time_saved': total_time_saved, 'market_alert': market_alert,
    }
    return render(request, 'procurement/dashboard.html', context)

def get_product_quotes_api(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
        requests_for_product = ProcurementRequest.objects.filter(product=product, status__in=['quotes-received', 'rfqs-sent'])
        quotes = Quote.objects.filter(procurement_request__in=requests_for_product).select_related('supplier', 'supplier__master_vendor')
        representative_request = requests_for_product.first()
        if not representative_request:
             return JsonResponse({'error': 'No active requests found for this product'}, status=404)

        quote_values = []
        best_quote_id = None
        best_score = None
        best_breakdown = None
        for q in quotes:
            score, breakdown = compute_quote_score(q, representative_request)
            item = {
                'id': q.id,
                'supplier__name': q.supplier.name if q.supplier else None,
                'supplier__email': q.supplier.email if q.supplier else None,
                'supplier__phone': q.supplier.phone if q.supplier else None,
                'price': float(q.price) if q.price is not None else None,
                'lead_time_days': q.lead_time_days,
                'payment_terms': q.payment_terms,
                'discount': q.discount,
                'full_email_body': q.full_email_body,
                'attachment_url': (q.attachment.url if getattr(q, 'attachment', None) else None),
                'quantity': q.quantity,
                'subtotal': float(q.subtotal) if q.subtotal is not None else None,
                'tax_amount': float(q.tax_amount) if q.tax_amount is not None else None,
                'freight_charges': float(q.freight_charges) if q.freight_charges is not None else None,
                'total_amount': float(q.total_amount) if q.total_amount is not None else None,
                'score': round(score, 2),
                'score_breakdown': breakdown,
            }
            quote_values.append(item)
            if best_score is None or score < best_score:
                best_score = score
                best_quote_id = q.id
                best_breakdown = breakdown

        data = {
            'id': product.id,
            'title': product.name,
            'representative_request_id': representative_request.id,
            'quantity': representative_request.quantity,
            'specs': representative_request.specs,
            'status': 'quotes-received',
            'quotes': quote_values,
            'best_quote_id': best_quote_id,
            'best_quote_score': round(best_score, 2) if best_score is not None else None,
            'best_quote_breakdown': best_breakdown,
            'suppliers': list(Supplier.objects.filter(procurement_request__in=requests_for_product).distinct().values('name', 'email', 'phone')),
            'benchmark_price': None,
            'benchmark_source': None,
        }
        if quotes.count() == 1:
            historical_avg = ProcurementRequest.objects.filter(
                product=product, status='finalized', selected_quote__price__isnull=False
            ).aggregate(avg_price=Avg('selected_quote__price'))['avg_price']
            if historical_avg:
                data['benchmark_price'] = float(historical_avg)
                data['benchmark_source'] = "Historical Average Price"
            else:
                ai_price = get_ai_benchmark_price(product.name, representative_request.specs)
                if ai_price:
                    data['benchmark_price'] = ai_price
                    data['benchmark_source'] = "AI Estimated Market Price"
        return JsonResponse(data)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)

@csrf_exempt
@require_POST
def upload_quote_api(request, pk):
    """
    Accepts a manual quote upload for a given ProcurementRequest ID.
    Supports multipart/form-data with optional file attachment and fields:
    supplier_name, price, quantity, lead_time_days, payment_terms, subtotal, tax_amount,
    freight_charges, total_amount, discount, full_text.
    """
    try:
        req = ProcurementRequest.objects.get(pk=pk)
    except ProcurementRequest.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Request not found'}, status=404)

    errors = {}
    supplier_name = (request.POST.get('supplier_name') or '').strip()
    has_attachment = 'attachment' in request.FILES
    has_full_text = bool((request.POST.get('full_text') or '').strip())
    # Supplier name is only required if neither attachment nor full_text are provided
    if not supplier_name and not (has_attachment or has_full_text):
        errors['supplier_name'] = 'Provide supplier name or upload a file/text.'
    supplier_email = request.POST.get('supplier_email')
    supplier_phone = request.POST.get('supplier_phone')

    supplier, _ = Supplier.objects.get_or_create(
        procurement_request=req,
        name=supplier_name,
        defaults={'email': supplier_email, 'phone': supplier_phone}
    )

    def parse_decimal_field(field_name):
        raw = request.POST.get(field_name)
        if raw in [None, '', 'null']:
            return None
        # Sanitize common currency formats like "₹1,000.00" or "1,000"
        raw_str = str(raw)
        sanitized = re.sub(r"[^\d\.\-]", "", raw_str)
        if sanitized in ['', '-', '.', '-.', '.-', '--']:
            errors[field_name] = 'Must be a number.'
            return None
        try:
            return Decimal(sanitized)
        except Exception:
            errors[field_name] = 'Must be a number.'
            return None

    price = parse_decimal_field('price')
    subtotal = parse_decimal_field('subtotal')
    tax_amount = parse_decimal_field('tax_amount')
    freight_charges = parse_decimal_field('freight_charges')
    total_amount = parse_decimal_field('total_amount')
    quantity = request.POST.get('quantity')
    lead_time_days_str = request.POST.get('lead_time_days')
    if lead_time_days_str not in [None, '']:
        # Accept values like "7-10 days" by extracting the last number
        digits = re.findall(r"\d+", str(lead_time_days_str))
        if digits:
            lead_time_days_str = digits[-1]
        try:
            int(lead_time_days_str)
        except Exception:
            errors['lead_time_days'] = 'Must be an integer number of days.'
    payment_terms = request.POST.get('payment_terms')
    discount = request.POST.get('discount')
    full_text = request.POST.get('full_text')

    # If there are basic validation errors on provided fields, stop early
    if errors:
        return JsonResponse({'success': False, 'errors': errors}, status=400)

    # Generate a unique manual UID to satisfy unique constraint
    manual_uid = f"manual:{uuid4()}"

    # If attachment exists and key fields are missing, try parsing attachment/full_text
    parsed_invoice = None
    parsed_items = None
    if 'attachment' in request.FILES:
        attachment_file = request.FILES['attachment']
        extracted = extract_text_from_uploaded_file(attachment_file)
        # Reset file pointer so Django can save the file correctly
        try:
            attachment_file.seek(0)
        except Exception:
            pass
        full_text = (full_text or '') + ("\n\n" + extracted if extracted else '')
    if (price is None or subtotal is None or total_amount is None) and full_text:
        parsed = parse_quote_text_to_items(full_text)
        if parsed:
            parsed_invoice = {
                'subtotal': parsed.get('subtotal'),
                'tax_amount': parsed.get('tax_amount'),
                'freight_charges': parsed.get('freight_charges'),
                'total_amount': parsed.get('total_amount'),
            }
            parsed_items = parsed.get('line_items') or []
            # If a single item matches request product, prefer its unit price/quantity
            def _to_decimal_value(v):
                try:
                    return Decimal(str(v))
                except Exception:
                    return None

            for item in parsed_items:
                if item.get('price') is not None:
                    price = _to_decimal_value(item.get('price')) or price
                if item.get('quantity') and not quantity:
                    quantity = str(item.get('quantity'))
                if item.get('lead_time_days') and not lead_time_days_str:
                    lead_time_days_str = str(item.get('lead_time_days'))
                if item.get('payment_terms') and not payment_terms:
                    payment_terms = item.get('payment_terms')
                if item.get('discount') and not discount:
                    discount = item.get('discount')
    # Apply parsed invoice fallback values
    if parsed_invoice:
        subtotal = _to_decimal_value(parsed_invoice.get('subtotal')) if subtotal is None else subtotal
        tax_amount = _to_decimal_value(parsed_invoice.get('tax_amount')) if tax_amount is None else tax_amount
        freight_charges = _to_decimal_value(parsed_invoice.get('freight_charges')) if freight_charges is None else freight_charges
        total_amount = _to_decimal_value(parsed_invoice.get('total_amount')) if total_amount is None else total_amount

    # Default supplier name if only file/text provided
    if not supplier_name:
        supplier_name = 'Manual Upload'
    
    quote = Quote(
        procurement_request=req,
        supplier=supplier,
        quantity=quantity,
        price=price,
        subtotal=subtotal,
        tax_amount=tax_amount,
        freight_charges=freight_charges,
        total_amount=total_amount,
        lead_time_days=int(lead_time_days_str) if lead_time_days_str else None,
        payment_terms=payment_terms,
        discount=discount,
        parsed_from_email_uid=manual_uid,
        full_email_body=full_text,
        source_type='manual',
    )

    # Optional file upload
    if 'attachment' in request.FILES:
        quote.attachment = attachment_file

    quote.save()

    # Ensure the request reflects that quotes have been received and has a product
    if req.status != 'quotes-received':
        req.status = 'quotes-received'
    if not req.product_id:
        # Fallback: bind to a product using request title if none set
        product_obj, _ = Product.objects.get_or_create(name=req.title)
        req.product = product_obj
    req.save(update_fields=['status', 'product'])

    # Return updated quotes for the product using existing API structure
    product_id = req.product_id
    try:
        return get_product_quotes_api(request, product_id)
    except Exception:
        # Fallback: if product aggregation fails, return request-level details
        quotes = list(req.quotes.all().values(
            'id', 'supplier__name', 'supplier__email', 'supplier__phone', 'price', 'lead_time_days', 'payment_terms', 'discount', 
            'full_email_body', 'quantity', 'subtotal', 'tax_amount', 'freight_charges', 'total_amount'
        ))
        data = {
            'id': req.id,
            'title': req.title,
            'quantity': req.quantity,
            'specs': req.specs,
            'status': req.status,
            'quotes': quotes,
        }
        return JsonResponse(data)

def analysis_view(request):
    selected_product_id = request.GET.get('product')
    
    finalized_requests = ProcurementRequest.objects.filter(status='finalized', selected_quote__isnull=False).select_related('selected_quote__supplier__master_vendor')
    savings_data = ProcurementRequest.objects.filter(status='finalized', estimated_savings__gt=0).values('product__name').annotate(total_savings=Sum('estimated_savings')).order_by('-total_savings')

    if selected_product_id:
        finalized_requests = finalized_requests.filter(product_id=selected_product_id)
        savings_data = savings_data.filter(product_id=selected_product_id)

    overall_total_savings = savings_data.aggregate(total=Sum('total_savings'))['total'] or 0
    
    products_with_vendors = Product.objects.annotate(
        vendor_count=Count('vendors')
    ).filter(vendor_count__gt=0).prefetch_related('vendors').order_by('name')
    if selected_product_id:
        products_with_vendors = products_with_vendors.filter(id=selected_product_id)
        
    line_chart_data = None
    selected_product_name = ""
    if selected_product_id:
        try:
            selected_product = Product.objects.get(id=selected_product_id)
            selected_product_name = selected_product.name
            price_history = ProcurementRequest.objects.filter(
                product_id=selected_product_id,
                status='finalized',
                selected_quote__price__isnull=False
            ).order_by('created_at').values(
                'created_at', 
                'selected_quote__price'
            )
            if price_history:
                line_chart_labels = [entry['created_at'].strftime('%d %b %Y') for entry in price_history]
                line_chart_values = [float(entry['selected_quote__price']) for entry in price_history]
                line_chart_data = {
                    'labels': json.dumps(line_chart_labels),
                    'values': json.dumps(line_chart_values)
                }
        except Product.DoesNotExist:
            pass

    context = {
        'products': Product.objects.all().order_by('name'),
        'finalized_requests': finalized_requests,
        'products_with_vendors': products_with_vendors,
        'selected_product_id': int(selected_product_id) if selected_product_id else None,
        'savings_data': savings_data,
        'overall_total_savings': overall_total_savings,
        'line_chart_data': line_chart_data,
        'selected_product_name': selected_product_name,
    }
    return render(request, 'procurement/analysis.html', context)

@csrf_exempt
@require_POST
def add_request_api(request):
    data = json.loads(request.body)
    product, _ = Product.objects.get_or_create(name=data.get('title'))
    new_request = ProcurementRequest.objects.create(
        title=data.get('title'),
        product=product,
        quantity=data.get('quantity'),
        specs=data.get('specs'),
        source=data.get('source', 'Manual'),
        status='new-request'
    )
    return JsonResponse({'success': True, 'id': new_request.id})

@require_POST
def bulk_upload_api(request):
    if 'file' not in request.FILES:
        messages.error(request, 'No file was uploaded. Please select a CSV file.')
        return redirect('procurement:dashboard')
    
    uploaded_file = request.FILES['file']
    existing_titles = set(ProcurementRequest.objects.values_list('title', flat=True))
    
    new_requests_count = 0
    skipped_existing_count = 0
    skipped_format_count = 0
    
    try:
        raw_bytes = uploaded_file.read()
        lines = None
        for enc in ('utf-8', 'utf-8-sig', 'latin-1', 'iso-8859-1'):
            try:
                lines = raw_bytes.decode(enc).splitlines()
                break
            except UnicodeDecodeError:
                continue
        if lines is None:
            raise UnicodeDecodeError('unknown', b'', 0, 1, 'Could not decode file with common encodings')
        reader = csv.DictReader(lines)
        # Handling kalika enterprises specific format to convert below given format 
        for row in reader:
            # Normalize headers and safely handle None values
            normalized_row = {}
            for key, value in row.items():
                if key is None:
                    continue
                norm_key = str(key).strip().lower()
                norm_val = value
                if norm_val is None:
                    norm_val = ''
                elif isinstance(norm_val, str):
                    norm_val = norm_val.strip()
                normalized_row[norm_key] = norm_val
            print('Normalized Row:', normalized_row)
            
            # title = normalized_row.get('product title') or normalized_row.get('product description')
            # quantity = normalized_row.get('quantity', 'N/A')
            # specs = normalized_row.get('specifications', '')

            # Explicit mapping: Item Description -> Product Title
            title = normalized_row.get('item description')
            if not title:
                # Fallbacks if the primary header is absent or empty
                title = (
                    normalized_row.get('product description')
                    or normalized_row.get('product title')
                    or normalized_row.get('item')
                    or normalized_row.get('description')
                    or normalized_row.get('product')
                    or normalized_row.get('material description')
                    or normalized_row.get('part description')
                    or normalized_row.get('product name')
                    or normalized_row.get('name')
                    or normalized_row.get('material')
                )
            # Map your 'PENDING' column to Quantity
            # Explicit mapping: PENDING -> Quantity
            quantity = normalized_row.get('pending')
            if not quantity:
                quantity = (
                    normalized_row.get('pending qty')
                    or normalized_row.get('pending quantity')
                    or normalized_row.get('quantity ordered')
                    or normalized_row.get('quantity')
                    or normalized_row.get('qty')
                    or 'N/A'
                )
            specs = normalized_row.get('supplier item') or normalized_row.get('specifications') or ''

            print('Processing row:', title, quantity, specs)
            
            if not title:
                # If title is missing, try deriving it from other meaningful fields
                candidate_fields = [
                    normalized_row.get('supplier item'),
                    normalized_row.get('material description'),
                    normalized_row.get('part description'),
                    normalized_row.get('description'),
                ]
                title = next((v for v in candidate_fields if isinstance(v, str) and v), None)
                if not title:
                    # As a last resort, pick the first non-empty string value from the row
                    for v in normalized_row.values():
                        if isinstance(v, str) and v:
                            title = v
                            break
                if not title:
                    skipped_format_count += 1
                    continue

            if title in existing_titles:
                skipped_existing_count += 1
                continue
            
            product, _ = Product.objects.get_or_create(name=title)
            new_request = ProcurementRequest.objects.create(
                title=title, product=product, quantity=quantity,
                specs=specs, source='Bulk Upload', status='new-request'
            )
            
            # ========== CLARIFICATION OF LOGIC ==========
            # The following line starts the automated supplier search for each new request from the CSV.
            # This agent's final step is to set the status to 'awaiting-approval'.
            # This ensures the process automatically stops for your manual review, as you requested.
            # Enqueue instead of spawning many threads
            start_supplier_scraping_agent(new_request.id)
            # ============================================

            existing_titles.add(title)
            new_requests_count += 1

    except Exception as e:
        print(f"Error processing bulk upload file '{uploaded_file.name}': {e}")
        messages.error(request, f"An error occurred while processing the file: {e}")
        return redirect('procurement:dashboard')
    
    if new_requests_count > 0:
        messages.success(request, f"Successfully started processing for {new_requests_count} new request(s). They will appear in 'Agent Working'.")
    if skipped_existing_count > 0:
        messages.info(request, f"Skipped {skipped_existing_count} request(s) because they already exist in the system.")
    if skipped_format_count > 0:
        messages.warning(request, f"Skipped {skipped_format_count} row(s) due to missing 'Item Description' (Product Title) column.")
    if new_requests_count == 0 and skipped_existing_count == 0 and skipped_format_count == 0:
        messages.warning(request, "The uploaded file was empty or did not contain any processable rows.")

    return redirect('procurement:dashboard')

def get_request_details_api(request, pk):
    try:
        req = ProcurementRequest.objects.get(pk=pk)
        # Build suppliers with provenance derived from source_link prefix
        suppliers_qs = req.suppliers.all().values('name', 'email', 'phone', 'source_link', 'indiamart_rfq_sent')
        suppliers = []
        for s in suppliers_qs:
            src = s.get('source_link') or ''
            provenance = 'existing' if isinstance(src, str) and src.startswith('csv:') else 'scraped'
            suppliers.append({
                'name': s.get('name'),
                'email': s.get('email'),
                'phone': s.get('phone'),
                'source_link': src[4:] if isinstance(src, str) and src.startswith('csv:') else src,
                'indiamart_rfq_sent': s.get('indiamart_rfq_sent'),
                'provenance': provenance,
            })
        quotes = list(req.quotes.all().values(
            'id', 'supplier__name', 'supplier__email', 'supplier__phone', 'price', 'lead_time_days', 'payment_terms', 'discount', 
            'full_email_body', 'quantity', 'subtotal', 'tax_amount', 'freight_charges', 'total_amount'
        ))
        data = {
            'id': req.id,
            'product_id': req.product_id,
            'title': req.title,
            'quantity': req.quantity,
            'specs': req.specs,
            'status': req.status,
            'source': req.source,
            'suppliers': suppliers,
            'quotes': quotes,
        }
        return JsonResponse(data)
    except ProcurementRequest.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)

def get_request_logs_api(request, pk):
    """Return raw agent logs for a given request ID as text.
    Logs reflect exact output of the scrape_suppliers management command.
    """
    try:
        ProcurementRequest.objects.get(pk=pk)
    except ProcurementRequest.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)

    log_path = _agent_log_path(pk)
    if not os.path.exists(log_path):
        return JsonResponse({'text': ''})
    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return JsonResponse({'text': content})
    except Exception as e:
        return JsonResponse({'error': f'Could not read logs: {e}'}, status=500)

@csrf_exempt
@require_POST
def find_suppliers_api(request, pk):
    """API endpoint for the manual flow (scrape only)."""
    if start_supplier_scraping_agent(pk):
        return JsonResponse({'success': True, 'message': 'Sourcing agent started in background thread.'})
    else:
        return JsonResponse({'error': 'Request not found'}, status=404)

@csrf_exempt
@require_POST
def find_more_suppliers_api(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
        active_request = ProcurementRequest.objects.filter(
            product=product, 
            status__in=['quotes-received', 'awaiting-approval', 'rfqs-sent']
        ).order_by('-created_at').first()

        if not active_request:
            return JsonResponse({'error': 'No active request found for this product to add suppliers to.'}, status=404)
        
        start_supplier_scraping_agent(active_request.id)
        
        return JsonResponse({'success': True, 'message': 'Agent has started searching for more suppliers in the background.'})
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def send_rfqs_api(request, pk):
    try:
        attachment = request.FILES.get('attachment')
        success, message = send_rfqs_for_request(pk, attachment)
        if success:
            return JsonResponse({'success': True, 'message': message})
        else:
            return JsonResponse({'error': message}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def check_and_parse_quotes_api(request, pk):
    try:
        new_quotes = process_incoming_quotes()
        return JsonResponse({'success': True, 'message': f'Global scan complete. Found {new_quotes} new quotes.', 'new_quotes_found': new_quotes})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def check_all_rfqs_api(request):
    try:
        new_quotes = process_incoming_quotes()
        return JsonResponse({'success': True, 'total_new_quotes': new_quotes, 'message': f'Global scan complete. Found {new_quotes} new quotes.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def finalize_request_api(request, pk):
    try:
        data = json.loads(request.body)
        quote_id = data.get('quote_id')
        final_quantity = data.get('final_quantity')

        proc_request = ProcurementRequest.objects.get(pk=pk)
        selected_quote = Quote.objects.get(pk=quote_id)
        
        if final_quantity:
            proc_request.quantity = final_quantity

        benchmark_price = Decimal('0.0')
        benchmark_source = "N/A"

        all_quotes_for_product = Quote.objects.filter(
            procurement_request__product=proc_request.product,
            price__isnull=False
        )

        if all_quotes_for_product.count() > 1:
            avg_price = all_quotes_for_product.exclude(id=selected_quote.id).aggregate(avg_price=Avg('price'))['avg_price']
            benchmark_price = avg_price or selected_quote.price
            benchmark_source = "Multi-Quote Average"
        else:
            historical_avg = ProcurementRequest.objects.filter(
                product=proc_request.product, status='finalized', selected_quote__price__isnull=False
            ).aggregate(avg_price=Avg('selected_quote__price'))['avg_price']
            
            if historical_avg:
                benchmark_price = historical_avg
                benchmark_source = "Historical Average"
            else:
                ai_price = get_ai_benchmark_price(proc_request.product.name, proc_request.specs)
                if ai_price:
                    benchmark_price = Decimal(ai_price)
                    benchmark_source = "AI Estimate"
                else:
                    benchmark_price = selected_quote.price
                    benchmark_source = "Manual (No Benchmark)"

        savings = benchmark_price - selected_quote.price
        total_savings = savings
        try:
            quantity_val = int(re.search(r'\d+', proc_request.quantity).group())
            total_savings = savings * quantity_val
        except (ValueError, AttributeError, TypeError):
            pass

        proc_request.status = 'finalized'
        proc_request.selected_quote = selected_quote
        proc_request.estimated_savings = total_savings
        proc_request.benchmark_source = benchmark_source
        proc_request.save()

        ProcurementRequest.objects.filter(
            product=proc_request.product, status='quotes-received'
        ).exclude(id=proc_request.id).update(status='finalized')


        supplier_name = selected_quote.supplier.name if selected_quote.supplier and selected_quote.supplier.name else "Supplier"
        product_name = proc_request.title
        price = selected_quote.price

        email_prompt = f"""
        You are an expert procurement assistant for a company named 'Kalika Enterprises'. 
        Your task is to draft a professional purchase confirmation email.

        The tone should be formal, clear, and appreciative. The email must serve as an official confirmation of the order.

        **Instructions:**
        1. Start with a clear and professional subject line like "Purchase Order Confirmation".
        2. Address the supplier professionally by their name: {supplier_name}.
        3. State clearly that their quotation has been accepted and you are confirming the purchase.
        4. List the order details in a structured way (Product, Final Quantity, Price per unit).
        5. Request the supplier to acknowledge receipt of this purchase order and provide an estimated dispatch date.
        6. Conclude professionally. The email will be signed by 'Vishal Kumbharkar' of 'Kalika Enterprises'.

        **Order Details:**
        - Supplier Name: {supplier_name}
        - Product: {product_name}
        - Final Order Quantity: {proc_request.quantity}
        - Final Price per unit: ₹{price}

        Generate ONLY the body of the email.
        """

        from .utils import model
        if model:
            gemini_response = model.generate_content(email_prompt)
            email_body_generated = gemini_response.text.strip()
            
            email_body_generated = email_body_generated.replace('[Your Name/Company Name]', 'Vishal Kumbharkar\nKalika Enterprises')

        else:
            email_body_generated = (
                f"Dear {supplier_name},\n\n"
                f"We are pleased to inform you that your quotation for {product_name} "
                f"has been reviewed and finalized by our procurement team.\n\n"
                f"Quantity: {proc_request.quantity}\n"
                f"Final Price: {price}\n\n"
                f"Thank you for your cooperation. We look forward to successful collaboration.\n"
            )

        footer = """
        
        Thanks & Regards,  
        Vishal Kumbharkar 
        +91 9405536016  
        Manager System Developer  

        Office Address:  
        Plot No M-59, MIDC, Ahmednagar - 414 001 (M.S.) INDIA  

        Web: www.kalikaindia.com  

        Contact Emails and Departments:
        - sales.kalikaenterprises@gmail.com (SWAPNIL ADHAV - SALES)
        - kalikaenterprises.purchase@gmail.com (PRACHI JADHAV - PURCHASE)
        - dispatchkalikaenterprises1667@gmail.com (NARAYAN DETHE - DISPATCH)
        - kalikaenterprisesmktg@gmail.com (RANI KASBE - MARKETING)
        - acckalikaenterprises@gmail.com (VAISHNAVI DHOLE - ACCOUNT)
        """

        final_email_body = email_body_generated + footer

        try:
            send_mail(
                subject=f"Confirmation of Finalized Quotation - {product_name}",
                message=final_email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[selected_quote.supplier.email],
                fail_silently=False,
            )
            print(f"✅ Confirmation email sent to {selected_quote.supplier.email}")
        except Exception as e:
            print(f"❌ Failed to send confirmation email: {e}")

        return JsonResponse({
            'success': True,
            'savings': total_savings,
            'message': f'Finalized successfully and confirmation email sent to {selected_quote.supplier.email}.'
        })

    except (ProcurementRequest.DoesNotExist, Quote.DoesNotExist):
        return JsonResponse({'error': 'Request or Quote not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def delete_request_api(request, pk):
    try:
        ProcurementRequest.objects.get(pk=pk).delete()
        return JsonResponse({'success': True})
    except ProcurementRequest.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)

@csrf_exempt
@require_POST
def manual_rfq_sent_api(request, pk):
    try:
        req = ProcurementRequest.objects.get(pk=pk)
        req.status = 'rfqs-sent'
        req.total_quotes_sent = 1 
        req.save()
        return JsonResponse({'success': True})
    except ProcurementRequest.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)