# command_center/urls.py
from django.contrib import admin
from django.urls import path, include
from django.urls import path


app_name = 'ai_agent_pitch'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('marketing/', include('marketing_outreach.urls')),
    path('procurement/', include('procurement.urls')),
    path('pitch/', include('ai_agent_pitch.urls')),
    path('shorts/', include('shorts_app.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)