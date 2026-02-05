# linkedin_automation/admin.py
from django.contrib import admin
from .models import RedditPost, LinkedInPost, PostHistory, SavedProfile


@admin.register(RedditPost)
class RedditPostAdmin(admin.ModelAdmin):
    """Admin configuration for RedditPost model"""
    list_display = ['title_short', 'subreddit', 'score', 'word_count', 'created_at']
    search_fields = ['title', 'content', 'subreddit']
    list_filter = ['subreddit', 'created_at']
    readonly_fields = ['reddit_id', 'created_at']
    ordering = ['-score', '-created_at']
    
    def title_short(self, obj):
        return obj.title[:50] + "..." if len(obj.title) > 50 else obj.title
    title_short.short_description = 'Title'
    
    def word_count(self, obj):
        return len(obj.content.split())
    word_count.short_description = 'Words'


@admin.register(LinkedInPost)
class LinkedInPostAdmin(admin.ModelAdmin):
    """Admin configuration for LinkedInPost model"""
    list_display = ['title_short', 'status', 'created_at', 'posted_at']
    search_fields = ['title', 'content']
    list_filter = ['status', 'created_at']
    readonly_fields = ['created_at', 'posted_at']
    ordering = ['-created_at']
    
    def title_short(self, obj):
        return obj.title[:50] + "..." if len(obj.title) > 50 else obj.title
    title_short.short_description = 'Title'


@admin.register(PostHistory)
class PostHistoryAdmin(admin.ModelAdmin):
    """Admin configuration for PostHistory model"""
    list_display = ['id', 'status', 'image_source', 'created_at', 'success']
    search_fields = ['rewritten_content', 'original_content']
    list_filter = ['status', 'image_source', 'success', 'created_at']
    readonly_fields = ['created_at', 'posted_at', 'timestamp']
    ordering = ['-created_at']


@admin.register(SavedProfile)
class SavedProfileAdmin(admin.ModelAdmin):
    """Admin configuration for SavedProfile model"""
    list_display = ['name', 'profile_type', 'priority', 'contacted', 'location', 'saved_at']
    search_fields = ['name', 'headline', 'description', 'tags', 'notes']
    list_filter = ['profile_type', 'priority', 'contacted', 'industry', 'saved_at']
    readonly_fields = ['saved_at', 'updated_at']
    ordering = ['-saved_at']
    
    actions = ['mark_as_contacted', 'mark_as_high_priority']
    
    def mark_as_contacted(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(contacted=True, contacted_date=timezone.now())
        self.message_user(request, f'{updated} profile(s) marked as contacted.')
    mark_as_contacted.short_description = 'Mark selected as contacted'
    
    def mark_as_high_priority(self, request, queryset):
        updated = queryset.update(priority='high')
        self.message_user(request, f'{updated} profile(s) marked as high priority.')
    mark_as_high_priority.short_description = 'Mark as high priority'
