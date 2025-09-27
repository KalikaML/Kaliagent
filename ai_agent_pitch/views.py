import csv
import io
import json
import random
import logging
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.core.paginator import Paginator
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, From, To, Subject, HtmlContent, CustomArg
from .models import EmailTemplate, Campaign, Recipient

logger = logging.getLogger(__name__)

def pitch_creator_view(request):
    if request.method == 'POST':
        subject = request.POST.get('subject')
        html_content = request.POST.get('html_content')
        recipient_list = []
        recipient_names = {}

        if 'csv_file' in request.FILES:
            csv_file = request.FILES('csv_file')
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'Error: This is not a CSV file.')
            else:
                try:
                    decoded_file = csv_file.read().decode('utf-8')
                    io_string = io.StringIO(decoded_file)
                    reader = csv.reader(io_string)
                    next(reader)  # Skip header row
                    for row in reader:
                        if row and row[0]:
                            recipient_list.append(row[0])
                            recipient_names[row[0]] = row[1] if len(row) > 1 else 'Partner'
                    messages.success(request, f'Success: Loaded {len(recipient_list)} emails from CSV.')
                except Exception as e:
                    messages.error(request, f"Error: Failed to process CSV file: {e}")
                    logger.error(f"CSV processing error: {e}")

        elif 'recipient' in request.POST and request.POST.get('recipient'):
            recipient_list.append(request.POST.get('recipient'))
            recipient_names[request.POST.get('recipient')] = 'Partner'

        if not recipient_list:
            messages.error(request, 'Error: Please provide at least one recipient email or a CSV file.')
        elif not subject:
            messages.error(request, 'Error: Please provide a subject.')
        elif not html_content:
            messages.error(request, 'Error: The HTML content cannot be empty.')
        else:
            try:
                campaign = Campaign.objects.create(subject=subject)
                sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
                
                for recipient in recipient_list:
                    personalized_content = html_content.replace('[Recipient]', recipient_names.get(recipient, 'Partner'))
                    personalized_content += (
                        f'<p style="font-size: 12px; color: #666;">'
                        f'Sent by Kalika AI, contact@kalisoftai.in<br>'
                        f'To unsubscribe, reply with "Unsubscribe".</p>'
                        f'<img src="{settings.SITE_URL}/ai_agent_pitch/mark-opened/{campaign.id}/{recipient}/" width="1" height="1" style="display:none;">'
                    )
                    mail = Mail(
                        from_email=From(settings.DEFAULT_FROM_EMAIL, "Kalika AI"),
                        to_emails=To(recipient),
                        subject=Subject(subject),
                        html_content=HtmlContent(personalized_content)
                    )
                    mail.add_custom_arg(CustomArg('campaign_id', str(campaign.id)))

                    recipient_obj = Recipient.objects.create(
                        campaign=campaign,
                        name=recipient_names.get(recipient, 'Partner'),
                        email=recipient,
                        status='sent'
                    )

                    logger.info(f"Sending email to {recipient} with subject: {subject}")
                    response = sg.send(mail)
                    
                    if response.status_code not in (200, 202):
                        recipient_obj.status = 'failed'
                        recipient_obj.save()
                        error_message = f'Error: Failed to send email to {recipient}. Status code: {response.status_code}'
                        messages.error(request, error_message)
                        logger.error(error_message)
                
                messages.success(request, f'Success: Sent pitch to {len(recipient_list)} recipient(s)!')
                logger.info(f"Emails sent successfully for campaign {campaign.id}")
            except Exception as e:
                error_message = f'Error: An error occurred while sending email: {e}'
                messages.error(request, error_message)
                logger.error(f"SendGrid API exception: {e}", exc_info=True)
        
        return redirect('ai_agent_pitch:pitch_creator')

    templates = EmailTemplate.objects.all().order_by('name')
    context = {
        'templates': templates
    }
    return render(request, 'ai_agent_pitch/pitch_creator.html', context)

@require_POST
@csrf_exempt
def save_template_view(request):
    try:
        data = json.loads(request.body)
        template_name = data.get('name')
        html_content = data.get('html_content')

        if not template_name or not html_content:
            return JsonResponse({'status': 'error', 'message': 'Template name and content cannot be empty.'}, status=400)

        template, created = EmailTemplate.objects.update_or_create(
            name=template_name,
            defaults={'html_content': html_content}
        )
        
        message = 'Template saved successfully!' if created else 'Template updated successfully!'
        return JsonResponse({'status': 'success', 'message': message, 'template_id': template.id, 'template_name': template.name})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def load_template_view(request, template_id):
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
    suggestions = [
        "Discover Kalika AI’s Tools for Your Business",
        "Streamline Operations with Kalika AI",
        "Partner with Kalika AI for Growth",
        "Explore AI Solutions with Kalika",
        "Optimize Your Business with Kalika AI",
    ]
    random.shuffle(suggestions)
    return JsonResponse({'status': 'success', 'subjects': suggestions[:3]})

@require_POST
@csrf_exempt
def enhance_with_ai_view(request):
    try:
        data = json.loads(request.body)
        html_content = data.get('html_content')
        prompt = data.get('prompt')

        if not html_content or not prompt:
            return JsonResponse({'status': 'error', 'message': 'HTML content and prompt are required.'}, status=400)

        enhanced_html = html_content
        prompt_lower = prompt.lower()

        color_map = {
            'blue': '#3b82f6',
            'purple': '#8b5cf6',
            'green': '#22c55e',
            'red': '#ef4444',
            'orange': '#f97316',
            'teal': '#14b8a6',
            'professional': '#2d3748',
            'vibrant': '#ec4899',
        }

        color_to_apply = None
        for keyword, hex_code in color_map.items():
            if keyword in prompt_lower:
                color_to_apply = hex_code
                break
        
        if color_to_apply:
            colors_to_replace = ['#8b5cf6', '#4facfe', '#4299e1', '#3b82f6', '#ec4899', '#ef4444', '#f59e0b', '#18bb9c'] 
            for color in colors_to_replace:
                enhanced_html = enhanced_html.replace(color, color_to_apply)
        else:
            enhanced_html = enhanced_html.replace(
                'Collaborate with Kalika AI', 
                'Partner with Kalika AI for Success'
            )

        return JsonResponse({'status': 'success', 'html_content': enhanced_html})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def dashboard_view(request):
    campaigns = Campaign.objects.all().order_by('-sent_at')
    gmail_recipients = Recipient.objects.filter(email__endswith='@gmail.com').order_by('-campaign__sent_at')
    
    # Paginate campaigns
    paginator = Paginator(campaigns, 10)  # 10 campaigns per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    campaign_data = []
    for campaign in page_obj:
        recipients = campaign.recipients.all()
        total_sent = recipients.count()
        total_opened = recipients.filter(status='opened').count()
        total_clicked = recipients.filter(status='opened', opened_at__isnull=False).count()
        total_failed = recipients.filter(status='failed').count()
        campaign_data.append({
            'subject': campaign.subject,
            'sent_at': campaign.sent_at,
            'total_sent': total_sent,
            'total_opened': total_opened,
            'total_clicked': total_clicked,
            'total_failed': total_failed,
            'open_rate': (total_opened / total_sent * 100) if total_sent > 0 else 0,
        })
    
    context = {
        'page_obj': page_obj,
        'gmail_recipients': gmail_recipients,
    }
    return render(request, 'ai_agent_pitch/dashboard.html', context)

@require_POST
def get_campaigns_view(request):
    try:
        campaigns = Campaign.objects.all().order_by('-sent_at')
        campaign_data = []
        for campaign in campaigns:
            recipients = campaign.recipients.all()
            total_sent = recipients.count()
            total_opened = recipients.filter(status='opened').count()
            total_clicked = recipients.filter(status='opened', opened_at__isnull=False).count()
            total_failed = recipients.filter(status='failed').count()
            campaign_data.append({
                'id': campaign.id,
                'subject': campaign.subject,
                'sent_at': campaign.sent_at.strftime('%Y-%m-%d %H:%M'),
                'total_sent': total_sent,
                'total_opened': total_opened,
                'total_clicked': total_clicked,
                'total_failed': total_failed,
                'open_rate': (total_opened / total_sent * 100) if total_sent > 0 else 0,
            })
        return JsonResponse({'status': 'success', 'campaigns': campaign_data})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def mark_as_opened_view(request, campaign_id, recipient_email):
    try:
        recipient = Recipient.objects.get(campaign_id=campaign_id, email=recipient_email)
        if recipient.status != 'opened':
            recipient.status = 'opened'
            recipient.opened_at = timezone.now()
            recipient.save()
        return HttpResponse(status=200)
    except Recipient.DoesNotExist:
        return HttpResponse(status=404)
    except Exception as e:
        logger.error(f"Error marking email as opened: {e}")
        return HttpResponse(status=500)

@require_POST
@csrf_exempt
def webhook_view(request):
    try:
        events = json.loads(request.body)
        for event in events:
            event_type = event.get('event')
            email = event.get('email')
            campaign_id = event.get('campaign_id')
            if not campaign_id or not email:
                continue

            try:
                recipient = Recipient.objects.get(campaign_id=campaign_id, email=email)
                if event_type == 'delivered':
                    recipient.status = 'sent'
                    recipient.save()
                elif event_type == 'open':
                    recipient.status = 'opened'
                    recipient.opened_at = timezone.now()
                    recipient.save()
                elif event_type == 'click':
                    recipient.status = 'opened'
                    recipient.opened_at = timezone.now()
                    recipient.save()
                elif event_type in ('bounce', 'dropped', 'spamreport'):
                    recipient.status = 'failed'
                    recipient.save()
            except Recipient.DoesNotExist:
                logger.warning(f"Recipient not found for email: {email}, campaign: {campaign_id}")
        
        return HttpResponse(status=200)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return HttpResponse(status=500)