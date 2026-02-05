"""
PDF to LinkedIn Post Views
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .services import PDFService, RedditService, GeminiService


def pdf_to_post_view(request):
    """Main view for PDF to LinkedIn Post feature"""
    # Handle clear request
    if request.GET.get('clear'):
        request.session.pop('pdf_to_post_state', None)
        request.session.modified = True
        return JsonResponse({'success': True, 'message': 'Session cleared'})
    
    context = {
        'pdf_content': None,
        'generated_post': None,
        'pdf_metadata': None
    }
    
    # Preserve state from session
    if 'pdf_to_post_state' in request.session:
        state = request.session['pdf_to_post_state']
        context.update(state)
    
    return render(request, 'linkedin_automation/pdf_to_post.html', context)


@require_http_methods(["POST"])
def upload_pdf(request):
    """Handle PDF file upload and extract content"""
    try:
        if 'pdf_file' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'No PDF file uploaded'}, status=400)
        
        pdf_file = request.FILES['pdf_file']
        
        # Validate file type
        if not pdf_file.name.endswith('.pdf'):
            return JsonResponse({'success': False, 'error': 'Please upload a PDF file'}, status=400)
        
        # Extract content using PDFService
        pdf_service = PDFService()
        result = pdf_service.extract_text_from_pdf(pdf_file)
        
        if not result:
            return JsonResponse({'success': False, 'error': 'Failed to extract PDF content'}, status=400)
        
        # Save state to session
        request.session['pdf_to_post_state'] = {
            'pdf_content': result['text'],
            'pdf_metadata': {
                'filename': result['filename'],
                'pages_processed': result['pages_processed'],
                'total_pages': result['total_pages'],
                'char_count': result['char_count']
            },
            'generated_post': None
        }
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'metadata': request.session['pdf_to_post_state']['pdf_metadata'],
            'preview': result['text'][:500] + '...' if len(result['text']) > 500 else result['text']
        })
        
    except Exception as e:
        print(f"❌ PDF upload error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["POST"])
def generate_post_from_pdf(request):
    """Generate LinkedIn post from extracted PDF content"""
    try:
        # Get PDF content from session
        if 'pdf_to_post_state' not in request.session:
            return JsonResponse({'success': False, 'error': 'No PDF content found. Please upload a PDF first.'}, status=400)
        
        pdf_content = request.session['pdf_to_post_state'].get('pdf_content')
        if not pdf_content:
            return JsonResponse({'success': False, 'error': 'PDF content is empty'}, status=400)
        
        # Get format style from request
        format_style = request.POST.get('format_style', 'paragraph')
        
        # Generate post using PDFService
        pdf_service = PDFService()
        
        try:
            generated_post = pdf_service.generate_linkedin_post_from_pdf(pdf_content, format_style=format_style)
        except Exception as gen_error:
            error_msg = str(gen_error)
            print(f"❌ Generation failed: {error_msg}")
            
            # Check if it's a quota error
            if '429' in error_msg or 'quota' in error_msg.lower() or 'exceeded' in error_msg.lower():
                return JsonResponse({
                    'success': False, 
                    'error': 'Gemini API quota exceeded. Your free tier limit has been reached. Please wait for quota reset or upgrade your API key at console.cloud.google.com'
                }, status=400)
            
            return JsonResponse({
                'success': False, 
                'error': f'Failed to generate post: {error_msg}'
            }, status=400)
        
        if not generated_post:
            return JsonResponse({'success': False, 'error': 'Failed to generate post content'}, status=400)
        
        # Update session state
        request.session['pdf_to_post_state']['generated_post'] = generated_post
        request.session.modified = True
        
        # Also save to main dashboard for posting
        request.session['dashboard_state'] = {
            'rewritten_text': generated_post,
            'reddit_posts': [],
            'selected_post': None,
            'custom_instruction': '',
            'image_source': 'pexels',
            'image_query': '',
            'images': [],
            'selected_image_url': None,
            'logs': ['✓ Post generated from PDF']
        }
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'post_content': generated_post,
            'char_count': len(generated_post)
        })
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Post generation error: {e}")
        
        # Check if it's a quota error
        if '429' in error_msg or 'quota' in error_msg.lower():
            return JsonResponse({
                'success': False, 
                'error': 'Gemini API quota exceeded. Please try again in a few minutes or check your API quota at console.cloud.google.com'
            }, status=429)
        
        return JsonResponse({'success': False, 'error': f'Failed to generate post: {error_msg}'}, status=500)

def combine_sources_view(request):
    """Main view for combining PDF + Reddit sources"""
    # Handle clear request
    if request.GET.get('clear'):
        request.session.pop('combine_sources_state', None)
        request.session.modified = True
        return JsonResponse({'success': True, 'message': 'Session cleared'})
    
    context = {
        'pdf_content': None,
        'reddit_posts': [],
        'selected_reddit': None,
        'generated_post': None,
        'pdf_metadata': None
    }
    
    # Preserve state from session
    if 'combine_sources_state' in request.session:
        state = request.session['combine_sources_state']
        context.update(state)
    
    return render(request, 'linkedin_automation/combine_sources.html', context)


@require_http_methods(["POST"])
def upload_pdf_combine(request):
    """Handle PDF file upload for combined feature"""
    try:
        if 'pdf_file' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'No PDF file uploaded'}, status=400)
        
        pdf_file = request.FILES['pdf_file']
        
        # Validate file type
        if not pdf_file.name.endswith('.pdf'):
            return JsonResponse({'success': False, 'error': 'Please upload a PDF file'}, status=400)
        
        # Extract content using PDFService
        pdf_service = PDFService()
        result = pdf_service.extract_text_from_pdf(pdf_file)
        
        if not result:
            return JsonResponse({'success': False, 'error': 'Failed to extract PDF content'}, status=400)
        
        # Initialize or update session state
        if 'combine_sources_state' not in request.session:
            request.session['combine_sources_state'] = {}
        
        request.session['combine_sources_state'].update({
            'pdf_content': result['text'],
            'pdf_metadata': {
                'filename': result['filename'],
                'pages_processed': result['pages_processed'],
                'total_pages': result['total_pages'],
                'char_count': result['char_count']
            },
            'generated_post': None
        })
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'metadata': request.session['combine_sources_state']['pdf_metadata'],
            'preview': result['text'][:500] + '...' if len(result['text']) > 500 else result['text']
        })
        
    except Exception as e:
        print(f"❌ PDF upload error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["POST"])
def search_reddit_combine(request):
    """Search Reddit for combining with PDF content"""
    try:
        query = request.POST.get('query', '').strip()
        sort_by = request.POST.get('sort_by', 'top')
        time_filter = request.POST.get('time_filter', 'month')
        
        if not query:
            return JsonResponse({'success': False, 'error': 'Search query is required'}, status=400)
        
        # Search using RedditService
        reddit_service = RedditService()
        posts = reddit_service.search_trending_posts(
            keyword=query,  # Changed from query to keyword
            sort_by=sort_by,
            time_filter=time_filter,
            limit=10
        )
        
        if not posts:
            return JsonResponse({'success': False, 'error': 'No Reddit posts found'}, status=404)
        
        # Save to session
        if 'combine_sources_state' not in request.session:
            request.session['combine_sources_state'] = {}
        
        request.session['combine_sources_state']['reddit_posts'] = posts
        request.session['combine_sources_state']['selected_reddit'] = None
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'posts': posts,
            'count': len(posts)
        })
        
    except Exception as e:
        print(f"❌ Reddit search error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["POST"])
def generate_combined_post(request):
    """Generate LinkedIn post from combined PDF + Reddit sources"""
    try:
        # Get state from session
        if 'combine_sources_state' not in request.session:
            return JsonResponse({'success': False, 'error': 'No sources found. Please upload PDF and search Reddit first.'}, status=400)
        
        state = request.session['combine_sources_state']
        pdf_content = state.get('pdf_content')
        reddit_post_id = request.POST.get('reddit_post_id')
        format_style = request.POST.get('format_style', 'paragraph')
        
        if not pdf_content:
            return JsonResponse({'success': False, 'error': 'No PDF content found'}, status=400)
        
        if not reddit_post_id:
            return JsonResponse({'success': False, 'error': 'No Reddit post selected'}, status=400)
        
        # Find selected Reddit post
        reddit_posts = state.get('reddit_posts', [])
        selected_post = next((p for p in reddit_posts if p['id'] == reddit_post_id), None)
        
        if not selected_post:
            return JsonResponse({'success': False, 'error': 'Selected Reddit post not found'}, status=404)
        
        # Combine sources and generate post
        gemini_service = GeminiService()
        
        combined_prompt = f"""You are an expert LinkedIn content creator. You have been provided with content from TWO sources:

SOURCE 1 - DOCUMENT/PDF:
{pdf_content[:8000]}

SOURCE 2 - REDDIT ARTICLE:
Title: {selected_post['title']}
Content: {selected_post['content'][:7000]}
Upvotes: {selected_post.get('score', 0)}
Comments: {selected_post.get('num_comments', 0)}

TASK:
Combine insights from BOTH sources to create a comprehensive, engaging LinkedIn post.
"""
        
        if format_style == 'points':
            combined_prompt += """
FORMAT: Point-wise style
- Start with a compelling hook that connects both sources
- List 5-7 key insights combining information from BOTH sources
- Use emoji bullets (💡, 🎯, ⚡, 🔥, ✨, 📌, etc.)
- Each point should be 1-2 lines maximum
- Add ONE blank line between each point
- End with a strong call-to-action
- DO NOT use markdown formatting (no **, no __, no #, no bullet points with *)
- Add TWO blank lines between the intro and first point, and between the last point and conclusion

Generate ONLY the LinkedIn post content, no explanations."""
        else:
            combined_prompt += """
FORMAT: Paragraph style
- Start with an attention-grabbing introduction that references both sources
- Write 3-4 short paragraphs (2-3 lines each) that:
  * Synthesize insights from BOTH the document and Reddit article
  * Show how the ideas complement or contrast each other
  * Provide unique value by connecting the sources
- Include relevant emojis where appropriate (but don't overuse)
- End with a thought-provoking question or call-to-action
- Add TWO blank lines between EACH paragraph
- DO NOT use markdown formatting (no **, no __, no #, no bullet points with *)

Generate ONLY the LinkedIn post content, no explanations."""
        
        try:
            generated_post = gemini_service._generate_with_gemini(combined_prompt)
        except Exception as gen_error:
            error_msg = str(gen_error)
            print(f"❌ Generation failed: {error_msg}")
            
            if '429' in error_msg or 'quota' in error_msg.lower() or 'exceeded' in error_msg.lower():
                return JsonResponse({
                    'success': False, 
                    'error': 'Gemini API quota exceeded. Please wait for quota reset or upgrade your API key.'
                }, status=400)
            
            return JsonResponse({
                'success': False, 
                'error': f'Failed to generate post: {error_msg}'
            }, status=400)
        
        if not generated_post:
            return JsonResponse({'success': False, 'error': 'Failed to generate post content'}, status=400)
        
        # Update session state
        request.session['combine_sources_state']['generated_post'] = generated_post
        request.session['combine_sources_state']['selected_reddit'] = selected_post
        request.session.modified = True
        
        # Also save to main dashboard for posting
        request.session['dashboard_state'] = {
            'rewritten_text': generated_post,
            'reddit_posts': [],
            'selected_post': None,
            'custom_instruction': '',
            'image_source': 'pexels',
            'image_query': '',
            'images': [],
            'selected_image_url': None,
            'logs': ['✓ Post generated from combined PDF + Reddit sources']
        }
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'post_content': generated_post,
            'char_count': len(generated_post),
            'sources_used': {
                'pdf': state['pdf_metadata']['filename'],
                'reddit': selected_post['title']
            }
        })
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Combined post generation error: {e}")
        
        if '429' in error_msg or 'quota' in error_msg.lower():
            return JsonResponse({
                'success': False, 
                'error': 'Gemini API quota exceeded. Please try again later.'
            }, status=429)
        
        return JsonResponse({'success': False, 'error': f'Failed to generate post: {error_msg}'}, status=500)