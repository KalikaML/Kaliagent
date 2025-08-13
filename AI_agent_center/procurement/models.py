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
    SOURCE_CHOICES = [('Manual', 'Manual'), ('Bulk Upload', 'Bulk Upload')]

    title = models.CharField(max_length=255)
    quantity = models.CharField(max_length=100)
    specs = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='new-request')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='Manual')
    created_at = models.DateTimeField(auto_now_add=True)
    quotes_in = models.IntegerField(default=0)
    total_quotes_sent = models.IntegerField(default=0)
    
    selected_quote = models.ForeignKey('Quote', related_name='chosen_for_request', on_delete=models.SET_NULL, null=True, blank=True)
    estimated_savings = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return self.title

class Supplier(models.Model):
    procurement_request = models.ForeignKey(ProcurementRequest, related_name='suppliers', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    source_link = models.URLField(max_length=500, blank=True, null=True)
    indiamart_rfq_sent = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class Quote(models.Model):
    procurement_request = models.ForeignKey(ProcurementRequest, related_name='quotes', on_delete=models.CASCADE)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    lead_time_days = models.IntegerField(blank=True, null=True)
    payment_terms = models.CharField(max_length=100, blank=True, null=True)
    # ✨ NEW: Field to store extracted discount information
    discount = models.CharField(max_length=100, blank=True, null=True)
    parsed_from_email_uid = models.CharField(max_length=100, unique=True)
    full_email_body = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Quote from {self.supplier.name} for {self.price}"
