from django.db import models
from django.utils import timezone

class EmailTemplate(models.Model):
    """
    A model to store reusable HTML email templates.
    """
    name = models.CharField(max_length=100, unique=True, help_text="A unique name for the template.")
    html_content = models.TextField(help_text="The full HTML content of the email template.")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Campaign(models.Model):
    """
    Represents a single bulk email campaign.
    """
    subject = models.CharField(max_length=255)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Campaign: {self.subject} ({self.sent_at.strftime('%Y-%m-%d %H:%M')})"

class Recipient(models.Model):
    """
    Represents a single recipient within a campaign, tracking their status.
    """
    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('opened', 'Opened'),
        ('failed', 'Failed'),
    ]
    campaign = models.ForeignKey(Campaign, related_name='recipients', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, blank=True, help_text="The recipient's name.")
    email = models.EmailField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='sent')
    opened_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} <{self.email}> - {self.get_status_display()}"
