from django.shortcuts import render

# Create your views here.
# marketing_outreach/views.py
import json
import requests as http_requests
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from serpapi import GoogleSearch

DEFAULT_PROFILE = {
    'companyName': 'Your Company Name',
    'contactPerson': 'Your Name',
    'role': 'Your Role',
    'products': 'High-quality stretch films, custom packaging solutions',
    'keyDifferentiators': 'Eco-friendly materials, competitive pricing, just-in-time delivery'
}

def dashboard_view(request):
    # Use session to store user profile, get default if not set
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
    search_term = request.GET.get('q', 'plastic molding companies in Texas')
    params = {
        "engine": "google",
        "q": search_term,
        "api_key": settings.SERPAPI_API_KEY
    }
    search = GoogleSearch(params)
    results = search.get_dict()

    companies = []
    if 'organic_results' in results:
        for i, result in enumerate(results.get('organic_results', [])[:7]): # Get top 7
            companies.append({
                'id': i + 1,
                'name': result.get('title'),
                'description': result.get('snippet', 'No description available.'),
                'industry': 'Varies', # SerpApi doesn't easily provide this
                'location': result.get('address', 'Location not available'),
                'relevance': 95 - i*2, # Mock relevance
            })
    return JsonResponse({'companies': companies})


@csrf_exempt
def generate_email_api(request):
    data = json.loads(request.body)
    user_profile = request.session.get('user_profile', DEFAULT_PROFILE)
    selected_company = data.get('company')
    contact_info = data.get('contact') # This is still mocked in the JS

    prompt = f"""
        Draft a professional and engaging B2B outreach email.
        My Company Details:
        - Company Name: {user_profile['companyName']}, My Name: {user_profile['contactPerson']}, My Role: {user_profile['role']}
        - Products/Services: {user_profile['products']}, Key Differentiators: {user_profile['keyDifferentiators']}
        Recipient Details:
        - Name: {contact_info['name']}, Company: {selected_company['name']}, Industry: {selected_company['industry']}
        Instructions:
        Write a concise, creative, and professional email. Personalize it based on the recipient's likely industry. Propose a brief call. Create a compelling subject line.
        The entire output should be a single block of text, starting with "Subject: ...".
    """

    try:
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={settings.GEMINI_API_KEY}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        response = http_requests.post(api_url, json=payload)
        response.raise_for_status()
        result = response.json()
        email_text = result['candidates'][0]['content']['parts'][0]['text']
        return JsonResponse({'email': email_text})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)