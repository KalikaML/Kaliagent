# procurement/urls.py
from django.urls import path
from . import views

app_name = 'procurement'

urlpatterns = [
    # Page view
    path('', views.procurement_dashboard_view, name='dashboard'),
    
    # API views for JavaScript
    path('api/add-request/', views.add_request_api, name='api_add_request'),
    path('api/get-request-details/<int:pk>/', views.get_request_details_api, name='api_get_request_details'),
    path('api/run-agent-simulation/<int:pk>/', views.run_agent_simulation_api, name='api_run_agent_simulation'),
    path('api/approve-rfqs/<int:pk>/', views.approve_rfqs_api, name='api_approve_rfqs'),
    path('api/check-quotes/<int:pk>/', views.check_quotes_api, name='api_check_quotes'),

    # NEW: Add the URL for bulk upload
    path('api/bulk-upload/', views.bulk_upload_api, name='api_bulk_upload'),
]