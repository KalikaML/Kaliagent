document.addEventListener('DOMContentLoaded', () => {

    // --- DOM Elements ---
    const searchInput = document.getElementById('search-input');
    const companyListEl = document.getElementById('company-list');
    const companyListLoader = document.getElementById('company-list-loader');
    const detailsPanelEl = document.getElementById('details-panel');
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    // --- State ---
    let selectedCompany = null;
    let searchTimeout;

    // --- ICONS ---
    const SPINNER_ICON = `<svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>`;
    const COPY_ICON = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`;
    const CHECK_ICON = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" class="text-green-400"><path d="M20 6 9 17l-5-5"/></svg>`;

    // --- UTILITY ---
    const escapeHTML = (str) => String(str).replace(/[&<>"']/g, (match) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[match]));

    // --- API & DATA HANDLING ---

    const performSearch = async () => {
        const query = searchInput.value.trim();
        if (query.length < 3) {
            companyListEl.innerHTML = `<div class="text-center py-10 text-slate-500"><p>Enter at least 3 characters to search.</p></div>`;
            return;
        }
        
        companyListEl.style.display = 'none';
        companyListLoader.style.display = 'block';
        detailsPanelEl.innerHTML = getInitialDetailsPanelHTML();

        try {
            const response = await fetch(`/marketing/api/search-companies/?q=${encodeURIComponent(query)}`);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Network response was not ok.');
            }
            
            const data = await response.json();
            renderCompanyList(data.companies);
        } catch (error) {
            console.error('Search failed:', error);
            companyListEl.innerHTML = `<div class="text-center py-10 text-red-400"><p><strong>Search Failed</strong></p><p class="text-sm">${error.message}</p></div>`;
        } finally {
            companyListLoader.style.display = 'none';
            companyListEl.style.display = 'block';
        }
    };

    const generateEmail = async () => {
        if (!selectedCompany) return;

        const generateBtn = document.getElementById('generate-email-btn');
        const mailContainer = document.getElementById('mail-container');
        if (!generateBtn || !mailContainer) return;
        
        generateBtn.disabled = true;
        generateBtn.innerHTML = `${SPINNER_ICON} Generating...`;
        mailContainer.innerHTML = `<div class="text-center py-8"><p class="text-slate-400 animate-pulse">🤖 AI agent is drafting your email...</p></div>`;
        mailContainer.classList.remove('hidden');

        try {
            const response = await fetch(`/marketing/api/generate-email/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ company: selectedCompany }),
            });

            const data = await response.json();
            if (!response.ok) {
                 throw new Error(data.error || 'Email generation failed.');
            }
            renderGeneratedEmail(data.email);

        } catch (error) {
            console.error('Email generation error:', error);
            mailContainer.innerHTML = `<div class="text-center py-8 text-red-400"><p><strong>An error occurred:</strong></p><p class="text-sm">${error.message}</p></div>`;
        } finally {
            generateBtn.disabled = false;
            generateBtn.innerHTML = 'Generate Email Again';
        }
    };

    // --- UI RENDERING ---

    const getInitialDetailsPanelHTML = () => `
        <div class="flex-1 flex items-center justify-center text-center text-slate-500 p-4">
            <div>
                <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" class="mx-auto mb-4 text-slate-600"><path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/><path d="M12 20h4"/><path d="M4 20h4"/><path d="M12 4h-4"/><rect width="4" height="4" x="8" y="12"/></svg>
                <h2 class="text-xl font-semibold text-slate-400">Select a company to view details</h2>
                <p>Search for potential clients and see their information here.</p>
            </div>
        </div>`;

    const renderCompanyList = (companies) => {
        if (!companies || companies.length === 0) {
            companyListEl.innerHTML = `<div class="text-center py-10 text-slate-500"><p>No relevant companies found. Try a different search term.</p></div>`;
            return;
        }

        companyListEl.innerHTML = companies.map(company => `
            <div class="p-4 rounded-lg cursor-pointer transition-all duration-200 bg-slate-800 hover:bg-slate-700/50 company-card" 
                 data-company='${escapeHTML(JSON.stringify(company))}'>
                <h3 class="font-semibold text-white w-full truncate pointer-events-none">${escapeHTML(company.name)}</h3>
                <p class="text-sm text-cyan-400 pointer-events-none">${escapeHTML(company.industry)}</p>
            </div>
        `).join('');
    };

    const renderSelectedCompany = () => {
        if (!selectedCompany) {
            detailsPanelEl.innerHTML = getInitialDetailsPanelHTML();
            return;
        }

        detailsPanelEl.innerHTML = `
            <div class="flex-1 flex flex-col animate-fade-in">
                <div class="p-6 border-b border-slate-700">
                    <h2 class="text-2xl font-bold text-white mb-1">${escapeHTML(selectedCompany.name)}</h2>
                    <p class="text-cyan-400 mb-4">${escapeHTML(selectedCompany.industry)}</p>
                    <p class="text-slate-300 text-sm mb-4">${escapeHTML(selectedCompany.description)}</p>
                     <a href="${escapeHTML(selectedCompany.link)}" target="_blank" rel="noopener noreferrer" class="text-sm text-cyan-500 hover:underline">Visit Website &rarr;</a>
                </div>

                <div class="p-6 flex-1">
                    <div class="bg-slate-800/50 p-6 rounded-xl">
                        <h3 class="text-lg font-semibold text-white mb-2">1. Extracted Contact Details</h3>
                        <p class="text-xs text-slate-400 mb-4">Contact info is automatically extracted from search results.</p>
                        <div class="p-4 bg-slate-700/50 rounded-lg space-y-2 text-sm mt-4">
                            <p class="flex items-center text-slate-400">Email: <strong class="ml-2 text-white">${escapeHTML(selectedCompany.email)}</strong></p>
                            <p class="flex items-center text-slate-400">Phone: <strong class="ml-2 text-white">${escapeHTML(selectedCompany.phone)}</strong></p>
                        </div>
                    </div>

                    <div class="bg-slate-800/50 p-6 rounded-xl mt-6">
                        <h3 class="text-lg font-semibold text-white mb-4">2. Draft Email with AI</h3>
                        <button id="generate-email-btn" class="w-full flex items-center justify-center bg-cyan-500 text-white font-semibold py-2.5 rounded-lg hover:bg-cyan-600 transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-900 focus:ring-cyan-500">
                            Generate Email
                        </button>
                    </div>

                    <div id="mail-container" class="mt-6 bg-slate-800/50 p-6 rounded-xl hidden"></div>
                </div>
            </div>`;
        
        document.getElementById('generate-email-btn').addEventListener('click', generateEmail);
    };
    
    const renderGeneratedEmail = (emailText) => {
        const mailContainer = document.getElementById('mail-container');
        if (!mailContainer) return;

        let subjectLine = "No Subject Found";
        let bodyText = emailText;

        const subjectMatch = emailText.match(/^Subject:\s*(.*)/i);
        if (subjectMatch) {
            subjectLine = subjectMatch[1];
            const bodyStartIndex = emailText.indexOf('\n\n');
            bodyText = bodyStartIndex !== -1 ? emailText.substring(bodyStartIndex + 2) : emailText.substring(subjectMatch[0].length).trim();
        }

        const bodyHtml = bodyText.split('\n').filter(p => p.trim() !== '').map(p => `<p class="mb-4 last:mb-0">${escapeHTML(p)}</p>`).join('');

        mailContainer.innerHTML = `
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-lg font-semibold text-white">Generated Email Draft</h3>
                <button id="copy-email-btn" class="flex items-center gap-2 text-sm bg-slate-700 hover:bg-slate-600 text-slate-300 font-semibold py-1 px-3 rounded-lg transition-colors">
                    ${COPY_ICON}
                    <span>Copy</span>
                </button>
            </div>
            <div id="mail-content-wrapper" class="prose prose-sm prose-invert max-w-none p-4 border border-slate-700 rounded-lg bg-slate-900/50">
                <h3 id="email-subject" class="!mt-0">${escapeHTML(subjectLine)}</h3>
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
            btn.innerHTML = `${CHECK_ICON} <span>Copied!</span>`;
            setTimeout(() => { 
                btn.innerHTML = `${COPY_ICON} <span>Copy</span>`;
             }, 2000);
        });
    };

    // --- EVENT LISTENERS ---
    searchInput.addEventListener('keyup', (e) => {
        if (e.key === 'Enter') {
            clearTimeout(searchTimeout);
            performSearch();
        } else {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(performSearch, 500);
        }
    });

    companyListEl.addEventListener('click', (e) => {
        const card = e.target.closest('.company-card');
        if (!card) return;

        document.querySelectorAll('.company-card').forEach(c => c.classList.remove('active'));
        card.classList.add('active');

        selectedCompany = JSON.parse(card.dataset.company);
        renderSelectedCompany();
    });
});