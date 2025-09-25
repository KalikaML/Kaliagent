import json
import re
import threading
import sys
import subprocess
from decimal import Decimal
import requests
import csv
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.mail import EmailMessage, send_mail
from django.db.models import Sum, Avg, Count
from django.contrib import messages
from .models import ProcurementRequest, Supplier, Quote, Product, MasterVendor
from .utils import process_incoming_quotes, get_ai_benchmark_price, get_ai_response, send_rfqs_for_request

# EXPLANATION: Yeh helper function sirf supplier scrape karta hai aur status ko 'awaiting-approval' set karta hai.
def start_supplier_scraping_agent(request_id):
    """Starts the scrape_suppliers management command for a given request ID in a background thread."""
    try:
        req = ProcurementRequest.objects.get(pk=request_id)
        req.status = 'agent-working'
        req.save()
        
        def run_in_thread():
            command = [sys.executable, 'manage.py', 'scrape_suppliers', str(request_id)]
            subprocess.run(command)
            
        thread = threading.Thread(target=run_in_thread)
        thread.start()
        return True
    except ProcurementRequest.DoesNotExist:
        print(f"Could not start agent for request ID {request_id}: DoesNotExist.")
        return False

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

        quote_values = list(quotes.values(
            'id', 'supplier__name', 'price', 'lead_time_days', 'payment_terms', 'discount', 
            'full_email_body', 'quantity', 'subtotal', 'tax_amount', 'freight_charges', 'total_amount'
        ))

        data = {
            'id': product.id,
            'title': product.name,
            'representative_request_id': representative_request.id,
            'quantity': representative_request.quantity,
            'specs': representative_request.specs,
            'status': 'quotes-received',
            'quotes': quote_values,
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
        decoded_file = uploaded_file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded_file)
        
        for row in reader:
            normalized_row = {key.strip().lower(): value for key, value in row.items()}
            
            title = normalized_row.get('product title') or normalized_row.get('product description')
            quantity = normalized_row.get('quantity', 'N/A')
            specs = normalized_row.get('specifications', '')
            
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
            
            # ========== THIS IS THE ONLY CHANGE IN THIS FUNCTION ==========
            # Ab yeh sirf supplier scraping agent ko call karega, full automation ko nahi.
            start_supplier_scraping_agent(new_request.id)
            # =============================================================

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
        messages.warning(request, f"Skipped {skipped_format_count} row(s) due to missing 'Product Title' or 'Product Description' column.")
    if new_requests_count == 0 and skipped_existing_count == 0 and skipped_format_count == 0:
        messages.warning(request, "The uploaded file was empty or did not contain any processable rows.")

    return redirect('procurement:dashboard')

def get_request_details_api(request, pk):
    try:
        req = ProcurementRequest.objects.get(pk=pk)
        suppliers = list(req.suppliers.all().values('name', 'email', 'phone', 'source_link', 'indiamart_rfq_sent'))
        quotes = list(req.quotes.all().values(
            'id', 'supplier__name', 'price', 'lead_time_days', 'payment_terms', 'discount', 
            'full_email_body', 'quantity', 'subtotal', 'tax_amount', 'freight_charges', 'total_amount'
        ))
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