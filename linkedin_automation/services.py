"""
API integration services for Reddit, Gemini, Image sources, and LinkedIn
Adapted for Kaliagents integration
"""
import praw
import requests
import google.generativeai as genai
from django.conf import settings
from typing import List, Dict, Optional
import json
import urllib.parse


class RedditService:
    """Handle Reddit API interactions using PRAW"""
    
    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=settings.REDDIT_CLIENT_ID,
            client_secret=settings.REDDIT_CLIENT_SECRET,
            user_agent=settings.REDDIT_USER_AGENT
        )
    
    def search_trending_posts(self, keyword: str, limit: int = 20, sort_by: str = 'hot', 
                             time_filter: str = 'week', min_word_count: int = 200, 
                             min_score: int = 10) -> List[Dict]:
        """
        Search for high-quality, long-form articles on Reddit
        
        Args:
            keyword: Search term
            limit: Maximum number of posts to return
            sort_by: Sort method ('hot', 'top', 'new', 'relevance')
            time_filter: Time filter ('hour', 'day', 'week', 'month', 'year', 'all')
            min_word_count: Minimum word count for articles (default 200)
            min_score: Minimum upvote score (default 10)
            
        Returns:
            List of post dictionaries with title, content, score, quality metrics
        """
        posts = []
        try:
            # Search across all subreddits, fetch more to filter for quality content
            for submission in self.reddit.subreddit('all').search(
                keyword, 
                sort=sort_by, 
                time_filter=time_filter,
                limit=limit * 5  # Fetch more to filter for quality articles
            ):
                # Only include posts with substantial text content
                content = submission.selftext.strip()
                word_count = len(content.split())
                
                # Filter for high-quality articles
                if (content and 
                    word_count >= min_word_count and 
                    submission.score >= min_score and
                    submission.upvote_ratio >= 0.70):  # 70% upvote ratio minimum
                    
                    # Calculate quality score
                    quality_score = (
                        submission.score * 0.4 + 
                        word_count * 0.3 + 
                        submission.num_comments * 0.2 + 
                        submission.upvote_ratio * 100 * 0.1
                    )
                    
                    posts.append({
                        'id': submission.id,
                        'title': submission.title,
                        'content': content,
                        'score': submission.score,
                        'upvote_ratio': submission.upvote_ratio,
                        'num_comments': submission.num_comments,
                        'created_utc': submission.created_utc,
                        'url': submission.url,
                        'permalink': f"https://reddit.com{submission.permalink}",
                        'subreddit': submission.subreddit.display_name,
                        'author': str(submission.author),
                        'word_count': word_count,
                        'quality_score': int(quality_score)
                    })
                    
                    # Stop once we have enough quality articles
                    if len(posts) >= limit:
                        break
            
            # Sort by quality score
            posts.sort(key=lambda x: x['quality_score'], reverse=True)
                
        except Exception as e:
            print(f"Reddit API Error: {e}")
        
        return posts


class GeminiService:
    """Handle Google Gemini AI interactions"""
    
    def __init__(self):
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set. Add it to your environment or .env")
        genai.configure(api_key=api_key)
        self.api_key = api_key
        self.model = genai.GenerativeModel("gemini-2.5-flash-lite")
    
    def rewrite_content(self, original_content: str, custom_instruction: str = "", format_style: str = "paragraph") -> str:
        """
        Rewrite content using Gemini with custom instructions.
        Tries SDK first, falls back to REST like your curl test.
        """
        # Choose prompt based on format style
        if format_style == "points":
            prompt = (
                "You are a professional LinkedIn content writer. "
                "Rewrite the following Reddit post into ONE professional LinkedIn post in POINT-WISE format. "
                "\n\nFORMATTING RULES (VERY IMPORTANT):\n"
                "- Start with a strong hook (1-2 sentences)\n"
                "- Add TWO blank lines after the hook\n"
                "- List 3-5 key points using emojis as bullets (e.g., ✓, •, →, 💡)\n"
                "- Add ONE blank line between EACH point\n"
                "- Keep each point to 1-2 sentences max\n"
                "- Add TWO blank lines before hashtags\n"
                "- Add 3-5 relevant hashtags at the very end\n"
                "\n\nCONTENT RULES:\n"
                "- Keep total length 150-250 words\n"
                "- Use professional but conversational tone\n"
                "- NO markdown formatting (no **, no __, no dashes for bullets)\n"
                "- Use emojis or simple symbols for bullets\n"
                "- Make it scannable and easy to read\n"
                "\n\nEXAMPLE FORMAT:\n"
                "Opening hook that grabs attention.\n\n"
                "✓ First key point explained.\n\n"
                "✓ Second insight here.\n\n"
                "✓ Third important detail.\n\n"
                "Closing thought?\n\n"
                "#Hashtag1 #Hashtag2 #Hashtag3\n"
            )
        else:  # paragraph style
            prompt = (
                "You are a professional LinkedIn content writer. "
                "Rewrite the following Reddit post into ONE professional LinkedIn post. "
                "\n\nFORMATTING RULES (VERY IMPORTANT):\n"
                "- Start with a strong hook (1-2 sentences)\n"
                "- Add TWO blank lines (press Enter twice) after the hook\n"
                "- Write 2-3 short paragraphs in the body (2-3 sentences each)\n"
                "- Add TWO blank lines between EACH paragraph\n"
                "- End with a call-to-action or thought-provoking question\n"
                "- Add TWO blank lines before hashtags\n"
                "- Add 3-5 relevant hashtags at the very end\n"
                "\n\nCONTENT RULES:\n"
                "- Keep total length 150-250 words\n"
                "- Use professional but conversational tone\n"
                "- NO markdown formatting (no **, no __, no bullets with *)\n"
                "- Use plain text only\n"
                "- Make it engaging and human-written\n"
                "\n\nEXAMPLE FORMAT:\n"
                "Opening hook that grabs attention.\n\n"
                "First key point explained clearly.\n\n"
                "Second insight or detail here.\n\n"
                "Closing thought or question?\n\n"
                "#Hashtag1 #Hashtag2 #Hashtag3\n"
            )
        
        if custom_instruction:
            prompt += f"\nADDITIONAL INSTRUCTIONS: {custom_instruction}\n"
        
        prompt += f"\n\nORIGINAL CONTENT:\n{original_content}\n\n---\n\nYOUR LINKEDIN POST:"
        
        # 1) Try SDK call
        try:
            res = self.model.generate_content(prompt)
            if hasattr(res, "text") and res.text:
                return res.text.strip()
            if getattr(res, "candidates", None):
                cand = res.candidates[0]
                content = getattr(cand, "content", None)
                if hasattr(content, "parts") and content.parts:
                    return content.parts[0].text.strip()
                if isinstance(content, dict):
                    parts = content.get("parts") or []
                    if parts:
                        return parts[0].get("text", "").strip()
            return str(res).strip()
        except Exception as e:
            print(f"Gemini SDK Error (falling back to REST): {e}")
        
        # 2) REST fallback
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            headers = {"Content-Type": "application/json"}
            r = requests.post(url, json=payload, headers=headers, timeout=10)
            r.raise_for_status()
            j = r.json()
            candidates = j.get("candidates") or []
            if candidates:
                content = candidates[0].get("content") or {}
                parts = content.get("parts") or []
                if parts:
                    return parts[0].get("text", "").strip()
            return "Error: no content returned from REST fallback"
        except Exception as e:
            print(f"Gemini REST Error: {e}")
            return f"Error rewriting content: {e}"
    
    def _generate_with_gemini(self, prompt: str) -> Optional[str]:
        """
        Generic helper method to generate content with Gemini.
        Tries SDK first, falls back to REST API.
        
        Args:
            prompt: The full prompt to send to Gemini
            
        Returns:
            Generated text content or None if failed
        """
        # 1) Try SDK call
        try:
            res = self.model.generate_content(prompt)
            if hasattr(res, "text") and res.text:
                return res.text.strip()
            if getattr(res, "candidates", None):
                cand = res.candidates[0]
                content = getattr(cand, "content", None)
                if hasattr(content, "parts") and content.parts:
                    return content.parts[0].text.strip()
                if isinstance(content, dict):
                    parts = content.get("parts") or []
                    if parts:
                        return parts[0].get("text", "").strip()
            return str(res).strip()
        except Exception as e:
            print(f"Gemini SDK Error (falling back to REST): {e}")
        
        # 2) REST fallback
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            headers = {"Content-Type": "application/json"}
            r = requests.post(url, json=payload, headers=headers, timeout=10)
            r.raise_for_status()
            j = r.json()
            candidates = j.get("candidates") or []
            if candidates:
                content = candidates[0].get("content") or {}
                parts = content.get("parts") or []
                if parts:
                    return parts[0].get("text", "").strip()
            raise RuntimeError("No content returned from Gemini REST API")
        except Exception as e:
            print(f"Gemini REST Error: {e}")
            raise RuntimeError(f"Error generating content: {e}")


class ImageGenerationService:
    """Handle AI image generation using Gemini 2.5 Flash with image generation"""
    
    def __init__(self):
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        self.api_key = api_key
    
    def generate_image_from_text(self, prompt: str) -> Optional[Dict]:
        """
        Generate an image using Gemini 2.5 Flash Image model
        
        Args:
            prompt: Text description for image generation
            
        Returns:
            Dictionary with generated image data or None if failed
        """
        try:
            # Create a highly detailed image generation prompt
            image_prompt = self._create_image_prompt(prompt)
            
            # Try Gemini 2.5 Flash Image model using SDK
            print(f"🎨 Attempting Gemini 2.5 Flash Image generation...")
            
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                
                # Try using the SDK with the image model
                model = genai.GenerativeModel('gemini-2.5-flash-image')
                response = model.generate_content(
                    f"Generate a high-quality professional image: {image_prompt}",
                    generation_config={
                        'temperature': 0.4,
                        'top_p': 0.95,
                        'top_k': 40,
                    }
                )
                
                # Check if response contains image data
                if response.parts:
                    for part in response.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            import base64
                            image_bytes = part.inline_data.data
                            if isinstance(image_bytes, str):
                                image_bytes = base64.b64decode(image_bytes)
                            
                            mime_type = part.inline_data.mime_type or 'image/png'
                            print(f"✅ Gemini AI Image generated ({len(image_bytes)} bytes)")
                            return {
                                'image_data': image_bytes,
                                'prompt': image_prompt,
                                'source': 'gemini-2.5-flash-image',
                                'mime_type': mime_type
                            }
                
                print(f"⚠️ No image data in Gemini response")
                return None
                
            except Exception as sdk_error:
                error_msg = str(sdk_error)
                if '429' in error_msg or 'quota' in error_msg.lower() or 'rate limit' in error_msg.lower():
                    print(f"⚠️ Gemini API quota exceeded or rate limited: {sdk_error}")
                    print(f"💡 Your API key may need quota increase at https://console.cloud.google.com/")
                elif '404' in error_msg or 'not found' in error_msg.lower():
                    print(f"⚠️ Gemini 2.5 Flash Image model not available yet: {sdk_error}")
                else:
                    print(f"⚠️ Gemini SDK error: {sdk_error}")
                return None
            
        except Exception as e:
            print(f"⚠️ Gemini error: {e}")
            return None
    
    def _create_image_prompt(self, text: str) -> str:
        """
        Create a highly detailed, specific image generation prompt from the LinkedIn post text
        Uses Gemini to extract precise visual concepts for 99% accuracy
        """
        try:
            # Use Gemini to create a detailed visual description
            api_key = settings.GEMINI_API_KEY
            if api_key:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-2.5-flash-lite")
                
                extraction_prompt = (
                    "You are an expert at creating detailed image generation prompts. "
                    "Analyze this LinkedIn post and create a HIGHLY SPECIFIC and DETAILED visual description "
                    "that captures the exact essence, mood, and key concepts of the content.\n\n"
                    "Requirements:\n"
                    "1. Identify the MAIN subject/topic (be very specific)\n"
                    "2. Describe the exact setting, environment, or context\n"
                    "3. Specify colors, mood, and atmosphere that match the content\n"
                    "4. Include specific objects, symbols, or elements that represent the topic\n"
                    "5. Define the style (photorealistic, modern, minimalist, etc.)\n"
                    "6. Keep it professional and suitable for LinkedIn\n"
                    "7. Be descriptive but concise (under 150 words)\n\n"
                    "OUTPUT FORMAT: Create a single detailed paragraph describing the exact image needed.\n\n"
                    f"LinkedIn Post Content:\n{text[:800]}\n\n"
                    "Detailed Image Description:"
                )
                
                response = model.generate_content(extraction_prompt)
                if hasattr(response, 'text') and response.text:
                    detailed_description = response.text.strip()
                    
                    # Enhance with technical parameters for better quality
                    final_prompt = (
                        f"{detailed_description}, "
                        "high quality, professional photography, sharp focus, "
                        "well-lit, 16:9 aspect ratio, 4K resolution, "
                        "corporate professional style, modern aesthetic, "
                        "suitable for LinkedIn business post, no text or words in image"
                    )
                    
                    print(f"Generated detailed prompt: {final_prompt[:200]}...")
                    return final_prompt
                    
        except Exception as e:
            print(f"Gemini prompt extraction error: {e}")
        
        # Fallback: create detailed prompt from content analysis
        text_sample = text[:600].strip()
        
        # Extract key words and concepts
        keywords = []
        important_words = ['AI', 'technology', 'business', 'innovation', 'data', 'cloud', 
                          'digital', 'software', 'leadership', 'strategy', 'growth',
                          'marketing', 'sales', 'customer', 'team', 'success']
        
        for word in important_words:
            if word.lower() in text_sample.lower():
                keywords.append(word)
        
        if keywords:
            topic = ', '.join(keywords[:3])
        else:
            topic = "professional business"
        
        return (
            f"Professional high-quality business image showcasing {topic}, "
            f"modern corporate setting, clean minimalist design, "
            f"representing the concept of: {text_sample[:150]}, "
            f"photorealistic style, professional lighting, sharp focus, "
            f"suitable for LinkedIn business post, 16:9 aspect ratio, "
            f"4K quality, no text overlays"
        )


class ImageService:
    """Handle image sourcing from multiple APIs"""
    
    def __init__(self):
        self.pexels_key = settings.PEXELS_API_KEY
        self.giphy_key = settings.GIPHY_API_KEY
        self.serpapi_key = settings.SERPAPI_API_KEY
    
    def search_pexels(self, query: str, per_page: int = 5) -> List[Dict]:
        """Search Pexels for images"""
        try:
            url = "https://api.pexels.com/v1/search"
            headers = {"Authorization": self.pexels_key}
            params = {"query": query, "per_page": per_page}
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            return [
                {
                    'url': photo['src']['large'],
                    'thumb': photo['src']['medium'],
                    'photographer': photo['photographer'],
                    'source': 'pexels'
                }
                for photo in data.get('photos', [])
            ]
        except Exception as e:
            print(f"Pexels API Error: {e}")
            return []
    
    def search_giphy(self, query: str, limit: int = 5) -> List[Dict]:
        """Search Giphy for GIFs"""
        try:
            url = "https://api.giphy.com/v1/gifs/search"
            params = {
                "api_key": self.giphy_key,
                "q": query,
                "limit": limit,
                "rating": "g"
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            return [
                {
                    'url': gif['images']['original']['url'],
                    'thumb': gif['images']['fixed_height']['url'],
                    'title': gif['title'],
                    'source': 'giphy'
                }
                for gif in data.get('data', [])
            ]

        except Exception as e:
            print(f"Giphy API Error: {e}")
            return []
    
    def search_serpapi(self, query: str, num: int = 5) -> List[Dict]:
        """Search Google Images via SerpApi"""
        try:
            url = "https://serpapi.com/search"
            params = {
                "engine": "google_images",
                "q": query,
                "api_key": self.serpapi_key,
                "num": num
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            return [
                {
                    'url': img['original'],
                    'thumb': img['thumbnail'],
                    'title': img.get('title', ''),
                    'source': 'google'
                }
                for img in data.get('images_results', [])
            ]
        except Exception as e:
            print(f"SerpApi Error: {e}")
            return []


class LinkedInService:
    """Handle LinkedIn API interactions with 3-step URN process"""
    
    def __init__(self):
        self.access_token = settings.LINKEDIN_ACCESS_TOKEN
        self.person_urn = settings.LINKEDIN_PERSON_URN
        
        # Validate access token (required)
        if not self.access_token:
            print("⚠️ LinkedIn ACCESS_TOKEN missing!")
            print("   Please set LINKEDIN_ACCESS_TOKEN in .env")
            self.credentials_valid = False
        else:
            # If Person URN is not provided, try to fetch it automatically
            if not self.person_urn:
                print("📡 Person URN not found, fetching automatically...")
                self.person_urn = self._fetch_person_urn()
                if self.person_urn:
                    print(f"✓ Person URN retrieved: {self.person_urn}")
                    self.credentials_valid = True
                else:
                    print("❌ Failed to retrieve Person URN")
                    self.credentials_valid = False
            else:
                self.credentials_valid = True
                print(f"✓ LinkedIn credentials found")
        
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }
    
    def _fetch_person_urn(self) -> Optional[str]:
        """
        Automatically fetch the Person URN using the access token
        
        Returns:
            Person URN string or None if failed
        """
        try:
            # Use the userinfo endpoint to get the user's ID
            url = "https://api.linkedin.com/v2/userinfo"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                person_id = data.get('sub')  # 'sub' contains the person ID
                if person_id:
                    return f"urn:li:person:{person_id}"
            else:
                print(f"⚠️ Failed to fetch Person URN: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                
        except Exception as e:
            print(f"❌ Error fetching Person URN: {e}")
        
        return None
    
    def register_upload(self) -> Optional[Dict]:
        """
        Step 1: Register an upload with LinkedIn
        
        Returns:
            Dictionary with asset_id and upload_url, or None with error details
        """
        if not self.credentials_valid:
            print("❌ Cannot register upload: LinkedIn credentials not configured")
            return None
            
        try:
            url = "https://api.linkedin.com/v2/assets?action=registerUpload"
            payload = {
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": self.person_urn,
                    "serviceRelationships": [
                        {
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent"
                        }
                    ]
                }
            }
            
            print(f"🔍 DEBUG: Person URN being used: {self.person_urn}")
            print(f"🔍 DEBUG: Payload: {payload}")
            
            response = requests.post(url, json=payload, headers=self.headers)
            
            # Detailed error handling
            if response.status_code == 401:
                print("❌ LinkedIn API: 401 Unauthorized - Access token expired or invalid")
                print("   Please regenerate your LinkedIn access token")
                return None
            elif response.status_code == 403:
                print("❌ LinkedIn API: 403 Forbidden - Insufficient permissions")
                print("   Ensure your app has w_member_social permission")
                return None
            elif response.status_code == 500:
                print("❌ LinkedIn API: 500 Server Error - LinkedIn API is experiencing issues")
                print(f"   Response: {response.text[:200]}")
                return None
            
            response.raise_for_status()
            
            data = response.json()
            asset_id = data['value']['asset']
            upload_url = data['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
            
            print("✓ LinkedIn upload registered successfully")
            return {
                'asset_id': asset_id,
                'upload_url': upload_url
            }
        
        except Exception as e:
            print(f"❌ LinkedIn Register Upload Error: {e}")
            return None
    
    def upload_image(self, upload_url: str, image_data: bytes) -> bool:
        """
        Step 2: Upload the binary image data
        
        Args:
            upload_url: The upload URL from register_upload
            image_data: Binary image data
            
        Returns:
            True if successful
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            response = requests.put(upload_url, data=image_data, headers=headers)
            response.raise_for_status()
            return True
        
        except Exception as e:
            print(f"LinkedIn Image Upload Error: {e}")
            return False
    
    def create_ugc_post(self, text: str, asset_id: str) -> Optional[str]:
        """
        Step 3: Create the UGC post with the uploaded asset
        
        Args:
            text: Post content
            asset_id: Asset ID from register_upload
            
        Returns:
            Post ID if successful
        """
        try:
            url = "https://api.linkedin.com/v2/ugcPosts"
            payload = {
                "author": self.person_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": text
                        },
                        "shareMediaCategory": "IMAGE",
                        "media": [
                            {
                                "status": "READY",
                                "description": {
                                    "text": "Image"
                                },
                                "media": asset_id,
                                "title": {
                                    "text": "Post Image"
                                }
                            }
                        ]
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }
            
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            return data.get('id')
        
        except Exception as e:
            print(f"LinkedIn Create Post Error: {e}")
            return None
    
    def create_text_post(self, text: str) -> Optional[str]:
        """
        Create a text-only LinkedIn post (no image)
        
        Args:
            text: Post content
            
        Returns:
            Post ID if successful
        """
        if not self.credentials_valid:
            print("❌ Cannot create post: Invalid credentials")
            return None
            
        try:
            url = "https://api.linkedin.com/v2/ugcPosts"
            payload = {
                "author": self.person_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": text
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }
            
            response = requests.post(url, json=payload, headers=self.headers)
            
            if response.status_code == 401:
                print("❌ LinkedIn API: 401 Unauthorized - Access token expired or invalid")
                return None
            elif response.status_code == 403:
                print("❌ LinkedIn API: 403 Forbidden - Insufficient permissions")
                return None
                
            response.raise_for_status()
            
            data = response.json()
            post_id = data.get('id')
            print(f"✓ Text post created successfully: {post_id}")
            return post_id
        
        except Exception as e:
            print(f"❌ LinkedIn Create Text Post Error: {e}")
            return None
    
    def post_with_image(self, text: str, image_data: bytes) -> Dict:
        """
        Complete 3-step process to post with image
        
        Args:
            text: Post content
            image_data: Binary image data
            
        Returns:
            Dictionary with status and details
        """
        if not self.credentials_valid:
            return {
                "success": False, 
                "error": "LinkedIn access token not configured or invalid. Please set LINKEDIN_ACCESS_TOKEN in your .env file with a valid token."
            }
        
        # Step 1: Register upload
        register_result = self.register_upload()
        if not register_result:
            return {
                "success": False, 
                "error": "Failed to register upload with LinkedIn. Check if your access token is valid and has proper permissions (w_member_social)"
            }
        
        # Step 2: Upload image
        upload_success = self.upload_image(
            register_result['upload_url'], 
            image_data
        )
        if not upload_success:
            return {"success": False, "error": "Failed to upload image to LinkedIn"}
        
        # Step 3: Create post
        post_id = self.create_ugc_post(text, register_result['asset_id'])
        if not post_id:
            return {"success": False, "error": "Failed to create LinkedIn post"}
        
        return {
            "success": True,
            "post_id": post_id,
            "asset_id": register_result['asset_id']
        }


class LinkedInFinderService:
    """Handle LinkedIn company and people search using SerpApi"""
    
    def __init__(self):
        # SerpApi is better for LinkedIn search as direct LinkedIn API has restrictions
        self.serpapi_key = getattr(settings, 'SERPAPI_API_KEY', None)
        self.use_mock_data = not self.serpapi_key  # Use mock data if no API key
        print(f"🔑 SerpApi Key: {'Found ✓' if self.serpapi_key else 'Not Found ✗'}")
    
    def search_companies(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search for companies on LinkedIn using SerpApi or mock data
        
        Args:
            query: Company name or keywords
            limit: Maximum number of results
            
        Returns:
            List of company dictionaries
        """
        try:
            if self.serpapi_key:
                # Use SerpApi for real LinkedIn company search
                url = "https://serpapi.com/search"
                params = {
                    'engine': 'google',
                    'q': f'{query} site:linkedin.com/company',
                    'api_key': self.serpapi_key,
                    'num': limit
                }
                
                response = requests.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    companies = []
                    
                    for result in data.get('organic_results', []):
                        company = {
                            'id': result.get('position'),
                            'name': result.get('title', 'N/A').replace(' - LinkedIn', '').replace(' | LinkedIn', ''),
                            'description': result.get('snippet', 'No description available'),
                            'industry': 'N/A',
                            'website': result.get('link', 'N/A'),
                            'logo': result.get('thumbnail', ''),
                            'followerCount': 'N/A',
                            'employeeCount': 'N/A'
                        }
                        companies.append(company)
                    
                    return companies[:limit]
                else:
                    print(f"SerpApi Error: {response.status_code}")
                    return self._get_mock_companies(query, limit)
            else:
                # Return mock data for development/testing
                return self._get_mock_companies(query, limit)
                
        except Exception as e:
            print(f"Company Search Exception: {e}")
            return self._get_mock_companies(query, limit)
    
    def _get_mock_companies(self, query: str, limit: int = 10) -> List[Dict]:
        """Generate mock company data for testing"""
        mock_companies = [
            {
                'id': 1,
                'name': f'{query.title()} Technologies',
                'description': f'Leading provider of innovative {query.lower()} solutions. We help businesses transform through cutting-edge technology and strategic consulting.',
                'industry': 'Technology & IT Services',
                'website': f'https://www.{query.lower().replace(" ", "")}.com',
                'logo': '',
                'followerCount': '125,430',
                'employeeCount': '1,200+'
            },
            {
                'id': 2,
                'name': f'{query.title()} Global Corp',
                'description': f'Fortune 500 company specializing in {query.lower()} with operations across 50+ countries. Industry leader with over 25 years of experience.',
                'industry': 'Enterprise Software',
                'website': f'https://www.{query.lower().replace(" ", "")}global.com',
                'logo': '',
                'followerCount': '450,230',
                'employeeCount': '10,000+'
            },
            {
                'id': 3,
                'name': f'{query.title()} Solutions Inc',
                'description': f'Innovative startup revolutionizing {query.lower()} industry. Backed by top-tier venture capital with rapid growth trajectory.',
                'industry': 'Software Development',
                'website': f'https://www.{query.lower().replace(" ", "")}solutions.io',
                'logo': '',
                'followerCount': '35,890',
                'employeeCount': '200-500'
            },
            {
                'id': 4,
                'name': f'{query.title()} Consulting Group',
                'description': f'Premium consulting services for {query.lower()}. Trusted by Fortune 1000 companies worldwide for strategic transformation.',
                'industry': 'Consulting',
                'website': f'https://www.{query.lower().replace(" ", "")}consulting.com',
                'logo': '',
                'followerCount': '89,320',
                'employeeCount': '5,000+'
            },
            {
                'id': 5,
                'name': f'{query.title()} Innovations Ltd',
                'description': f'Award-winning {query.lower()} company focused on sustainable and impactful solutions. ISO certified and internationally recognized.',
                'industry': 'Innovation & R&D',
                'website': f'https://www.{query.lower().replace(" ", "")}innovations.com',
                'logo': '',
                'followerCount': '67,540',
                'employeeCount': '800+'
            }
        ]
        return mock_companies[:limit]
    
    def search_people(self, query: str, role: str = '', location: str = '', limit: int = 10) -> List[Dict]:
        """
        Search for people on LinkedIn using SerpApi or mock data
        
        Args:
            query: Person name or keywords
            role: Job role/title filter (e.g., 'CEO', 'Founder', 'Engineer')
            location: Location filter (e.g., 'San Francisco', 'New York')
            limit: Maximum number of results
            
        Returns:
            List of people dictionaries
        """
        try:
            if self.serpapi_key:
                # Use SerpApi for real LinkedIn people search
                # Build enhanced search query with role and location
                search_query = f'{query}'
                if role:
                    search_query += f' {role}'
                if location:
                    search_query += f' {location}'
                search_query += ' site:linkedin.com/in'
                
                url = "https://serpapi.com/search"
                params = {
                    'engine': 'google',
                    'q': search_query,
                    'api_key': self.serpapi_key,
                    'num': limit
                }
                
                response = requests.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    people = []
                    
                    for result in data.get('organic_results', []):
                        title_parts = result.get('title', '').split(' - ')
                        name = title_parts[0] if title_parts else 'N/A'
                        headline = title_parts[1] if len(title_parts) > 1 else 'No headline'
                        
                        person = {
                            'id': result.get('position'),
                            'firstName': name.split()[0] if name != 'N/A' else 'N/A',
                            'lastName': ' '.join(name.split()[1:]) if name != 'N/A' and len(name.split()) > 1 else '',
                            'headline': headline.replace(' | LinkedIn', ''),
                            'industry': 'N/A',
                            'location': 'N/A',
                            'profilePicture': result.get('thumbnail', ''),
                            'publicIdentifier': result.get('link', '').split('/in/')[-1].split('?')[0] if '/in/' in result.get('link', '') else ''
                        }
                        people.append(person)
                    
                    return people[:limit]
                else:
                    print(f"SerpApi Error: {response.status_code}")
                    return self._get_mock_people(query, role, location, limit)
            else:
                # Return mock data for development/testing
                return self._get_mock_people(query, role, location, limit)
                
        except Exception as e:
            print(f"People Search Exception: {e}")
            return self._get_mock_people(query, role, location, limit)
    
    def _get_mock_people(self, query: str, role: str = '', location: str = '', limit: int = 10) -> List[Dict]:
        """Generate mock people data for testing with role and location filtering"""
        # Define roles mapping for smart filtering
        role_titles = {
            'CEO': ['CEO', 'Chief Executive Officer'],
            'Founder': ['Founder', 'Co-Founder', 'Founding Partner'],
            'Co-Founder': ['Co-Founder', 'Founder'],
            'Owner': ['Owner', 'Business Owner', 'Company Owner'],
            'President': ['President', 'VP'],
            'CTO': ['CTO', 'Chief Technology Officer', 'VP Engineering'],
            'CFO': ['CFO', 'Chief Financial Officer', 'VP Finance'],
            'COO': ['COO', 'Chief Operating Officer', 'VP Operations'],
            'CMO': ['CMO', 'Chief Marketing Officer', 'VP Marketing'],
            'VP': ['VP Engineering', 'VP Sales', 'VP Marketing', 'VP Operations'],
            'Director': ['Director of Engineering', 'Marketing Director', 'Sales Director'],
            'Manager': ['Product Manager', 'Engineering Manager', 'Marketing Manager'],
            'Engineer': ['Senior Software Engineer', 'Software Engineer', 'DevOps Engineer'],
            'Developer': ['Full Stack Developer', 'Frontend Developer', 'Backend Developer'],
            'Designer': ['Product Designer', 'UX Designer', 'UI/UX Designer'],
            'Analyst': ['Data Analyst', 'Business Analyst', 'Financial Analyst']
        }
        
        all_titles = ['CEO', 'Founder', 'CTO', 'VP Engineering', 'Senior Software Engineer', 'Data Scientist', 
                  'Product Manager', 'Marketing Director', 'Chief Architect', 'DevOps Lead', 'AI Researcher',
                  'Co-Founder', 'CFO', 'COO', 'Director of Engineering', 'Full Stack Developer']
        
        all_locations = ['San Francisco, CA', 'New York, NY', 'Seattle, WA', 'Austin, TX', 'Boston, MA',
                     'London, UK', 'Toronto, Canada', 'Berlin, Germany', 'Singapore', 'Remote',
                     'Los Angeles, CA', 'Chicago, IL', 'Miami, FL', 'Denver, CO', 'Portland, OR']
        
        # Filter titles based on role if specified
        if role and role in role_titles:
            filtered_titles = role_titles[role]
        else:
            filtered_titles = all_titles
        
        # Filter locations if specified
        if location:
            filtered_locations = [loc for loc in all_locations if location.lower() in loc.lower()]
            if not filtered_locations:
                filtered_locations = all_locations  # Fallback to all if no match
        else:
            filtered_locations = all_locations
        
        mock_people = []
        for i in range(min(limit, 15)):
            first_name = f"{query.split()[0] if query.split() else 'John'}{i+1}"
            last_name = 'Doe' if i == 0 else f'Smith{i}'
            selected_title = filtered_titles[i % len(filtered_titles)]
            selected_location = filtered_locations[i % len(filtered_locations)]
            
            mock_people.append({
                'id': i + 1,
                'firstName': first_name,
                'lastName': last_name,
                'headline': f'{selected_title} | {query.title()} Expert',
                'industry': 'Technology',
                'location': selected_location,
                'profilePicture': '',
                'publicIdentifier': f'{first_name.lower()}-{last_name.lower()}'
            })
        
        return mock_people


class PDFService:
    """Handle PDF content extraction and processing"""
    
    def __init__(self):
        self.max_pages = 50  # Limit pages to avoid token overload
        self.max_chars = 50000  # Character limit for processing
    
    def extract_text_from_pdf(self, pdf_file) -> Optional[Dict]:
        """
        Extract text content from uploaded PDF file
        
        Args:
            pdf_file: Django UploadedFile object
            
        Returns:
            Dictionary with extracted text and metadata or None if failed
        """
        try:
            import PyPDF2
            import io
            
            # Read PDF from uploaded file
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_file.read()))
            
            total_pages = len(pdf_reader.pages)
            pages_to_process = min(total_pages, self.max_pages)
            
            extracted_text = []
            for page_num in range(pages_to_process):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                if text.strip():
                    extracted_text.append(text)
            
            full_text = "\n\n".join(extracted_text)
            
            # Truncate if too long
            if len(full_text) > self.max_chars:
                full_text = full_text[:self.max_chars] + "\n\n[Content truncated...]"
            
            print(f"✅ Extracted {len(full_text)} characters from {pages_to_process} pages")
            
            return {
                'text': full_text,
                'pages_processed': pages_to_process,
                'total_pages': total_pages,
                'filename': pdf_file.name,
                'char_count': len(full_text)
            }
            
        except Exception as e:
            print(f"❌ PDF extraction error: {e}")
            return None
    
    def generate_linkedin_post_from_pdf(self, pdf_content: str, format_style: str = 'paragraph') -> Optional[str]:
        """
        Convert PDF content into engaging LinkedIn post using Gemini
        
        Args:
            pdf_content: Extracted text from PDF
            format_style: 'paragraph' or 'points' for formatting style
            
        Returns:
            Generated LinkedIn post content or None if failed
        """
        try:
            api_key = settings.GEMINI_API_KEY
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY not set")
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.5-flash-lite")
            
            if format_style == 'points':
                prompt = f"""You are an expert LinkedIn content creator. Read the following document content and create an engaging LinkedIn post.

DOCUMENT CONTENT:
{pdf_content[:15000]}

INSTRUCTIONS:
1. Extract the KEY INSIGHTS or most valuable takeaways from the document
2. Create a compelling LinkedIn post in POINT-WISE format:
   - Start with a strong hook or introduction line
   - List 4-6 key points using emoji bullets (💡, 🎯, ⚡, 🔥, ✨, 📌, etc.)
   - Each point should be 1-2 lines maximum
   - Add ONE blank line between each point
   - End with a call-to-action or engaging question
3. Make it professional yet conversational
4. Focus on ACTIONABLE VALUE for the reader
5. DO NOT use markdown formatting (no **, no __, no #, no bullet points with *)
6. Add TWO blank lines between the intro and first point, and between the last point and conclusion

Generate ONLY the LinkedIn post content, no explanations."""
            else:
                prompt = f"""You are an expert LinkedIn content creator. Read the following document content and create an engaging LinkedIn post.

DOCUMENT CONTENT:
{pdf_content[:15000]}

INSTRUCTIONS:
1. Extract the KEY MESSAGE or most valuable insight from the document
2. Create a compelling LinkedIn post (200-300 words) that:
   - Starts with a hook that grabs attention
   - Presents the main insight or takeaway clearly
   - Uses short paragraphs for readability (2-3 lines each)
   - Includes relevant emojis where appropriate (but don't overuse)
   - Ends with a call-to-action or thought-provoking question
3. Make it professional yet conversational
4. Focus on VALUE for the reader
5. Add TWO blank lines between EACH paragraph
6. DO NOT use markdown formatting (no **, no __, no #, no bullet points with *)

Generate ONLY the LinkedIn post content, no explanations."""

            response = model.generate_content(prompt)
            
            if response and response.text:
                post_content = response.text.strip()
                print(f"✅ Generated LinkedIn post ({len(post_content)} chars)")
                return post_content
            
            raise RuntimeError("Gemini returned empty response")
            
        except Exception as e:
            print(f"❌ Post generation error: {e}")
            # Re-raise the exception so the view can handle it properly
            raise
