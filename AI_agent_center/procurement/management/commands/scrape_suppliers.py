# procurement/management/commands/scrape_suppliers.py

import os
import re
import json
import time
import asyncio
import requests
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
    cleaned = re.sub(r'[^\d+]', '', phone_text)
    if len(re.sub(r'^\+91', '', cleaned)) >= 10:
        return cleaned
    return None

async def find_contact_info(page: Page) -> dict:
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

# --- SearXNG Search Function ---
def search_with_searxng(query: str, num_results: int = 10, start_index: int = 0) -> list:
    if not settings.SEARXNG_INSTANCE_URL:
        print("   - SearXNG configure nahi hai. Fallback skip kiya ja raha hai.")
        return []
    
    try:
        print(f"   - SearXNG se query ki ja rahi hai: '{query}'")
        params = {
            'q': query,
            'format': 'json',
            'pageno': (start_index // num_results) + 1,
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(
            settings.SEARXNG_INSTANCE_URL + "/search",
            params=params, 
            headers=headers, 
            timeout=10
        )
        
        response.raise_for_status()
        
        data = response.json()
        
        formatted_results = []
        for result in data.get('results', []):
            formatted_results.append({
                'title': result.get('title', 'N/A'),
                'link': result.get('url', '')
            })
        return formatted_results
        
    except requests.RequestException as e:
        print(f"   - ❌ SearXNG se connect hone mein error: {e}")
        return []
    except json.JSONDecodeError:
        print(f"   - ❌ SearXNG se JSON response decode karne mein error.")
        return []

# --- Django Database Interaction ---
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
    print(f"🚀 Sourcing shuru: '{product_name}'")

    scraped_domains = set()
    all_found_suppliers_data = []
    MARKETPLACE_DOMAINS = ["indiamart.com", "tradeindia.com", "alibaba.com", "amazon.com", "ebay.com", "exportersindia.com"]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # --- PHASE 1: Indiamart se Sourcing ---
        print("\n--- AGENT PHASE 1: Indiamart se Sourcing... ---")
        try:
            search_query_im = quote_plus(product_name)
            indiamart_search_url = f"https://dir.indiamart.com/search.mp?ss={search_query_im}"
            await page.goto(indiamart_search_url, wait_until="load", timeout=45000)
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            vendor_links = soup.find_all('a', href=re.compile(r'/proddetail/'))
            vendor_names = {link.get_text(strip=True) for link in vendor_links if link.get_text(strip=True)}
            
            if vendor_names:
                print(f"  -> Indiamart par {len(vendor_names)} vendors mile. Unki official sites dhundhi ja rahi hain...")
                for name in list(vendor_names)[:10]:
                    try:
                        search_query = f'"{name}" official website'
                        results = []
                        try:
                            print(f"   - SerpApi try kiya ja raha hai '{name}' ke liye...")
                            search = GoogleSearch({"q": search_query, "api_key": settings.SERPAPI_API_KEY})
                            results = search.get_dict().get("organic_results", [])
                            if not results: raise ValueError("SerpApi se koi result nahi mila.")
                        except Exception as e:
                            print(f"   - SerpApi fail hua ({e}). SearXNG par fallback kiya ja raha hai.")
                            results = search_with_searxng(search_query)

                        if not results or not results[0].get("link"): continue
                        website_url = results[0].get("link")
                        domain = urlparse(website_url).netloc.replace("www.", "")
                        if domain in scraped_domains or any(m in domain for m in MARKETPLACE_DOMAINS): continue
                        
                        scraped_domains.add(domain)
                        print(f"    - Visit kiya ja raha hai: {name} ({website_url})")
                        await page.goto(website_url, wait_until="domcontentloaded", timeout=20000)
                        details = await find_contact_info(page)
                        if any(details.values()):
                            all_found_suppliers_data.append({'name': name, **details, 'source_link': website_url})
                            print(f"      ✅ Mila: Email - {details['email']}, Phone - {details['phone']}")
                    except Exception as e:
                        print(f"      ❌ Vendor '{name}' process karne mein error: {e}")
        except Exception as e:
            print(f"❌ Indiamart scraping phase mein error: {e}")

        # --- PHASE 2: Google Search se Sourcing ---
        print("\n--- AGENT PHASE 2: Google Search se Sourcing... ---")
        try:
            for start_index in range(0, 20, 10):
                print(f"  -> Google page {start_index//10 + 1} search kiya ja raha hai...")
                search_query = f'"{product_name}" suppliers manufacturers India'
                results = []
                try:
                    print(f"   - SerpApi try kiya ja raha hai page {start_index//10 + 1} ke liye...")
                    search = GoogleSearch({ "q": search_query, "api_key": settings.SERPAPI_API_KEY, "num": 10, "start": start_index })
                    results = search.get_dict().get("organic_results", [])
                    if not results: raise ValueError("SerpApi se koi result nahi mila.")
                except Exception as e:
                    print(f"   - SerpApi fail hua ({e}). SearXNG par fallback kiya ja raha hai.")
                    results = search_with_searxng(search_query, start_index=start_index)
                
                if not results: break

                for result in results:
                    website_url = result.get("link")
                    if not website_url: continue
                    domain = urlparse(website_url).netloc.replace("www.", "")
                    if domain in scraped_domains or any(m in domain for m in MARKETPLACE_DOMAINS): continue
                    
                    scraped_domains.add(domain)
                    name = result.get("title")
                    print(f"    - Visit kiya ja raha hai: {name} ({website_url})")
                    await page.goto(website_url, wait_until="domcontentloaded", timeout=20000)
                    details = await find_contact_info(page)
                    if any(details.values()):
                        all_found_suppliers_data.append({'name': name, **details, 'source_link': website_url})
                        print(f"      ✅ Mila: Email - {details['email']}, Phone - {details['phone']}")
        except Exception as e:
            print(f"❌ Google sourcing phase mein error: {e}")

        await browser.close()

    # --- PHASE 3: Database mein Data Save Karein ---
    print("\n--- AGENT PHASE 3: Suppliers ko save kiya ja raha hai... ---")
    try:
        saved_count = await save_suppliers_to_db(proc_request, all_found_suppliers_data)
        print(f"✅ Database mein {saved_count} naye suppliers save kiye gaye.")
    except Exception as e:
        print(f"❌ Suppliers ko database mein save karne mein error: {e}")
    finally:
        await set_request_status(proc_request, 'awaiting-approval')
        print(f"\nAgent ka kaam request {request_id} ke liye khatm. Status 'Awaiting Approval' set kiya gaya.")

class Command(BaseCommand):
    help = 'SearXNG fallback ke saath supplier sourcing agent chalata hai.'
    
    def add_arguments(self, parser):
        parser.add_argument('request_id', type=int, help='Procurement request ki ID jise process karna hai')
    
    def handle(self, *args, **options):
        request_id = options['request_id']
        asyncio.run(run_supplier_sourcing_agent(request_id))