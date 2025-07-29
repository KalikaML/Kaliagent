import csv
import io
import json
import random
from django.shortcuts import render, redirect
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import EmailTemplate

def pitch_creator_view(request):
    """
    Handles the main view for creating and sending pitches.
    Also handles loading the list of saved templates.
    """
    if request.method == 'POST':
        # This view will now primarily handle the email sending part.
        # Saving templates will be handled by a separate AJAX view.
        subject = request.POST.get('subject')
        html_content = request.POST.get('html_content')
        recipient_list = []

        # Check for a CSV file upload
        if 'csv_file' in request.FILES:
            csv_file = request.FILES['csv_file']
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'Error: This is not a CSV file.')
            else:
                try:
                    decoded_file = csv_file.read().decode('utf-8')
                    io_string = io.StringIO(decoded_file)
                    # Skip header row
                    next(csv.reader(io_string))
                    for row in csv.reader(io_string):
                        if row and row[0]:
                           recipient_list.append(row[0])
                    messages.success(request, f'Success: Loaded {len(recipient_list)} emails from CSV.')
                except Exception as e:
                    messages.error(request, f"Error: Failed to process CSV file: {e}")

        # Check for a single email address
        elif 'recipient' in request.POST and request.POST.get('recipient'):
            recipient_list.append(request.POST.get('recipient'))

        if not recipient_list:
            messages.error(request, 'Error: Please provide at least one recipient email or a CSV file.')
        elif not subject:
            messages.error(request, 'Error: Please provide a subject.')
        elif not html_content:
             messages.error(request, 'Error: The HTML content cannot be empty.')
        else:
            try:
                send_mail(
                    subject,
                    '',
                    settings.EMAIL_HOST_USER,
                    recipient_list,
                    fail_silently=False,
                    html_message=html_content,
                )
                messages.success(request, f'Success: Sent pitch to {len(recipient_list)} recipient(s)!')
            except Exception as e:
                messages.error(request, f'Error: An error occurred while sending email: {e}')
        
        return redirect('ai_agent_pitch:pitch_creator')

    # For GET request
    templates = EmailTemplate.objects.all().order_by('name')
    context = {
        'templates': templates
    }
    return render(request, 'ai_agent_pitch/pitch_creator.html', context)


@require_POST
@csrf_exempt # Using exempt for simplicity in this tool, for production consider full CSRF handling
def save_template_view(request):
    """
    Handles saving a new email template via AJAX.
    """
    try:
        data = json.loads(request.body)
        template_name = data.get('name')
        html_content = data.get('html_content')

        if not template_name or not html_content:
            return JsonResponse({'status': 'error', 'message': 'Template name and content cannot be empty.'}, status=400)

        # Create or update template
        template, created = EmailTemplate.objects.update_or_create(
            name=template_name,
            defaults={'html_content': html_content}
        )
        
        message = 'Template saved successfully!' if created else 'Template updated successfully!'
        return JsonResponse({'status': 'success', 'message': message, 'template_id': template.id, 'template_name': template.name})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def load_template_view(request, template_id):
    """
    Handles loading a specific email template's content via AJAX.
    """
    try:
        template = EmailTemplate.objects.get(id=template_id)
        return JsonResponse({'status': 'success', 'html_content': template.html_content})
    except EmailTemplate.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Template not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_POST
@csrf_exempt
def generate_subject_view(request):
    """
    A mock AI subject line generator.
    In a real app, this would call a generative AI model.
    """
    # For now, we'll just return some creative, pre-defined suggestions.
    suggestions = [
        "A New AI-Powered Opportunity for You",
        "Exclusive Invitation: Discover Our New AI Tools",
        "Transform Your Business with Kalika AI",
        "Unlock Growth: A Special Offer for Kalika Suppliers",
        "Your Competitve Edge: Introducing Our Latest AI",
    ]
    random.shuffle(suggestions)
    return JsonResponse({'status': 'success', 'subjects': suggestions[:3]})
