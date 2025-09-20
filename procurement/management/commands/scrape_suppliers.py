# procurement/management/commands/scrape_suppliers.py

import os
import re
import json
import asyncio
import requests
from urllib.parse import urlparse, urljoin, quote_plus
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Page
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.conf import settings
from serpapi import GoogleSearch
# 🔄 MODIFIED: Import new models
from procurement.models import ProcurementRequest, Supplier, Product, MasterVendor
from asgiref.sync import sync_to_async

# --- Helper Functions for Scraping ---

def clean_phone_number(phone_text: str) -> str | None:
    cleaned = re.sub(r'[^\d+]', '', phone_text)
    if len(re.sub(r'^\+91', '', cleaned)) >= 10:
        return cleaned
    return None

# 🔄 MODIFIED: Made the function more resilient to timeouts and errors
async def find_contact_info(page: Page) -> dict:
    details = {'email': None, 'phone': None}
    base_url = page.url
    try:
        # Give more time for lazy-loading elements
        await page.wait_for_load_state('networkidle', timeout=30000)
        content = await page.content()
        
        email_match = re.search(r'[\w\.\-]+@[\w\.\-]+\.\w+', content)
        if email_match: details['email'] = email_match.group(0).lower()

        phone_match = re.search(r'(?:\+91|0)?[-\s]?(?:[6-9]\d{2,3}[-\s]?\d{3}[-\s]?\d{4})', content)
        if phone_match: details['phone'] = clean_phone_number(phone_match.group(0))

        # If details are missing, try to find a contact page
        if not all(details.values()):
            contact_link = page.locator('a[href*="contact"]').first
            if await contact_link.is_visible(timeout=5000):
                contact_href = await contact_link.get_attribute("href")
                if contact_href:
                    contact_url = urljoin(base_url, contact_href)
                    print(f"      - Navigating to contact page: {contact_url}")
                    # Use a separate try-except for contact page navigation
                    try:
                        await page.goto(contact_url, wait_until="domcontentloaded", timeout=30000)
                        contact_content = await page.content()
                        if not details['email']:
                            email_match = re.search(r'[\w\.\-]+@[\w\.\-]+\.\w+', contact_content)
                            if email_match: details['email'] = email_match.group(0).lower()
                        if not details['phone']:
                            phone_match = re.search(r'(?:\+91|0)?[-\s]?(?:[6-9]\d{2,3}[-\s]?\d{3}[-\s]?\d{4})', contact_content)
                            if phone_match: details['phone'] = clean_phone_number(phone_match.group(0))
                    except PlaywrightTimeoutError:
                        print(f"      - Timeout while navigating to contact page: {contact_url}")
                    except Exception as e_contact:
                        print(f"      - Error on contact page {contact_url}: {e_contact}")
    except Exception as e:
        print(f"      - Could not extract contact details from {base_url}: {e}")
    return details

# 🔄 MODIFIED: Increased timeout for SearXNG
def search_with_searxng(query: str, num_results: int = 10, start_index: int = 0) -> list:
    if not settings.SEARXNG_INSTANCE_URL:
        print("   - SearXNG is not configured. Skipping fallback.")
        return []
    
    try:
        print(f"   - Querying SearXNG: '{query}'")
        params = {'q': query, 'format': 'json', 'pageno': (start_index // num_results) + 1}
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

        response = requests.get(
            settings.SEARXNG_INSTANCE_URL + "/search",
            params=params, 
            headers=headers, 
            timeout=20  # Increased timeout
        )
        response.raise_for_status()
        data = response.json()
        
        return [{'title': r.get('title', 'N/A'), 'link': r.get('url', '')} for r in data.get('results', [])]
        
    except requests.RequestException as e:
        print(f"   - ❌ Error connecting to SearXNG: {e}")
        return []
    except json.JSONDecodeError:
        print(f"   - ❌ Error decoding JSON response from SearXNG.")
        return []

# --- Django Database Interaction ---
@sync_to_async
def get_procurement_request(request_id: int):
    return ProcurementRequest.objects.select_related('product').get(id=request_id)

# 🔄 MODIFIED: Logic to save to MasterVendor and Product models
@sync_to_async
def save_suppliers_to_db(proc_request: ProcurementRequest, suppliers_data: list):
    proc_request.suppliers.all().delete()
    saved_count = 0
    seen_emails = set()
    product = proc_request.product

    for data in suppliers_data:
        email = data.get('email')
        if email and email not in seen_emails:
            # Get or create a master vendor record
            master_vendor, created = MasterVendor.objects.get_or_create(
                email=email,
                defaults={
                    'name': data.get('name', 'N/A'),
                    'phone': data.get('phone'),
                    'source_link': data.get('source_link')
                }
            )
            # Link master vendor to the product
            if product:
                master_vendor.products.add(product)

            # Create the request-specific supplier entry
            Supplier.objects.create(
                procurement_request=proc_request,
                master_vendor=master_vendor,
                name=master_vendor.name,
                email=master_vendor.email,
                phone=master_vendor.phone,
                source_link=master_vendor.source_link
            )
            seen_emails.add(email)
            saved_count += 1
    return saved_count

@sync_to_async
def set_request_status(proc_request: ProcurementRequest, status: str):
    proc_request.status = status
    proc_request.save()

# --- Main Sourcing Agent Logic ---
async def run_supplier_sourcing_agent(request_id):
    proc_request = await get_procurement_request(request_id)
    if not proc_request:
        print(f"Error: ProcurementRequest with ID {request_id} not found.")
        return

    # Use the product name from the request's linked product, if available
    product_name = proc_request.product.name if proc_request.product else proc_request.title
    print(f"🚀 Sourcing started: '{product_name}'")

    scraped_domains = set()
    all_found_suppliers_data = []
    MARKETPLACE_DOMAINS = ["indiamart.com", "tradeindia.com", "alibaba.com", "amazon.com", "ebay.com", "exportersindia.com"]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # 🔄 MODIFIED: Set a realistic user agent and default timeout for the browser context
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        page.set_default_navigation_timeout(60000) # 60 seconds default timeout

        # --- PHASE 1: Sourcing from Indiamart ---
        print("\n--- AGENT PHASE 1: Sourcing from Indiamart... ---")
        try:
            search_query_im = quote_plus(product_name)
            indiamart_search_url = f"https://dir.indiamart.com/search.mp?ss={search_query_im}"
            await page.goto(indiamart_search_url, wait_until="load", timeout=60000)
            soup = BeautifulSoup(await page.content(), 'html.parser')
            vendor_links = soup.select('a.prd-name') # More specific selector
            vendor_names = {link.get_text(strip=True) for link in vendor_links if link.get_text(strip=True)}
            
            if vendor_names:
                print(f"  -> Found {len(vendor_names)} vendors on Indiamart. Finding their official sites...")
                for name in list(vendor_names)[:10]: # Limit to top 10 to be faster
                    # 🔄 MODIFIED: Wrap in try-except to handle failures for individual vendors
                    try:
                        search_query = f'"{name}" official website contact'
                        results = []
                        try:
                            print(f"   - Trying SerpApi for '{name}'...")
                            search = GoogleSearch({"q": search_query, "api_key": settings.SERPAPI_API_KEY})
                            results = search.get_dict().get("organic_results", [])
                            if not results: raise ValueError("No results from SerpApi.")
                        except Exception as e:
                            print(f"   - SerpApi failed ({e}). Fallback to SearXNG.")
                            results = search_with_searxng(search_query)

                        if not results or not results[0].get("link"): continue
                        
                        website_url = results[0].get("link")
                        domain = urlparse(website_url).netloc.replace("www.", "")
                        if domain in scraped_domains or any(m in domain for m in MARKETPLACE_DOMAINS): continue
                        
                        scraped_domains.add(domain)
                        print(f"    - Visiting: {name} ({website_url})")
                        await page.goto(website_url, wait_until="domcontentloaded")
                        details = await find_contact_info(page)
                        if any(details.values()):
                            all_found_suppliers_data.append({'name': name, **details, 'source_link': website_url})
                            print(f"      ✅ Found: Email - {details['email']}, Phone - {details['phone']}")
                    except PlaywrightTimeoutError:
                        print(f"      ❌ Timeout while processing vendor '{name}'. Skipping.")
                    except Exception as e:
                        print(f"      ❌ Error processing vendor '{name}': {e}")
        except Exception as e:
            print(f"❌ Error in Indiamart scraping phase: {e}")

        # --- PHASE 2: Sourcing from Google Search ---
        print("\n--- AGENT PHASE 2: Sourcing from Google Search... ---")
        for start_index in range(0, 20, 10):
            try:
                print(f"  -> Searching Google page {start_index//10 + 1}...")
                search_query = f'"{product_name}" suppliers manufacturers India contact email'
                results = []
                try:
                    print(f"   - Trying SerpApi for page {start_index//10 + 1}...")
                    search = GoogleSearch({ "q": search_query, "api_key": settings.SERPAPI_API_KEY, "num": 10, "start": start_index })
                    results = search.get_dict().get("organic_results", [])
                    if not results: raise ValueError("No results from SerpApi.")
                except Exception as e:
                    print(f"   - SerpApi failed ({e}). Fallback to SearXNG.")
                    results = search_with_searxng(search_query, start_index=start_index)
                
                if not results: break

                for result in results:
                    # 🔄 MODIFIED: Wrap in try-except to handle failures for individual search results
                    try:
                        website_url = result.get("link")
                        if not website_url: continue
                        domain = urlparse(website_url).netloc.replace("www.", "")
                        if domain in scraped_domains or any(m in domain for m in MARKETPLACE_DOMAINS): continue
                        
                        scraped_domains.add(domain)
                        name = result.get("title")
                        print(f"    - Visiting: {name} ({website_url})")
                        await page.goto(website_url, wait_until="domcontentloaded")
                        details = await find_contact_info(page)
                        if any(details.values()):
                            all_found_suppliers_data.append({'name': name, **details, 'source_link': website_url})
                            print(f"      ✅ Found: Email - {details['email']}, Phone - {details['phone']}")
                    except PlaywrightTimeoutError:
                        print(f"      ❌ Timeout while processing URL '{website_url}'. Skipping.")
                    except Exception as e:
                        print(f"      ❌ Error processing URL '{website_url}': {e}")
            except Exception as e_phase2:
                print(f"❌ Error in Google sourcing phase: {e_phase2}")
                break # Stop if a major error occurs in this phase

        await browser.close()

    # --- PHASE 3: Save Data to Database ---
    print("\n--- AGENT PHASE 3: Saving suppliers... ---")
    try:
        saved_count = await save_suppliers_to_db(proc_request, all_found_suppliers_data)
        print(f"✅ Saved {saved_count} new suppliers to the database.")
    except Exception as e:
        print(f"❌ Error saving suppliers to database: {e}")
    finally:
        await set_request_status(proc_request, 'awaiting-approval')
        print(f"\nAgent finished for request {request_id}. Status set to 'Awaiting Approval'.")

class Command(BaseCommand):
    help = 'Runs the supplier sourcing agent with improved error handling.'
    
    def add_arguments(self, parser):
        parser.add_argument('request_id', type=int, help='The ID of the ProcurementRequest to process')
    
    def handle(self, *args, **options):
        request_id = options['request_id']
        asyncio.run(run_supplier_sourcing_agent(request_id))