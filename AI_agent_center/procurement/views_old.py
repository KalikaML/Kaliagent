# procurement/views.py
import json
import imaplib
import email
from email.header import decode_header
import csv
import re
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.mail import send_mail
from .models import ProcurementRequest, Supplier, Quote
from serpapi import GoogleSearch

### new code dynamic data instead of Hardcoded sample data 
# procurement/views.py
import json
from django.shortcuts import render
from .models import ProcurementRequest

def procurement_kanban_view(request):
    # Fetch all requests from the database
    requests = ProcurementRequest.objects.all().order_by('created_at')

    # Format the data into a list of dictionaries that matches the JS structure
    requests_data = [
        {
            "id": req.id,
            "title": req.title,
            "quantity": req.quantity,
            "specs": req.specs,
            "status": req.status,
            "source": req.source,
            "quotesIn": req.quotes_in,
            "totalQuotes": req.total_quotes_sent
        }
        for req in requests
    ]

    context = {
        'requests_json': json.dumps(requests_data) # Convert to a JSON string
    }
    return render(request, 'procurement/procurement_tool.html', context)

#### end of dynamic data 
 
 
# procurement_dashboard_view and other unchanged views...
def procurement_dashboard_view(request):
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
    context = {'columns': columns_data}
    return render(request, 'procurement/dashboard.html', context)

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
    csv_file = request.FILES['file']
    if not csv_file.name.endswith('.csv'): return redirect('procurement:dashboard')
    try:
        decoded_file = csv_file.read().decode('utf-8').splitlines()
        reader = csv.reader(decoded_file)
        next(reader, None)
        for row in reader:
            if len(row) >= 3:
                ProcurementRequest.objects.create(
                    title=row[0], quantity=row[1], specs=row[2],
                    source='Bulk Upload', status='new-request'
                )
    except Exception as e:
        print(f"Error processing bulk upload: {e}")
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

# --- REAL AGENT STAGE APIs ---

# MODIFIED: find_suppliers_api now performs a two-step "deep search" for emails
@csrf_exempt
@require_POST
def find_suppliers_api(request, pk):
    req = ProcurementRequest.objects.get(pk=pk)
    req.status = 'agent-working'
    req.save()

    # Step 1: Broad search for a list of potential suppliers
    broad_search_query = f'"{req.title}" supplier OR manufacturer India site:indiamart.com OR site:tradeindia.com'
    params = {"engine": "google", "q": broad_search_query, "api_key": settings.SERPAPI_API_KEY}
    search = GoogleSearch(params)
    initial_results = search.get_dict().get('organic_results', [])[:7] # Get top 7 potential suppliers

    req.suppliers.all().delete()
    
    email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_regex = r'(\+91[\s-]?)?[789]\d{9}'

    for result in initial_results:
        supplier_name = result.get('title')
        supplier_link = result.get('link')
        snippet = result.get('snippet', '')
        
        # Quick scan the initial snippet for contact info
        email_match = re.search(email_regex, snippet)
        phone_match = re.search(phone_regex, snippet)

        # Step 2: If email not found in the initial scan, perform a "deep search" on the supplier's website
        if not email_match and supplier_link:
            try:
                deep_search_query = f'email OR contact us site:{supplier_link}'
                deep_params = {"engine": "google", "q": deep_search_query, "api_key": settings.SERPAPI_API_KEY}
                deep_search = GoogleSearch(deep_params)
                deep_results = deep_search.get_dict().get('organic_results', [])
                
                for deep_result in deep_results:
                    deep_snippet = deep_result.get('snippet', '') + " " + deep_result.get('title', '')
                    email_match = re.search(email_regex, deep_snippet)
                    if email_match:
                        break # Found an email, stop the deep search for this supplier
            except Exception as e:
                print(f"Deep search failed for {supplier_link}: {e}")

        # Save the supplier with the best information we could find
        Supplier.objects.create(
            procurement_request=req,
            name=supplier_name,
            email=email_match.group(0) if email_match else None,
            phone=phone_match.group(0) if phone_match else None,
            source_link=supplier_link
        )

    req.status = 'awaiting-approval'
    req.save()
    
    return JsonResponse({'success': True, 'new_status': 'awaiting-approval'})

# MODIFIED: send_rfqs_api now includes better error handling
@csrf_exempt
@require_POST
def send_rfqs_api(request, pk):
    req = ProcurementRequest.objects.get(pk=pk)
    suppliers = req.suppliers.all()
    if not suppliers:
        return JsonResponse({'error': 'No suppliers were found for this request.'}, status=400)
    
    # Filter for suppliers that actually have an email address
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

# check_and_parse_quotes_api remains the same...
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
        if not uid or uid in processed_uids:
            continue
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
            parsed_from_email_uid=uid,
            full_email_body=body
        )
        new_quotes_found += 1
    mail.logout()
    if new_quotes_found > 0:
        req.status = 'quotes-received'
        req.save()
    return JsonResponse({'success': True, 'new_quotes_found': new_quotes_found})