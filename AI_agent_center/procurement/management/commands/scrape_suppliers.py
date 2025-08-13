# procurement/management/commands/scrape_suppliers.py

import os
import re
import json
import time
import asyncio
from urllib.parse import urlparse, urljoin, quote_plus
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Page
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.conf import settings
from serpapi import GoogleSearch
from procurement.models import ProcurementRequest, Supplier
from asgiref.sync import sync_to_async

# --- Helper Functions for Scraping ---

def clean_phone_number(phone_text: str) -> str | None:
    """Cleans and validates a found phone number string."""
    cleaned = re.sub(r'[^\d+]', '', phone_text)
    if len(re.sub(r'^\+91', '', cleaned)) >= 10:
        return cleaned
    return None

async def find_contact_info(page: Page) -> dict:
    """Finds email and phone by checking page content and then a potential contact page."""
    details = {'email': None, 'phone': None}
    base_url = page.url
    try:
        await page.wait_for_load_state('networkidle', timeout=15000)
        content = await page.content()
        
        email_match = re.search(r'[\w\.\-]+@[\w\.\-]+\.\w+', content)
        if email_match: details['email'] = email_match.group(0)

        phone_match = re.search(r'(?:\+91|0)?[-\s]?(?:[6-9]\d{2,3}[-\s]?\d{3}[-\s]?\d{4})', content)
        if phone_match: details['phone'] = clean_phone_number(phone_match.group(0))

        if not all(details.values()):
            contact_link = page.locator('a[href*="contact"]').first
            if await contact_link.is_visible(timeout=3000):
                contact_href = await contact_link.get_attribute("href")
                if contact_href:
                    contact_url = urljoin(base_url, contact_href)
                    print(f"      - Navigating to contact page: {contact_url}")
                    await page.goto(contact_url, wait_until="domcontentloaded", timeout=15000)
                    contact_content = await page.content()
                    if not details['email']:
                        email_match = re.search(r'[\w\.\-]+@[\w\.\-]+\.\w+', contact_content)
                        if email_match: details['email'] = email_match.group(0)
                    if not details['phone']:
                        phone_match = re.search(r'(?:\+91|0)?[-\s]?(?:[6-9]\d{2,3}[-\s]?\d{3}[-\s]?\d{4})', contact_content)
                        if phone_match: details['phone'] = clean_phone_number(phone_match.group(0))
    except Exception as e:
        print(f"      - Could not extract contact details from {base_url}: {e}")
    return details

# --- Django Database Interaction (sync_to_async wrappers) ---

@sync_to_async
def get_procurement_request(request_id: int):
    return ProcurementRequest.objects.get(id=request_id)

@sync_to_async
def save_suppliers_to_db(proc_request: ProcurementRequest, suppliers_data: list):
    proc_request.suppliers.all().delete()
    saved_count = 0
    seen_emails = set()
    for data in suppliers_data:
        if data.get('email') and data['email'] not in seen_emails:
            Supplier.objects.create(
                procurement_request=proc_request, name=data.get('name', 'N/A'),
                email=data.get('email'), phone=data.get('phone'), source_link=data.get('source_link'))
            seen_emails.add(data['email'])
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

    product_name = proc_request.title
    print(f"🚀 Starting 2-Phase sourcing for: '{product_name}'")

    scraped_domains = set()
    all_found_suppliers_data = []
    MARKETPLACE_DOMAINS = ["indiamart.com", "tradeindia.com", "alibaba.com", "amazon.com", "ebay.com", "exportersindia.com"]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # --- PHASE 1: Scrape Indiamart & Find Official Websites ---
        print("\n--- AGENT PHASE 1: Sourcing from Indiamart... ---")
        try:
            search_query = quote_plus(product_name)
            indiamart_search_url = f"https://dir.indiamart.com/search.mp?ss={search_query}"
            print(f"  -> Navigating directly to Indiamart search results...")
            await page.goto(indiamart_search_url, wait_until="load", timeout=45000)
            await page.wait_for_timeout(5000) # Wait for page to settle

            # EXPERT STRATEGY: Get page HTML and parse with BeautifulSoup for reliability
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all links that contain '/proddetail/' in their URL, which is a stable pattern for product listings
            vendor_links = soup.find_all('a', href=re.compile(r'/proddetail/'))
            
            vendor_names = set()
            for link in vendor_links:
                # The text of the link is usually the product or company name
                name = link.get_text(strip=True)
                if name:
                    vendor_names.add(name)

            if not vendor_names:
                print("  -> Could not find any vendor names using structural parsing. Indiamart structure may have significantly changed.")
            else:
                print(f"  -> Found {len(vendor_names)} unique vendors on Indiamart. Finding their official sites...")
                for name in list(vendor_names)[:10]: # Limit to first 10 to be efficient
                    try:
                        search = GoogleSearch({"q": f'"{name}" official website', "api_key": settings.SERPAPI_API_KEY})
                        results = search.get_dict().get("organic_results", [])
                        if not results: continue

                        website_url = results[0].get("link")
                        if not website_url: continue
                        domain = urlparse(website_url).netloc.replace("www.", "")
                        if domain in scraped_domains or any(m in domain for m in MARKETPLACE_DOMAINS): continue
                        
                        scraped_domains.add(domain)
                        print(f"    - Visiting: {name} ({website_url})")
                        await page.goto(website_url, wait_until="domcontentloaded", timeout=20000)
                        details = await find_contact_info(page)
                        if any(details.values()):
                            all_found_suppliers_data.append({'name': name, **details, 'source_link': website_url})
                            print(f"      ✅ Found: Email - {details['email']}, Phone - {details['phone']}")
                    except Exception as e:
                        print(f"      ❌ Error processing vendor '{name}': {e}")
        except Exception as e:
            print(f"❌ Could not complete Indiamart scraping phase: {e}")

        # --- PHASE 2: Broad Google Search for More Suppliers ---
        print("\n--- AGENT PHASE 2: Sourcing from Google Search... ---")
        try:
            for start_index in range(0, 20, 10):
                print(f"  -> Searching Google page {start_index//10 + 1}...")
                search = GoogleSearch({ "q": f'"{product_name}" suppliers manufacturers India', "api_key": settings.SERPAPI_API_KEY, "num": 10, "start": start_index })
                results = search.get_dict().get("organic_results", [])
                if not results: break

                for result in results:
                    website_url = result.get("link")
                    if not website_url: continue
                    domain = urlparse(website_url).netloc.replace("www.", "")
                    if domain in scraped_domains or any(m in domain for m in MARKETPLACE_DOMAINS): continue
                    
                    title = result.get("title", "").lower()
                    if "captcha" in title or "robot" in title:
                        print(f"    - Skipping site with potential CAPTCHA: {website_url}")
                        continue

                    scraped_domains.add(domain)
                    name = result.get("title")
                    print(f"    - Visiting: {name} ({website_url})")
                    await page.goto(website_url, wait_until="domcontentloaded", timeout=20000)
                    
                    page_title = (await page.title()).lower()
                    if "captcha" in page_title or "robot" in page_title or "verify" in page_title:
                        print(f"      - CAPTCHA detected on page. Skipping.")
                        continue
                        
                    details = await find_contact_info(page)
                    if any(details.values()):
                        all_found_suppliers_data.append({'name': name, **details, 'source_link': website_url})
                        print(f"      ✅ Found: Email - {details['email']}, Phone - {details['phone']}")
        except Exception as e:
            print(f"❌ Could not complete Google sourcing phase: {e}")

        await browser.close()

    # --- PHASE 3: Save all collected data to the database ---
    print("\n--- AGENT PHASE 3: Consolidating and saving suppliers... ---")
    try:
        saved_count = await save_suppliers_to_db(proc_request, all_found_suppliers_data)
        print(f"✅ Saved {saved_count} unique new suppliers to the database.")
    except Exception as e:
        print(f"❌ Error saving suppliers to database: {e}")
    finally:
        await set_request_status(proc_request, 'awaiting-approval')
        print(f"\nAgent finished for request {request_id}. Status set to 'Awaiting Approval'.")

class Command(BaseCommand):
    help = 'Runs the expert 2-phase async supplier sourcing agent.'
    
    def add_arguments(self, parser):
        parser.add_argument('request_id', type=int, help='The ID of the procurement request to process')
    
    def handle(self, *args, **options):
        request_id = options['request_id']
        asyncio.run(run_supplier_sourcing_agent(request_id))