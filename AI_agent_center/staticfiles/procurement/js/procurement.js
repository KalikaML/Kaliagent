// procurement/static/procurement/js/procurement.js

document.addEventListener('DOMContentLoaded', () => {
    const app = {
        // --- DOM Element references ---
        addRequestBtn: document.getElementById('add-request-btn'),
        addRequestModal: document.getElementById('add-request-modal'),
        cancelAddRequestBtn: document.getElementById('cancel-add-request'),
        addRequestForm: document.getElementById('add-request-form'),
        bulkUploadBtn: document.getElementById('bulk-upload-btn'),
        bulkUploadModal: document.getElementById('bulk-upload-modal'),
        cancelBulkUploadBtn: document.getElementById('cancel-bulk-upload'),
        fileUploadInput: document.getElementById('file-upload-input'),
        fileUploadStatus: document.getElementById('file-upload-status'),
        drillDownModal: document.getElementById('drill-down-modal'),
        modalContentContainer: document.getElementById('modal-content-container'),
        kanbanBoard: document.getElementById('kanban-board'),
        csrfToken: document.querySelector('[name=csrfmiddlewaretoken]').value,
        checkAllQuotesBtn: document.getElementById('check-all-quotes-btn'),

        // --- State Management ---
        currentRequestData: null,
        pollingInterval: null,
        currentLogMessages: [],

        init() {
            this.attachEventListeners();
        },

        attachEventListeners() {
            this.addRequestBtn.addEventListener('click', () => this.addRequestModal.classList.remove('hidden'));
            this.cancelAddRequestBtn.addEventListener('click', () => this.addRequestModal.classList.add('hidden'));
            this.addRequestForm.addEventListener('submit', (e) => this.handleAddNewRequest(e));
            this.bulkUploadBtn.addEventListener('click', () => this.bulkUploadModal.classList.remove('hidden'));
            this.cancelBulkUploadBtn.addEventListener('click', () => {
                this.bulkUploadModal.classList.add('hidden');
                this.fileUploadInput.value = '';
                this.fileUploadStatus.textContent = '';
            });
            this.fileUploadInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) this.fileUploadStatus.textContent = `File selected: ${e.target.files[0].name}`;
            });

            if (this.checkAllQuotesBtn) {
                this.checkAllQuotesBtn.addEventListener('click', () => this.runCheckAllRfqs());
            }

            this.kanbanBoard.addEventListener('click', (e) => {
                const card = e.target.closest('.kanban-card');
                const deleteBtn = e.target.closest('.delete-request-btn');

                if (deleteBtn) {
                    e.stopPropagation(); // Prevent modal from opening
                    const requestId = deleteBtn.dataset.requestId;
                    if (confirm(`Are you sure you want to delete request #${requestId}?`)) {
                        this.runDeleteRequest(requestId, deleteBtn.closest('.kanban-card'));
                    }
                } else if (card) {
                    this.openDrillDownModal(card.dataset.requestId);
                }
            });

            this.modalContentContainer.addEventListener('click', (e) => {
                if (e.target.matches('.view-quote-btn')) {
                    const quoteId = e.target.dataset.quoteId;
                    this.showQuoteDetails(quoteId);
                }
                if (e.target.matches('.finalize-request-btn')) {
                    const quoteId = e.target.dataset.quoteId;
                    this.runFinalizeRequest(this.currentRequestData, quoteId);
                }
                if (e.target.matches('#manual-rfq-btn')) {
                    this.runManualRfq(this.currentRequestData);
                }
            });
        },

        addLog(message) {
            this.currentLogMessages.push(message);
            const logEl = document.getElementById('action-log');
            if (logEl) {
                const p = document.createElement('p');
                p.innerHTML = message;
                logEl.appendChild(p);
                logEl.scrollTop = logEl.scrollHeight;
            }
        },

        async openDrillDownModal(requestId) {
            if (this.pollingInterval) clearInterval(this.pollingInterval);

            if (!this.currentRequestData || this.currentRequestData.id !== parseInt(requestId)) {
                this.currentLogMessages = [];
            }

            const response = await fetch(`/procurement/api/get-request-details/${requestId}/`);
            if (!response.ok) {
                alert('Could not fetch request details.');
                return;
            }

            const request = await response.json();
            this.currentRequestData = request;
            this.modalContentContainer.innerHTML = this.generateModalContent(request);

            const logEl = document.getElementById('action-log');
            if (logEl) {
                this.currentLogMessages.forEach(msg => {
                    const p = document.createElement('p');
                    p.innerHTML = msg;
                    logEl.appendChild(p);
                });
                if (logEl.children.length > 0) logEl.scrollTop = logEl.scrollHeight;
            }

            this.drillDownModal.classList.remove('hidden');
            this.attachModalEventListeners(request);

            if (request.status === 'new-request') this.runSupplierSearch(request);
            if (request.status === 'rfqs-sent') this.runQuoteCheck(request);
        },

        async runSupplierSearch(request) {
            this.addLog('▶️ <b>Agent 1:</b> Parsing request details...');
            await new Promise(res => setTimeout(res, 500));
            this.addLog('▶️ <b>Agent 2:</b> Starting hybrid web sourcing...');

            const response = await fetch(`/procurement/api/find-suppliers/${request.id}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken
                }
            });

            if (!response.ok) {
                this.addLog('❌ Error: Could not start the scraping agent.');
                return;
            }

            this.addLog('🤖 Agent is working in the background. This may take a few minutes...');

            this.pollingInterval = setInterval(async () => {
                const statusResponse = await fetch(`/procurement/api/get-request-details/${request.id}/`);
                const statusData = await statusResponse.json();

                if (statusData.status !== 'agent-working') {
                    clearInterval(this.pollingInterval);
                    this.addLog('✅ <b>Success!</b> Sourcing complete.');
                    this.openDrillDownModal(request.id);
                } else {
                    this.addLog('... still scraping ...');
                }
            }, 7000);
        },

        closeDrillDownModal() {
            if (this.pollingInterval) clearInterval(this.pollingInterval);
            this.currentRequestData = null;
            this.currentLogMessages = [];
            this.drillDownModal.classList.add('hidden');
            window.location.reload();
        },

        async runDeleteRequest(requestId, cardElement) {
            const response = await fetch(`/procurement/api/delete-request/${requestId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken
                }
            });
            if (response.ok) {
                cardElement.remove();
            } else {
                alert('Failed to delete the request.');
            }
        },

        async runManualRfq(request) {
            this.addLog('Manually marking this request as RFQ Sent...');
            const response = await fetch(`/procurement/api/manual-rfq/${request.id}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken
                }
            });
            if (response.ok) {
                this.addLog('✅ Success! Request moved to RFQs Sent.');
                setTimeout(() => this.closeDrillDownModal(), 1500);
            } else {
                this.addLog('❌ Error: Could not update the request status.');
            }
        },

        async runCheckAllRfqs() {
            const btn = this.checkAllQuotesBtn;
            btn.textContent = 'Checking...';
            btn.disabled = true;
            this.addLog('🤖 Checking all active RFQs for new quotes...'); // Global log message
            const response = await fetch('/procurement/api/check-all-rfqs/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken
                }
            });
            if (response.ok) {
                const data = await response.json();
                alert(`Checked for quotes and found ${data.total_new_quotes} new quote(s).`);
                window.location.reload();
            } else {
                alert('An error occurred while checking for quotes.');
            }
            btn.textContent = 'Check for New Quotes';
            btn.disabled = false;
        },

        async handleAddNewRequest(e) {
            e.preventDefault();
            const formData = {
                title: document.getElementById('product-name').value,
                quantity: document.getElementById('quantity').value,
                specs: document.getElementById('specs').value,
                source: 'Manual'
            };
            const response = await fetch('/procurement/api/add-request/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify(formData)
            });
            if (response.ok) {
                this.addRequestModal.classList.add('hidden');
                e.target.reset();
                window.location.reload();
            } else {
                alert('Failed to add request.');
            }
        },

        async runRfqSend(request) {
            this.addLog('✅ Approval received. <b>Agent 4</b> is now creating RFQ package...');

            const attachmentInput = document.getElementById('rfq-attachment-input');
            const attachmentFile = attachmentInput ? attachmentInput.files[0] : null;

            const formData = new FormData();
            if (attachmentFile) {
                formData.append('attachment', attachmentFile);
                this.addLog(`📎 Attaching file: ${attachmentFile.name}`);
            }

            this.addLog('Sending RFQ emails...');

            const response = await fetch(`/procurement/api/send-rfqs/${request.id}/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': this.csrfToken },
                body: formData
            });

            if (response.ok) {
                const data = await response.json();
                this.addLog(`📬 <b>RFQs Sent!</b> ${data.message}`);
                this.addLog('▶️ <b>Agent 5</b> will now monitor inbox for replies.');
                setTimeout(() => this.closeDrillDownModal(), 2000);
            } else {
                const errorData = await response.json();
                this.addLog(`❌ Error: Could not send RFQs. ${errorData.error || 'Unknown error'}`);
            }
        },


        async runQuoteCheck(request) {
            this.addLog(`🤖 <b>Agent 5</b> checking inbox...`);
            const response = await fetch(`/procurement/api/check-and-parse-quotes/${request.id}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken
                }
            });
            const data = await response.json();
            if (data.success) {
                if (data.new_quotes_found > 0) {
                    this.addLog(`📊 <b>Success!</b> Found and parsed ${data.new_quotes_found} new quote(s).`);
                    this.openDrillDownModal(request.id);
                } else {
                    this.addLog('📪 No new quotes found in this check.');
                }
            } else {
                this.addLog(`❌ Error checking for quotes: ${data.error}`);
            }
        },

        async runFinalizeRequest(request, quoteId) {
            this.addLog(`Finalizing request...`);
            const response = await fetch(`/procurement/api/finalize-request/${request.id}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    quote_id: quoteId
                })
            });
            const data = await response.json();
            if (data.success) {
                this.addLog(`✅ <b>Request Finalized!</b> Estimated savings: <b>₹${parseFloat(data.savings).toFixed(2)}</b>`);
                setTimeout(() => this.closeDrillDownModal(), 2000);
            } else {
                this.addLog(`❌ Error: Could not finalize request. ${data.error || ''}`);
            }
        },

        showQuoteDetails(quoteId) {
            const quote = this.currentRequestData.quotes.find(q => q.id == quoteId);
            if (!quote) return;
            const detailContainer = document.createElement('div');
            detailContainer.innerHTML = this.generateQuoteDetailView(quote);

            const mainPanel = this.modalContentContainer.querySelector('.lg\\:col-span-2');
            if (mainPanel) {
                mainPanel.innerHTML = '';
                mainPanel.appendChild(detailContainer);

                const backButton = detailContainer.querySelector('.back-to-compare-btn');
                backButton.addEventListener('click', () => {
                    mainPanel.innerHTML = this.generateQuotesPanel(this.currentRequestData);
                });
            }
        },

        generateModalContent(request) {
            const briefingPanel = `
                <div class="bg-slate-900 p-6 rounded-lg">
                    <h3 class="text-xl font-bold mb-4">📝 The Briefing</h3>
                    <div class="space-y-3">
                        <div>
                            <label class="text-sm text-slate-400">Product</label>
                            <p class="font-semibold text-lg">${request.title}</p>
                        </div>
                        <div>
                            <label class="text-sm text-slate-400">Quantity</label>
                            <p class="font-semibold text-lg">${request.quantity}</p>
                        </div>
                        <div>
                            <label class="text-sm text-slate-400">Specifications</label>
                            <p class="text-slate-300">${request.specs || 'N/A'}</p>
                        </div>
                    </div>
                </div>`;

            const actionLogPanel = `
                <div class="bg-slate-900 p-6 rounded-lg">
                    <h3 class="text-xl font-bold mb-4">⚡ Agent Action Log</h3>
                    <div id="action-log" class="space-y-3 text-sm h-48 overflow-y-auto pr-2"></div>
                </div>`;

            let mainActionPanel;
            switch (request.status) {
                case 'agent-working':
                    mainActionPanel = `<div class="bg-slate-900 p-6 rounded-lg flex items-center justify-center h-full"><p class="text-slate-400 animate-pulse">Agent is working in the background...</p></div>`;
                    break;
                case 'awaiting-approval':
                    mainActionPanel = this.generateApprovalPanel(request);
                    break;
                case 'quotes-received':
                case 'finalized':
                    mainActionPanel = this.generateQuotesPanel(request);
                    break;
                default:
                    mainActionPanel = `<div class="bg-slate-900 p-6 rounded-lg flex items-center justify-center h-full"><p class="text-slate-400">No actions available at this stage.</p></div>`;
            }

            return `
                <div class="p-4 flex justify-between items-center border-b border-slate-700">
                    <h2 class="text-2xl font-bold">${request.title}</h2>
                    <button id="close-modal-btn" class="text-slate-400 hover:text-white text-3xl leading-none">&times;</button>
                </div>
                <div class="p-4 grid grid-cols-1 lg:grid-cols-3 gap-4 flex-grow">
                    <div class="lg:col-span-1 flex flex-col gap-4">${briefingPanel}${actionLogPanel}</div>
                    <div class="lg:col-span-2">${mainActionPanel}</div>
                </div>`;
        },

        generateApprovalPanel(request) {
            const suppliers = request.suppliers || [];
            let supplierListHtml;
            let actionButtonHtml;

            if (suppliers.length > 0) {
                supplierListHtml = suppliers.map(s => `
                    <li class="flex items-center justify-between p-3 bg-slate-800 rounded-md">
                        <div>
                            <p class="font-semibold">${s.name}</p>
                            <p class="text-xs text-slate-400">Email: ${s.email || 'Not Found'}</p>
                            <p class="text-xs text-slate-400">Phone: ${s.phone || 'Not Found'}</p>
                        </div>
                        <input type="checkbox" checked class="form-checkbox h-5 w-5 bg-slate-600 border-slate-500 rounded text-indigo-600 focus:ring-indigo-500">
                    </li>
                `).join('');
                actionButtonHtml = `<button id="approve-rfq-btn" class="w-full bg-green-600 hover:bg-green-500 text-white font-bold py-3 px-4 rounded-lg transition-colors">Approve & Send Email RFQs</button>`;
            } else {
                supplierListHtml = '<li class="text-slate-400">The agent could not find any suppliers. You can manually contact suppliers and then mark this request as sent.</li>';
                actionButtonHtml = `<button id="manual-rfq-btn" class="w-full bg-sky-600 hover:bg-sky-500 text-white font-bold py-3 px-4 rounded-lg transition-colors">Manually Mark as RFQ Sent</button>`;
            }

            const subject = `Request for Quotation - ${request.title} [REQ-${request.id}]`;
            const messageBody = `Dear Supplier,\n\nWe are interested in procuring the following item:\n\nProduct: ${request.title}\nQuantity: ${request.quantity}\nSpecifications: ${request.specs || 'As per standard'}\n\nPlease provide your best quotation in a reply to this email.\n\nThank you,\nProcunova Automated System`;

            const rfqDraftHtml = `
                <h4 class="font-bold text-slate-300 mb-2">Drafted RFQ Email Preview:</h4>
                <div class="bg-slate-800 p-3 rounded-md text-sm border border-slate-700 mb-4">
                    <p><strong>Subject:</strong> ${subject}</p>
                    <div class="border-t border-slate-700 my-2"></div>
                    <pre class="whitespace-pre-wrap font-sans text-slate-300">${messageBody}</pre>
                </div>
                <h4 class="font-bold text-slate-300 mb-2 mt-4">Attach File (Optional):</h4>
                <div class="bg-slate-800 p-3 rounded-md border border-slate-700 mb-4">
                    <input type="file" id="rfq-attachment-input" class="block w-full text-sm text-slate-300 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-500 file:text-white hover:file:bg-indigo-600"/>
                </div>
                `;

            return `
                <div class="bg-slate-900 p-6 rounded-lg h-full flex flex-col">
                    <h3 class="text-xl font-bold mb-2">Vetted Supplier List</h3>
                    <ul class="space-y-2 flex-grow overflow-y-auto pr-2 mb-4">${supplierListHtml}</ul>
                    <div class="border-t border-slate-700 pt-4">
                        ${(suppliers.length > 0 ? rfqDraftHtml : '')}
                        ${actionButtonHtml}
                    </div>
                </div>`;
        },

        generateQuotesPanel(request) {
            const quotes = request.quotes || [];
            quotes.sort((a, b) => (a.price || Infinity) - (b.price || Infinity));

            const quotesHtml = quotes.map((q, index) => {
                const supplier = this.currentRequestData.suppliers.find(s => s.name === q.supplier__name);
                const negotiateLink = supplier && supplier.email ? `mailto:${supplier.email}?subject=Re: Quote for ${this.currentRequestData.title} (REQ-${this.currentRequestData.id})` : '#';

                let priceClass = 'text-slate-300';
                let bestQuoteBadge = '';
                if (index === 0 && q.price) {
                    priceClass = 'text-green-400';
                    bestQuoteBadge = '<span class="ml-2 text-xs font-bold bg-green-500 text-white py-0.5 px-2 rounded-full">🏆 Best Quote</span>';
                } else if (index === 1) {
                    priceClass = 'text-amber-400';
                }

                return `
                <tr class="border-b border-slate-700 hover:bg-slate-800">
                    <td class="p-3 font-semibold">${q.supplier__name}</td>
                    <td class="p-3 font-bold ${priceClass}">₹${q.price || 'N/A'} ${bestQuoteBadge}</td>
                    <td class="p-3">${q.lead_time_days || 'N/A'} days</td>
                    <td class="p-3">${q.payment_terms || 'N/A'}</td>
                    <td class="p-3">${q.discount || 'None'}</td>
                    <td class="p-3 text-right">
                        <button class="view-quote-btn text-sm bg-indigo-600 hover:bg-indigo-500 px-3 py-1 rounded" data-quote-id="${q.id}">Details</button>
                        <a href="${negotiateLink}" class="text-sm bg-sky-600 hover:bg-sky-500 px-3 py-1 rounded ml-2">Negotiate</a>
                        <button class="finalize-request-btn text-sm bg-green-600 hover:bg-green-500 px-3 py-1 rounded ml-2" data-quote-id="${q.id}">Award</button>
                    </td>
                </tr>`
            }).join('') || '<tr><td colspan="6" class="text-center p-4 text-slate-400">No valid quotes parsed yet. The agent is monitoring the inbox.</td></tr>';

            return `
                <div class="bg-slate-900 p-6 rounded-lg h-full flex flex-col">
                    <h3 class="text-xl font-bold mb-2">Quotation Comparison</h3>
                    <p class="text-sm text-slate-400 mb-4">Quotes are sorted by best price. The lowest price is highlighted as the <b>Best Quote</b>.</p>
                    <div class="flex-grow overflow-y-auto">
                        <table class="w-full text-left text-sm">
                            <thead class="sticky top-0 bg-slate-900 z-10">
                                <tr class="border-b border-slate-600">
                                    <th class="p-3">Supplier</th>
                                    <th class="p-3">Price (per unit)</th>
                                    <th class="p-3">Lead Time</th>
                                    <th class="p-3">Payment Terms</th>
                                    <th class="p-3">Discount</th>
                                    <th class="p-3 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody>${quotesHtml}</tbody>
                        </table>
                    </div>
                </div>`;
        },

        generateQuoteDetailView(quote) {
            const supplier = this.currentRequestData.suppliers.find(s => s.name === quote.supplier__name);
            const negotiateLink = supplier && supplier.email ? `mailto:${supplier.email}?subject=Re: Quote for ${this.currentRequestData.title} (REQ-${this.currentRequestData.id})` : '#';

            return `
                <div class="bg-slate-900 p-6 rounded-lg h-full flex flex-col">
                    <div class="flex justify-between items-start mb-4">
                        <div>
                            <h3 class="text-xl font-bold">Quote Details from: ${quote.supplier__name}</h3>
                            <p class="text-sm text-slate-400">Full email response from the supplier.</p>
                        </div>
                        <div class="flex gap-x-2">
                            <button class="back-to-compare-btn bg-slate-600 hover:bg-slate-500 text-white font-bold py-2 px-4 rounded-lg text-sm">← Back to Comparison</button>
                        </div>
                    </div>
                    <div class="grid grid-cols-4 gap-4 mb-4 text-center">
                        <div class="bg-slate-800 p-3 rounded"><dt class="text-sm text-slate-400">Price</dt><dd class="font-bold text-lg text-green-400">₹${quote.price || 'N/A'}</dd></div>
                        <div class="bg-slate-800 p-3 rounded"><dt class="text-sm text-slate-400">Lead Time</dt><dd class="font-bold text-lg">${quote.lead_time_days || 'N/A'} days</dd></div>
                        <div class="bg-slate-800 p-3 rounded"><dt class="text-sm text-slate-400">Payment</dt><dd class="font-bold text-lg">${quote.payment_terms || 'N/A'}</dd></div>
                        <div class="bg-slate-800 p-3 rounded"><dt class="text-sm text-slate-400">Discount</dt><dd class="font-bold text-lg">${quote.discount || 'None'}</dd></div>
                    </div>
                    <h4 class="font-bold text-slate-300 mb-2">Full Email Response:</h4>
                    <div class="flex-grow overflow-y-auto bg-slate-800 p-4 rounded-md border border-slate-700">
                        <pre class="text-sm text-slate-300 whitespace-pre-wrap font-sans">${quote.full_email_body || 'Email body not available.'}</pre>
                    </div>
                </div>`;
        },

        attachModalEventListeners(request) {
            document.getElementById('close-modal-btn')?.addEventListener('click', () => this.closeDrillDownModal());
            const approveBtn = document.getElementById('approve-rfq-btn');
            if (approveBtn) approveBtn.addEventListener('click', () => this.runRfqSend(request));
        },
    };
    app.init();
});