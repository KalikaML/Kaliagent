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
                    const requestId = card.dataset.requestId;
                    const productId = card.dataset.productId;

                    if (requestId) {
                        this.openDrillDownModal(requestId);
                    } else if (productId) {
                        this.openProductQuotesModal(productId);
                    }
                }
            });

            this.modalContentContainer.addEventListener('click', (e) => {
                if (e.target.matches('.view-quote-btn')) {
                    const quoteId = e.target.dataset.quoteId;
                    this.showQuoteDetails(quoteId);
                }
                if (e.target.matches('.finalize-request-btn')) {
                    const quoteId = e.target.dataset.quoteId;
                    const representativeId = this.currentRequestData.representative_request_id || this.currentRequestData.id;
                    this.runFinalizeRequest(representativeId, quoteId);
                }
                if (e.target.matches('#manual-rfq-btn')) {
                    this.runManualRfq(this.currentRequestData);
                }
                if (e.target.matches('#approve-rfq-btn')) {
                    this.runRfqSend(this.currentRequestData);
                }
                if (e.target.matches('#find-more-suppliers-btn')) {
                    const productId = e.target.dataset.productId;
                    this.runFindMoreSuppliers(productId, e.target);
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
        
        async openProductQuotesModal(productId) {
            if (this.pollingInterval) clearInterval(this.pollingInterval);
            this.currentLogMessages = [];

            const response = await fetch(`/procurement/api/get-product-quotes/${productId}/`);
            if (!response.ok) {
                alert('Could not fetch product quote details.');
                return;
            }
            const productData = await response.json();
            this.currentRequestData = productData;
            this.modalContentContainer.innerHTML = this.generateModalContent(productData);
            this.drillDownModal.classList.remove('hidden');
            this.attachModalEventListeners(productData);
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
        
        async runFindMoreSuppliers(productId, buttonElement) {
            if (!confirm('This will re-run the sourcing agent to find more suppliers for this product. The request will move to the "Agent Working" column. Continue?')) {
                return;
            }

            buttonElement.textContent = 'Searching...';
            buttonElement.disabled = true;

            const response = await fetch(`/procurement/api/find-more-suppliers/${productId}/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': this.csrfToken },
            });
            const data = await response.json();

            if (data.success) {
                alert('Agent has started searching for more suppliers. The page will now reload to reflect the status change.');
                window.location.reload();
            } else {
                alert(`Error: ${data.error || 'Could not start the agent.'}`);
                buttonElement.textContent = '+ Find More Suppliers';
                buttonElement.disabled = false;
            }
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

        async runFinalizeRequest(requestId, quoteId) {
            this.addLog(`Finalizing request...`);
            const response = await fetch(`/procurement/api/finalize-request/${requestId}/`, {
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
            const isProductView = !!request.representative_request_id;
            
            let briefingPanel;

            if (isProductView) {
                briefingPanel = `
                <div class="bg-slate-900 p-6 rounded-lg">
                    <h3 class="text-xl font-bold mb-4">📝 Product Briefing</h3>
                    <div class="space-y-3">
                        <div><label class="text-sm text-slate-400">Product</label><p class="font-semibold text-lg">${request.title}</p></div>
                        <div><label class="text-sm text-slate-400">Sample Quantity</label><p class="font-semibold text-lg">${request.quantity}</p></div>
                        <div><label class="text-sm text-slate-400">Sample Specifications</label><p class="text-slate-300">${request.specs || 'N/A'}</p></div>
                    </div>
                </div>`;
            } else {
                 briefingPanel = `
                <div class="bg-slate-900 p-6 rounded-lg">
                    <h3 class="text-xl font-bold mb-4">📝 The Briefing</h3>
                    <div class="space-y-3">
                        <div><label class="text-sm text-slate-400">Product</label><p class="font-semibold text-lg">${request.title}</p></div>
                        <div><label class="text-sm text-slate-400">Quantity</label><p class="font-semibold text-lg">${request.quantity}</p></div>
                        <div><label class="text-sm text-slate-400">Specifications</label><p class="text-slate-300">${request.specs || 'N/A'}</p></div>
                    </div>
                </div>`;
            }

            const actionLogPanel = `
                <div class="bg-slate-900 p-6 rounded-lg">
                    <h3 class="text-xl font-bold mb-4">⚡ Agent Action Log</h3>
                    <div id="action-log" class="space-y-3 text-sm h-48 overflow-y-auto pr-2"></div>
                </div>`;

            let mainActionPanel;
            switch (request.status) {
                case 'agent-working':
                    mainActionPanel = `<div class="bg-slate-900 p-6 rounded-lg flex items-center justify-center h-full"><p class="text-slate-400 animate-pulse">Agent is working...</p></div>`;
                    break;
                case 'awaiting-approval':
                    mainActionPanel = this.generateApprovalPanel(request);
                    break;
                case 'quotes-received':
                case 'finalized':
                    mainActionPanel = this.generateQuotesPanel(request);
                    break;
                default:
                    mainActionPanel = `<div class="bg-slate-900 p-6 rounded-lg flex items-center justify-center h-full"><p class="text-slate-400">No actions available.</p></div>`;
            }

            return `
                <div class="p-4 flex justify-between items-center border-b border-slate-700">
                    <h2 class="text-2xl font-bold">${request.title}</h2>
                    <button id="close-modal-btn" class="text-slate-400 hover:text-white text-3xl leading-none">&times;</button>
                </div>
                <div class="p-4 grid grid-cols-1 lg:grid-cols-3 gap-4 flex-grow">
                    <div class="lg:col-span-1 flex flex-col gap-4">${briefingPanel}${(isProductView ? '' : actionLogPanel)}</div>
                    <div class="lg:col-span-2">${mainActionPanel}</div>
                </div>`;
        },

        // 🔄 MODIFIED: This function is now fixed to show the full RFQ draft.
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
                        </div>
                        <input type="checkbox" checked class="form-checkbox h-5 w-5 bg-slate-600 border-slate-500 rounded text-indigo-600">
                    </li>
                `).join('');
                actionButtonHtml = `<button id="approve-rfq-btn" class="w-full bg-green-600 hover:bg-green-500 text-white font-bold py-3 px-4 rounded-lg">Approve & Send Email RFQs</button>`;
            } else {
                supplierListHtml = '<li class="text-slate-400">Agent found no suppliers. Manually contact suppliers and mark as sent.</li>';
                actionButtonHtml = `<button id="manual-rfq-btn" class="w-full bg-sky-600 hover:bg-sky-500 text-white font-bold py-3 px-4 rounded-lg">Manually Mark as RFQ Sent</button>`;
            }
            
            // ✨ NEW: Complete RFQ Draft HTML
            const rfqSubject = `Request for Quotation - ${request.title} [REQ-${request.id}]`;
            const rfqBody = `Dear Supplier,\n\nWe are interested in procuring the following item:\n\nProduct: ${request.title}\nQuantity: ${request.quantity}\n\nSpecifications:\n${request.specs || 'As per standard'}\n\nPlease provide your best quotation in a reply to this email.\n\nThank you,\nProcunova Automated System`;

            const rfqDraftHtml = `
                <h4 class="font-bold text-slate-300 mb-2 mt-4">RFQ Email Draft</h4>
                <div class="bg-slate-800 p-3 rounded-md border border-slate-700 mb-4">
                    <p class="text-sm font-semibold">Subject: ${rfqSubject}</p>
                    <pre class="mt-2 text-sm text-slate-300 whitespace-pre-wrap font-sans">${rfqBody}</pre>
                </div>
                <h4 class="font-bold text-slate-300 mb-2 mt-4">Attach File (Optional):</h4>
                <div class="bg-slate-800 p-3 rounded-md border border-slate-700 mb-4">
                    <input type="file" id="rfq-attachment-input" class="block w-full text-sm text-slate-300 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:bg-indigo-500 file:text-white"/>
                </div>
                `;

            return `
                <div class="bg-slate-900 p-6 rounded-lg h-full flex flex-col">
                    <h3 class="text-xl font-bold mb-2">Vetted Supplier List</h3>
                    <div class="flex-grow overflow-y-auto pr-2 mb-4">
                         <ul class="space-y-2">${supplierListHtml}</ul>
                         ${(suppliers.length > 0 ? rfqDraftHtml : '')}
                    </div>
                    <div class="border-t border-slate-700 pt-4">
                        ${actionButtonHtml}
                    </div>
                </div>`;
        },
        
        generateQuotesPanel(request) {
            const quotes = request.quotes || [];
            
            if (quotes.length === 1) {
                const quote = quotes[0];
                let benchmarkHtml = '';
                if (request.benchmark_price && request.benchmark_source) {
                    const benchmarkPrice = parseFloat(request.benchmark_price).toFixed(2);
                    const currentPrice = parseFloat(quote.price).toFixed(2);
                    const difference = parseFloat(request.benchmark_price) - parseFloat(quote.price);
                    let diffClass = 'text-slate-400';
                    let diffText = `(₹${difference.toFixed(2)} difference)`;
                    if (difference > 0) {
                        diffClass = 'text-green-400';
                        diffText = `(You save ₹${difference.toFixed(2)})`;
                    } else if (difference < 0) {
                        diffClass = 'text-red-400';
                        diffText = `(₹${Math.abs(difference).toFixed(2)} more expensive)`;
                    }

                    benchmarkHtml = `
                        <div class="mt-4 border-t border-slate-700 pt-4">
                            <h4 class="font-bold text-slate-300">Price Benchmark</h4>
                            <div class="mt-2 flex justify-between items-center bg-slate-800 p-3 rounded-lg">
                                <div>
                                    <p class="text-sm text-slate-400">${request.benchmark_source}</p>
                                    <p class="text-xl font-bold text-sky-400">₹${benchmarkPrice}</p>
                                </div>
                                <div class="text-right">
                                    <p class="text-sm text-slate-400">vs. Current Quote</p>
                                    <p class="text-xl font-bold text-green-400">₹${currentPrice} <span class="text-sm ${diffClass}">${diffText}</span></p>
                                </div>
                            </div>
                        </div>
                    `;
                }

                return `
                <div class="bg-slate-900 p-6 rounded-lg h-full flex flex-col">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="text-xl font-bold">Quote Received</h3>
                        <button id="find-more-suppliers-btn" data-product-id="${request.id}" class="bg-sky-600 hover:bg-sky-500 text-white font-semibold py-2 px-3 rounded-lg text-sm">
                            + Find More Suppliers
                        </button>
                    </div>
                    <p class="text-sm text-slate-400 mb-4">Only one quote has been received. Use the benchmark for comparison or find more suppliers.</p>
                    <div class="space-y-3 bg-slate-800 p-4 rounded-lg">
                        <div class="grid grid-cols-2 gap-4">
                            <div><p class="text-sm text-slate-400">Supplier</p><p class="font-bold">${quote.supplier__name}</p></div>
                            <div><p class="text-sm text-slate-400">Price</p><p class="font-bold text-green-400">₹${quote.price ? parseFloat(quote.price).toFixed(2) : 'N/A'}</p></div>
                            <div><p class="text-sm text-slate-400">Lead Time</p><p class="font-bold">${quote.lead_time_days || 'N/A'} days</p></div>
                            <div><p class="text-sm text-slate-400">Payment Terms</p><p class="font-bold">${quote.payment_terms || 'N/A'}</p></div>
                        </div>
                    </div>
                    ${benchmarkHtml}
                    <div class="mt-auto pt-6 flex gap-4">
                        <button class="view-quote-btn flex-1 text-sm bg-indigo-600 hover:bg-indigo-500 px-3 py-2 rounded-lg" data-quote-id="${quote.id}">View Full Email</button>
                        <button class="finalize-request-btn flex-1 text-sm bg-green-600 hover:bg-green-500 px-3 py-2 rounded-lg" data-quote-id="${quote.id}">Award Contract</button>
                    </div>
                </div>`;
            }

            quotes.sort((a, b) => (a.price || Infinity) - (b.price || Infinity));
            const quotesHtml = quotes.map((q, index) => {
                let priceClass = 'text-slate-300';
                let bestQuoteBadge = '';
                if (index === 0 && q.price) {
                    priceClass = 'text-green-400';
                    bestQuoteBadge = '<span class="ml-2 text-xs font-bold bg-green-500 text-white py-0.5 px-2 rounded-full">🏆 Best Quote</span>';
                } else if (index === 1 && q.price) {
                    priceClass = 'text-amber-400';
                }
                return `<tr class="border-b border-slate-700 hover:bg-slate-800">
                    <td class="p-3 font-semibold">${q.supplier__name}</td>
                    <td class="p-3 font-bold ${priceClass}">₹${q.price ? parseFloat(q.price).toFixed(2) : 'N/A'} ${bestQuoteBadge}</td>
                    <td class="p-3">${q.lead_time_days || 'N/A'} days</td>
                    <td class="p-3">${q.payment_terms || 'N/A'}</td>
                    <td class="p-3 text-right">
                        <button class="view-quote-btn text-sm bg-indigo-600 hover:bg-indigo-500 px-3 py-1 rounded" data-quote-id="${q.id}">Details</button>
                        <button class="finalize-request-btn text-sm bg-green-600 hover:bg-green-500 px-3 py-1 rounded ml-2" data-quote-id="${q.id}">Award</button>
                    </td>
                </tr>`
            }).join('') || '<tr><td colspan="5" class="text-center p-4 text-slate-400">No quotes parsed yet.</td></tr>';

            return `
                <div class="bg-slate-900 p-6 rounded-lg h-full flex flex-col">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="text-xl font-bold">Quotation Comparison</h3>
                        <button id="find-more-suppliers-btn" data-product-id="${request.id}" class="bg-sky-600 hover:bg-sky-500 text-white font-semibold py-2 px-3 rounded-lg text-sm">
                            + Find More Suppliers
                        </button>
                    </div>
                    <p class="text-sm text-slate-400 mb-4">Quotes are sorted by best price.</p>
                    <div class="flex-grow overflow-y-auto">
                        <table class="w-full text-left text-sm">
                            <thead class="sticky top-0 bg-slate-900 z-10">
                                <tr class="border-b border-slate-600">
                                    <th class="p-3">Supplier</th><th class="p-3">Price</th><th class="p-3">Lead Time</th>
                                    <th class="p-3">Payment Terms</th><th class="p-3 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody>${quotesHtml}</tbody>
                        </table>
                    </div>
                </div>`;
        },

        generateQuoteDetailView(quote) {
             return `
                <div class="bg-slate-900 p-6 rounded-lg h-full flex flex-col">
                    <div class="flex justify-between items-start mb-4">
                        <div>
                            <h3 class="text-xl font-bold">Details from: ${quote.supplier__name}</h3>
                        </div>
                        <button class="back-to-compare-btn bg-slate-600 hover:bg-slate-500 text-white font-bold py-2 px-4 rounded-lg text-sm">← Back</button>
                    </div>
                    <div class="grid grid-cols-4 gap-4 mb-4 text-center">
                        <div class="bg-slate-800 p-3 rounded"><dt class="text-sm text-slate-400">Price</dt><dd class="font-bold text-lg text-green-400">₹${quote.price ? parseFloat(quote.price).toFixed(2) : 'N/A'}</dd></div>
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
            document.getElementById('close-modal-btn')?.addEventListener('click', () => {
                this.closeDrillDownModal()
            });
            // This button is dynamically added, so we don't attach listener here anymore
            // It's handled by the main modalContentContainer listener
        },
    };
    app.init();
});