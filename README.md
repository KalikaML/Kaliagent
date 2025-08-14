AI Agent Command CenterWelcome to the AI Agent Command Center, a powerful Django-based platform designed to host a suite of specialized AI agents. This application streamlines complex workflows, from generating professional marketing emails to automatically creating viral short-form videos from longer content.Live Demo(Optional: Add a link to your live demo or a GIF of the project in action here)FeaturesThis project is a multi-agent platform containing several independent but integrated applications:1.  Shorts AI (shorts_app)The flagship agent for content creation.YouTube Video Processing: Download any YouTube video by providing its URL.AI-Powered Clip Suggestions: Uses Google's Gemini 1.5 Flash to analyze the video's transcript and suggest the most compelling segments for short videos.Automatic Short Generation: Creates vertical (9:16) or horizontal (16:9) short videos from the suggested or manually selected timestamps.Trending Video Discovery: Features an integrated browser to discover trending YouTube videos by topic, providing endless content ideas.2. AI Gmail Pitch Agent (ai_agent_pitch)A sophisticated tool for automating email marketing.Generate HTML from a Prompt: Uses Google's Gemini AI to transform a simple text description into a complete, professionally designed HTML email.Template Management: Save, load, and update your best-performing email templates directly in the UI.Bulk Sending: Send your email campaigns to an entire list of contacts by uploading a simple CSV file.3. Procurement AI (procurement)An agent designed to streamline procurement workflows by extracting and processing data from documents.4. Marketing Outreach AI (marketing_outreach)An agent focused on lead generation and automating initial marketing contact.Tech StackBackend: Python, DjangoAI: Google Gemini API (gemini-1.5-flash, gemini-pro)Video/Audio Processing: yt-dlp (video download), MoviePy (video editing)Frontend: HTML, Tailwind CSS (for ai_agent_pitch), Vanilla JavaScriptDatabase: Django ORM with SQLite (default)Setup and InstallationFollow these steps to get the project running on your local machine.1. PrerequisitesPython 3.9+GitFFmpeg: This is critical for MoviePy to work. Download it from the official FFmpeg website and ensure the ffmpeg executable is in your system's PATH.2. Clone the Repositorygit clone <your-repository-url>
cd AI_agent_center
3. Set Up Virtual Environment# For Windows
python -m venv venv
venv\Scripts\activate

# For macOS/Linux
python3 -m venv venv
source venv/bin/activate
4. Install DependenciesInstall all the required Python packages.pip install -r requirements.txt
5. Configure Environment VariablesOpen command_center/settings.py and fill in your API keys and secret key:# command_center/settings.py

SECRET_KEY = 'your-super-secret-key'

# For AI Gmail Pitch Agent & Shorts AI
GEMINI_API_KEY = "your-google-gemini-api-key"

# For Shorts AI (Trending Videos)
YOUTUBE_API_KEY = "your-google-youtube-data-v3-api-key"

# For Email Sending
EMAIL_HOST_USER = 'your-gmail-address@gmail.com'
EMAIL_HOST_PASSWORD = 'your-16-character-gmail-app-password'
6. Run Database MigrationsThis will set up the necessary tables in your database for all the apps.python manage.py makemigrations
python manage.py migrate
7. Seed Initial Data (Optional but Recommended)To populate the AI Gmail Pitch Agent with default templates, run the custom management command:python manage.py seed_templates
8. Run the Development Serverpython manage.py runserver
The application should now be running at http://127.0.0.1:8000/.Troubleshooting Common ErrorsSolving moviepy.editor or movie.py ErrorsOne of the most common and frustrating issues when working with video is an error related to moviepy. The error might look like a NameError, an OSError, or a message saying a program could not be found.Cause: These errors almost always mean that MoviePy cannot find the FFmpeg software on your computer. MoviePy is a Python library that acts as a "controller" for FFmpeg, which does the actual heavy lifting of cutting, merging, and writing video files.How to Fix It (Step-by-Step):Verify FFmpeg Installation:Open a new terminal or command prompt (not the one with your venv activated).Type ffmpeg -version and press Enter.If you see version information: FFmpeg is installed and in your PATH. The problem might be with how your Python environment sees the PATH.If you get an error like "command not found": FFmpeg is either not installed or not accessible from your terminal. Proceed to the next step.Install or Fix FFmpeg Path:Installation: Download the correct version for your operating system from the official FFmpeg website.Add to System PATH (Crucial Step): You must add the folder containing the ffmpeg.exe (or ffmpeg on Mac/Linux) file to your system's environment variables PATH. This allows any program, including Python, to find and run it. After adding it to your PATH, you must close and reopen your terminal and code editor for the changes to take effect.Explicitly Tell MoviePy Where to Find FFmpeg (If all else fails):If for some reason your system PATH isn't working, you can tell MoviePy the exact location of the executable directly in your Python code.Find the file where you use MoviePy (e.g., shorts_app/views.py).Before you use any MoviePy functions, add the following lines (adjust the path for your system):# shorts_app/views.py
import os
from moviepy.config import change_config

# For Windows (Example Path)
change_config({"FFMPEG_BINARY": r"C:\path\to\ffmpeg\bin\ffmpeg.exe"})

# For macOS/Linux (Example Path)
# change_config({"FFMPEG_BINARY": "/usr/local/bin/ffmpeg"})

from moviepy.editor import VideoFileClip
# ... rest of your code
This hardcoded path is a last resort but is a guaranteed way to fix the problem.By following these steps, you can resolve virtually any error related to MoviePy and ensure the Shorts AI agent functions correctly.
