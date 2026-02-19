# command_center/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.urls import re_path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    
    
    # --- ADD THESE TWO LINES ---
    # This tells Django to look in marketing_outreach/urls.py for any URL starting with 'marketing/'
    path('marketing/', include('marketing_outreach.urls')),
    # This tells Django to look in procurement/urls.py for any URL starting with 'procurement/'
    path('procurement/', include('procurement.urls')),
    # This tells Django to look in linkedin_automation/urls.py for any URL starting with 'linkedin/'
    path('linkedin/', include('linkedin_automation.urls')),
]

# Media files serving for development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # Also serve media in non-DEBUG mode for local testing
    # Remove this in production and use proper media server (nginx, S3, etc.)
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]

