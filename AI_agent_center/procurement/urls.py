from django.urls import path
from . import views

app_name = 'procurement'

urlpatterns = [
    # Page views
    path('', views.procurement_dashboard_view, name='dashboard'),
    path('analysis/', views.analysis_view, name='analysis'),
    
    # API views for creating requests
    path('api/add-request/', views.add_request_api, name='api_add_request'),
    path('api/bulk-upload/', views.bulk_upload_api, name='api_bulk_upload'),
    
    # Main request details and action endpoints
    path('api/get-request-details/<int:pk>/', views.get_request_details_api, name='api_get_request_details'),
    path('api/get-product-quotes/<int:product_id>/', views.get_product_quotes_api, name='api_get_product_quotes'),
    path('api/delete-request/<int:pk>/', views.delete_request_api, name='api_delete_request'),

    # Agent stage APIs
    path('api/find-suppliers/<int:pk>/', views.find_suppliers_api, name='api_find_suppliers'),
    # ✨ NEW: API to find more suppliers for an existing product request
    path('api/find-more-suppliers/<int:product_id>/', views.find_more_suppliers_api, name='api_find_more_suppliers'),
    path('api/send-rfqs/<int:pk>/', views.send_rfqs_api, name='api_send_rfqs'),
    path('api/check-and-parse-quotes/<int:pk>/', views.check_and_parse_quotes_api, name='api_check_and_parse_quotes'),
    path('api/check-all-rfqs/', views.check_all_rfqs_api, name='api_check_all_rfqs'),
    
    # Manual override and finalization
    path('api/manual-rfq/<int:pk>/', views.manual_rfq_sent_api, name='api_manual_rfq'),
    path('api/finalize-request/<int:pk>/', views.finalize_request_api, name='api_finalize_request'),
]