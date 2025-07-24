# marketing_outreach/views.py
import json
import re
import logging
import requests # <--- **THE FIX**: This line was missing
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.conf import settings
from serpapi import GoogleSearch

logger = logging.getLogger(__name__)

DEFAULT_PROFILE = {
    'companyName': 'Your Company Name',
    'contactPerson': 'Your Name',
    'role': 'Your Role',
    'products': 'High-quality stretch films, custom packaging solutions',
    'keyDifferentiators': 'Eco-friendly materials, competitive pricing, just-in-time delivery'
}

def dashboard_view(request):
    user_profile = request.session.get('user_profile', DEFAULT_PROFILE)
    return render(request, 'marketing_outreach/dashboard.html', {'user_profile': user_profile})

def settings_view(request):
    if request.method == 'POST':
        profile_data = {
            'companyName': request.POST.get('companyName'),
            'contactPerson': request.POST.get('contactPerson'),
            'role': request.POST.get('role'),
            'products': request.POST.get('products'),
            'keyDifferentiators': request.POST.get('keyDifferentiators'),
        }
        request.session['user_profile'] = profile_data
        return redirect('marketing_outreach:dashboard')
    user_profile = request.session.get('user_profile', DEFAULT_PROFILE)
    return render(request, 'marketing_outreach/settings.html', {'user_profile': user_profile})

# --- API Views ---

def search_companies_api(request):
    search_term = request.GET.get('q')
    if not search_term:
        return JsonResponse({'companies': []})
    search_query = f'"{search_term}" company contact site:indiamart.com OR site:tradeindia.com OR site:zaubacorp.com'
    params = {"engine": "google", "q": search_query, "api_key": settings.SERPAPI_API_KEY, "num": 20}
    search = GoogleSearch(params)
    results = search.get_dict().get('organic_results', [])
    companies = []
    email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_regex = r'(\+91[\s-]?)?[789]\d{9}|\b\d{4}[-\s]?\d{4}\b'
    for i, result in enumerate(results):
        snippet = result.get('snippet', '')
        title = result.get('title', '')
        text_content = (title + " " + snippet).lower()
        email_match = re.search(email_regex, text_content)
        phone_match = re.search(phone_regex, text_content)
        industry_keywords = {
            'manufacturing': ['manufacturing', 'manufacturer'], 'plastic': ['plastic', 'polymer'],
            'packaging': ['packaging', 'wrap'], 'steel': ['steel', 'metal'],
        }
        found_industries = [industry.capitalize() for industry, kws in industry_keywords.items() if any(kw in text_content for kw in kws)]
        industry = ", ".join(found_industries) if found_industries else 'General Business'
        if '...' not in title and len(title) > 10:
             companies.append({
                'id': i + 1, 'name': title, 'description': snippet, 'industry': industry,
                'link': result.get('link'), 'email': email_match.group(0) if email_match else 'Not Found',
                'phone': phone_match.group(0) if phone_match else 'Not Found',
            })
    return JsonResponse({'companies': companies[:10]})

def generate_email_api(request):
    try:
        data = json.loads(request.body)
        user_profile = request.session.get('user_profile', DEFAULT_PROFILE)
        selected_company = data.get('company', {})
        company_name = selected_company.get('name', 'your company')
        contact_email = selected_company.get('email', '[contact email]')
        industry = selected_company.get('industry', 'your industry')

        prompt = f"""
            Draft a professional and engaging B2B outreach email.
            My Company Details:
            - Company Name: {user_profile.get('companyName')}
            - My Name: {user_profile.get('contactPerson')}
            - My Role: {user_profile.get('role')}
            - Products/Services: {user_profile.get('products')}
            - Key Differentiators: {user_profile.get('keyDifferentiators')}
            Recipient Details:
            - Company: {company_name}
            - Industry: {industry}
            Instructions:
            Write a concise, creative, and professional email to "{contact_email}". Personalize it for the recipient's industry ({industry}). Propose a brief call to discuss how our products can help them. Create a compelling subject line. The entire output must be a single block of text, starting with "Subject: ...".
        """

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={settings.GEMINI_API_KEY}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        
        # **THE FIX**: Changed 'http_requests' to the correctly imported 'requests'
        response = requests.post(api_url, json=payload, timeout=20)
        response.raise_for_status()
        
        result = response.json()
        email_text = result['candidates'][0]['content']['parts'][0]['text']
        return JsonResponse({'email': email_text})
    except Exception as e:
        logger.error(f"Email generation failed. Payload: {data}. Error: {e}")
        return JsonResponse({'error': 'Failed to generate email due to a server error.'}, status=500)