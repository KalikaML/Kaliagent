Kaliagent: A Multi-Agent AI System for Business Automation
Welcome to Kaliagent, a sophisticated, multi-agent AI system designed to streamline and automate critical business operations across sales, marketing, procurement, and content creation. Each agent is a specialized workflow that leverages cutting-edge AI models like Google's Gemini, vector databases, and various APIs to enhance efficiency, reduce manual effort, and drive intelligent decision-making.

🏛️ High-Level System Architecture
This diagram provides a holistic view of how the different Kaliagents interact with data sources, core services, and end-users to create a cohesive automation ecosystem.

graph TD
    subgraph "External Data & APIs"
        direction LR
        A1[Gmail API]
        A2[Indiamart]
        A3[Supplier Websites]
        A4[SearxNG / SerpAPI]
        A5[YouTube API]
    end

    subgraph "Core Kaliagent Services"
        B1[Gemini AI Models]
        B2[FAISS Vector Index]
        B3[Database (Postgres/MySQL)]
        B4[AWS S3 Storage]
        B5[MoviePy Engine]
    end

    subgraph "Kaliagent Agents"
        C1[1. Sales PO Processing]
        C2[2. Marketing Lead Generation]
        C3[3. Procurement Supplier Discovery]
        C4[4. E-commerce Ad Generation]
        C5[5. Cinematic Video Creator]
        C6[6. YouTube Shorts Automator]
    end

    subgraph "End-Users & Interfaces"
        D1[Sales Team UI]
        D2[Marketing Team UI]
        D3[Purchase Team UI]
        D4[E-commerce Website]
        D5[Content Team Web UI]
    end

    A1 --> C1
    A2 & A3 & A4 --> C3
    A4 --> C2
    A5 --> C6

    C1 & C2 & C3 & C4 & C5 & C6 <--> B1
    C1 <--> B2
    C1 & C3 --> B3
    C4 & C5 & C6 --> B4
    C5 <--> B5

    C1 --> D1
    C2 --> D2
    C3 --> D3
    C4 --> D4
    C5 & C6 --> D5

🕵️‍♂️ Agent 1: Sales Team Purchase Order (PO) Automation
This agent automates the entire lifecycle of processing purchase orders received via email, from data extraction to inventory checking and internal communication.

Architecture
graph TD
    A[Gmail API] -- Fetches Emails with PDFs --> B(PDF Parser);
    B -- Extracts Raw Text --> C(FAISS Vector Index);
    C -- Creates & Stores Text Vectors --> D(Gemini AI Model);
    D -- 1. Extracts Structured PO Data <br> (Order ID, Items, Qty) --> E[Database];
    E -- Stores PO Details --> F(Role-Based UI);
    F -- Displays PO Info to Sales/Stock Team --> G{Check Stock System};
    D -- 2. Analyzes Items for Raw Materials --> G;
    G -- Queries Inventory --> H{Material Available?};
    H -- Yes --> I[Update UI: "Material Available"];
    H -- No --> J[Drafts Request to Purchase Manager];
    J -- Sends Internal Alert/Email --> K(Purchase Manager);

Process Flow
Email Ingestion: The agent continuously monitors a dedicated Gmail inbox for emails containing keywords like "Purchase Order" and attachments (PDFs).

Data Extraction: When a PO PDF is detected, it's parsed to extract raw text. This text is then converted into a numerical vector and stored in a FAISS index for efficient similarity searching.

Intelligent Analysis: Gemini processes the extracted text to identify and structure key information: Order ID, customer details, a list of items and quantities, and required raw materials.

Database Storage: The structured PO data is saved to a central database.

Role-Based UI: A web interface provides different views based on user roles (e.g., Sales, Inventory). The sales team sees the order status, while the inventory team sees the material requirements.

Automated Inventory Check: The agent automatically checks the internal stock system for the availability of required raw materials.

Status Update & Escalation:

If materials are available, the UI is updated with an estimated availability time.

If materials are unavailable, Gemini drafts a pre-filled request to the purchase manager, detailing the required items, which can be sent via an internal messaging system or email.

🎯 Agent 2: B2B Marketing Lead Generation
This agent automates the discovery of potential new clients, finds contact information for key personnel, and drafts personalized outreach emails.

Architecture
graph TD
    A[Internal Data <br> (Existing Clients, Product Info)] --> B(Gemini AI Model);
    B -- Generates Search Queries --> C(SearxNG / SerpAPI);
    C -- Finds Similar Companies --> D[Company List];
    D -- For Each Company --> E{Scrape Website & LinkedIn};
    E -- Extracts Contact Person Details --> F[Contact Info <br> (Name, Email)];
    F --> G(Gemini AI Model);
    A --> G;
    G -- Drafts Personalized Email <br> (using company/product info) --> H(Marketing Team UI);
    H -- Displays Draft for Review & Send --> I[Potential Client];

Process Flow
Ideal Customer Profiling: The agent analyzes data on existing successful clients and the company's product catalog to create a profile of an ideal new customer.

Company Discovery: Using this profile, Gemini generates strategic search queries. SearxNG and SerpAPI execute these queries to find companies that match the profile (e.g., "plastic moulding companies in North America").

Contact Extraction: For each identified company, the agent scrapes the official website or uses LinkedIn search to find contact information for relevant roles (e.g., "Purchasing Manager," "Head of Procurement").

Personalized Email Drafting: With the contact details secured, Gemini drafts a highly personalized and engaging email. The draft incorporates:

The prospect's company name and potential needs.

Information about our company's products that are relevant to them.

A compelling call-to-action.

Human-in-the-Loop: The drafted email is presented in a UI for the marketing team to review, edit if necessary, and send.

🤝 Agent 3: Automated Procurement & Supplier Discovery
This agent transforms the tedious process of finding and vetting new suppliers into an automated workflow, from discovery to quotation request.

Architecture
graph TD
    A[Product Requirement Input] --> B{Check Existing Supplier Database};
    B -- Found --> C{Product in Supplier's Catalog?};
    C -- Yes --> D(Gemini AI: Draft Quotation Request);
    D --> E[Send Email to Existing Supplier];
    B -- Not Found --> F(SearxNG / SerpAPI);
    C -- No --> F;
    F -- Finds New Potential Suppliers --> G[Supplier List from Indiamart/Websites];
    G -- For Each New Supplier --> H{Scrape Website/Indiamart Page};
    H -- Extracts Product Info & Contact Details --> I(Gemini AI: Draft Intro & Quote Request);
    I --> J[Send Email to New Supplier];

Process Flow
Requirement Input: A new product requirement is entered into the system.

Existing Supplier Check: The agent first searches its internal database of existing suppliers and their product catalogs.

Automated Quotation Request (Existing Supplier): If a current supplier offers the required product, Gemini drafts and sends a standardized email requesting a quotation, availability, and delivery timelines.

New Supplier Discovery: If no existing supplier is found, the agent uses SearxNG and SerpAPI to find new suppliers on platforms like Indiamart and Google.

Information Gathering: It scrapes the websites of potential new suppliers to confirm they offer the relevant products and to find contact information.

Automated Outreach (New Supplier): For promising new suppliers, Gemini drafts a more detailed introductory email that explains our company's needs and requests a formal quotation.

📢 Agent 4: E-commerce Ad Generation for B2B Suppliers
This agent creates a pipeline for your B2B suppliers to advertise their products on your e-commerce website, complete with a Proof-of-Concept (POC) generator.

Architecture
graph TD
    A[Supplier's Product Data <br> (Images, Descriptions)] --> B(Gemini AI Model);
    B -- Analyzes Product & Benefits --> C{Generate Ad Copy & Visual Concepts};
    C --> D(POC Generator);
    A --> D;
    subgraph "Proof of Concept (POC)"
        D -- Creates Mockup Ad --> E[Sample Ad on E-commerce Site];
    end
    E --> F(Supplier-Facing UI);
    F -- Shows POC & Explains Benefits --> G{Supplier Uploads Final Assets};
    G -- Product Images, Brand Guidelines --> H(Ad Pipeline);
    H -- Creates Final Ad --> I[Display on E-commerce Website];

Process Flow
POC Generation: To entice suppliers, the agent first creates a Proof-of-Concept. It takes a sample product from a supplier and uses Gemini to generate compelling ad copy and suggest design layouts.

Supplier Pitch: The POC ad is presented to the supplier through a dedicated portal, showcasing how their products would look on your e-commerce site and explaining the benefits (e.g., increased visibility, direct access to buyers).

Asset Collection: Convinced suppliers can then use the portal to upload their official product images, logos, and brand guidelines.

End-to-End Ad Pipeline: Once assets are uploaded, the agent uses pre-defined templates and AI-driven design principles to automatically generate high-quality ads.

Deployment: The finalized ads are then deployed across strategic locations on your B2B e-commerce website, such as the homepage, category pages, or in checkout recommendations.

🎬 Agent 5: Image to Cinematic Video Creation
A creative agent that transforms a collection of still images into a polished, cinematic video with music, captions, and professional transitions.

Architecture
graph TD
    subgraph "Web UI"
        A[User Uploads Multiple Images] --> B;
        B[User Uploads Music or Provides URL] --> C;
    end
    C --> D(Gemini AI Model);
    A --> D;
    D -- Generates Contextual Captions for Each Image --> E[Image & Caption Pairs];
    E --> F(MoviePy Engine);
    B --> F;
    F -- 1. Adds Captions to Images <br> 2. Applies Fade Transitions <br> 3. Synchronizes with Music --> G[Final Video File];
    G -- Uploads Video --> H(AWS S3 Bucket);
    H -- Provides Secure Download/Stream URL --> I(Web UI);

Process Flow
Asset Upload: Users upload a series of images in their desired sequence and provide a music track via upload or a link.

AI Captioning: Gemini analyzes each image to understand its content and context, then generates a relevant and engaging caption for it.

Video Assembly: The MoviePy engine takes over and performs the following tasks:

Overlays the generated captions onto each image.

Creates smooth fade-in/fade-out transitions between images.

Arranges the image sequence and synchronizes it to the length of the provided music track.

Cloud Storage & Delivery: The final rendered video is automatically uploaded to a secure AWS S3 bucket.

Access: The user receives a direct link to view, download, or share the finished cinematic video.

🔥 Agent 6: Automated YouTube Shorts Generation
This agent automates the creation of viral, engaging YouTube Shorts by intelligently identifying the best moments from longer videos.

Architecture
graph TD
    A[User Provides YouTube URL] --> B(YouTube Downloader);
    B -- Downloads Full Video & Subtitles --> C(Gemini AI Model);
    C -- Analyzes Transcript & Visuals for "Hook" Moments --> D[Identifies Top 3-5 Clips];
    D -- Sends Clip Timestamps --> E(Video Processing Engine);
    B --> E;
    E -- 1. Extracts Clips <br> 2. Auto-Resizes to 9:16 <br> 3. Burns in Subtitles --> F[Generated YouTube Shorts];
    F -- Uploads to Cloud --> G(AWS S3 Bucket);
    G -- Provides Download Links --> H(Centralized Web UI);
    H -- Shows Progress & Links to Finished Shorts --> I[Content Manager];

Process Flow
Source Input: A user provides a link to a longer YouTube video.

Content Retrieval: The system downloads the full video and its corresponding subtitles/transcript.

AI Clip Detection: Gemini analyzes the transcript to identify the most engaging parts of the video—moments with emotional peaks, key questions, or powerful statements that would make a great "hook" for a short.

Automated Editing: The video processing engine uses the timestamps identified by Gemini to:

Extract these short segments (15-60 seconds).

Automatically crop and rescale the video to a vertical (9:16) aspect ratio.

Burn the subtitles directly onto the video for better engagement.

Cloud Upload and Management: The generated Shorts are uploaded to AWS S3. A centralized web UI allows content managers to track the progress of video creation and access the finished files for easy publishing.
