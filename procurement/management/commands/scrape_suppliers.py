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
from procurement.models import ProcurementRequest, Supplier, Product, MasterVendor
from asgiref.sync import sync_to_async
from procurement.utils import append_suppliers_to_sheet, load_previous_suppliers_for_product

# --- Relevance Filtering Helpers ---
STOPWORDS = {
    'india', 'indian', 'private', 'limited', 'ltd', 'pvt', 'company', 'co', 'manufacturers', 'manufacturer',
    'suppliers', 'supplier', 'exporters', 'exporter', 'dealer', 'dealers', 'contact', 'email', 'phone', 'product',
    'products', 'services', 'service', 'industrial', 'engineering', 'home', 'about', 'catalog', 'catalogue', 'profile'
}

# Minimum relevance score required to accept a supplier
MIN_RELEVANCE_SCORE = 0

def extract_keywords(text: str) -> set:
    if not text:
        return set()
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return {t for t in tokens if len(t) >= 4}

def get_email_domain(email: str | None) -> str | None:
    if not email or '@' not in email:
        return None
    return email.split('@')[-1].lower()

def html_to_text(content: str) -> str:
    try:
        soup = BeautifulSoup(content, 'html.parser')
        # Remove script/style tags
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()
        return soup.get_text(separator=' ', strip=True)
    except Exception:
        return ''

def compute_relevance(product_keywords: set, supplier_name: str | None, page_text: str, website_domain: str, email: str | None) -> int:
    name_tokens = extract_keywords(supplier_name or '')
    text_tokens = set(re.findall(r"[a-zA-Z0-9]+", page_text.lower()))
    text_keywords = {t for t in text_tokens if len(t) >= 4}
    overlap_in_name = len(product_keywords & name_tokens)
    overlap_in_text = len(product_keywords & text_keywords)
    score = overlap_in_name * 2 + overlap_in_text
    email_domain = get_email_domain(email)
    if email_domain and email_domain.endswith(website_domain):
        score += 2  # prefer official domain email
    return score

# --- Helper Functions for Scraping ---

def clean_phone_number(phone_text: str) -> str | None:
    """Normalize and validate phone numbers.
    - Preserves leading '+' for international format
    - Strips spaces, dashes, parentheses
    - Prefers Indian mobile numbers (10 digits starting 6-9)
    - Returns None for unlikely numbers (too short)
    """
    if not phone_text:
        return None
    raw = re.sub(r'[\s\-()]', '', str(phone_text))
    raw = raw.strip()
    # Keep leading plus if present, drop other non-digits
    if raw.startswith('+'):
        digits = re.sub(r'[^\d]', '', raw)
        cleaned = '+' + digits
    else:
        cleaned = re.sub(r'[^\d]', '', raw)

    if not cleaned:
        return None

    # Normalize common Indian formats
    digits_only = re.sub(r'^\+', '', cleaned)
    # Drop leading 0 used for STD dialing
    digits_only = re.sub(r'^0+', '', digits_only)
    # If starts with 91 country code, trim for length checks
    local = re.sub(r'^91', '', digits_only)

    # Prefer mobile: 10 digits starting 6-9
    if re.fullmatch(r'[6-9]\d{9}', local):
        return '+91' + local

    # Accept longer sequences (landlines) >=10
    if len(local) <= 10:
        # Return E.164-ish with +91 when plausible
        if cleaned.startswith('+') or digits_only.startswith('91'):
            return '+' + digits_only
        # Assume India if unknown but 10+ digits
        return '+91' + local

    return None

def extract_phone_candidates(html: str) -> list[str]:
    """Extract multiple candidate phone numbers from HTML via tel: links and regex.
    Returns a list of normalized numbers (best-effort)."""
    if not html:
        return []
    candidates: list[str] = []
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.lower().startswith('tel:'):
                num = href.split(':', 1)[1]
                norm = clean_phone_number(num)
                if norm:
                    candidates.append(norm)
        # Also itemprop="telephone"
        for el in soup.find_all(attrs={'itemprop': 'telephone'}):
            norm = clean_phone_number(el.get_text(strip=True))
            if norm:
                candidates.append(norm)
    except Exception:
        pass

    # Regex-based fallback: try to capture common patterns
    patterns = [
        r'(?:\+91\s?)?[6-9]\d{1,2}\s?\d{3}\s?\d{4}',  # Indian mobile with spaces
        r'(?:\+91\s?)?[6-9]\d{9}',                       # Indian mobile contiguous
        r'(?:\+\d{1,3}\s?)?\d{2,4}\s?\d{6,8}'         # Intl + landline-ish
    ]
    for pat in patterns:
        for m in re.finditer(pat, html):
            norm = clean_phone_number(m.group(0))
            if norm:
                candidates.append(norm)

    # Deduplicate, preserve order
    seen = set()
    unique = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique

async def find_contact_info(page: Page) -> dict:
    details = {'email': None, 'phone': None}
    base_url = page.url
    try:
        await page.wait_for_load_state('networkidle', timeout=30000)
        content = await page.content()
        
        email_match = re.search(r'[\w\.\-]+@[\w\.\-]+\.\w+', content)
        if email_match: details['email'] = email_match.group(0).lower()

        # Prefer phone from tel: anchors and itemprop before regex
        phone_candidates = extract_phone_candidates(content)
        if phone_candidates:
            # Prefer mobile (10-digit local) first
            mobile_like = [p for p in phone_candidates if re.search(r'^\+?91?[6-9]\d{9}$', re.sub(r'^\+', '', p))]
            details['phone'] = (mobile_like[0] if mobile_like else phone_candidates[0])

        if not all(details.values()):
            contact_link = page.locator('a[href*="contact"]').first
            if await contact_link.is_visible(timeout=5000):
                contact_href = await contact_link.get_attribute("href")
                if contact_href:
                    contact_url = urljoin(base_url, contact_href)
                    print(f"      - Navigating to contact page: {contact_url}")
                    try:
                        await page.goto(contact_url, wait_until="domcontentloaded", timeout=30000)
                        contact_content = await page.content()
                        if not details['email']:
                            email_match = re.search(r'[\w\.\-]+@[\w\.\-]+\.\w+', contact_content)
                            if email_match: details['email'] = email_match.group(0).lower()
                        if not details['phone']:
                            contact_candidates = extract_phone_candidates(contact_content)
                            if contact_candidates:
                                mobile_like = [p for p in contact_candidates if re.search(r'^\+?91?[6-9]\d{9}$', re.sub(r'^\+', '', p))]
                                details['phone'] = (mobile_like[0] if mobile_like else contact_candidates[0])
                    except PlaywrightTimeoutError:
                        print(f"      - Timeout while navigating to contact page: {contact_url}")
                    except Exception as e_contact:
                        print(f"      - Error on contact page {contact_url}: {e_contact}")
    except Exception as e:
        print(f"      - Could not extract contact details from {base_url}: {e}")
    return details

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
            params=params, headers=headers, timeout=20
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

def search_with_serpapi(query: str, num_results: int = 10, start_index: int = 0) -> list:
    """Search using SerpApi if configured, return list of {title, link}."""
    if not settings.SERPAPI_API_KEY:
        return []
    try:
        print(f"   - Trying SerpApi for page {start_index//num_results + 1}...")
        search = GoogleSearch({
            "q": query,
            "api_key": settings.SERPAPI_API_KEY,
            "num": num_results,
            "start": start_index
        })
        results = search.get_dict().get('organic_results') or []
        return [{
            'title': r.get('title', 'N/A'),
            'link': r.get('link', '')
        } for r in results]
    except Exception as e:
        print(f"   - SerpApi failed ({e}).")
        return []

def unified_web_search(query: str, num_results: int = 10, start_index: int = 0) -> list:
    """Try SerpApi first, then SearXNG, return de-duplicated list of results."""
    seen = set()
    combined = []
    for provider in (search_with_serpapi, search_with_searxng):
        try:
            results = provider(query, num_results=num_results, start_index=start_index)
        except TypeError:
            # search_with_searxng signature doesn't accept num_results
            results = provider(query, start_index=start_index)
        for r in results:
            url = r.get('link') or r.get('url') or ''
            if url and url not in seen:
                seen.add(url)
                combined.append({'title': r.get('title', 'N/A'), 'url': url})
        if combined:
            break
    return combined
#store query 
# ✨ NEW: Helper function to scrape product specifications from an IndiaMart product page
async def scrape_product_specifications(page: Page) -> str | None:
    print("      - Scraping for detailed product specifications...")
    try:
        # Wait for either a "Product Specification" heading or a specification table
        spec_heading_selector = "h2:has-text('Product Specification')"
        spec_table_selector = "table.pro-spec-table"
        
        # Wait for either of the elements to be present
        await page.wait_for_selector(f"{spec_heading_selector}, {spec_table_selector}", timeout=15000)

        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')

        spec_table = soup.find('table', class_='pro-spec-table')
        if spec_table:
            specs_text = []
            rows = spec_table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) == 2:
                    key = cols[0].get_text(strip=True)
                    value = cols[1].get_text(strip=True)
                    if key and value:
                        specs_text.append(f"{key}: {value}")
            if specs_text:
                print("      ✅ Found specifications in table.")
                return "\n".join(specs_text)

        # Fallback to finding the section by heading if table fails
        heading = soup.find('h2', string='Product Specification')
        if heading:
            parent_section = heading.find_parent('section')
            if parent_section:
                specs_list = parent_section.find('ul')
                if specs_list:
                    specs_text = [li.get_text(strip=True) for li in specs_list.find_all('li')]
                    if specs_text:
                        print("      ✅ Found specifications in list format.")
                        return "\n".join(specs_text)

    except PlaywrightTimeoutError:
        print("      - Timed out waiting for specification elements on the page.")
        return None
    except Exception as e:
        print(f"      - Error scraping specifications: {e}")
        return None
    
    print("      - Could not find specifications in a structured format.")
    return None


# --- Django Database Interaction ---
@sync_to_async
def get_procurement_request(request_id: int):
    return ProcurementRequest.objects.select_related('product').get(id=request_id)

@sync_to_async
def save_suppliers_to_db(proc_request: ProcurementRequest, suppliers_data: list):
    proc_request.suppliers.all().delete()
    saved_count = 0
    seen_contacts = set()
    product = proc_request.product
    
    newly_saved_suppliers_for_sheet = []

    # 👈 DEBUG: Check how many suppliers were received from the scraper
    print(f"\n[DEBUG] save_suppliers_to_db function received {len(suppliers_data)} suppliers.")

    for data in suppliers_data:
        name = data.get('name') or 'N/A'
        email = (data.get('email') or None)
        phone = (data.get('phone') or None)
        source_link = data.get('source_link')
        provenance = (data.get('provenance') or '').lower()

        # Skip entries with no contact info at all
        if not email and not phone:
            print(f"[DEBUG] Skipping supplier '{name}' — no email or phone found.")
            continue

        # De-duplication key: prefer email, else phone, else source_link
        key = None
        if email:
            key = f"email:{email.lower()}"
        elif phone:
            key = f"phone:{phone}"
        elif source_link:
            key = f"link:{source_link}"
        if key and key in seen_contacts:
            print(f"[DEBUG] Skipping duplicate supplier '{name}' via {key}.")
            continue

        master_vendor = None
        if email:
            master_vendor, _ = MasterVendor.objects.get_or_create(
                email=email,
                defaults={'name': name, 'phone': phone, 'source_link': source_link}
            )
            if product:
                master_vendor.products.add(product)

        # Persist provenance by prefixing source_link with 'csv:' for historical entries
        src_link = (master_vendor.source_link if master_vendor else None) or source_link
        if src_link and provenance == 'existing' and not str(src_link).startswith('csv:'):
            src_link = f"csv:{src_link}"

        Supplier.objects.create(
            procurement_request=proc_request,
            master_vendor=master_vendor,
            name=name,
            email=email,
            phone=phone,
            source_link=src_link
        )
        if key:
            seen_contacts.add(key)
        saved_count += 1
        newly_saved_suppliers_for_sheet.append({'name': name, 'email': email, 'phone': phone, 'source_link': source_link, 'provenance': provenance})

    # 👈 DEBUG: Check how many suppliers are ready to be written to Google Sheets
    print(f"[DEBUG] {len(newly_saved_suppliers_for_sheet)} suppliers are ready to be written to Google Sheets.")

    if newly_saved_suppliers_for_sheet:
        product_name = product.name if product else proc_request.title
        try:
            append_suppliers_to_sheet(product_name, newly_saved_suppliers_for_sheet)
        except Exception as e:
            print(f"   ❌ Failed to write to Google Sheets: {e}")
    else:
        # 👈 DEBUG: Print a message if no new suppliers are available
        print("[DEBUG] No new suppliers to process, so the Google Sheet function was not called.")

    return saved_count

# ✨ NEW: Async function to update the request's specifications
@sync_to_async
def update_request_specs(proc_request: ProcurementRequest, new_specs: str):
    """Appends scraped specifications to the existing specs."""
    current_specs = proc_request.specs or ""
    
    # Append new specs, ensuring not to add if already present
    if "--- Auto-scraped Specifications ---" not in current_specs:
        updated_specs = f"{current_specs}\n\n--- Auto-scraped Specifications ---\n{new_specs}".strip()
        proc_request.specs = updated_specs
        proc_request.save(update_fields=['specs'])
        print(f"   ✅ Updated request {proc_request.id} with scraped specifications.")

@sync_to_async
def set_request_status(proc_request: ProcurementRequest, status: str):
    proc_request.status = status
    proc_request.save()

# --- Main Sourcing Agent Logic ---
async def run_supplier_sourcing_agent(request_id):
    print(f"[INIT] Starting agent for request {request_id}...", flush=True)
    
    proc_request = await get_procurement_request(request_id)
    if not proc_request:
        print(f"Error: ProcurementRequest with ID {request_id} not found.", flush=True)
        return

    product_name = proc_request.product.name if proc_request.product else proc_request.title
    print(f"🚀 Sourcing started: '{product_name}'", flush=True)
    
    # Test Playwright availability
    try:
        print("[CHECK] Testing Playwright availability...", flush=True)
        import subprocess
        result = subprocess.run(['playwright', '--version'], capture_output=True, text=True, timeout=5)
        print(f"[CHECK] Playwright version: {result.stdout.strip()}", flush=True)
    except Exception as e:
        print(f"⚠️ WARNING: Playwright check failed: {e}", flush=True)

    scraped_domains = set()
    all_found_suppliers_data = []
    MARKETPLACE_DOMAINS = ["indiamart.com", "tradeindia.com", "alibaba.com", "amazon.com", "ebay.com", "exportersindia.com"]
    UNDESIRED_DOMAINS = {"linkedin.com", "facebook.com", "instagram.com", "twitter.com", "youtube.com", "kalikaindia.com"}
    product_keywords = extract_keywords(product_name)

    # Phase 0: Load historical suppliers from local CSV
    try:
        historical = load_previous_suppliers_for_product(product_name)
        if historical:
            print(f"\n--- AGENT PHASE 0: Loaded {len(historical)} historical suppliers from CSV ---")
            for h in historical:
                h['provenance'] = 'existing'
            all_found_suppliers_data.extend(historical)
        else:
            from django.conf import settings as _s
            print(f"\n--- AGENT PHASE 0: No historical suppliers found for '{product_name}'. CSV path: {_s.PREVIOUS_SUPPLIERS_CSV} ---")
    except Exception as e:
        print(f"   ❌ Error loading historical suppliers: {e}", flush=True)

    print("[INIT] Launching Playwright browser...", flush=True)
    try:
        async with async_playwright() as p:
            print("[INIT] Playwright context created, launching Chromium...", flush=True)
            browser = await p.chromium.launch(headless=True)
            print(f"[INIT] Browser launched successfully", flush=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            page.set_default_navigation_timeout(60000)
            print("[INIT] Browser page ready", flush=True)

            # --- PHASE 1: Sourcing from Indiamart ---
            print("\n--- AGENT PHASE 1: Scrape Specs & Find Suppliers from Indiamart ---")
            try:
                search_query_im = quote_plus(product_name)
                indiamart_search_url = f"https://dir.indiamart.com/search.mp?ss={search_query_im}"
                await page.goto(indiamart_search_url, wait_until="load", timeout=60000)
                
                # 🔄 OPTIONAL: Try to scrape product specifications if available (non-blocking)
                print("  -> Attempting to find and scrape product specifications (optional)...")
                try:
                    # Find the first product link on the search results page
                    first_product_link_selector = 'a.prd-name'
                    first_product_link = page.locator(first_product_link_selector).first
                    
                    if await first_product_link.is_visible(timeout=10000):
                        product_href = await first_product_link.get_attribute('href')
                        if product_href:
                            product_url = urljoin(indiamart_search_url, product_href)
                            print(f"    - Navigating to first product page: {product_url}")
                            await page.goto(product_url, wait_until="domcontentloaded")
                            
                            # Scrape specifications from the product detail page
                            scraped_specs = await scrape_product_specifications(page)
                            
                            if scraped_specs:
                                # Save the scraped specs to the database
                                await update_request_specs(proc_request, scraped_specs)
                            
                            # IMPORTANT: Go back to the search results page to find suppliers
                            print("    - Navigating back to search results page.")
                            await page.go_back(wait_until="domcontentloaded")
                    else:
                        print("    - No product link found for specification scraping (skipping, will continue with suppliers).")
                except Exception as e_specs:
                    print(f"    - ⚠️ Specification scraping failed (optional feature): {e_specs}")
                    print("    - Continuing with supplier search...")
                    # Ensure we are back on the search page if an error occurred
                    if page.url != indiamart_search_url:
                        await page.goto(indiamart_search_url, wait_until="load", timeout=60000)

                # Now, continue to find supplier names from the search results page
                soup = BeautifulSoup(await page.content(), 'html.parser')
                vendor_links = soup.select('a.prd-name') 
                vendor_names = {link.get_text(strip=True) for link in vendor_links if link.get_text(strip=True)}
                
                if vendor_names:
                    print(f"  -> Found {len(vendor_names)} potential vendors on Indiamart. Finding their official sites...")
                    for name in list(vendor_names)[:10]:
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
                            page_text = html_to_text(await page.content())
                            relevance = compute_relevance(product_keywords, name, page_text, domain, details.get('email'))
                            if any(details.values()) and relevance >= MIN_RELEVANCE_SCORE:
                                all_found_suppliers_data.append({'name': name, **details, 'source_link': website_url, 'provenance': 'scraped'})
                                print(f"      ✅ Relevant: Email - {details['email']}, Phone - {details['phone']} (score={relevance})")
                            else:
                                print(f"      ⚠️ Skipped low-relevance supplier '{name}' (score={relevance}).")
                        except PlaywrightTimeoutError:
                            print(f"      ❌ Timeout while processing vendor '{name}'. Skipping.")
                        except Exception as e:
                            print(f"      ❌ Error processing vendor '{name}': {e}")
            except Exception as e:
                print(f"❌ Error in Indiamart scraping phase: {e}")
            
            print(f"  📊 Indiamart phase complete: {len(all_found_suppliers_data)} suppliers collected so far.")

            # --- PHASE 2: Sourcing from Google Search ---
            print("\n--- AGENT PHASE 2: Sourcing from Google Search... ---")
            for start_index in range(0, 20, 10):
                try:
                    print(f"  -> Searching Google page {start_index//10 + 1}...")
                    search_query = f'"{product_name}" suppliers manufacturers India contact email'
                    results = unified_web_search(search_query, num_results=10, start_index=start_index)
                    
                    if not results: break

                    for result in results:
                        try:
                            website_url = result.get("url") or result.get("link")
                            if not website_url: continue
                            domain = urlparse(website_url).netloc.replace("www.", "")
                            if domain in scraped_domains or any(m in domain for m in MARKETPLACE_DOMAINS) or any(u in domain for u in UNDESIRED_DOMAINS): continue
                            
                            scraped_domains.add(domain)
                            name = result.get("title")
                            print(f"   - Visiting: {name} ({website_url})")
                            await page.goto(website_url, wait_until="domcontentloaded")
                            details = await find_contact_info(page)
                            page_text = html_to_text(await page.content())
                            relevance = compute_relevance(product_keywords, name, page_text, domain, details.get('email'))
                            if any(details.values()) and relevance >= MIN_RELEVANCE_SCORE:
                                all_found_suppliers_data.append({'name': name, **details, 'source_link': website_url, 'provenance': 'scraped'})
                                print(f"      ✅ Relevant: Email - {details['email']}, Phone - {details['phone']} (score={relevance})")
                            else:
                                print(f"      ⚠️ Skipped low-relevance supplier '{name}' (score={relevance}).")
                        except PlaywrightTimeoutError:
                            print(f"      ❌ Timeout while processing URL '{website_url}'. Skipping.")
                        except Exception as e:
                            print(f"      ❌ Error processing URL '{website_url}': {e}")
                except Exception as e_phase2:
                    print(f"❌ Error in Google sourcing phase: {e_phase2}")
                    break
            
            print(f"  📊 Google search phase complete: {len(all_found_suppliers_data)} suppliers collected so far.")

            # --- PHASE 2B: Target major Indian supplier portals directly if results are few ---
            ALT_PORTALS = [
                'site:tradeindia.com',
                'site:alibaba.com',
                'site:justdial.com',
                'site:ofbusiness.com',
            ]
            if len(all_found_suppliers_data) < 5:
                print("\n--- AGENT PHASE 2B: Targeted portal searches (TradeIndia, Alibaba, Justdial, OfBusiness)... ---")
                for portal in ALT_PORTALS:
                    try:
                        q = f'"{product_name}" suppliers manufacturers India contact email {portal}'
                        results = unified_web_search(q, num_results=10, start_index=0)
                        for r in results:
                            website_url = r.get('url') or r.get('link') or ''
                            if not website_url:
                                continue
                            domain = urlparse(website_url).netloc.replace('www.', '')
                            if domain in scraped_domains or any(u in domain for u in UNDESIRED_DOMAINS):
                                continue
                            scraped_domains.add(domain)
                            name = r.get('title')
                            print(f"    - Visiting: {name} ({website_url})")
                            try:
                                await page.goto(website_url, wait_until="domcontentloaded")
                                details = await find_contact_info(page)
                                page_text = html_to_text(await page.content())
                                relevance = compute_relevance(product_keywords, name, page_text, domain, details.get('email'))
                                if any(details.values()) and relevance >= MIN_RELEVANCE_SCORE:
                                    all_found_suppliers_data.append({'name': name, **details, 'source_link': website_url, 'provenance': 'scraped'})
                                    print(f"      ✅ Relevant: Email - {details['email']}, Phone - {details['phone']} (score={relevance})")
                                else:
                                    print(f"      ⚠️ Skipped low-relevance supplier '{name}' (score={relevance}).")
                            except PlaywrightTimeoutError:
                                print(f"      ❌ Timeout while processing URL '{website_url}'. Skipping.")
                            except Exception as e_visit:
                                print(f"      ❌ Error processing URL '{website_url}': {e_visit}")
                    except Exception as e_portal:
                        print(f"   - ❌ Portal-targeted search failed for {portal}: {e_portal}")
            
                print(f"  📊 Portal search phase complete: {len(all_found_suppliers_data)} suppliers collected total.")

            await browser.close()
            print("[CLEANUP] Browser closed successfully", flush=True)
    except Exception as playwright_error:
        print(f"❌ PLAYWRIGHT ERROR: {playwright_error}", flush=True)
        import traceback
        traceback.print_exc()
        print(f"[ERROR] Playwright failed, proceeding with any suppliers found so far: {len(all_found_suppliers_data)}", flush=True)
    
    # --- PHASE 3: Save Data to Database ---
    print(f"\n--- AGENT PHASE 3: Saving suppliers (found {len(all_found_suppliers_data)} total)... ---", flush=True)
    try:
        saved_count = await save_suppliers_to_db(proc_request, all_found_suppliers_data)
        print(f"✅ Saved {saved_count} suppliers to database (out of {len(all_found_suppliers_data)} found).", flush=True)
        if saved_count == 0 and len(all_found_suppliers_data) > 0:
            print("⚠️ WARNING: Suppliers were found but none were saved! Check contact info (email/phone).", flush=True)
        elif saved_count == 0:
            print("⚠️ INFO: No suppliers found during scraping. Consider retry or manual sourcing.", flush=True)
    except Exception as e:
        print(f"❌ Error saving suppliers to database: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        await set_request_status(proc_request, 'awaiting-approval')
        print(f"\n✅ Agent finished for request {request_id}. Status set to 'Awaiting Approval'.", flush=True)

class Command(BaseCommand):
    help = 'Runs the supplier sourcing agent, now with automatic specification scraping.'
    
    def add_arguments(self, parser):
        parser.add_argument('request_id', type=int, help='The ID of the ProcurementRequest to process')
    
    def handle(self, *args, **options):
        import sys
        request_id = options['request_id']
        print(f"=" * 80, flush=True)
        print(f"SCRAPE_SUPPLIERS COMMAND STARTED - Request ID: {request_id}", flush=True)
        print(f"Python: {sys.executable}", flush=True)
        print(f"Working directory: {os.getcwd()}", flush=True)
        print(f"=" * 80, flush=True)
        sys.stdout.flush()
        
        try:
            asyncio.run(run_supplier_sourcing_agent(request_id))
        except Exception as e:
            print(f"FATAL ERROR in scrape_suppliers: {e}", flush=True)
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
            raise