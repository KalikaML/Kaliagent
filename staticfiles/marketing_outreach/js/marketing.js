document.addEventListener('DOMContentLoaded', () => {

    const searchInput = document.getElementById('search-input');
    const companyListEl = document.getElementById('company-list');
    const detailsPanelEl = document.getElementById('details-panel');
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    let selectedCompany = null;
    let contactInfo = null; // This will store the extracted contact info for the email generator
    let searchTimeout;

    // --- API & DATA HANDLING ---

    const performSearch = async () => {
        const query = searchInput.value.trim();
        if (query.length < 3) {
            companyListEl.innerHTML = `<div class="text-center py-10 text-slate-500"><p>Enter at least 3 characters to search.</p></div>`;
            return;
        }
        
        companyListEl.innerHTML = `<div class="text-center py-10 text-slate-500 animate-pulse"><p>Searching for companies and contacts...</p></div>`;
        detailsPanelEl.innerHTML = ''; // Clear details panel during search

        try {
            const response = await fetch(`/marketing/api/search-companies/?q=${encodeURIComponent(query)}`);
            if (!response.ok) throw new Error('Network response was not ok.');
            
            const data = await response.json();
            renderCompanyList(data.companies);
        } catch (error) {
            console.error('Search failed:', error);
            companyListEl.innerHTML = `<div class="text-center py-10 text-red-400"><p>Could not perform search. Please try again.</p></div>`;
        }
    };

    const findContactInfo = () => {
        const btn = document.getElementById('find-contact-btn');
        const container = document.getElementById('contact-info-container');
        if (!btn || !container || !selectedCompany) return;
        
        btn.disabled = true;
        btn.innerHTML = 'Extracting...';

        // Simulate a delay to preserve the feel of an action happening
        setTimeout(() => {
            // The contact info is already in the selectedCompany object from the backend.
            // We just format and reveal it here.
            contactInfo = {
                name: 'Contact', // Name is hard to find, so we use a generic title
                title: 'Relevant Person',
                email: selectedCompany.email,
                phone: selectedCompany.phone,
            };

            container.innerHTML = `
                <div class="p-4 bg-slate-700/50 rounded-lg space-y-2 text-sm animate-fade-in">
                    <p class="flex items-center text-slate-400">Email: <strong class="ml-2 text-white">${contactInfo.email}</strong></p>
                    <p class="flex items-center text-slate-400">Phone: <strong class="ml-2 text-white">${contactInfo.phone}</strong></p>
                </div>`;
            btn.innerHTML = 'Contact Found';
            
            // Enable the "Generate Email" button
            const generateBtn = document.getElementById('generate-email-btn');
            const generateHeader = document.getElementById('draft-email-header');
            const generatePrompt = document.getElementById('generate-email-prompt');

            if (generateBtn) {
                generateBtn.disabled = false;
                generateHeader.classList.remove('text-slate-500');
                generateHeader.classList.add('text-white');
                if(generatePrompt) generatePrompt.classList.add('hidden');
            }
        }, 1000); // 1-second simulated delay
    };

    const generateEmail = async () => {
        if (!selectedCompany || !contactInfo) return;

        const generateBtn = document.getElementById('generate-email-btn');
        const mailContainer = document.getElementById('mail-container');
        if (!generateBtn || !mailContainer) return;
        
        generateBtn.disabled = true;
        generateBtn.innerHTML = 'Generating...';
        mailContainer.innerHTML = `<div class="text-center py-8"><p class="text-slate-400 animate-pulse">🤖 AI agent is drafting your email...</p></div>`;
        mailContainer.classList.remove('hidden');

        try {
            const response = await fetch(`/marketing/api/generate-email/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                // Pass the full company object, which now includes contact info
                body: JSON.stringify({ company: selectedCompany }),
            });

            const data = await response.json();
            if (response.ok) {
                renderGeneratedEmail(data.email);
            } else {
                 throw new Error(data.error || 'Email generation failed.');
            }

        } catch (error) {
            console.error('Email generation error:', error);
            mailContainer.innerHTML = `<div class="text-center py-8 text-red-400"><p>An error occurred: ${error.message}</p></div>`;
        } finally {
            generateBtn.disabled = false;
            generateBtn.innerHTML = 'Generate Email';
        }
    };

    // --- UI RENDERING ---

    const renderCompanyList = (companies) => {
        if (!companies || companies.length === 0) {
            companyListEl.innerHTML = `<div class="text-center py-10 text-slate-500"><p>No relevant companies found. Try a different search term.</p></div>`;
            return;
        }

        companyListEl.innerHTML = companies.map(company => `
            <div class="p-4 rounded-lg cursor-pointer transition-all duration-200 bg-slate-800 hover:bg-slate-700/50 company-card" 
                 data-company='${JSON.stringify(company)}'>
                <h3 class="font-semibold text-white w-full truncate pointer-events-none">${company.name}</h3>
                <p class="text-sm text-cyan-400 pointer-events-none">${company.industry}</p>
            </div>
        `).join('');
    };

    const renderSelectedCompany = () => {
        if (!selectedCompany) {
            detailsPanelEl.innerHTML = `<div class="flex-1 flex items-center justify-center text-center text-slate-500"><div><svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" class="mx-auto mb-4"><path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/><path d="M12 20h4"/><path d="M4 20h4"/><path d="M12 4h- miljø"/><rect width="4" height="4" x="8" y="12"/></svg><h2 class="text-xl font-semibold text-slate-400">Select a company to view details</h2></div></div>`;
            return;
        }

        detailsPanelEl.innerHTML = `
            <div class="flex-1 flex flex-col">
                <div class="p-6 border-b border-slate-700">
                    <h2 class="text-2xl font-bold text-white mb-1">${selectedCompany.name}</h2>
                    <p class="text-cyan-400 mb-4">${selectedCompany.industry}</p>
                    <p class="text-slate-300 text-sm">${selectedCompany.description}</p>
                </div>
                <div class="p-6 flex-1">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div class="bg-slate-800/50 p-6 rounded-xl">
                            <h3 class="text-lg font-semibold text-white mb-4">1. Find Contact Details</h3>
                            <button id="find-contact-btn" class="w-full bg-cyan-500 text-white font-semibold py-2.5 rounded-lg hover:bg-cyan-600 transition-colors">
                                Extract Contact Info
                            </button>
                            <div id="contact-info-container" class="mt-4"></div>
                        </div>
                        <div class="bg-slate-800/50 p-6 rounded-xl">
                            <h3 id="draft-email-header" class="text-lg font-semibold text-slate-500 mb-4">2. Draft Email with AI</h3>
                            <button id="generate-email-btn" disabled class="w-full bg-cyan-500 text-white font-semibold py-2.5 rounded-lg hover:bg-cyan-600 transition-colors disabled:bg-slate-600 disabled:cursor-not-allowed">
                                Generate Email
                            </button>
                            <p id="generate-email-prompt" class="text-xs text-center text-slate-500 mt-2">Please extract contact info first.</p>
                        </div>
                    </div>
                    <div id="mail-container" class="mt-6 bg-slate-800/50 p-6 rounded-xl hidden animate-fade-in"></div>
                </div>
            </div>`;
        
        document.getElementById('find-contact-btn').addEventListener('click', findContactInfo);
        document.getElementById('generate-email-btn').addEventListener('click', generateEmail);
    };
    
    const renderGeneratedEmail = (emailText) => {
        const mailContainer = document.getElementById('mail-container');
        if (!mailContainer) return;
        
        const [subjectLine, ...bodyParts] = emailText.replace(/^Subject: /i, '').split('\n\n');
        const bodyHtml = bodyParts.map(p => `<p>${p}</p>`).join('');

        mailContainer.innerHTML = `
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-lg font-semibold text-white">Generated Email Draft</h3>
                <button id="copy-email-btn" class="flex items-center text-sm bg-slate-700 hover:bg-slate-600 text-slate-300 font-semibold py-1 px-3 rounded-lg transition-colors">Copy</button>
            </div>
            <div id="mail-content-wrapper" class="prose prose-sm prose-invert max-w-none prose-p:text-slate-300 prose-h3:text-white">
                <h3 id="email-subject">${subjectLine}</h3>
                <div id="email-body">${bodyHtml}</div>
            </div>`;
        
        document.getElementById('copy-email-btn').addEventListener('click', handleCopyToClipboard);
    };
    
    const handleCopyToClipboard = () => {
        const subject = document.getElementById('email-subject')?.innerText;
        const body = document.getElementById('email-body')?.innerText;
        const btn = document.getElementById('copy-email-btn');
        if (!subject || !body || !btn) return;
        
        const fullEmailText = `Subject: ${subject}\n\n${body}`;
        navigator.clipboard.writeText(fullEmailText).then(() => {
            btn.innerHTML = 'Copied!';
            setTimeout(() => { btn.innerHTML = 'Copy'; }, 2000);
        });
    };

    // --- EVENT LISTENERS ---
    searchInput.addEventListener('keyup', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => { performSearch(); }, 500);
    });

    companyListEl.addEventListener('click', (e) => {
        const card = e.target.closest('.company-card');
        if (!card) return;

        document.querySelectorAll('.company-card').forEach(c => c.classList.remove('bg-cyan-500/20', 'ring-2', 'ring-cyan-500'));
        card.classList.add('bg-cyan-500/20', 'ring-2', 'ring-cyan-500');

        selectedCompany = JSON.parse(card.dataset.company);
        contactInfo = null;
        renderSelectedCompany();
    });
});