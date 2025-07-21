# procurement/models.py
from django.db import models

class ProcurementRequest(models.Model):
    STATUS_CHOICES = [
        ('new-request', 'New Request'),
        ('agent-working', 'Agent Working'),
        ('awaiting-approval', 'Awaiting Approval'),
        ('rfqs-sent', 'RFQs Sent'),
        ('quotes-received', 'Quotes Received'),
        ('finalized', 'Finalized'),
    ]

    SOURCE_CHOICES = [
        ('Manual', 'Manual'),
        ('Bulk Upload', 'Bulk Upload'),
    ]

    title = models.CharField(max_length=255)
    quantity = models.CharField(max_length=100)
    specs = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='new-request')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='Manual')
    created_at = models.DateTimeField(auto_now_add=True)

    # Fields for quote tracking
    quotes_in = models.IntegerField(default=0)
    total_quotes_sent = models.IntegerField(default=0)

    def __str__(self):
        return self.title