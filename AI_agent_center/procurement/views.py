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
from django.core.mail import send_mail, EmailMessage
from django.db.models import Sum, Avg, Count, OuterRef, Subquery
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
        {'id': 'rfqs-sent', 'title': '📨 RFQs Sent', 'color': 'border-blue-500'},
        {'id': 'quotes-received', 'title': '📊 Quotes Received', 'color': 'border-green-500'},
        {'id': 'finalized', 'title': '🏆 Finalized', 'color': 'border-slate-500'}
    ]
    
    all_requests = ProcurementRequest.objects.all().order_by('-created_at')
    
    for column in columns_data:
        # 🔄 MODIFIED: Logic updated for the 'quotes-received' column to group by product.
        if column['id'] == 'quotes-received':
            # Get products that have requests in 'quotes-received' status
            products_in_stage = Product.objects.filter(
                procurementrequest__status='quotes-received'
            ).distinct().annotate(
                # Count all quotes across all requests for this product
                quote_count=Count('procurementrequest__quotes')
            )
            column['products'] = products_in_stage
            column['requests'] = [] # Ensure this is empty for the new logic
        else:
            # Original logic for all other columns
            column['requests'] = [req for req in all_requests if req.status == column['id']]
            column['products'] = [] # Ensure this is empty

    context = {
        'columns': columns_data, 'total_savings': total_savings,
        'total_time_saved': total_time_saved, 'market_alert': market_alert,
    }
    return render(request, 'procurement/dashboard.html', context)

# ✨ NEW: API View to get all quotes for a specific Product ID
def get_product_quotes_api(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
        # Find all requests for this product that are in the 'quotes-received' stage
        requests_for_product = ProcurementRequest.objects.filter(product=product, status='quotes-received')
        
        # Aggregate all quotes and related suppliers from these requests
        quotes = Quote.objects.filter(procurement_request__in=requests_for_product).select_related('supplier', 'supplier__master_vendor')
        
        # We need a representative request to pass to the finalize API. We pick the first one.
        representative_request = requests_for_product.first()
        if not representative_request:
             return JsonResponse({'error': 'No active requests found for this product'}, status=404)

        data = {
            'id': product.id,
            'title': product.name, # Use product name as title
            'representative_request_id': representative_request.id,
            'quantity': representative_request.quantity, # Show quantity from a sample request
            'specs': representative_request.specs, # Show specs from a sample request
            'status': 'quotes-received', # The status is implicitly this
            'quotes': list(quotes.values('id', 'supplier__name', 'price', 'lead_time_days', 'payment_terms', 'discount', 'full_email_body')),
            'suppliers': list(Supplier.objects.filter(procurement_request__in=requests_for_product).distinct().values('name', 'email', 'phone')),
        }
        return JsonResponse(data)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)


def analysis_view(request):
    selected_product_id = request.GET.get('product')
    finalized_requests = ProcurementRequest.objects.filter(status='finalized', selected_quote__isnull=False).select_related('selected_quote__supplier__master_vendor')
    if selected_product_id:
        finalized_requests = finalized_requests.filter(product_id=selected_product_id)

    products_with_vendors = Product.objects.annotate(
        vendor_count=Count('vendors')
    ).filter(vendor_count__gt=0).prefetch_related('vendors').order_by('name')

    if selected_product_id:
        products_with_vendors = products_with_vendors.filter(id=selected_product_id)
        
    savings_data = ProcurementRequest.objects.filter(status='finalized', estimated_savings__gt=0).values('product__name').annotate(total_savings=Sum('estimated_savings')).order_by('-total_savings')
    
    chart_labels = [item['product__name'] for item in savings_data if item['product__name']]
    chart_values = [float(item['total_savings']) for item in savings_data if item['product__name']]

    context = {
        'products': Product.objects.all().order_by('name'),
        'finalized_requests': finalized_requests,
        'products_with_vendors': products_with_vendors,
        'selected_product_id': int(selected_product_id) if selected_product_id else None,
        'chart_labels': json.dumps(chart_labels),
        'chart_values': json.dumps(chart_values),
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
    if 'file' not in request.FILES: return redirect('procurement:dashboard')
    uploaded_file = request.FILES['file']
    existing_titles = set(ProcurementRequest.objects.values_list('title', flat=True))
    new_requests = []
    try:
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
        
        attachment = request.FILES.get('attachment')
        
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
        # This function can remain as it is, as it processes all unseen emails globally.
        # The logic in utils.py correctly identifies the product and creates/links the quote.
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
        
        # The 'pk' here is the representative request ID
        proc_request = ProcurementRequest.objects.get(pk=pk)
        selected_quote = Quote.objects.get(pk=quote_id)

        # Get all quotes for the same PRODUCT, not just the single request
        all_quotes_for_product = Quote.objects.filter(
            procurement_request__product=proc_request.product,
            price__isnull=False
        )
        average_price = all_quotes_for_product.aggregate(avg_price=Avg('price'))['avg_price'] or selected_quote.price

        savings = average_price - selected_quote.price
        total_savings = savings

        try:
            quantity_val = int(re.search(r'\d+', proc_request.quantity).group())
            total_savings = savings * quantity_val
        except (ValueError, AttributeError, TypeError):
            print(f"Could not parse quantity '{proc_request.quantity}'. Using per-unit savings.")

        # Update the representative request
        proc_request.status = 'finalized'
        proc_request.selected_quote = selected_quote
        proc_request.estimated_savings = total_savings
        proc_request.save()

        # 🔄 MODIFIED: Update all other open requests for the same product to 'finalized' as well.
        # This cleans up the Kanban board.
        ProcurementRequest.objects.filter(
            product=proc_request.product, 
            status='quotes-received'
        ).exclude(id=proc_request.id).update(status='finalized')


        supplier_name = selected_quote.supplier.name if selected_quote.supplier and selected_quote.supplier.name else "Supplier"
        product_name = proc_request.title
        quantity = proc_request.quantity
        price = selected_quote.price

        email_prompt = f"""
        Write a professional and polite confirmation email to a supplier named {supplier_name} 
        informing them that their quotation for {product_name} has been selected and finalized.

        Details:
        - Product: {product_name}
        - Quantity: {quantity}
        - Final Price: {price}

        The tone should be appreciative and professional. 
        Do NOT add unnecessary text, keep it clear and business-oriented.
        """

        from .utils import model
        if model:
            gemini_response = model.generate_content(email_prompt)
            email_body_generated = gemini_response.text.strip()
        else:
            email_body_generated = (
                f"Dear {supplier_name},\n\n"
                f"We are pleased to inform you that your quotation for {product_name} "
                f"has been reviewed and finalized by our procurement team.\n\n"
                f"Quantity: {quantity}\n"
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