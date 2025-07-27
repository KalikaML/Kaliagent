# procurement/views.py
import json
import imaplib
import email
from email.header import decode_header
import csv
import re
import requests
import threading  # <-- NEW: To run the scraper in the background
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Sum, Avg
from .models import ProcurementRequest, Supplier, Quote
from .scraper import run_supplier_sourcing_agent # <-- NEW: Import our scraper function

# --- Constants for Time Saved Calculation ---
TIME_SAVED_FIND_SUPPLIERS = 0.5
TIME_SAVED_SEND_RFQS = 0.75
TIME_SAVED_PARSE_QUOTES = 0.25

def procurement_dashboard_view(request):
    # This view's logic for calculating metrics and displaying the board remains the same
    total_savings = ProcurementRequest.objects.filter(status='finalized').aggregate(total=Sum('estimated_savings'))['total'] or 0
    time_saved_sourcing = ProcurementRequest.objects.filter(status__in=['awaiting-approval', 'rfqs-sent', 'quotes-received', 'finalized']).count() * TIME_SAVED_FIND_SUPPLIERS
    time_saved_rfqs = ProcurementRequest.objects.filter(status__in=['rfqs-sent', 'quotes-received', 'finalized']).count() * TIME_SAVED_SEND_RFQS
    time_saved_parsing = Quote.objects.count() * TIME_SAVED_PARSE_QUOTES
    total_time_saved = time_saved_sourcing + time_saved_rfqs + time_saved_parsing
    market_alert = "Market data currently unavailable."
    try:
        response = requests.get("https://api.nbp.pl/api/cenyzlota", timeout=5)
        if response.status_code == 200:
            market_alert = f"Gold prices: PLN {response.json()[0]['cena']}/gram."
    except requests.RequestException:
        print("Could not fetch market data.")
    columns_data = [
        {'id': 'new-request', 'title': '📥 New Request', 'color': 'border-sky-500'},
        {'id': 'agent-working', 'title': '🤖 Agent Working', 'color': 'border-amber-500'},
        {'id': 'awaiting-approval', 'title': '📨 Awaiting Approval', 'color': 'border-purple-500'},
        {'id': 'rfqs-sent', 'title': '📬 RFQs Sent', 'color': 'border-blue-500'},
        {'id': 'quotes-received', 'title': '📊 Quotes Received', 'color': 'border-green-500'},
        {'id': 'finalized', 'title': '🏆 Finalized', 'color': 'border-slate-500'}
    ]
    all_requests = ProcurementRequest.objects.all().order_by('-created_at')
    for column in columns_data:
        column['requests'] = [req for req in all_requests if req.status == column['id']]
    context = {
        'columns': columns_data, 'total_savings': total_savings,
        'total_time_saved': total_time_saved, 'market_alert': market_alert,
    }
    return render(request, 'procurement/dashboard.html', context)

# MODIFIED: This now calls the new hybrid agent in a background thread
@csrf_exempt
@require_POST
def find_suppliers_api(request, pk):
    req = ProcurementRequest.objects.get(pk=pk)
    req.status = 'agent-working'
    req.save()

    # Run the new, powerful sourcing agent in a separate thread
    scraper_thread = threading.Thread(target=run_supplier_sourcing_agent, args=(pk,))
    scraper_thread.start()
    
    return JsonResponse({'success': True, 'message': 'Hybrid sourcing agent started in the background.'})


# --- All other API views remain exactly the same ---
# (add_request_api, bulk_upload_api, get_request_details_api, finalize_request_api, send_rfqs_api, check_and_parse_quotes_api)
@csrf_exempt
@require_POST
def add_request_api(request):
    data = json.loads(request.body)
    new_request = ProcurementRequest.objects.create(
        title=data.get('title'), quantity=data.get('quantity'),
        specs=data.get('specs'), source=data.get('source', 'Manual'), status='new-request'
    )
    return JsonResponse({'success': True, 'id': new_request.id})

@require_POST
def bulk_upload_api(request):
    if 'file' not in request.FILES: return redirect('procurement:dashboard')
    uploaded_file = request.FILES['file']
    try:
        if uploaded_file.name.endswith('.csv'):
            decoded_file = uploaded_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            for row in reader:
                ProcurementRequest.objects.create(
                    title=row.get('Product Title'), quantity=row.get('Quantity'),
                    specs=row.get('Specifications'), source='Bulk Upload', status='new-request'
                )
        elif uploaded_file.name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file)
            for index, row in df.iterrows():
                ProcurementRequest.objects.create(
                    title=row['Product Title'], quantity=row['Quantity'],
                    specs=row['Specifications'], source='Bulk Upload', status='new-request'
                )
    except Exception as e:
        print(f"Error processing bulk upload file '{uploaded_file.name}': {e}")
    return redirect('procurement:dashboard')

def get_request_details_api(request, pk):
    try:
        req = ProcurementRequest.objects.get(pk=pk)
        suppliers = list(req.suppliers.all().values('name', 'email', 'phone', 'source_link'))
        quotes = list(req.quotes.all().values('id', 'supplier__name', 'price', 'lead_time_days', 'payment_terms', 'full_email_body'))
        data = {
            'id': req.id, 'title': req.title, 'quantity': req.quantity,
            'specs': req.specs, 'status': req.status, 'source': req.source,
            'suppliers': suppliers, 'quotes': quotes,
        }
        return JsonResponse(data)
    except ProcurementRequest.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)

@csrf_exempt
@require_POST
def finalize_request_api(request, pk):
    try:
        data = json.loads(request.body)
        quote_id = data.get('quote_id')
        proc_request = ProcurementRequest.objects.get(pk=pk)
        selected_quote = Quote.objects.get(pk=quote_id)
        all_quotes_for_request = Quote.objects.filter(procurement_request=proc_request, price__isnull=False)
        average_price = all_quotes_for_request.aggregate(avg_price=Avg('price'))['avg_price'] or selected_quote.price
        savings = average_price - selected_quote.price
        try:
            quantity_val = int(re.search(r'\d+', proc_request.quantity).group())
            total_savings = savings * quantity_val
        except (ValueError, AttributeError):
            total_savings = savings
        proc_request.status = 'finalized'
        proc_request.selected_quote = selected_quote
        proc_request.estimated_savings = total_savings
        proc_request.save()
        return JsonResponse({'success': True, 'savings': total_savings})
    except (ProcurementRequest.DoesNotExist, Quote.DoesNotExist):
        return JsonResponse({'error': 'Request or Quote not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def send_rfqs_api(request, pk):
    req = ProcurementRequest.objects.get(pk=pk)
    suppliers = req.suppliers.all()
    if not suppliers:
        return JsonResponse({'error': 'No suppliers were found for this request.'}, status=400)
    recipient_list = [s.email for s in suppliers if s.email]
    if not recipient_list:
        return JsonResponse({'error': 'No suppliers with valid email addresses were found.'}, status=400)
    subject = f"Request for Quotation (RFQ) - {req.title}"
    message = f"Dear Supplier,\n\nWe are interested in procuring the following item:\n\nProduct: {req.title}\nQuantity: {req.quantity}\nSpecifications: {req.specs}\n\nPlease provide a quotation including price, availability, estimated lead time, and payment terms.\nReference ID: REQ-{req.id}\n\nThank you,\nProcurement Team"
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)
    req.status = 'rfqs-sent'
    req.total_quotes_sent = len(recipient_list)
    req.save()
    return JsonResponse({'success': True, 'new_status': 'rfqs-sent', 'sent_to_count': len(recipient_list)})


@csrf_exempt
@require_POST
def check_and_parse_quotes_api(request, pk):
    req = ProcurementRequest.objects.get(pk=pk)
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
    mail.select('inbox')
    search_criteria = f'TEXT "REQ-{req.id}"'
    status, data = mail.search(None, search_criteria)
    email_ids = data[0].split()
    processed_uids = set(Quote.objects.filter(procurement_request=req).values_list('parsed_from_email_uid', flat=True))
    new_quotes_found = 0
    for e_id in email_ids:
        status, single_email_data = mail.fetch(e_id, '(RFC822 UID)')
        raw_email = single_email_data[0][1]
        uid_match = re.search(r'UID\s+(\d+)', single_email_data[0][0].decode())
        uid = uid_match.group(1) if uid_match else None
        if not uid or uid in processed_uids: continue
        msg = email.message_from_bytes(raw_email)
        from_ = msg.get("From")
        sender_name, sender_email = email.utils.parseaddr(from_)
        try:
            supplier = req.suppliers.get(email__iexact=sender_email)
        except Supplier.DoesNotExist:
            continue
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if "text/plain" in part.get_content_type():
                    body = part.get_payload(decode=True).decode()
                    break
        else:
            body = msg.get_payload(decode=True).decode()
        price_match = re.search(r'(?:price|rate|cost)[\s:]*₹?[\s]*([\d,]+\.?\d*)', body, re.IGNORECASE)
        lead_time_match = re.search(r'lead time[\s:]*(\d+)\s*days', body, re.IGNORECASE)
        payment_match = re.search(r'payment terms[\s:]*(.*)', body, re.IGNORECASE)
        Quote.objects.create(
            procurement_request=req, supplier=supplier,
            price=float(price_match.group(1).replace(',', '')) if price_match else None,
            lead_time_days=int(lead_time_match.group(1)) if lead_time_match else None,
            payment_terms=payment_match.group(1).strip() if payment_match else 'N/A',
            parsed_from_email_uid=uid, full_email_body=body
        )
        new_quotes_found += 1
    mail.logout()
    if new_quotes_found > 0:
        req.status = 'quotes-received'
        req.save()
    return JsonResponse({'success': True, 'new_quotes_found': new_quotes_found})