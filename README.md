# 🚀 Kaliagents - Multi-AI Business Automation Platform

[![Django](https://img.shields.io/badge/Django-6.0+-092E20?style=flat&logo=django)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat&logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Kaliagents** is an advanced business automation platform powered by AI, featuring three specialized intelligent agents designed to streamline marketing, procurement, and social media operations. Built with Django and integrated with cutting-edge AI services, it provides end-to-end automation for modern businesses.

---

## 📋 Table of Contents

- [Features](#-features)
- [AI Agents](#-ai-agents)
  - [LinkedIn Automation AI](#-linkedin-automation-ai)
  - [Marketing Outreach AI](#-marketing-outreach-ai)
  - [Procurement AI](#-procurement-ai)
- [Tech Stack](#-tech-stack)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [API Integrations](#-api-integrations)
- [Project Structure](#-project-structure)
- [Screenshots](#-screenshots)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

### Core Platform

- 🎯 **Unified Agent Dashboard** - Select and switch between AI agents seamlessly
- 🔐 **User Authentication** - Secure login/registration with session management
- 📊 **Real-time Processing** - Live updates and automation workflows
- 💾 **Persistent Storage** - SQLite database with Django ORM
- 🎨 **Modern UI** - Responsive, gradient-based interface with neon effects
- 🔄 **State Management** - Session-based state preservation across workflows

---

## 🤖 AI Agents

### 🚀 LinkedIn Automation AI

**Transform your LinkedIn presence with AI-powered content creation**

#### Key Features

**1. Reddit Content Sourcing**

- 🔍 Search trending articles from Reddit by keyword
- 📈 Filter by hot, top, new, or relevance
- ⏰ Time-based filtering (today, week, month, year, all)
- 📊 Quality metrics: upvotes, word count, comments
- 🎯 Minimum thresholds for content quality

**2. AI Content Rewriting (Gemini AI)**

- ✍️ Transform Reddit posts into LinkedIn-ready content
- 🎭 Multiple format styles:
  - **Paragraph Style**: Professional narrative format
  - **Point-wise List**: Bullet-point structure
- 🎨 Custom style & tone instructions
- 📝 Real-time content editing
- 💬 Context-aware AI transformations

**3. Visual Asset Selection**

- 🖼️ **Pexels Integration**: High-quality stock photos
- 🎥 **Giphy Integration**: Animated GIFs
- 🎨 **AI Image Generation**: Custom visuals with Gemini
- 🔍 **SerpApi**: Web image search
- 📤 **Local Upload**: Upload your own images
- 👁️ Live preview with thumbnails

**4. LinkedIn Publishing**

- 📤 Direct post to LinkedIn with images
- 📊 Post preview before publishing
- 📜 Complete post history tracking
- ✅ Status monitoring (draft, posted, failed)
- 🔄 Quick dashboard clearing

**5. PDF to LinkedIn Post**

- 📄 Upload PDF documents
- 🤖 AI extraction of key points
- ✍️ Automatic LinkedIn post generation
- 🎨 Complete workflow integration

**6. Multi-Source Content Combination**

- 🔗 Combine PDF + Reddit content
- 🧠 AI-powered synthesis
- 📝 Unified post creation
- 🎯 Enhanced content relevance

**7. LinkedIn Profile Finder**

- 🔍 Search companies on LinkedIn
- 👥 Extract people profiles by role (CEO, CTO, CFO, etc.)
- 💾 Save profiles for future outreach
- 📊 Lead management dashboard
- 📂 Export to CSV

**8. Saved Leads Management**

- 💼 Track all saved LinkedIn profiles
- 🔍 Search and filter leads
- 📤 Export lead database
- 🗑️ Bulk delete operations

#### Workflow Example

```
1. Search Reddit → "artificial intelligence trends"
2. Select high-quality post (500+ upvotes)
3. Rewrite with Gemini → Professional paragraph style
4. Select Pexels image → "AI technology"
5. Preview final post
6. Publish to LinkedIn ✅
```

---

### 📢 Marketing Outreach AI

**Intelligent B2B marketing automation with AI-powered personalization**

#### Key Features

**1. Company Discovery**

- 🔍 **SerpApi Integration**: Search companies on Indiamart, TradeIndia, Zaubacorp
- 🏢 Automatic company information extraction
- 📧 Email and phone number detection
- 🏭 Industry classification
- 📊 Bulk company data aggregation

**2. AI-Powered Email Generation**

- 🤖 **Gemini AI**: Generate personalized outreach emails
- 🎯 Context-aware messaging based on industry
- 📝 Custom company profile input
- 💼 Professional tone and formatting
- ✨ Unique value propositions

**3. Company Profile Management**

- ✏️ Configure your company details
- 🎯 Set key differentiators
- 📦 Define products/services
- 👤 Contact person information
- 🔄 Reusable profiles

**4. Email Campaign Management**

- 📤 Send emails directly from dashboard
- 📊 Track sent campaigns
- 📧 SMTP integration
- 🔄 Batch processing
- ✅ Delivery confirmation

#### Workflow Example

```
1. Set Company Profile → "Tech Solutions Inc."
2. Search Companies → "plastic manufacturing"
3. AI generates email for each company
4. Review and customize
5. Send bulk outreach campaign ✅
```

---

### 📦 Procurement AI

**Automated RFQ management with intelligent quote analysis**

#### Key Features

**1. Procurement Request Management**

- 📝 Create detailed RFQs (Request for Quotations)
- 📊 Product specifications and quantities
- 📅 Delivery requirements
- 💰 Budget constraints
- 🏢 Multi-supplier management

**2. Intelligent Supplier Discovery**

- 🔍 **Web Scraping**: Automated supplier search
- 🌐 Indiamart, TradeIndia integration
- 📧 Contact extraction
- 🏭 Industry-specific filtering
- 💾 Master vendor database

**3. Automated RFQ Distribution**

- 📧 **Email Integration**: Send RFQs to multiple suppliers
- 📎 Attachment support
- 📋 Professional email templates
- 🔄 Bulk sending
- ✅ Delivery tracking

**4. Quote Collection & Processing**

- 📥 **IMAP Integration**: Automatically receive quotes via email
- 📄 **PDF Extraction**: Parse quote documents
- 🤖 **AI Analysis**: Extract pricing, terms, lead times
- 📊 Structured quote database
- 🔍 Duplicate detection

**5. AI-Powered Quote Comparison**

- 💰 **Smart Scoring Algorithm**:
  - Price comparison
  - Lead time penalties
  - Payment terms evaluation
  - Missing field penalties
- 📊 Side-by-side comparison view
- 🏆 Automatic best quote selection
- 📈 Visual score breakdown

**6. Benchmark Price Analysis**

- 🤖 **Gemini AI**: Estimate market prices
- 📊 Compare quotes vs market rates
- 💡 Identify overpriced quotes
- 📈 Historical price tracking

**7. Quote Approval Workflow**

- ✅ Review and approve quotes
- 📧 Generate purchase orders
- 📤 Send to suppliers
- 📊 Procurement analytics
- 📜 Complete audit trail

**8. Advanced Features**

- 📤 Manual quote upload
- 📑 CSV export/import
- 📊 Dashboard analytics
- 🔔 Email notifications
- 📈 Supplier performance tracking

#### Workflow Example

```
1. Create RFQ → "1000 plastic containers"
2. System finds 15 suppliers automatically
3. Send RFQs to all suppliers
4. Quotes arrive via email (automated)
5. AI extracts and scores all quotes
6. Review comparison dashboard
7. Approve best quote
8. Generate purchase order ✅
```

---

## 🛠️ Tech Stack

### Backend

- **Framework**: Django 6.0+
- **Database**: SQLite (default) / PostgreSQL (production)
- **API**: Django REST principles
- **Authentication**: Django Auth System

### AI & Machine Learning

- **Google Gemini AI**: Content generation, price analysis
- **Natural Language Processing**: Email generation, text extraction

### External APIs

- **PRAW (Python Reddit API Wrapper)**: Reddit integration
- **SerpApi**: Google search, company discovery
- **LinkedIn API**: Post publishing, profile search
- **Pexels API**: Stock photos
- **Giphy API**: GIF search

### Document Processing

- **PyPDF2**: PDF extraction
- **PDFPlumber**: Advanced PDF parsing
- **PDFMiner**: Text mining
- **PyMuPDF**: Document processing
- **Pytesseract**: OCR capabilities

### Web Scraping

- **Playwright**: Browser automation
- **BeautifulSoup4**: HTML parsing
- **HTTPX**: Async HTTP requests

### Frontend

- **HTML5/CSS3**: Modern responsive design
- **JavaScript**: Vanilla JS with async/await
- **Gradient UI**: Custom neon-style interface

### Email Integration

- **SMTP**: Sending emails (Gmail, custom)
- **IMAP**: Receiving emails
- **Email Parser**: Quote extraction

### Other Libraries

- **Google Sheets API**: Data export
- **Pillow**: Image processing
- **Requests**: HTTP client
- **Python-dotenv**: Environment management

---

## 📥 Installation

### Prerequisites

```bash
Python 3.8+
pip (Python package manager)
Virtual environment (recommended)
```

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/kaliagents.git
cd kaliagents
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Environment Configuration

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` with your API keys (see [Configuration](#-configuration))

### Step 5: Database Setup

```bash
# Run migrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser
# Username: kalisoft
# Password: kalisoft309 (or your choice)
```

### Step 6: Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### Step 7: Run Development Server

```bash
python manage.py runserver
```

Visit: `http://127.0.0.1:8000/`

---

## ⚙️ Configuration

### Required API Keys

Edit `.env` file with your credentials:

```bash
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True

# Database (Optional - uses SQLite by default)
DB_NAME=kaliagents_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

# Google Gemini AI (Required for AI features)
GEMINI_API_KEY=your_gemini_api_key_here

# Reddit API (Required for LinkedIn AI)
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=Kaliagents/1.0

# LinkedIn API (Required for LinkedIn AI)
LINKEDIN_ACCESS_TOKEN=your_linkedin_access_token
LINKEDIN_AUTHOR_ID=urn:li:person:YOUR_PERSON_ID

# Pexels API (Optional - for images)
PEXELS_API_KEY=your_pexels_api_key

# Giphy API (Optional - for GIFs)
GIPHY_API_KEY=your_giphy_api_key

# SerpAPI (Required for Marketing & Procurement)
SERPAPI_API_KEY=your_serpapi_key_here

# Email Configuration (Required for Procurement)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_gmail_app_password
DEFAULT_FROM_EMAIL=your_email@gmail.com

# Email Reading (IMAP - Required for Procurement)
GMAIL_IMAP_HOST=imap.gmail.com
GMAIL_ADDRESS=your_email@gmail.com
GMAIL_APP_PASSWORD=your_gmail_app_password
```

### How to Get API Keys

#### 1. Google Gemini AI

```
1. Visit: https://makersuite.google.com/app/apikey
2. Sign in with Google account
3. Click "Create API Key"
4. Copy and paste into .env
```

#### 2. Reddit API

```
1. Visit: https://www.reddit.com/prefs/apps
2. Click "Create App" or "Create Another App"
3. Select "script" type
4. Fill in details, get client_id and client_secret
```

#### 3. LinkedIn API

```
1. Visit: https://www.linkedin.com/developers/apps
2. Create an app
3. Get OAuth 2.0 credentials
4. Obtain access token via OAuth flow
```

#### 4. SerpApi

```
1. Visit: https://serpapi.com/
2. Sign up for free account
3. Get API key from dashboard
```

#### 5. Pexels & Giphy

```
Pexels: https://www.pexels.com/api/
Giphy: https://developers.giphy.com/
```

#### 6. Gmail App Password

```
1. Enable 2-Factor Authentication
2. Visit: https://myaccount.google.com/apppasswords
3. Generate app-specific password
```

---

## 📖 Usage

### Quick Start

1. **Login**: Visit `http://127.0.0.1:8000/` and login with credentials
   - Default admin: `kalisoft` / `kalisoft309`

2. **Agent Selection**: Choose from three AI agents on the dashboard

3. **LinkedIn Automation**:

   ```
   Dashboard → Search Reddit → Select Post → Rewrite with AI →
   Select Image → Post to LinkedIn
   ```

4. **Marketing Outreach**:

   ```
   Dashboard → Set Company Profile → Search Companies →
   Generate Emails → Send Campaign
   ```

5. **Procurement**:
   ```
   Dashboard → Create RFQ → Find Suppliers → Send RFQs →
   Collect Quotes → Compare & Approve
   ```

### Common Tasks

#### LinkedIn: Schedule Content

```python
# Search trending content
keyword = "AI trends"
posts = reddit_search(keyword, limit=10)

# AI rewrite
rewritten = gemini_rewrite(posts[0], style="paragraph")

# Select image
image = pexels_search("artificial intelligence")

# Post to LinkedIn
linkedin_post(content=rewritten, image=image)
```

#### Marketing: Send Bulk Emails

```python
# Find companies
companies = serpapi_search("plastic manufacturers")

# Generate personalized emails
for company in companies:
    email = gemini_generate_email(company, your_profile)
    send_email(company.email, email)
```

#### Procurement: Automate RFQ

```python
# Create RFQ
rfq = create_rfq(product="Plastic Containers", quantity=1000)

# Find suppliers
suppliers = scrape_suppliers(rfq.product)

# Send RFQs
send_rfqs(rfq, suppliers)

# Collect & compare quotes (automated)
quotes = collect_quotes_from_email()
best_quote = ai_compare_quotes(quotes)
```

---

## 🔌 API Integrations

### Webhook Support

The platform supports webhook integrations for:

- Quote submissions
- Email notifications
- Real-time updates

### REST API (Optional)

You can extend with Django REST Framework for:

- Mobile app integration
- Third-party integrations
- API-first architecture

---

## 📁 Project Structure

```
Kaliagents/
├── core/                          # Core app (auth, agent selector)
│   ├── templates/core/
│   │   ├── agent_selector.html   # Main agent dashboard
│   │   ├── login.html
│   │   └── register.html
│   ├── views.py
│   └── urls.py
│
├── linkedin_automation/           # LinkedIn AI Agent
│   ├── templates/linkedin_automation/
│   │   ├── main.html             # Main dashboard
│   │   ├── history.html          # Post history
│   │   ├── pdf_to_post.html      # PDF converter
│   │   ├── combine_sources.html  # Multi-source
│   │   ├── finder.html           # Profile finder
│   │   └── saved_profiles.html   # Lead management
│   ├── models.py                 # RedditPost, LinkedInPost, etc.
│   ├── services.py               # API integrations
│   ├── views.py                  # View logic
│   └── pdf_views.py              # PDF processing
│
├── marketing_outreach/            # Marketing AI Agent
│   ├── templates/marketing_outreach/
│   │   ├── dashboard.html        # Search & campaign
│   │   └── settings.html         # Company profile
│   ├── views.py
│   └── urls.py
│
├── procurement/                   # Procurement AI Agent
│   ├── templates/procurement/
│   │   ├── dashboard.html        # Main dashboard
│   │   ├── create_request.html   # RFQ creation
│   │   ├── view_request.html     # RFQ details
│   │   ├── compare_quotes.html   # Quote comparison
│   │   ├── suppliers.html        # Supplier management
│   │   └── analytics.html        # Procurement analytics
│   ├── models.py                 # ProcurementRequest, Quote, etc.
│   ├── utils.py                  # Helper functions
│   ├── views.py                  # 1000+ lines of logic
│   └── urls.py
│
├── static/                        # Static assets
├── media/                         # User uploads
├── requirements.txt              # Python dependencies
├── manage.py                     # Django management
├── .env                          # Environment variables
└── README.md                     # This file
```

---

## 📸 Screenshots

### Agent Selection Dashboard

> Unified dashboard for selecting AI agents

### LinkedIn Automation

> Reddit sourcing → AI rewriting → Image selection → LinkedIn posting

### Marketing Outreach

> Company search → AI email generation → Bulk campaigns

### Procurement Management

> RFQ creation → Quote collection → AI comparison → Approval

_(Add actual screenshots here)_

---

## 🤝 Contributing

We welcome contributions! Here's how:

### 1. Fork the Repository

```bash
git clone https://github.com/yourusername/kaliagents.git
```

### 2. Create Feature Branch

```bash
git checkout -b feature/amazing-feature
```

### 3. Commit Changes

```bash
git commit -m 'Add amazing feature'
```

### 4. Push to Branch

```bash
git push origin feature/amazing-feature
```

### 5. Open Pull Request

### Guidelines

- Follow PEP 8 style guide
- Add tests for new features
- Update documentation
- Comment complex logic

---

## 🐛 Known Issues & Troubleshooting

### Issue: LinkedIn API Rate Limits

**Solution**: Implement exponential backoff, cache tokens

### Issue: Email IMAP Connection Fails

**Solution**: Enable "Less secure app access" or use App Password

### Issue: PDF Extraction Errors

**Solution**: Install system dependencies (Tesseract, Poppler)

### Issue: Gemini AI Quota Exceeded

**Solution**: Implement request throttling, upgrade API plan

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👥 Authors

**Kalisoft Team**

- LinkedIn: [Your LinkedIn](https://linkedin.com/in/yourprofile)
- Email: kalisoft@example.com

---

## 🙏 Acknowledgments

- Google Gemini AI for content generation
- Reddit community for quality content sources
- Django community for excellent framework
- All API providers (Pexels, Giphy, SerpApi, etc.)

---

## 📞 Support

For issues, questions, or feature requests:

- 📧 Email: support@kaliagents.com
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/kaliagents/issues)
- 💬 Discord: [Join our community](https://discord.gg/yourlink)

---

## 🚀 Future Roadmap

### Version 2.0

- [ ] AI Agent for Customer Support
- [ ] WhatsApp Business Integration
- [ ] Advanced Analytics Dashboard
- [ ] Multi-language Support
- [ ] Mobile App (React Native)
- [ ] Docker Deployment
- [ ] CI/CD Pipeline
- [ ] Kubernetes Orchestration

### AI Enhancements

- [ ] GPT-4 Integration
- [ ] Custom AI Model Training
- [ ] Sentiment Analysis
- [ ] Predictive Analytics

---

## ⭐ Star History

If you find this project useful, please consider giving it a star! ⭐

---

<div align="center">

**Built with ❤️ by Kalisoft**

[Website](https://kaliagents.com) • [Documentation](https://docs.kaliagents.com) • [Demo](https://demo.kaliagents.com)

</div>
