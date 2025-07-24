# core/views.py
from django.shortcuts import render

def agent_selector_view(request):
    return render(request, 'core/agent_selector.html')