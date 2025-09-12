# marketing_outreach/views.py
import json
import logging
import re
import requests
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render
from serpapi import GoogleSearch

logger = logging.getLogger(__name__)

# Default profile to use if none is set in the session
DEFAULT_PROFILE = {
    'companyName': 'Your Company Name',
    'contactPerson': 'Your Name',
    'role': 'Your Role',
    'products': 'High-quality products and solutions',
    'keyDifferentiators': 'Unique selling proposition 1, Unique selling proposition 2'
}

def dashboard_view(request):
    """Renders the main dashboard page."""
    user_profile = request.session.get('user_profile', DEFAULT_PROFILE)
    return render(request, 'marketing_outreach/dashboard.html', {'user_profile': user_profile})

def settings_view(request):
    """Handles updating and rendering the user's company profile."""
    if request.method == 'POST':
        profile_data = {
            'companyName': request.POST.get('companyName', '').strip(),
            'contactPerson': request.POST.get('contactPerson', '').strip(),
            'role': request.POST.get('role', '').strip(),
            'products': request.POST.get('products', '').strip(),
            'keyDifferentiators': request.POST.get('keyDifferentiators', '').strip(),
        }
        request.session['user_profile'] = profile_data
        return redirect('marketing_outreach:dashboard')

    user_profile = request.session.get('user_profile', DEFAULT_PROFILE)
    return render(request, 'marketing_outreach/settings.html', {'user_profile': user_profile})


# --- API Views ---

def search_companies_api(request):
    """
    Searches Google for companies using SerpApi and extracts contact info from snippets.
    """
    search_term = request.GET.get('q')
    if not search_term:
        return JsonResponse({'error': 'Search term cannot be empty.'}, status=400)
    
    # Check for API Key
    if not settings.SERPAPI_API_KEY:
        logger.error("SERPAPI_API_KEY is not configured.")
        return JsonResponse({'error': 'The search service is not configured.'}, status=500)

    search_query = f'"{search_term}" company contact email site:indiamart.com OR site:tradeindia.com OR site:zaubacorp.com'
    params = {
        "engine": "google",
        "q": search_query,
        "api_key": settings.SERPAPI_API_KEY,
        "num": 20
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict().get('organic_results', [])
    except Exception as e:
        logger.error(f"SerpApi search failed: {e}")
        return JsonResponse({'error': 'Failed to perform search.'}, status=500)

    companies = []
    email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_regex = r'(?:\+91[\s-]?)?[6-9]\d{9}\b'

    for i, result in enumerate(results):
        snippet = result.get('snippet', '')
        title = result.get('title', '')
        link = result.get('link')
        text_content = (title + " " + snippet).lower()

        email_match = re.search(email_regex, text_content)
        phone_match = re.search(phone_regex, text_content)

        industry_keywords = {
            'manufacturing': ['manufacturing', 'manufacturer'], 'plastic': ['plastic', 'polymer'],
            'packaging': ['packaging', 'wrap'], 'steel': ['steel', 'metal'],
        }
        found_industries = [industry.capitalize() for industry, kws in industry_keywords.items() if any(kw in text_content for kw in kws)]
        industry = ", ".join(found_industries) if found_industries else 'General Business'

        # More robustly clean the title and filter out junk results
        clean_title = title.split('|')[0].split('-')[0].strip()
        if len(clean_title) > 5 and '...' not in clean_title:
             companies.append({
                'id': i, # Use index as a simple ID
                'name': clean_title,
                'description': snippet,
                'industry': industry,
                'link': link,
                'email': email_match.group(0) if email_match else 'Not Found',
                'phone': phone_match.group(0) if phone_match else 'Not Found',
            })
    
    return JsonResponse({'companies': companies[:10]})

def generate_email_api(request):
    """
    Generates a personalized B2B outreach email using the Gemini API.
    """
    try:
        data = json.loads(request.body)
        user_profile = request.session.get('user_profile', DEFAULT_PROFILE)
        selected_company = data.get('company', {})

        # Prepare details for the prompt
        company_name = selected_company.get('name', 'your company')
        industry = selected_company.get('industry', 'your industry')

        prompt = f"""
            Draft a professional and engaging B2B outreach email.

            My Company Profile:
            - Company Name: {user_profile.get('companyName')}
            - My Name: {user_profile.get('contactPerson')}
            - My Role: {user_profile.get('role')}
            - Our Products/Services: {user_profile.get('products')}
            - Our Key Differentiators: {user_profile.get('keyDifferentiators')}

            Recipient Company Profile:
            - Company Name: {company_name}
            - Their Industry: {industry}

            Instructions:
            1. Create a compelling and professional subject line.
            2. Write a concise and creative email.
            3. Personalize the email for the recipient's industry ({industry}).
            4. Propose a brief call to discuss how our offerings can benefit their business.
            5. The entire output must be a single block of text. Start with "Subject: " on the first line. Do not add any other pleasantries before or after the email content.
        """

        
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={settings.GEMINI_API_KEY}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        
        # Make the API call to Google Gemini
        response = requests.post(api_url, json=payload, timeout=20)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        
        result = response.json()
        email_text = result['candidates'][0]['content']['parts'][0]['text']
        
        return JsonResponse({'email': email_text})

    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return JsonResponse({'error': 'Failed to connect to the email generation service.'}, status=503)
    except Exception as e:
        logger.error(f"Email generation failed. Error: {e}")
        return JsonResponse({'error': 'Failed to generate email due to a server error.'}, status=500)