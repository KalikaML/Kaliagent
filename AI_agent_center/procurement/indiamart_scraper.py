from playwright.sync_api import sync_playwright
import csv

def scrape_indiamart(product, location):
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/138.0.7204.169 Safari/537.36"
        ))

        page = context.new_page()

        page.goto("https://www.indiamart.com")
        page.wait_for_load_state("networkidle")
        
        # DEBUG: Take a screenshot of homepage and dump HTML
        page.screenshot(path="homepage_debug.png")
        html_content = page.content()
        print("Page HTML length:", len(html_content))

        try:
            # Try to fill product input (update selector after inspecting live site)
            page.fill("#autocomplete-1", product)
        except Exception as e:
            print("Could not find or fill product input:", e)
            print("Please update the selector based on real input field on homepage.")
            browser.close()
            return results

        try:
            page.fill("#autocomplete-2", location)
        except Exception as e:
            print("Could not find or fill location input:", e)

        # Click search button; update selector if needed
        try:
            page.click("button.searchbutton")
        except Exception as e:
            print("Could not click search button:", e)

        # Continue rest of scraping...

        browser.close()
    return results

if __name__ == "__main__":
    product = "sugar"
    location = "Delhi"
    scrape_indiamart(product, location)
