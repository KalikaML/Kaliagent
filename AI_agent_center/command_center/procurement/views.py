# procurement/views.py
import json
import imaplib
import email
import csv # Import the csv module for file processing
import re  # Import the regular expression module

from django.shortcuts import render, redirect # Import redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import ProcurementRequest
from serpapi import GoogleSearch

# ... (procurement_dashboard_view remains the same) ...
# ... (add_request_api remains the same) ...
# ... (get_request_details_api remains the same) ...

def procurement_dashboard_view(request):
    # This view remains unchanged from the previous fix.
    columns_data = [
        {'id': 'new-request', 'title': '📥 New Request', 'color': 'border-sky-500'},
        {'id': 'agent-working', 'title': '🤖 Agent Working', 'color': 'border-amber-500'},
        {'id': 'awaiting-approval', 'title': '📨 Awaiting Approval', 'color': 'border-purple-500'},
        {'id': 'rfqs-sent', 'title': '📬 RFQs Sent', 'color': 'border-blue-500'},
        {'id': 'quotes-received', 'title': '📊 Quotes Received', 'color': 'border-green-500'},
        {'id': 'finalized', 'title': '🏆 Finalized', 'color': 'border-slate-500'}
    ]
    all_requests = ProcurementRequest.objects.all().order_by('created_at')
    for column in columns_data:
        column['requests'] = [req for req in all_requests if req.status == column['id']]
    context = {'columns': columns_data}
    return render(request, 'procurement/dashboard.html', context)

@csrf_exempt
@require_POST
def add_request_api(request):
    data = json.loads(request.body)
    new_request = ProcurementRequest.objects.create(
        title=data.get('title'),
        quantity=data.get('quantity'),
        specs=data.get('specs'),
        source=data.get('source', 'Manual'),
        status='new-request'
    )
    return JsonResponse({'success': True, 'id': new_request.id})

def get_request_details_api(request, pk):
    try:
        req = ProcurementRequest.objects.get(pk=pk)
        data = {
            'id': req.id, 'title': req.title, 'quantity': req.quantity,
            'specs': req.specs, 'status': req.status, 'source': req.source,
            'quotesIn': req.quotes_in, 'totalQuotesSent': req.total_quotes_sent,
        }
        return JsonResponse(data)
    except ProcurementRequest.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)

# --- MODIFIED: Enhanced Agent Simulation Logic ---
def run_agent_simulation_api(request, pk):
    try:
        req = ProcurementRequest.objects.get(pk=pk)
        req.status = 'agent-working'
        req.save()
        
        # Enhanced query to find contact details on specific sites
        search_query = f'"{req.title}" supplier contact email OR phone site:indiamart.com OR site:tradeindia.com OR official website'
        
        params = {
            "engine": "google",
            "q": search_query,
            "api_key": settings.SERPAPI_API_KEY
        }
        search = GoogleSearch(params)
        results = search.get_dict()
        
        suppliers = []
        if 'organic_results' in results:
            for result in results.get('organic_results', [])[:8]: # Take top 8
                snippet = result.get('snippet', '')
                
                # --- Regex to find email and phone (best-effort) ---
                # NOTE: This is heuristic and may not be 100% accurate.
                email_found = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
                phone_found = re.search(r'(\+91[\s-]?)?[789]\d{9}', snippet)

                suppliers.append({
                    'name': result.get('title'),
                    'email': email_found.group(0) if email_found else 'Not found',
                    'phone': phone_found.group(0) if phone_found else 'Not found',
                    'source': result.get('link') 
                })
        
        req.status = 'awaiting-approval'
        req.total_quotes_sent = len(suppliers)
        req.save()

        return JsonResponse({
            'success': True, 
            'new_status': 'awaiting-approval',
            'suppliers': suppliers
        })
    except ProcurementRequest.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)
        
# --- NEW: View for Bulk CSV Upload ---
@require_POST
def bulk_upload_api(request):
    if 'file' not in request.FILES:
        # Handle case where no file is uploaded
        return redirect('procurement:dashboard')

    csv_file = request.FILES['file']
    
    # Basic validation for file type
    if not csv_file.name.endswith('.csv'):
        # Handle incorrect file type error (e.g., messages framework)
        return redirect('procurement:dashboard')

    try:
        # Decode the file and read it using the csv module
        decoded_file = csv_file.read().decode('utf-8').splitlines()
        reader = csv.reader(decoded_file)
        
        # Skip header row
        next(reader, None)

        for row in reader:
            # Assumes CSV columns are: Product Title, Quantity, Specifications
            if len(row) >= 3:
                ProcurementRequest.objects.create(
                    title=row[0],
                    quantity=row[1],
                    specs=row[2],
                    source='Bulk Upload',
                    status='new-request'
                )
    except Exception as e:
        # Handle potential errors during file processing
        print(f"Error processing bulk upload: {e}")

    return redirect('procurement:dashboard')


# ... (approve_rfqs_api and check_quotes_api remain the same) ...
@csrf_exempt
@require_POST
def approve_rfqs_api(request, pk):
    try:
        req = ProcurementRequest.objects.get(pk=pk)
        req.status = 'rfqs-sent'
        req.save()
        return JsonResponse({'success': True, 'new_status': 'rfqs-sent'})
    except ProcurementRequest.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)


def check_quotes_api(request, pk):
    try:
        req = ProcurementRequest.objects.get(pk=pk)
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
        mail.select('inbox')
        search_criteria = f'(SUBJECT "Re: RFQ - {req.title}")'
        status, data = mail.search(None, search_criteria)
        email_ids = data[0].split()
        found_quotes = len(email_ids)
        req.quotes_in = found_quotes
        if found_quotes > 0: req.status = 'quotes-received'
        req.save()
        mail.logout()
        dummy_quotes = [{'supplier': f'Supplier {i+1}', 'price': 52.50 + i, 'leadTime': f'{5+i} days', 'terms': 'Net 30', 'valueScore': 92 - i*2} for i in range(found_quotes)] if found_quotes > 0 else []
        return JsonResponse({'success': True, 'quotes_found': found_quotes, 'new_status': req.status, 'quotes_data': dummy_quotes})
    except ProcurementRequest.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)