# # procurement/urls.py
# from django.urls import path
# from . import views_old

# app_name = 'procurement'

# urlpatterns = [
#     # Page view
#     path('', views_old.procurement_dashboard_view, name='dashboard'),
    
#     # API views for manual requests and bulk upload
#     path('api/add-request/', views_old.add_request_api, name='api_add_request'),
#     path('api/bulk-upload/', views_old.bulk_upload_api, name='api_bulk_upload'),
    
#     # Main request details endpoint
#     path('api/get-request-details/<int:pk>/', views_old.get_request_details_api, name='api_get_request_details'),

#     # --- REAL AGENT STAGE APIs ---
#     # Stage 1: Find suppliers and save them to the database
#     path('api/find-suppliers/<int:pk>/', views_old.find_suppliers_api, name='api_find_suppliers'),
#     # Stage 2: Send actual RFQ emails to the saved suppliers
#     path('api/send-rfqs/<int:pk>/', views_old.send_rfqs_api, name='api_send_rfqs'),
#     # Stage 3: Check email replies and parse them for quote data
#     path('api/check-and-parse-quotes/<int:pk>/', views_old.check_and_parse_quotes_api, name='api_check_and_parse_quotes'),
# ]


# procurement/urls.py
from django.urls import path
from . import views

app_name = 'procurement'

urlpatterns = [
    path('', views.procurement_dashboard_view, name='dashboard'),
    path('api/add-request/', views.add_request_api, name='api_add_request'),
    path('api/bulk-upload/', views.bulk_upload_api, name='api_bulk_upload'),
    path('api/get-request-details/<int:pk>/', views.get_request_details_api, name='api_get_request_details'),
    path('api/find-suppliers/<int:pk>/', views.find_suppliers_api, name='api_find_suppliers'),
    path('api/send-rfqs/<int:pk>/', views.send_rfqs_api, name='api_send_rfqs'),
    path('api/check-and-parse-quotes/<int:pk>/', views.check_and_parse_quotes_api, name='api_check_and_parse_quotes'),
    
    # NEW: URL for finalizing a request
    path('api/finalize-request/<int:pk>/', views.finalize_request_api, name='api_finalize_request'),
]