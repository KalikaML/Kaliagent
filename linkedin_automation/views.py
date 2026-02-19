"""
Views for LinkedIn Marketing Agent Dashboard
Preserves state across form submissions
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.contrib import messages
from .models import RedditPost, LinkedInPost, PostHistory, SavedProfile
from .services import RedditService, GeminiService, ImageService, ImageGenerationService, LinkedInService, LinkedInFinderService, PDFService
import json
import requests
import csv
from io import BytesIO
from django.db.models import Q
from django.utils import timezone

# ...existing imports...

def dashboard_view(request):
    """
    Main dashboard view with state preservation
    """
    # Auto-clear state if 'clear' parameter is in URL
    if request.GET.get('clear'):
        if 'dashboard_state' in request.session:
            del request.session['dashboard_state']
        messages.info(request, "Dashboard cleared!")
    
    context = {
        'reddit_posts': [],
        'selected_post': None,
        'rewritten_text': '',
        'custom_instruction': '',
        'image_source': 'pexels',
        'image_query': '',
        'images': [],
        'selected_image_url': None,
        'recent_posts': LinkedInPost.objects.all()[:5],
        'logs': []
    }
    
    # Preserve state from session
    if 'dashboard_state' in request.session:
        state = request.session['dashboard_state']
        context.update(state)
    
    return render(request, 'linkedin_automation/main.html', context)


@require_http_methods(["POST"])
def search_reddit(request):
    """Search Reddit for high-quality articles"""
    keyword = request.POST.get('keyword', '').strip()
    sort_by = request.POST.get('sort_by', 'hot')
    time_filter = request.POST.get('time_filter', 'week')
    min_words = int(request.POST.get('min_words', '200'))
    min_score = int(request.POST.get('min_score', '10'))
    logs = []
    
    if not keyword:
        messages.error(request, "Please enter a search keyword")
        return redirect('linkedin_automation:dashboard')
    
    logs.append(f"🔍 Searching Reddit for: '{keyword}' (Sort: {sort_by}, Time: {time_filter}, Min words: {min_words})")
    
    try:
        reddit_service = RedditService()
        posts = reddit_service.search_trending_posts(
            keyword, 
            limit=20, 
            sort_by=sort_by,
            time_filter=time_filter,
            min_word_count=min_words,
            min_score=min_score
        )
        
        # Save to database
        for post_data in posts:
            RedditPost.objects.update_or_create(
                reddit_id=post_data['id'],
                defaults={
                    'title': post_data['title'],
                    'content': post_data['content'],
                    'subreddit': post_data['subreddit'],
                    'score': post_data['score'],
                    'url': post_data['permalink']
                }
            )
        
        logs.append(f"✅ Found {len(posts)} high-quality articles")
        
        # Update session state
        request.session['dashboard_state'] = {
            'reddit_posts': posts,
            'keyword': keyword,
            'sort_by': sort_by,
            'time_filter': time_filter,
            'min_words': min_words,
            'min_score': min_score,
            'logs': logs
        }
        
        messages.success(request, f"Found {len(posts)} Reddit posts!")
        
    except Exception as e:
        logs.append(f"❌ Error: {str(e)}")
        messages.error(request, f"Reddit search failed: {str(e)}")
    
    return redirect('linkedin_automation:dashboard')


@require_http_methods(["POST"])
def select_reddit_post(request):
    """Select a Reddit post and preserve in state"""
    post_index = int(request.POST.get('post_index', 0))
    
    state = request.session.get('dashboard_state', {})
    reddit_posts = state.get('reddit_posts', [])
    
    if 0 <= post_index < len(reddit_posts):
        selected_post = reddit_posts[post_index]
        state['selected_post'] = selected_post
        state['logs'] = state.get('logs', []) + [
            f"📝 Selected: {selected_post['title'][:50]}..."
        ]
        request.session['dashboard_state'] = state
        messages.success(request, "Post selected!")
    
    return redirect('linkedin_automation:dashboard')


@require_http_methods(["POST"])
def rewrite_with_gemini(request):
    """Rewrite content using Gemini AI"""
    state = request.session.get('dashboard_state', {})
    logs = state.get('logs', [])
    
    selected_post = state.get('selected_post')
    if not selected_post:
        messages.error(request, "Please select a Reddit post first")
        return redirect('linkedin_automation:dashboard')
    
    custom_instruction = request.POST.get('custom_instruction', '').strip()
    format_style = request.POST.get('format_style', 'paragraph')
    
    logs.append(f"🤖 Rewriting with Gemini AI ({format_style} style)...")
    
    if custom_instruction:
        logs.append(f"📋 Custom instruction: {custom_instruction[:50]}...")
    
    try:
        gemini_service = GeminiService()
        original_content = f"{selected_post['title']}\n\n{selected_post['content']}"
        rewritten = gemini_service.rewrite_content(original_content, custom_instruction, format_style)
        
        state['rewritten_text'] = rewritten
        state['custom_instruction'] = custom_instruction
        state['format_style'] = format_style
        state['logs'] = logs + ["✅ Content rewritten successfully!"]
        
        request.session['dashboard_state'] = state
        messages.success(request, f"Content rewritten in {format_style} style!")
        
    except Exception as e:
        logs.append(f"❌ Gemini Error: {str(e)}")
        state['logs'] = logs
        request.session['dashboard_state'] = state
        messages.error(request, f"Gemini rewriting failed: {str(e)}")
    
    return redirect('linkedin_automation:dashboard')


@require_http_methods(["POST"])
def search_images(request):
    """Search for images from selected API"""
    state = request.session.get('dashboard_state', {})
    logs = state.get('logs', [])
    
    image_source = request.POST.get('image_source', 'pexels')
    image_query = request.POST.get('image_query', '').strip()
    
    if not image_query:
        messages.error(request, "Please enter an image search query")
        return redirect('linkedin_automation:dashboard')
    
    logs.append(f"🖼️ Searching {image_source.upper()} for: '{image_query}'...")
    
    try:
        image_service = ImageService()
        images = []
        
        if image_source == 'pexels':
            images = image_service.search_pexels(image_query)
        elif image_source == 'giphy':
            images = image_service.search_giphy(image_query)
        elif image_source == 'serpapi':
            images = image_service.search_serpapi(image_query)
        
        state['images'] = images
        state['image_source'] = image_source
        state['image_query'] = image_query
        state['logs'] = logs + [f"✅ Found {len(images)} images"]
        
        request.session['dashboard_state'] = state
        messages.success(request, f"Found {len(images)} images!")
        
    except Exception as e:
        logs.append(f"❌ Image Search Error: {str(e)}")
        state['logs'] = logs
        request.session['dashboard_state'] = state
        messages.error(request, f"Image search failed: {str(e)}")
    
    return redirect('linkedin_automation:dashboard')


@require_http_methods(["POST"])
def generate_image_ai(request):
    """Generate an image using AI from the rewritten text"""
    state = request.session.get('dashboard_state', {})
    logs = state.get('logs', [])
    
    rewritten_text = state.get('rewritten_text', '')
    
    if not rewritten_text:
        messages.error(request, "Please rewrite content with Gemini first")
        return redirect('linkedin_automation:dashboard')
    
    logs.append(f"🎨 Generating AI image from your post content...")
    
    try:
        import base64
        import os
        from django.core.files.base import ContentFile
        from django.conf import settings
        
        # Generate image using Imagen
        image_gen_service = ImageGenerationService()
        result = image_gen_service.generate_image_from_text(rewritten_text)
        
        if result and result.get('image_data'):
            # Ensure uploads directory exists
            uploads_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
            os.makedirs(uploads_dir, exist_ok=True)
            
            # Save the generated image to media folder
            filename = f"generated_{os.urandom(8).hex()}.png"
            filepath = f"uploads/{filename}"
            
            # Save to Django storage
            saved_path = default_storage.save(filepath, ContentFile(result['image_data']))
            image_url = default_storage.url(saved_path)
            
            # Verify file was saved
            full_path = os.path.join(settings.MEDIA_ROOT, saved_path)
            if os.path.exists(full_path):
                logs.append(f"✅ Image saved successfully: {saved_path} ({os.path.getsize(full_path)} bytes)")
            else:
                logs.append(f"⚠️ Warning: Image URL created but file not found at {full_path}")
            
            # Get the source information
            source = result.get('source', 'ai-generated')
            
            # Display source
            if 'gemini' in source:
                source_display = '🎨 AI Generated Image'
            elif 'google-imagen' in source:
                source_display = '🌟 Google Imagen'
            else:
                source_display = '🎨 AI Generated'
            
            # Add to images list with source information
            generated_image = {
                'url': request.build_absolute_uri(image_url),
                'thumb': request.build_absolute_uri(image_url),
                'title': f'{source_display}',
                'source': source,
                'is_generated': True
            }
            
            # Add to the front of images list
            current_images = state.get('images', [])
            state['images'] = [generated_image] + current_images
            state['selected_image_url'] = generated_image['url']
            
            # Generic success messages
            success_msg = "✅ AI image generated successfully"
            log_msg = "✅ Professional AI-generated image ready"
            
            state['logs'] = logs + [log_msg]
            
            request.session['dashboard_state'] = state
            messages.success(request, success_msg)
        else:
            logs.append("❌ Failed to generate image")
            state['logs'] = logs
            request.session['dashboard_state'] = state
            messages.error(request, "Image generation failed. Please try again.")
        
    except Exception as e:
        logs.append(f"❌ Image Generation Error: {str(e)}")
        state['logs'] = logs
        request.session['dashboard_state'] = state
        messages.error(request, f"Image generation failed: {str(e)}")
    
    return redirect('linkedin_automation:dashboard')


@require_http_methods(["POST"])
def select_image(request):
    """Select an image and preserve in state"""
    image_url = request.POST.get('image_url')
    
    state = request.session.get('dashboard_state', {})
    state['selected_image_url'] = image_url
    state['logs'] = state.get('logs', []) + ["✅ Image selected"]
    
    request.session['dashboard_state'] = state
    messages.success(request, "Image selected!")
    
    return redirect('linkedin_automation:dashboard')


@require_http_methods(["POST"])
def upload_image(request):
    """Upload image from local filesystem"""
    state = request.session.get('dashboard_state', {})
    logs = state.get('logs', [])
    
    if 'image_file' not in request.FILES:
        messages.error(request, "Please select a file to upload")
        return redirect('linkedin_automation:dashboard')
    
    image_file = request.FILES['image_file']
    logs.append(f"📤 Uploading: {image_file.name}...")
    
    try:
        # Save file
        file_path = default_storage.save(f'uploads/{image_file.name}', image_file)
        file_url = default_storage.url(file_path)
        
        state['selected_image_url'] = file_url
        state['image_source'] = 'upload'
        state['uploaded_file_path'] = file_path
        state['logs'] = logs + [f"✅ Uploaded: {image_file.name}"]
        
        request.session['dashboard_state'] = state
        messages.success(request, "Image uploaded successfully!")
        
    except Exception as e:
        logs.append(f"❌ Upload Error: {str(e)}")
        state['logs'] = logs
        request.session['dashboard_state'] = state
        messages.error(request, f"Upload failed: {str(e)}")
    
    return redirect('linkedin_automation:dashboard')


# Find the post_linkedin function and update it

@require_http_methods(["POST"])
def post_linkedin(request):
    """Post content to LinkedIn with image"""
    rewritten_text = request.POST.get('rewritten_text', '').strip()
    image_url = request.POST.get('image_url', '').strip()
    
    if not rewritten_text:
        messages.error(request, "No content to post!")
        return redirect('linkedin_automation:dashboard')
    
    # Create a LinkedInPost record BEFORE attempting to post
    linkedin_post = LinkedInPost.objects.create(
        title=rewritten_text[:100],  # First 100 chars as title
        content=rewritten_text,
        image_url=image_url,
        status='draft'  # Start as draft
    )
    
    # Also create PostHistory record
    post_history = PostHistory.objects.create(
        original_content=request.session.get('dashboard_state', {}).get('selected_post', {}).get('content', ''),
        rewritten_content=rewritten_text,
        image_url=image_url,
        image_source=request.session.get('dashboard_state', {}).get('image_source', 'unknown'),
        success=False  # Will update if successful
    )
    
    try:
        linkedin_service = LinkedInService()
        
        if image_url:
            import requests
            import os
            from django.conf import settings
            
            # Check if this is a local media file or external URL
            if '/media/' in image_url:
                # Local file - read from disk (works in Docker)
                media_path = image_url.split('/media/')[-1]
                file_path = os.path.join(settings.MEDIA_ROOT, media_path)
                
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        image_data = f.read()
                else:
                    raise FileNotFoundError(f"Local image not found: {file_path}")
            else:
                # External URL - download via HTTP
                img_response = requests.get(image_url, timeout=10)
                img_response.raise_for_status()
                image_data = img_response.content
            
            # Post with image
            result = linkedin_service.post_with_image(rewritten_text, image_data)
            
            if result.get('success'):
                # Update LinkedInPost to posted status
                linkedin_post.status = 'posted'
                linkedin_post.post_id = result.get('post_id')
                linkedin_post.asset_id = result.get('asset_id')
                linkedin_post.posted_at = timezone.now()
                linkedin_post.save()
                
                # Update PostHistory
                post_history.success = True
                post_history.save()
                
                messages.success(request, f"Posted to LinkedIn successfully! Post ID: {result.get('post_id')}")
            else:
                # Mark as failed
                linkedin_post.status = 'failed'
                linkedin_post.save()
                
                post_history.error_message = result.get('error', 'Unknown error')
                post_history.save()
                
                messages.error(request, f"Failed to post: {result.get('error')}")
        else:
            # Post without image (text only)
            post_id = linkedin_service.create_text_post(rewritten_text)
            
            if post_id:
                linkedin_post.status = 'posted'
                linkedin_post.post_id = post_id
                linkedin_post.posted_at = timezone.now()
                linkedin_post.save()
                
                post_history.success = True
                post_history.save()
                
                messages.success(request, f"Posted to LinkedIn successfully! Post ID: {post_id}")
            else:
                linkedin_post.status = 'failed'
                linkedin_post.save()
                
                post_history.error_message = 'Failed to create text post'
                post_history.save()
                
                messages.error(request, "Failed to post to LinkedIn")
    
    except Exception as e:
        # Mark as failed on exception
        linkedin_post.status = 'failed'
        linkedin_post.save()
        
        post_history.error_message = str(e)
        post_history.save()
        
        messages.error(request, f"Error posting to LinkedIn: {str(e)}")
    
    return redirect('linkedin_automation:dashboard')
@require_http_methods(["POST"])
def clear_state(request):
    """Clear dashboard state and start fresh"""
    if 'dashboard_state' in request.session:
        del request.session['dashboard_state']
    
    messages.info(request, "Dashboard cleared!")
    return redirect('linkedin_automation:dashboard')

def history_view(request):
    """Display post and image history"""
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')
    
    linkedin_posts = LinkedInPost.objects.all()
    
    if status_filter != 'all':
        linkedin_posts = linkedin_posts.filter(status=status_filter)
    
    if search_query:
        linkedin_posts = linkedin_posts.filter(
            Q(title__icontains=search_query) |
            Q(content__icontains=search_query)
        )
    
    post_history = PostHistory.objects.all()[:50]
    
    stats = {
        'total_posts': LinkedInPost.objects.count(),
        'posted': LinkedInPost.objects.filter(status='posted').count(),
        'drafts': LinkedInPost.objects.filter(status='draft').count(),
        'failed': LinkedInPost.objects.filter(status='failed').count(),
        'success_rate': 0
    }
    
    total_attempts = PostHistory.objects.count()
    if total_attempts > 0:
        successful = PostHistory.objects.filter(success=True).count()
        stats['success_rate'] = round((successful / total_attempts) * 100, 1)
    
    context = {
        'linkedin_posts': linkedin_posts[:20],
        'post_history': post_history,
        'stats': stats,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'linkedin_automation/history.html', context)

@require_http_methods(["POST"])
def delete_history_item(request, item_id):
    """Delete a history item"""
    try:
        post = LinkedInPost.objects.get(id=item_id)
        post.delete()
        messages.success(request, "Post deleted successfully!")
    except LinkedInPost.DoesNotExist:
        messages.error(request, "Post not found!")
    
    return redirect('linkedin_automation:history')


@require_http_methods(["POST"])
def clear_all_history(request):
    """Clear all post history"""
    try:
        # Delete all LinkedIn posts
        linkedin_count = LinkedInPost.objects.all().count()
        LinkedInPost.objects.all().delete()
        
        # Delete all post history
        history_count = PostHistory.objects.all().count()
        PostHistory.objects.all().delete()
        
        total_deleted = linkedin_count + history_count
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully deleted {total_deleted} history items ({linkedin_count} posts, {history_count} activity logs)'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def finder_view(request):
    """
    Company and People Finder view
    """
    context = {
        'search_type': 'company',
        'query': '',
        'companies': [],
        'people': [],
        'searched': False
    }
    
    return render(request, 'linkedin_automation/finder.html', context)


@require_http_methods(["POST"])
def search_companies(request):
    """Search for companies on LinkedIn"""
    query = request.POST.get('query', '').strip()
    
    if not query:
        messages.error(request, "Please enter a company name or keyword")
        return redirect('linkedin_automation:finder')
    
    try:
        finder_service = LinkedInFinderService()
        companies = finder_service.search_companies(query, limit=20)
        
        # Check if using mock data
        if finder_service.use_mock_data:
            messages.info(request, "📝 Showing demo data. Add SERPAPI_KEY to .env for real LinkedIn search.")
        
        context = {
            'search_type': 'company',
            'query': query,
            'companies': companies,
            'people': [],
            'searched': True
        }
        
        if companies:
            messages.success(request, f"Found {len(companies)} companies!")
        else:
            messages.info(request, "No companies found. Try a different search term.")
        
        return render(request, 'linkedin_automation/finder.html', context)
        
    except Exception as e:
        messages.error(request, f"Company search failed: {str(e)}")
        return redirect('linkedin_automation:finder')


@require_http_methods(["POST"])
def search_people(request):
    """Search for people on LinkedIn"""
    query = request.POST.get('query', '').strip()
    role = request.POST.get('role', '').strip()
    location = request.POST.get('location', '').strip()
    
    if not query:
        messages.error(request, "Please enter a person's name or keyword")
        return redirect('linkedin_automation:finder')
    
    try:
        finder_service = LinkedInFinderService()
        people = finder_service.search_people(query, role=role, location=location, limit=20)
        
        # Check if using mock data
        if finder_service.use_mock_data:
            messages.info(request, "📝 Showing demo data. Add SERPAPI_KEY to .env for real LinkedIn search.")
        
        # Build search description
        search_desc = f"Query: '{query}'"
        if role:
            search_desc += f", Role: '{role}'"
        if location:
            search_desc += f", Location: '{location}'"
        
        context = {
            'search_type': 'people',
            'query': query,
            'role': role,
            'location': location,
            'companies': [],
            'people': people,
            'searched': True
        }
        
        if people:
            messages.success(request, f"Found {len(people)} people! ({search_desc})")
        else:
            messages.info(request, f"No people found for {search_desc}. Try different criteria.")
        
        return render(request, 'linkedin_automation/finder.html', context)
        
    except Exception as e:
        messages.error(request, f"People search failed: {str(e)}")
        return redirect('linkedin_automation:finder')


@require_http_methods(["POST"])
def save_profile(request):
    """Save a company or person profile for lead tracking"""
    try:
        profile_type = request.POST.get('profile_type')
        data = json.loads(request.POST.get('data', '{}'))
        
        # Create or update saved profile
        profile, created = SavedProfile.objects.get_or_create(
            profile_type=profile_type,
            name=data.get('name', ''),
            linkedin_url=data.get('linkedin_url', data.get('website', '')),
            defaults={
                'headline': data.get('headline', data.get('industry', '')),
                'description': data.get('description', ''),
                'location': data.get('location', ''),
                'industry': data.get('industry', ''),
                'profile_picture': data.get('profilePicture', data.get('logo', '')),
                'website': data.get('website', ''),
                'follower_count': str(data.get('followerCount', '')),
                'employee_count': str(data.get('employeeCount', '')),
            }
        )
        
        if created:
            messages.success(request, f"✓ Saved {profile.name} to your leads!")
        else:
            messages.info(request, f"{profile.name} is already in your saved leads.")
        
        return JsonResponse({'success': True, 'created': created, 'id': profile.id})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


def saved_profiles_view(request):
    """View and manage saved profiles"""
    profile_type = request.GET.get('type', 'all')
    priority = request.GET.get('priority', 'all')
    search = request.GET.get('search', '')
    
    profiles = SavedProfile.objects.all()
    
    if profile_type != 'all':
        profiles = profiles.filter(profile_type=profile_type)
    
    if priority != 'all':
        profiles = profiles.filter(priority=priority)
    
    if search:
        profiles = profiles.filter(
            Q(name__icontains=search) |
            Q(headline__icontains=search) |
            Q(tags__icontains=search)
        )
    
    stats = {
        'total': SavedProfile.objects.count(),
        'companies': SavedProfile.objects.filter(profile_type='company').count(),
        'people': SavedProfile.objects.filter(profile_type='person').count(),
        'contacted': SavedProfile.objects.filter(contacted=True).count(),
        'high_priority': SavedProfile.objects.filter(priority='high').count(),
    }
    
    context = {
        'profiles': profiles,
        'stats': stats,
        'current_type': profile_type,
        'current_priority': priority,
        'search_query': search
    }
    
    return render(request, 'linkedin_automation/saved_profiles.html', context)


@require_http_methods(["POST"])
@csrf_exempt
@require_http_methods(["POST"])
def generate_outreach_message(request, profile_id):
    """Generate AI outreach message for a saved profile"""
    try:
        print(f"🔍 DEBUG: Generating outreach for profile_id={profile_id}")
        print(f"🔍 DEBUG: Request method={request.method}")
        print(f"🔍 DEBUG: Content-Type={request.content_type}")
        
        profile = get_object_or_404(SavedProfile, id=profile_id)
        print(f"✅ Profile found: {profile.name} ({profile.profile_type})")
        
        custom_instruction = request.POST.get('instruction', '')
        
        # Build context for AI
        if profile.profile_type == 'company':
            prompt = f"""Generate a professional LinkedIn outreach message for connecting with {profile.name}.
            
Company Details:
- Name: {profile.name}
- Industry: {profile.industry or 'Not specified'}
- Description: {profile.description[:200] if profile.description else 'Not available'}
- Employees: {profile.employee_count or 'Not specified'}

{f'Additional context: {custom_instruction}' if custom_instruction else ''}

Create a personalized, professional message (max 300 characters) that:
1. Shows genuine interest in their company
2. Mentions specific details about what they do
3. Suggests a potential collaboration or value proposition
4. Keeps it concise and professional"""
        else:
            prompt = f"""Generate a professional LinkedIn connection request message for {profile.name}.
            
Person Details:
- Name: {profile.name}
- Headline: {profile.headline or 'Professional'}
- Location: {profile.location or 'Not specified'}
- Industry: {profile.industry or 'Not specified'}

{f'Additional context: {custom_instruction}' if custom_instruction else ''}

Create a personalized message (max 300 characters) that:
1. Mentions common ground or shared interests
2. Shows you've reviewed their profile
3. States why you'd like to connect
4. Keeps it natural and professional"""
        
        print(f"📝 Prompt created, calling Gemini API...")
        # Generate message using Gemini
        gemini_service = GeminiService()
        message = gemini_service.rewrite_content(prompt, "")
        print(f"✅ Message generated: {message[:100]}...")
        
        # Save to profile
        profile.ai_outreach_message = message
        profile.save()
        print(f"💾 Saved to database")
        
        messages.success(request, "✨ Outreach message generated!")
        return JsonResponse({'success': True, 'message': message})
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ ERROR in generate_outreach_message:")
        print(error_trace)
        return JsonResponse({'success': False, 'error': str(e), 'trace': error_trace}, status=400)


@require_http_methods(["POST"])
def update_profile_notes(request, profile_id):
    """Update notes and tags for a saved profile"""
    try:
        profile = get_object_or_404(SavedProfile, id=profile_id)
        
        profile.notes = request.POST.get('notes', profile.notes)
        profile.tags = request.POST.get('tags', profile.tags)
        profile.priority = request.POST.get('priority', profile.priority)
        
        if request.POST.get('contacted') == 'true':
            profile.contacted = True
            profile.contacted_date = timezone.now()
        
        profile.save()
        messages.success(request, f"✓ Updated {profile.name}")
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


def export_profiles_csv(request):
    """Export saved profiles to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="linkedin_leads.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Type', 'Name', 'Headline', 'Location', 'Industry', 'LinkedIn URL', 
                     'Priority', 'Tags', 'Notes', 'Contacted', 'Saved Date'])
    
    profiles = SavedProfile.objects.all()
    for profile in profiles:
        writer.writerow([
            profile.profile_type,
            profile.name,
            profile.headline,
            profile.location,
            profile.industry,
            profile.linkedin_url,
            profile.priority,
            profile.tags,
            profile.notes,
            'Yes' if profile.contacted else 'No',
            profile.saved_at.strftime('%Y-%m-%d %H:%M')
        ])
    
    return response


@require_http_methods(["POST"])
def delete_saved_profile(request, profile_id):
    """Delete a saved profile"""
    try:
        profile = get_object_or_404(SavedProfile, id=profile_id)
        name = profile.name
        profile.delete()
        messages.success(request, f"✓ Deleted {name}")
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)