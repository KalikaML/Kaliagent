# procurement/management/commands/scrape_suppliers.py

import os
import re
import json
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from django.core.management.base import BaseCommand
from django.conf import settings
from serpapi import GoogleSearch
from procurement.models import ProcurementRequest, Product, Vendor
from procurement.utils import get_ai_response

# --- (Helper functions like get_cleaned_html, extract_with_regex, find_email_on_official_site remain the same) ---

# --- Main Sourcing Agent Logic ---
def run_supplier_sourcing_agent(request_id):
    proc_request = None
    try:
        proc_request = ProcurementRequest.objects.get(id=request_id)
        product = proc_request.product
        product_name = product.name
        
        # इस स्क्रैप के लिए पुराने नतीजों को साफ करें
        proc_request.vendors_found_this_scrape.clear()
        
        all_found_suppliers_data = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # --- PHASE 1 & 2: Scraping logic remains the same ---
            # It will scrape IndiaMART and Official websites and populate a list of dictionaries
            # Let's assume the result of scraping is a list called `all_found_suppliers_data`
            # where each item is a dictionary: {'name': ..., 'email': ..., 'phone': ..., 'source_link': ...}
            
            # Example of how scraped data would be processed inside the scraping loops:
            # scraped_supplier_info = {'name': 'Example Supplier', 'email': 'contact@example.com', ...}
            # all_found_suppliers_data.append(scraped_supplier_info)

            # --- Placeholder for your scraping logic ---
            # ...
            # After scraping is done, all_found_suppliers_data is populated.
            # ...
            browser.close()

        # --- PHASE 3: Deduplicate and Save to Database ---
        print("\n--- AGENT PHASE 3: Consolidating and saving all found vendors... ---")
        
        seen_vendor_names = set()
        for supplier_data in all_found_suppliers_data:
            name = supplier_data.get('name')
            if name and name.lower().strip() not in seen_vendor_names:
                # ग्लोबल वेंडर लिस्ट में वेंडर को बनाएँ या प्राप्त करें
                vendor, created = Vendor.objects.get_or_create(
                    name__iexact=name,
                    defaults={
                        'name': name,
                        'email': supplier_data.get('email'),
                        'phone': supplier_data.get('phone'),
                        'source_link': supplier_data.get('source_link')
                    }
                )
                
                # वेंडर को इस प्रोडक्ट की ऐतिहासिक सूची में जोड़ें
                product.historical_vendors.add(vendor)
                
                # वेंडर को इस खास रिक्वेस्ट की "इस स्क्रैप में मिले" सूची में जोड़ें
                proc_request.vendors_found_this_scrape.add(vendor)

                seen_vendor_names.add(name.lower().strip())
                if created:
                    print(f"✅ New global vendor '{vendor.name}' created and saved.")
                else:
                    print(f"🔄 Existing global vendor '{vendor.name}' found and associated.")

    except ProcurementRequest.DoesNotExist:
        print(f"Error: ProcurementRequest with ID {request_id} does not exist.")
    except Exception as e:
        print(f"An unexpected error occurred in the agent: {e}")
    finally:
        if proc_request:
            proc_request.status = 'awaiting-approval'
            proc_request.save()
            print(f"Agent finished for request {request_id}. Status set to 'Awaiting Approval'.")

class Command(BaseCommand):
    help = 'Runs the enhanced supplier scraper using a global Vendor model.'
    
    def add_arguments(self, parser):
        parser.add_argument('request_id', type=int, help='The ID of the procurement request to process')
    
    def handle(self, *args, **options):
        request_id = options['request_id']
        self.stdout.write(self.style.SUCCESS(f"🚀 Starting global vendor sourcing for request ID: {request_id}"))
        run_supplier_sourcing_agent(request_id)
        self.stdout.write(self.style.SUCCESS(f"✅ Finished sourcing for request ID: {request_id}"))