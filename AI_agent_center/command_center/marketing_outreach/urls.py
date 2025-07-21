# marketing_outreach/urls.py
from django.urls import path
from . import views

app_name = 'marketing_outreach'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('settings/', views.settings_view, name='settings'),

    # API views
    path('api/search-companies/', views.search_companies_api, name='api_search_companies'),
    path('api/generate-email/', views.generate_email_api, name='api_generate_email'),
]