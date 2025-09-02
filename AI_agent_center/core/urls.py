# core/urls.py
from django.urls import path, reverse_lazy
from . import views
# Import Django's built-in auth views for password reset
from django.contrib.auth import views as auth_views

app_name = 'core'

urlpatterns = [
    # Your custom views
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    
    # Agent selector (homepage after login)
    path('', views.agent_selector_view, name='agent_selector'),

    # Password Reset URLs (Updated to handle namespaces)
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='core/password_reset.html',
             email_template_name='core/password_reset_email.html', # Custom email template
             subject_template_name='core/password_reset_subject.txt', # Custom subject template
             success_url=reverse_lazy('core:password_reset_done') # Use reverse_lazy for namespaced URL
         ), 
         name='password_reset'),
         
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='core/password_reset_done.html'
         ), 
         name='password_reset_done'),
         
    path('password-reset-confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='core/password_reset_confirm.html',
             success_url=reverse_lazy('core:password_reset_complete') # Use reverse_lazy for namespaced URL
         ), 
         name='password_reset_confirm'),
         
    path('password-reset-complete/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='core/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
]