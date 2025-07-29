from django.db import models

# Create your models here.
class EmailTemplate(models.Model):
    """
    A model to store reusable HTML email templates.
    """
    name = models.CharField(max_length=100, unique=True, help_text="A unique name for the template.")
    html_content = models.TextField(help_text="The full HTML content of the email template.")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name