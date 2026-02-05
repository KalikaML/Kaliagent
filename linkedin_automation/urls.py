# linkedin_automation/urls.py
from django.urls import path
from . import views
from . import pdf_views

app_name = 'linkedin_automation'

urlpatterns = [
    # Main Dashboard
    path('', views.dashboard_view, name='dashboard'),
    
    # Reddit Content Creation Workflow
    path('search-reddit/', views.search_reddit, name='search_reddit'),
    path('select-post/', views.select_reddit_post, name='select_post'),
    path('rewrite/', views.rewrite_with_gemini, name='rewrite'),
    
    # Image Selection & Upload
    path('search-images/', views.search_images, name='search_images'),
    path('generate-image/', views.generate_image_ai, name='generate_image_ai'),
    path('select-image/', views.select_image, name='select_image'),
    path('upload-image/', views.upload_image, name='upload_image'),
    
    # LinkedIn Posting
    path('post-linkedin/', views.post_linkedin, name='post_linkedin'),
    path('clear/', views.clear_state, name='clear_state'),
    
    # Post History
    path('history/', views.history_view, name='history'),
    path('history/delete/<int:item_id>/', views.delete_history_item, name='delete_history'),
    path('history/clear-all/', views.clear_all_history, name='clear_all_history'),
    
    # LinkedIn Finder (Companies & People)
    path('finder/', views.finder_view, name='finder'),
    path('finder/search-companies/', views.search_companies, name='search_companies'),
    path('finder/search-people/', views.search_people, name='search_people'),
    path('finder/save-profile/', views.save_profile, name='save_profile'),
    
    # Saved Profiles Management
    path('saved-profiles/', views.saved_profiles_view, name='saved_profiles'),
    path('saved-profiles/generate-outreach/<int:profile_id>/', views.generate_outreach_message, name='generate_outreach'),
    path('saved-profiles/update/<int:profile_id>/', views.update_profile_notes, name='update_profile_notes'),
    path('saved-profiles/export/', views.export_profiles_csv, name='export_profiles_csv'),
    path('saved-profiles/delete/<int:profile_id>/', views.delete_saved_profile, name='delete_saved_profile'),
    
    # PDF to Post Conversion
    path('pdf-to-post/', pdf_views.pdf_to_post_view, name='pdf_to_post'),
    path('pdf-to-post/upload/', pdf_views.upload_pdf, name='upload_pdf'),
    path('pdf-to-post/generate/', pdf_views.generate_post_from_pdf, name='generate_post_from_pdf'),
    
    # Combined Sources (PDF + Reddit)
    path('combine-sources/', pdf_views.combine_sources_view, name='combine_sources'),
    path('combine-sources/upload-pdf/', pdf_views.upload_pdf_combine, name='upload_pdf_combine'),
    path('combine-sources/search-reddit/', pdf_views.search_reddit_combine, name='search_reddit_combine'),
    path('combine-sources/generate/', pdf_views.generate_combined_post, name='generate_combined_post'),
]
