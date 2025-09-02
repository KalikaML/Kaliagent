import json
import imaplib
import email
from email.header import decode_header
import csv
import re
import requests
import threading
import fitz
import io
import sys
import subprocess
import pytesseract
from PIL import Image

from urllib.parse import urlparse
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Sum, Avg, Count
from .models import ProcurementRequest, Supplier, Quote, Product, MasterVendor
from .utils import get_ai_response, process_incoming_quotes

# This setting may be required for some systems, e.g., Windows
# pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'

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
        {'id': 'rfqs-sent', 'title': '📧 RFQs Sent', 'color': 'border-blue-500'},
        {'id': 'quotes-received', 'title': '📥 Quotes Received', 'color': 'border-green-500'},
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

# ✨ NEW: View for the Analysis Dashboard
def analysis_view(request):
    # Filter logic for product
    selected_product_id = request.GET.get('product')
    
    # 1. Data for Historical Finalized Orders table
    finalized_requests = ProcurementRequest.objects.filter(status='finalized', selected_quote__isnull=False).select_related('selected_quote__supplier__master_vendor')
    if selected_product_id:
        finalized_requests = finalized_requests.filter(product_id=selected_product_id)

    # 2. Data for Master Vendor List table
    vendors = MasterVendor.objects.prefetch_related('products').annotate(product_count=Count('products'))
    if selected_product_id:
        vendors = vendors.filter(products__id=selected_product_id)
        
    # 3. Data for Savings Chart (product-wise savings)
    savings_data = ProcurementRequest.objects.filter(status='finalized', estimated_savings__gt=0).values('product__name').annotate(total_savings=Sum('estimated_savings')).order_by('-total_savings')
    
    chart_labels = [item['product__name'] for item in savings_data if item['product__name']]
    chart_values = [float(item['total_savings']) for item in savings_data if item['product__name']]

    context = {
        'products': Product.objects.all().order_by('name'),
        'finalized_requests': finalized_requests,
        'vendors': vendors,
        'selected_product_id': int(selected_product_id) if selected_product_id else None,
        'chart_labels': json.dumps(chart_labels),
        'chart_values': json.dumps(chart_values),
    }
    return render(request, 'procurement/analysis.html', context)


@csrf_exempt
@require_POST
def add_request_api(request):
    data = json.loads(request.body)
    # Get or create the product from the master list
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
    if 'file' not in request.FILES: return redirect('procurement:dashboard')
    uploaded_file = request.FILES['file']
    existing_titles = set(ProcurementRequest.objects.values_list('title', flat=True))
    new_requests = []
    try:
        # Simplified logic for brevity, assuming CSV for this example
        decoded_file = uploaded_file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded_file)
        for row in reader:
            title = row.get('Product Title')
            if title and title not in existing_titles:
                product, _ = Product.objects.get_or_create(name=title)
                new_requests.append(ProcurementRequest(
                    title=title,
                    product=product,
                    quantity=row.get('Quantity'),
                    specs=row.get('Specifications'),
                    source='Bulk Upload',
                    status='new-request'
                ))
                existing_titles.add(title)
        if new_requests:
            ProcurementRequest.objects.bulk_create(new_requests)
    except Exception as e:
        print(f"Error processing bulk upload file '{uploaded_file.name}': {e}")
    return redirect('procurement:dashboard')

def get_request_details_api(request, pk):
    try:
        req = ProcurementRequest.objects.get(pk=pk)
        suppliers = list(req.suppliers.all().values('name', 'email', 'phone', 'source_link', 'indiamart_rfq_sent'))
        quotes = list(req.quotes.all().values('id', 'supplier__name', 'price', 'lead_time_days', 'payment_terms', 'discount', 'full_email_body'))
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
def find_suppliers_api(request, pk):
    try:
        req = ProcurementRequest.objects.get(pk=pk)
        req.status = 'agent-working'
        req.save()
        def run_scraper_in_thread():
            command = [sys.executable, 'manage.py', 'scrape_suppliers', str(pk)]
            subprocess.run(command)
        thread = threading.Thread(target=run_scraper_in_thread)
        thread.start()
        return JsonResponse({'success': True, 'message': 'Sourcing agent started in background thread.'})
    except ProcurementRequest.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)

@csrf_exempt
@require_POST
def send_rfqs_api(request, pk):
    try:
        req = ProcurementRequest.objects.get(pk=pk)
        suppliers = req.suppliers.all()
        if not suppliers.exists():
            return JsonResponse({'error': 'No suppliers were found for this request.'}, status=400)
        
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
                    send_mail(subject, message_body, settings.DEFAULT_FROM_EMAIL, [supplier.email])
                    sent_via_email += 1
                except Exception as e:
                    print(f"Could not send email to {supplier.email}. Error: {e}")

        req.status = 'rfqs-sent'
        req.total_quotes_sent = req.suppliers.count()
        req.save()

        return JsonResponse({
            'success': True, 
            'message': f'Process complete. {sent_via_email} RFQs sent via email.', 
            'sent_to_count': req.total_quotes_sent
        })
    except ProcurementRequest.DoesNotExist:
        return JsonResponse({'error': 'Request not found.'}, status=404)
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
        proc_request = ProcurementRequest.objects.get(pk=pk)
        selected_quote = Quote.objects.get(pk=quote_id)
        
        all_quotes_for_request = Quote.objects.filter(procurement_request=proc_request, price__isnull=False)
        average_price = all_quotes_for_request.aggregate(avg_price=Avg('price'))['avg_price'] or selected_quote.price
        
        savings = average_price - selected_quote.price
        total_savings = savings
        
        try:
            quantity_val = int(re.search(r'\d+', proc_request.quantity).group())
            total_savings = savings * quantity_val
        except (ValueError, AttributeError, TypeError):
            print(f"Could not parse quantity '{proc_request.quantity}'. Using per-unit savings.")
            
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