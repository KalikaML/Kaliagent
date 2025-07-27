import os
import csv
import json
from playwright.sync_api import sync_playwright
import google.generativeai as genai
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Use a model that is good at understanding code and structured data
model = genai.GenerativeModel('gemini-1.5-flash')

# --- Helper Functions ---
def get_cleaned_html(page_content):
    """Removes script and style tags to reduce token count for the AI model."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(page_content, 'html.parser')
    for script_or_style in soup(['script', 'style']):
        script_or_style.decompose()
    return str(soup)

def get_interaction_plan(html, product_name):
    """Asks Gemini to find the search input and button selectors."""
    prompt = f"""
    Analyze the following HTML from an e-commerce homepage. Your task is to identify the CSS selectors
    for the main product search input field and the primary search button.
    The product to search for is "{product_name}".

    HTML Content:
    {html}

    Provide your answer as a JSON object with two keys:
    1. "product_input_selector": The CSS selector for the search text box.
    2. "search_button_selector": The CSS selector for the search button.
    """
    try:
        response = model.generate_content(prompt)
        # Clean up the response to extract only the JSON part
        json_text = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(json_text)
    except Exception as e:
        print(f"Error getting interaction plan from AI: {e}")
        return None

def get_data_extraction_plan(html):
    """Asks Gemini to extract supplier data from a results page."""
    prompt = f"""
    Analyze the following HTML from an IndiaMART search results page. Your task is to extract supplier information.
    For each supplier listed, find their name, phone number (if available), and address (if available).

    HTML Content:
    {html}

    Provide your answer as a JSON array, where each object represents a supplier and has the keys:
    "name", "phone", "address". If a piece of information is not found, use "Not Found".
    """
    try:
        response = model.generate_content(prompt)
        # Clean up the response to extract only the JSON part
        json_text = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(json_text)
    except Exception as e:
        print(f"Error getting data extraction plan from AI: {e}")
        return []

# --- Main Scraping Logic ---
def scrape_products(products_to_scrape: list):
    """
    Scrapes IndiaMART for a list of products using an AI-guided approach.
    :param products_to_scrape: A list of dictionaries, each with a 'Product Title'.
    :return: A list of all found suppliers.
    """
    all_suppliers = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) # Set to False to watch it run
        page = browser.new_page()

        for product_info in products_to_scrape:
            product_name = product_info['Product Title']
            print(f"\n--- Scraping for: {product_name} ---")

            try:
                # 1. Go to homepage and get the interaction plan from Gemini
                page.goto("https://www.indiamart.com", wait_until='domcontentloaded', timeout=60000)
                html_content = get_cleaned_html(page.content())
                
                plan = get_interaction_plan(html_content, product_name)
                if not plan or 'product_input_selector' not in plan or 'search_button_selector' not in plan:
                    print(f"AI could not determine how to search for {product_name}. Skipping.")
                    continue

                print(f"AI Plan: Fill '{plan['product_input_selector']}' and click '{plan['search_button_selector']}'")

                # 2. Execute the plan using Playwright
                page.fill(plan['product_input_selector'], product_name)
                page.click(plan['search_button_selector'])
                
                # 3. Wait for results page and extract data with Gemini
                page.wait_for_url("**/search.mp**", wait_until='domcontentloaded', timeout=60000)
                print(f"On results page: {page.url}")
                
                results_html = get_cleaned_html(page.content())
                suppliers = get_data_extraction_plan(results_html)
                
                if suppliers:
                    print(f"Found {len(suppliers)} suppliers for {product_name}.")
                    for supplier in suppliers:
                        supplier['searched_product'] = product_name # Add context
                    all_suppliers.extend(suppliers)
                else:
                    print(f"AI could not extract any suppliers for {product_name}.")

            except Exception as e:
                print(f"An error occurred while scraping for '{product_name}': {e}")
                page.screenshot(path=f"error_{product_name}.png")

        browser.close()
    return all_suppliers


if __name__ == "__main__":
    # 1. Read products from the input CSV
    products_from_csv = []
    with open('products.csv', mode='r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            products_from_csv.append(row)

    # 2. Run the scraper
    if products_from_csv:
        found_suppliers = scrape_products(products_from_csv)

        # 3. Write results to the output CSV
        if found_suppliers:
            output_filename = 'indiamart_suppliers.csv'
            with open(output_filename, mode='w', newline='', encoding='utf-8') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=['searched_product', 'name', 'phone', 'address'])
                writer.writeheader()
                writer.writerows(found_suppliers)
            print(f"\n✅ Success! All data saved to {output_filename}")