import os
import re
import json
import time
from playwright.sync_api import sync_playwright
import google.generativeai as genai
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import requests

# --- AI and Django Model Setup ---
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'command_center.settings')
import django
django.setup()
from django.db import connection
from procurement.models import ProcurementRequest, Supplier

# Configure the Gemini model
try:
    from django.conf import settings
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    print(f"Could not configure Gemini. Ensure GEMINI_API_KEY is set. Error: {e}")
    model = None

# --- Helper functions from previous steps ---
def get_cleaned_html(page_content):
    soup = BeautifulSoup(page_content, 'html.parser')
    for script_or_style in soup(['script', 'style', 'link', 'meta']):
        script_or_style.decompose()
    return str(soup)

def get_interaction_plan(html, product_name):
    if not model: return None
    prompt = f"Analyze this HTML from indiamart.com. Identify CSS selectors for the product search input and the search button to find '{product_name}'. Return a JSON with keys 'product_input_selector' and 'search_button_selector'. HTML: {html}"
    try:
        response = model.generate_content(prompt)
        json_text = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(json_text)
    except Exception as e:
        print(f"AI Error (Interaction Plan): {e}")
        return None

def get_data_extraction_plan(html):
    if not model: return None
    prompt = f"Analyze this HTML from an IndiaMART search results page. Extract supplier information. For each supplier, find 'name', 'phone', and 'address'. Return a JSON array of objects. HTML: {html}"
    try:
        response = model.generate_content(prompt)
        json_text = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(json_text)
    except Exception as e:
        print(f"AI Error (Data Extraction): {e}")
        return []


# --- Main Hybrid Sourcing Agent Logic ---
def run_supplier_sourcing_agent(request_id):
    """
    A hybrid agent that uses both SerpApi for broad searching and Playwright for deep scraping.
    """
    suppliers_found = {} # Use a dictionary to store suppliers and avoid duplicates
    
    try:
        proc_request = ProcurementRequest.objects.get(id=request_id)
        product_name = proc_request.title
        
        # --- PHASE 1: Broad Search with SerpApi + Hunter.io ---
        print(f"AGENT PHASE 1: Starting broad search for '{product_name}' with SerpApi.")
        try:
            from serpapi import GoogleSearch
            broad_search_query = f'top "{product_name}" manufacturers OR suppliers in India'
            params = {"engine": "google", "q": broad_search_query, "api_key": settings.SERPAPI_API_KEY}
            search = GoogleSearch(params)
            initial_results = search.get_dict().get('organic_results', [])[:5] # Get top 5

            for result in initial_results:
                supplier_name = result.get('title')
                supplier_link = result.get('link')
                domain = urlparse(supplier_link).netloc.replace('www.', '') if supplier_link else None
                found_email = None

                if domain and settings.HUNTER_API_KEY:
                    hunter_url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={settings.HUNTER_API_KEY}&type=generic"
                    resp = requests.get(hunter_url, timeout=10)
                    if resp.status_code == 200 and resp.json().get('data', {}).get('emails'):
                        found_email = resp.json()['data']['emails'][0]['value']
                
                if supplier_name not in suppliers_found:
                    suppliers_found[supplier_name] = {'name': supplier_name, 'email': found_email, 'phone': None, 'source_link': supplier_link}
        except Exception as e:
            print(f"SerpApi/Hunter phase failed: {e}")

        # --- PHASE 2: Deep Scrape with Playwright + Gemini on IndiaMART ---
        print(f"AGENT PHASE 2: Starting deep scrape for '{product_name}' on IndiaMART.")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto("https://www.indiamart.com", wait_until='domcontentloaded', timeout=60000)
                plan = get_interaction_plan(get_cleaned_html(page.content()), product_name)
                if plan:
                    page.fill(plan['product_input_selector'], product_name)
                    page.click(plan['search_button_selector'])
                    page.wait_for_url("**/search.mp**", wait_until='domcontentloaded', timeout=60000)
                    
                    try: # Handle pop-up
                        page.locator('[data-dismiss="modal"]').click(timeout=5000)
                        print("Closed pop-up.")
                    except Exception:
                        print("No pop-up found.")

                    extracted_suppliers = get_data_extraction_plan(get_cleaned_html(page.content()))
                    if extracted_suppliers:
                        for supplier in extracted_suppliers:
                            name = supplier.get('name')
                            if name and name not in suppliers_found:
                                suppliers_found[name] = {'name': name, 'email': None, 'phone': supplier.get('phone'), 'source_link': page.url}
            finally:
                browser.close()

        # --- FINAL STEP: Save all unique suppliers to the database ---
        proc_request.suppliers.all().delete()
        if suppliers_found:
            print(f"Combining results. Total unique suppliers found: {len(suppliers_found)}")
            for supplier_data in suppliers_found.values():
                Supplier.objects.create(
                    procurement_request=proc_request,
                    name=supplier_data['name'],
                    email=supplier_data['email'],
                    phone=supplier_data['phone'],
                    source_link=supplier_data['source_link']
                )
        else:
            print("No suppliers found by any method.")

    except Exception as e:
        print(f"A critical error occurred in the sourcing agent: {e}")
    finally:
        # **THE FIX for SynchronousOnlyOperation error**:
        # The background thread must close its own database connection when it's done.
        proc_request.status = 'awaiting-approval'
        proc_request.save()
        connection.close()
        print(f"Agent finished for request {request_id}. DB connection closed.")