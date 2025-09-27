# core/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from .forms import UserRegisterForm
from django.contrib import messages

# Helper function to create an Admin User
def create_admin_user():
    """Creates the 'kalisoft' admin user if it doesn't exist."""
    if not User.objects.filter(username='kalisoft').exists():
        User.objects.create_superuser('kalisoft', 'kalisoft@example.com', 'kalisoft309')
        print("Admin user 'kalisoft' created successfully.")

# Register View
def register_view(request):
    if request.user.is_authenticated:
        return redirect('core:agent_selector')
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Your account, {username}, has been created! You can now log in.')
            return redirect('core:login')
    else:
        form = UserRegisterForm()
    return render(request, 'core/register.html', {'form': form})

# Login View
def login_view(request):
    # On app start, check for admin user and create if necessary
    create_admin_user()
    
    if request.user.is_authenticated:
        return redirect('core:agent_selector')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('core:agent_selector')
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Invalid username or password.')
    form = AuthenticationForm()
    return render(request, 'core/login.html', {'form': form})

# Logout View
def logout_view(request):
    logout(request)
    return redirect('core:login')

# Agent Selector View (Login is now required)
@login_required
def agent_selector_view(request):
    return render(request, 'core/agent_selector.html')

# Admin Dashboard View
@user_passes_test(lambda u: u.is_superuser)
def admin_dashboard_view(request):
    users = User.objects.all().order_by('-date_joined')
    total_users = users.count()
    context = {
        'users': users,
        'total_users': total_users
    }
    return render(request, 'core/admin_dashboard.html', context)