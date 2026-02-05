from django.db import models
from django.utils import timezone


class RedditPost(models.Model):
    """Store Reddit posts for reference"""
    reddit_id = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=500)
    content = models.TextField()
    subreddit = models.CharField(max_length=100)
    score = models.IntegerField(default=0)
    url = models.URLField(max_length=500)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-score', '-created_at']
    
    def __str__(self):
        return f"{self.title[:50]} ({self.subreddit})"


class LinkedInPost(models.Model):
    """Track LinkedIn posts with images"""
    title = models.CharField(max_length=500, blank=True)
    content = models.TextField(default='', blank=True)
    image_url = models.URLField(blank=True, null=True)
    image_thumbnail = models.URLField(blank=True, null=True)
    post_id = models.CharField(max_length=200, blank=True, null=True)
    asset_id = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(max_length=50, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title[:50]} - {self.status}"


class PostHistory(models.Model):
    """Track all posting attempts"""
    IMAGE_SOURCE_CHOICES = [
        ('pexels', 'Pexels'),
        ('giphy', 'Giphy'),
        ('serpapi', 'SerpApi'),
        ('upload', 'Local Upload'),
        ('ai_generated', 'AI Generated'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('processing', 'Processing'),
        ('posted', 'Posted'),
        ('failed', 'Failed'),
    ]
    
    # Content fields
    original_content = models.TextField(help_text="Original Reddit content", blank=True)
    rewritten_content = models.TextField(help_text="AI-rewritten content")
    custom_instruction = models.TextField(blank=True, help_text="Custom style/tone instructions for Gemini")
    
    # Image fields
    image_source = models.CharField(max_length=20, choices=IMAGE_SOURCE_CHOICES)
    image_url = models.URLField(max_length=500, blank=True, null=True)
    image_file = models.ImageField(upload_to='uploads/', blank=True, null=True)
    image_query = models.CharField(max_length=200, blank=True, help_text="Search query for image APIs")
    
    # LinkedIn fields
    linkedin_urn = models.CharField(max_length=200, blank=True, null=True)
    linkedin_post_id = models.CharField(max_length=200, blank=True, null=True)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    error_message = models.TextField(blank=True)
    success = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    posted_at = models.DateTimeField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Related Reddit post
    reddit_post = models.ForeignKey(
        RedditPost, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='linkedin_posts'
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Post Histories"
    
    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"{status} {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class SavedProfile(models.Model):
    """Track saved LinkedIn profiles and companies for lead management"""
    PROFILE_TYPE_CHOICES = [
        ('person', 'Person'),
        ('company', 'Company'),
    ]
    
    PRIORITY_CHOICES = [
        ('high', 'High Priority'),
        ('medium', 'Medium Priority'),
        ('low', 'Low Priority'),
    ]
    
    # Basic Info
    profile_type = models.CharField(max_length=10, choices=PROFILE_TYPE_CHOICES)
    name = models.CharField(max_length=500)
    headline = models.TextField(blank=True)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=200, blank=True)
    industry = models.CharField(max_length=200, blank=True)
    
    # LinkedIn Details
    linkedin_url = models.URLField(max_length=500, blank=True)
    profile_picture = models.URLField(max_length=500, blank=True)
    
    # Company-specific fields
    website = models.URLField(max_length=500, blank=True, null=True)
    follower_count = models.CharField(max_length=50, blank=True)
    employee_count = models.CharField(max_length=50, blank=True)
    
    # Lead Management
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    notes = models.TextField(blank=True)
    ai_outreach_message = models.TextField(blank=True, help_text="AI-generated outreach message")
    
    # Status tracking
    contacted = models.BooleanField(default=False)
    contacted_date = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    saved_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-saved_at']
        unique_together = ['profile_type', 'name', 'linkedin_url']
    
    def __str__(self):
        return f"{self.profile_type.title()}: {self.name}"
    
    def get_tags_list(self):
        """Return tags as a list"""
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
