# command_center/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('marketing/', include('marketing_outreach.urls')),
    path('procurement/', include('procurement.urls')),
]