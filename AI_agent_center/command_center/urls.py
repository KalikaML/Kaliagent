# command_center/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings  # <-- ADD THIS LINE
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('pitch/', include('ai_agent_pitch.urls')),
    path('shorts/', include('shorts_app.urls')),
]

# This line below is what was causing the error
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)