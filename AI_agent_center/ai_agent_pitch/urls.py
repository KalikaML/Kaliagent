from django.urls import path
from . import views

app_name = 'ai_agent_pitch'

urlpatterns = [
    # Main page
    path('', views.pitch_creator_view, name='pitch_creator'),
    
    # AJAX endpoints
    path('save-template/', views.save_template_view, name='save_template'),
    path('load-template/<int:template_id>/', views.load_template_view, name='load_template'),
    path('generate-subject/', views.generate_subject_view, name='generate_subject'),
]
