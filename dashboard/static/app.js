/**
 * Website Pitcher Dashboard - Frontend JavaScript
 * Vanilla ES6+ implementation with WebSocket and REST API support
 */

(function() {
    'use strict';

    // ============================================================================
    // State Management
    // ============================================================================

    const state = {
        leads: [],
        stats: null,
        runs: [],
        currentRun: null,
        filters: {
            status: null,
            lead_type: null,
            search: '',
            min_score: null,
            max_score: null
        },
        pagination: {
            offset: 0,
            limit: 50,
            total: 0
        },
        sorting: {
            column: 'created_at',
            direction: 'desc'
        },
        isConnected: false,
        pipelineRunning: false
    };

    // ============================================================================
    // WebSocket Management
    // ============================================================================

    let ws = null;
    let wsReconnectAttempts = 0;
    const WS_MAX_RECONNECT_ATTEMPTS = 5;
    const WS_RECONNECT_DELAY = 3000;

    /**
     * Connect to WebSocket server
     */
    function connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        try {
            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                console.log('WebSocket connected');
                state.isConnected = true;
                wsReconnectAttempts = 0;
                updateConnectionStatus(true);
            };

            ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    handleMessage(message);
                } catch (err) {
                    console.error('Failed to parse WebSocket message:', err);
                }
            };

            ws.onclose = () => {
                console.log('WebSocket disconnected');
                state.isConnected = false;
                updateConnectionStatus(false);
                attemptReconnect();
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                state.isConnected = false;
                updateConnectionStatus(false);
            };

        } catch (error) {
            console.error('Failed to connect to WebSocket:', error);
            attemptReconnect();
        }
    }

    /**
     * Attempt to reconnect with exponential backoff
     */
    function attemptReconnect() {
        if (wsReconnectAttempts < WS_MAX_RECONNECT_ATTEMPTS) {
            wsReconnectAttempts++;
            const delay = WS_RECONNECT_DELAY * wsReconnectAttempts;
            console.log(`Reconnecting in ${delay}ms (attempt ${wsReconnectAttempts})`);
            setTimeout(connect, delay);
        }
    }

    /**
     * Disconnect from WebSocket
     */
    function disconnect() {
        if (ws) {
            ws.close();
            ws = null;
        }
    }

    /**
     * Handle incoming WebSocket messages
     * @param {Object} message - Parsed message object
     */
    function handleMessage(message) {
        const { type, data, timestamp } = message;

        console.log('Received event:', type, data);

        switch (type) {
            case 'pipeline_start':
                handlePipelineStart(data);
                break;
            case 'pipeline_step':
                handlePipelineStep(data);
                break;
            case 'lead_scraped':
                handleLeadScraped(data);
                break;
            case 'lead_qualified':
                handleLeadQualified(data);
                break;
            case 'lead_scored':
                handleLeadScored(data);
                break;
            case 'report_generated':
                handleReportGenerated(data);
                break;
            case 'pipeline_complete':
                handlePipelineComplete(data);
                break;
            case 'pipeline_error':
                handlePipelineError(data);
                break;
            default:
                console.log('Unknown event type:', type);
        }
    }

    // ============================================================================
    // WebSocket Event Handlers
    // ============================================================================

    function handlePipelineStart(data) {
        state.pipelineRunning = true;
        state.currentRun = {
            id: data.run_id,
            status: 'running',
            started_at: data.timestamp,
            leads_scraped: 0,
            leads_qualified: 0,
            leads_scored: 0,
            reports_generated: 0
        };

        updatePipelineStatus(state.currentRun);
        showNotification('Pipeline started', `Processing leads from ${data.location || 'unknown location'}`, 'info');

        // Enable pipeline controls
        document.getElementById('btn-start-pipeline')?.classList.add('hidden');
        document.getElementById('btn-stop-pipeline')?.classList.remove('hidden');
    }

    function handlePipelineStep(data) {
        if (state.currentRun) {
            state.currentRun.current_step = data.step;
            state.currentRun.progress = data.progress;
            updatePipelineStatus(state.currentRun);
        }
    }

    function handleLeadScraped(data) {
        state.currentRun.leads_scraped++;
        updateLeadCount('scraped', state.currentRun.leads_scraped);

        // Add to lead list if visible
        if (data.lead) {
            state.leads.unshift(data.lead);
            renderLeadTable();
        }

        animateProgress('leads-scraped');
    }

    function handleLeadQualified(data) {
        state.currentRun.leads_qualified++;
        updateLeadCount('qualified', state.currentRun.leads_qualified);
        animateProgress('leads-qualified');
    }

    function handleLeadScored(data) {
        state.currentRun.leads_scored++;
        updateLeadCount('scored', state.currentRun.leads_scored);
        animateProgress('leads-scored');

        // Update lead in list
        const leadIndex = state.leads.findIndex(l => l.id === data.lead_id);
        if (leadIndex !== -1 && data.lead) {
            state.leads[leadIndex] = { ...state.leads[leadIndex], ...data.lead };
            renderLeadTable();
        }
    }

    function handleReportGenerated(data) {
        state.currentRun.reports_generated++;
        updateLeadCount('reports', state.currentRun.reports_generated);
        animateProgress('reports-generated');

        showNotification('Report generated', `For lead: ${data.business_name || 'Unknown'}`, 'success');
    }

    function handlePipelineComplete(data) {
        state.pipelineRunning = false;

        if (state.currentRun) {
            state.currentRun.status = 'completed';
            state.currentRun.completed_at = data.timestamp || new Date().toISOString();
            state.currentRun.duration = data.duration;
        }

        updatePipelineStatus(state.currentRun);
        showNotification('Pipeline complete', `Processed ${data.total_leads || 0} leads`, 'success');

        // Refresh data
        fetchStats();
        fetchLeads();

        // Reset pipeline controls
        document.getElementById('btn-start-pipeline')?.classList.remove('hidden');
        document.getElementById('btn-stop-pipeline')?.classList.add('hidden');
    }

    function handlePipelineError(data) {
        state.pipelineRunning = false;

        if (state.currentRun) {
            state.currentRun.status = 'failed';
            state.currentRun.error_message = data.error;
        }

        updatePipelineStatus(state.currentRun);
        showNotification('Pipeline error', data.error || 'An error occurred', 'error');

        // Reset pipeline controls
        document.getElementById('btn-start-pipeline')?.classList.remove('hidden');
        document.getElementById('btn-stop-pipeline')?.classList.add('hidden');
    }

    // ============================================================================
    // API Calls
    // ============================================================================

    const API_BASE = '/api';

    /**
     * Fetch leads from API with filters
     * @param {Object} params - Query parameters
     */
    async function fetchLeads(params = {}) {
        try {
            const queryParams = new URLSearchParams();

            // Apply filters
            if (state.filters.status) queryParams.set('status', state.filters.status);
            if (state.filters.lead_type) queryParams.set('lead_type', state.filters.lead_type);
            if (state.filters.search) queryParams.set('search', state.filters.search);
            if (state.filters.min_score) queryParams.set('min_score', state.filters.min_score);
            if (state.filters.max_score) queryParams.set('max_score', state.filters.max_score);

            // Apply pagination
            queryParams.set('limit', state.pagination.limit);
            queryParams.set('offset', state.pagination.offset);

            // Apply sorting
            queryParams.set('sort', state.sorting.column);
            queryParams.set('order', state.sorting.direction);

            const url = `${API_BASE}/leads?${queryParams.toString()}`;
            const response = await fetch(url);

            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }

            const data = await response.json();
            state.leads = data.leads || [];
            state.pagination.total = data.total || 0;

            renderLeadTable();
            updatePagination();

        } catch (error) {
            console.error('Failed to fetch leads:', error);
            showNotification('Error', 'Failed to fetch leads', 'error');
        }
    }

    /**
     * Fetch dashboard statistics
     */
    async function fetchStats() {
        try {
            const response = await fetch(`${API_BASE}/leads/stats`);

            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }

            const data = await response.json();
            state.stats = data;

            renderKPICards(data);

        } catch (error) {
            console.error('Failed to fetch stats:', error);
        }
    }

    /**
     * Fetch lead details
     * @param {string} leadId - Lead ID
     */
    async function fetchLeadDetail(leadId) {
        try {
            const response = await fetch(`${API_BASE}/leads/${leadId}`);

            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }

            const data = await response.json();
            return data;

        } catch (error) {
            console.error('Failed to fetch lead detail:', error);
            showNotification('Error', 'Failed to fetch lead details', 'error');
            return null;
        }
    }

    /**
     * Start a new pipeline run
     * @param {string} location - Target location
     * @param {number} count - Number of leads
     * @param {Array} categories - Business categories
     */
    async function startPipeline(location, count, categories) {
        try {
            const response = await fetch(`${API_BASE}/runs`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    location,
                    count,
                    categories
                })
            });

            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }

            const data = await response.json();
            state.currentRun = data;
            state.pipelineRunning = true;

            showNotification('Pipeline started', `Processing ${count} leads from ${location}`, 'info');

            return data;

        } catch (error) {
            console.error('Failed to start pipeline:', error);
            showNotification('Error', 'Failed to start pipeline', 'error');
            return null;
        }
    }

    /**
     * Fetch pipeline runs
     */
    async function fetchRuns() {
        try {
            const response = await fetch(`${API_BASE}/runs`);

            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }

            const data = await response.json();
            state.runs = data.runs || [];

            renderPipelineSteps(data.runs);

        } catch (error) {
            console.error('Failed to fetch runs:', error);
        }
    }

    // ============================================================================
    // UI Rendering Functions
    // ============================================================================

    /**
     * Render KPI cards with statistics
     * @param {Object} stats - Statistics data
     */
    function renderKPICards(stats) {
        const container = document.getElementById('kpi-cards');
        if (!container) return;

        if (!stats) {
            container.innerHTML = '<p class="text-muted">Loading statistics...</p>';
            return;
        }

        const kpis = [
            { label: 'Total Leads', value: stats.total || 0, icon: 'users', color: 'blue' },
            { label: 'Qualified', value: stats.by_status?.qualified || stats.qualified_leads || 0, icon: 'check', color: 'green' },
            { label: 'High Priority', value: stats.high_priority_count || stats.high_priority || 0, icon: 'star', color: 'yellow' },
            { label: 'Reports', value: stats.reports_generated || 0, icon: 'file', color: 'purple' }
        ];

        container.innerHTML = kpis.map(kpi => `
            <div class="kpi-card" data-kpi="${kpi.label.toLowerCase().replace(' ', '-')}">
                <div class="kpi-icon ${kpi.color}">
                    <i class="icon-${kpi.icon}"></i>
                </div>
                <div class="kpi-content">
                    <span class="kpi-value">${kpi.value}</span>
                    <span class="kpi-label">${kpi.label}</span>
                </div>
            </div>
        `).join('');

        // Animate values on load
        animateKPICounts();
    }

    /**
     * Render lead table with data
     */
    function renderLeadTable() {
        const tbody = document.getElementById('lead-table-body');
        if (!tbody) return;

        if (state.leads.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center text-muted">
                        No leads found. ${state.filters.search ? 'Try adjusting your search.' : 'Start a pipeline to scrape leads.'}
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = state.leads.map(lead => `
            <tr class="lead-row" data-lead-id="${lead.id}">
                <td>
                    <div class="lead-name">${escapeHtml(lead.business_name)}</div>
                    <div class="lead-category">${escapeHtml(lead.category || 'Unknown')}</div>
                </td>
                <td>${escapeHtml(lead.address || '-')}</td>
                <td>${formatPhone(lead.phone)}</td>
                <td>${formatRating(lead.google_rating)}</td>
                <td><span class="status-badge ${lead.status}">${formatStatus(lead.status)}</span></td>
                <td>${formatScore(lead.reachability_score)}</td>
                <td>${formatDate(lead.created_at)}</td>
            </tr>
        `).join('');

        // Add click handlers
        tbody.querySelectorAll('.lead-row').forEach(row => {
            row.addEventListener('click', () => {
                const leadId = row.dataset.leadId;
                openLeadModal(leadId);
            });
        });
    }

    /**
     * Render pipeline steps/progress
     * @param {Array} runs - Pipeline runs
     */
    function renderPipelineSteps(runs) {
        const container = document.getElementById('pipeline-steps');
        if (!container) return;

        const steps = [
            { id: 'scrape', label: 'Scraping', count: state.currentRun?.leads_scraped || 0 },
            { id: 'qualify', label: 'Qualifying', count: state.currentRun?.leads_qualified || 0 },
            { id: 'score', label: 'Scoring', count: state.currentRun?.leads_scored || 0 },
            { id: 'report', label: 'Reports', count: state.currentRun?.reports_generated || 0 }
        ];

        container.innerHTML = steps.map(step => `
            <div class="pipeline-step" data-step="${step.id}">
                <div class="step-indicator">
                    <div class="step-circle">${step.count}</div>
                </div>
                <div class="step-label">${step.label}</div>
            </div>
        `).join('');
    }

    /**
     * Update pagination controls
     */
    function updatePagination() {
        const container = document.getElementById('pagination');
        if (!container) return;

        const { offset, limit, total } = state.pagination;
        const currentPage = Math.floor(offset / limit) + 1;
        const totalPages = Math.ceil(total / limit);

        container.innerHTML = `
            <span class="pagination-info">
                Showing ${offset + 1} - ${Math.min(offset + limit, total)} of ${total}
            </span>
            <div class="pagination-controls">
                <button class="btn-pagination" ${offset === 0 ? 'disabled' : ''} onclick="app.goToPage(${currentPage - 1})">
                    Previous
                </button>
                <span class="page-number">Page ${currentPage} of ${totalPages}</span>
                <button class="btn-pagination" ${offset + limit >= total ? 'disabled' : ''} onclick="app.goToPage(${currentPage + 1})">
                    Next
                </button>
            </div>
        `;
    }

    // ============================================================================
    // Real-time Update Functions
    // ============================================================================

    /**
     * Update pipeline status display
     * @param {Object} runData - Pipeline run data
     */
    function updatePipelineStatus(runData) {
        const statusEl = document.getElementById('pipeline-status');
        if (!statusEl) return;

        if (!runData) {
            statusEl.innerHTML = '<span class="status-idle">Idle</span>';
            return;
        }

        const statusClass = runData.status === 'running' ? 'running' : runData.status;
        statusEl.innerHTML = `
            <span class="status-badge ${statusClass}">${runData.status}</span>
            ${runData.current_step ? `<span class="current-step">${runData.current_step}</span>` : ''}
        `;

        // Update progress bar
        const progressBar = document.getElementById('pipeline-progress');
        if (progressBar && runData.progress !== undefined) {
            progressBar.style.width = `${runData.progress}%`;
        }

        renderPipelineSteps();
    }

    /**
     * Update lead count in UI
     * @param {string} type - Count type (scraped, qualified, scored, reports)
     * @param {number} count - Current count
     */
    function updateLeadCount(type, count) {
        const el = document.getElementById(`count-${type}`);
        if (el) {
            el.textContent = count;
        }

        // Update pipeline step count
        const stepEl = document.querySelector(`.pipeline-step[data-step="${type === 'reports' ? 'report' : type}"] .step-circle`);
        if (stepEl) {
            stepEl.textContent = count;
        }
    }

    /**
     * Animate progress indicator
     * @param {string} elementId - Element ID to animate
     */
    function animateProgress(elementId) {
        const el = document.getElementById(elementId);
        if (el) {
            el.classList.add('animate-pulse');
            setTimeout(() => el.classList.remove('animate-pulse'), 500);
        }
    }

    /**
     * Animate KPI count values
     */
    function animateKPICounts() {
        document.querySelectorAll('.kpi-value').forEach(el => {
            const target = parseInt(el.textContent, 10) || 0;
            animateValue(el, 0, target, 500);
        });
    }

    /**
     * Animate a number value
     * @param {HTMLElement} element - Target element
     * @param {number} start - Start value
     * @param {number} end - End value
     * @param {number} duration - Animation duration in ms
     */
    function animateValue(element, start, end, duration) {
        const startTime = performance.now();

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const easeProgress = 1 - Math.pow(1 - progress, 3); // Ease out cubic
            const current = Math.floor(start + (end - start) * easeProgress);

            element.textContent = current;

            if (progress < 1) {
                requestAnimationFrame(update);
            }
        }

        requestAnimationFrame(update);
    }

    /**
     * Update connection status indicator
     * @param {boolean} connected - Connection status
     */
    function updateConnectionStatus(connected) {
        const indicator = document.getElementById('connection-status');
        if (indicator) {
            indicator.className = connected ? 'connected' : 'disconnected';
            indicator.textContent = connected ? 'Connected' : 'Disconnected';
        }
    }

    // ============================================================================
    // Modal Functions
    // ============================================================================

    /**
     * Open lead detail modal
     * @param {string} leadId - Lead ID
     */
    async function openLeadModal(leadId) {
        const modal = document.getElementById('lead-modal');
        if (!modal) return;

        const modalContent = modal.querySelector('.modal-content');
        modalContent.innerHTML = '<div class="loading">Loading...</div>';

        modal.classList.remove('hidden');
        modal.classList.add('active');

        const data = await fetchLeadDetail(leadId);

        if (data) {
            renderLeadModal(data);
        } else {
            modalContent.innerHTML = '<div class="error">Failed to load lead details</div>';
        }
    }

    /**
     * Render lead modal content
     * @param {Object} data - Lead detail data
     */
    function renderLeadModal(data) {
        const modal = document.getElementById('lead-modal');
        const modalContent = modal?.querySelector('.modal-content');
        if (!modalContent) return;

        const { lead, audit, report } = data;

        modalContent.innerHTML = `
            <div class="modal-header">
                <h2>${escapeHtml(lead.business_name)}</h2>
                <button class="modal-close" onclick="app.closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="lead-detail-section">
                    <h3>Basic Information</h3>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <label>Category</label>
                            <span>${escapeHtml(lead.category || '-')}</span>
                        </div>
                        <div class="detail-item">
                            <label>Address</label>
                            <span>${escapeHtml(lead.address || '-')}</span>
                        </div>
                        <div class="detail-item">
                            <label>Phone</label>
                            <span>${formatPhone(lead.phone)}</span>
                        </div>
                        <div class="detail-item">
                            <label>Email</label>
                            <span>${lead.email ? escapeHtml(lead.email) : '-'}</span>
                        </div>
                        <div class="detail-item">
                            <label>Website</label>
                            <span>${lead.website_url ? `<a href="${lead.website_url}" target="_blank">${escapeHtml(lead.website_url)}</a>` : '-'}</span>
                        </div>
                        <div class="detail-item">
                            <label>Google Rating</label>
                            <span>${formatRating(lead.google_rating)}</span>
                        </div>
                        <div class="detail-item">
                            <label>Status</label>
                            <span class="status-badge ${lead.status}">${formatStatus(lead.status)}</span>
                        </div>
                        <div class="detail-item">
                            <label>Score</label>
                            <span>${formatScore(lead.reachability_score)}</span>
                        </div>
                    </div>
                </div>

                ${audit ? `
                <div class="lead-detail-section">
                    <h3>Website Audit</h3>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <label>Page Speed</label>
                            <span class="score-badge ${getScoreClass(audit.page_speed_score)}">${audit.page_speed_score || '-'}/100</span>
                        </div>
                        <div class="detail-item">
                            <label>Mobile Score</label>
                            <span class="score-badge ${getScoreClass(audit.mobile_score)}">${audit.mobile_score || '-'}/100</span>
                        </div>
                        <div class="detail-item">
                            <label>SEO Score</label>
                            <span class="score-badge ${getScoreClass(audit.seo_score)}">${audit.seo_score || '-'}/100</span>
                        </div>
                        <div class="detail-item">
                            <label>HTTPS</label>
                            <span>${audit.https_enabled ? 'Yes' : 'No'}</span>
                        </div>
                        <div class="detail-item">
                            <label>Tech Stack</label>
                            <span>${escapeHtml(audit.tech_stack || 'Unknown')}</span>
                        </div>
                        <div class="detail-item">
                            <label>Design Quality</label>
                            <span>${escapeHtml(audit.design_quality || '-')}</span>
                        </div>
                        <div class="detail-item">
                            <label>Broken Links</label>
                            <span>${audit.broken_links_count || 0}</span>
                        </div>
                    </div>
                </div>
                ` : ''}

                ${report ? `
                <div class="lead-detail-section">
                    <h3>Report & Pitch</h3>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <label>Opportunity Score</label>
                            <span class="score-badge ${getScoreClass(report.opportunity_score)}">${report.opportunity_score || '-'}/100</span>
                        </div>
                        <div class="detail-item">
                            <label>Classification</label>
                            <span class="classification-badge ${report.classification}">${escapeHtml(report.classification || '-')}</span>
                        </div>
                        <div class="detail-item">
                            <label>Lead Type</label>
                            <span>${escapeHtml(report.lead_type || '-')}</span>
                        </div>
                        <div class="detail-item">
                            <label>Pitch Type</label>
                            <span>${escapeHtml(report.pitch_type || '-')}</span>
                        </div>
                    </div>
                    ${report.executive_summary ? `
                    <div class="summary-block">
                        <label>Executive Summary</label>
                        <p>${escapeHtml(report.executive_summary)}</p>
                    </div>
                    ` : ''}
                    ${report.email_body ? `
                    <div class="email-preview">
                        <label>Email Body</label>
                        <pre>${escapeHtml(report.email_body)}</pre>
                    </div>
                    ` : ''}
                </div>
                ` : ''}

                ${lead.social_handles ? `
                <div class="lead-detail-section">
                    <h3>Social Media</h3>
                    <div class="social-links">
                        ${lead.social_handles.facebook ? `<a href="${lead.social_handles.facebook}" target="_blank" class="social-link facebook">Facebook</a>` : ''}
                        ${lead.social_handles.instagram ? `<a href="${lead.social_handles.instagram}" target="_blank" class="social-link instagram">Instagram</a>` : ''}
                        ${lead.social_handles.linkedin ? `<a href="${lead.social_handles.linkedin}" target="_blank" class="social-link linkedin">LinkedIn</a>` : ''}
                        ${lead.social_handles.twitter ? `<a href="${lead.social_handles.twitter}" target="_blank" class="social-link twitter">Twitter</a>` : ''}
                    </div>
                </div>
                ` : ''}
            </div>
        `;
    }

    /**
     * Close lead modal
     */
    function closeModal() {
        const modal = document.getElementById('lead-modal');
        if (modal) {
            modal.classList.add('hidden');
            modal.classList.remove('active');
        }
    }

    // ============================================================================
    // Filtering Functions
    // ============================================================================

    /**
     * Filter leads by criteria
     * @param {Object} filters - Filter criteria
     */
    function filterLeads(filters) {
        state.filters = { ...state.filters, ...filters };
        state.pagination.offset = 0; // Reset to first page
        fetchLeads();
    }

    /**
     * Search leads by text
     * @param {string} query - Search query
     */
    function searchLeads(query) {
        state.filters.search = query;
        state.pagination.offset = 0;
        debounceFetch();
    }

    /**
     * Debounced fetch to prevent rapid API calls
     */
    let debounceTimer = null;
    function debounceFetch() {
        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(fetchLeads, 300);
    }

    // ============================================================================
    // Sorting Functions
    // ============================================================================

    /**
     * Sort leads by column
     * @param {string} column - Column name
     */
    function sortByColumn(column) {
        if (state.sorting.column === column) {
            state.sorting.direction = state.sorting.direction === 'asc' ? 'desc' : 'asc';
        } else {
            state.sorting.column = column;
            state.sorting.direction = 'asc';
        }

        // Update sort indicators
        document.querySelectorAll('.sortable').forEach(el => {
            el.classList.remove('sort-asc', 'sort-desc');
            if (el.dataset.column === column) {
                el.classList.add(`sort-${state.sorting.direction}`);
            }
        });

        fetchLeads();
    }

    /**
     * Go to specific page
     * @param {number} page - Page number
     */
    function goToPage(page) {
        const totalPages = Math.ceil(state.pagination.total / state.pagination.limit);
        if (page < 1 || page > totalPages) return;

        state.pagination.offset = (page - 1) * state.pagination.limit;
        fetchLeads();
    }

    // ============================================================================
    // Utility Functions
    // ============================================================================

    /**
     * Show notification message
     * @param {string} title - Notification title
     * @param {string} message - Notification message
     * @param {string} type - Notification type (info, success, error)
     */
    function showNotification(title, message, type = 'info') {
        const container = document.getElementById('notifications');
        if (!container) return;

        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <div class="notification-title">${escapeHtml(title)}</div>
            <div class="notification-message">${escapeHtml(message)}</div>
        `;

        container.appendChild(notification);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            notification.classList.add('fade-out');
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} - Escaped text
     */
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Format phone number
     * @param {string} phone - Phone number
     * @returns {string} - Formatted phone
     */
    function formatPhone(phone) {
        if (!phone) return '-';
        return phone;
    }

    /**
     * Format Google rating
     * @param {number} rating - Rating value
     * @returns {string} - Formatted rating
     */
    function formatRating(rating) {
        if (!rating && rating !== 0) return '-';
        return `${rating} <span class="stars">${'★'.repeat(Math.round(rating))}</span>`;
    }

    /**
     * Format lead status
     * @param {string} status - Status value
     * @returns {string} - Formatted status
     */
    function formatStatus(status) {
        if (!status) return '-';
        return status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    /**
     * Format reachability score
     * @param {number} score - Score value
     * @returns {string} - Formatted score with badge
     */
    function formatScore(score) {
        if (!score && score !== 0) return '-';
        const className = getScoreClass(score);
        return `<span class="score-badge ${className}">${score}</span>`;
    }

    /**
     * Get score CSS class based on value
     * @param {number} score - Score value
     * @returns {string} - CSS class name
     */
    function getScoreClass(score) {
        if (score >= 80) return 'high';
        if (score >= 50) return 'medium';
        return 'low';
    }

    /**
     * Format date string
     * @param {string} dateStr - ISO date string
     * @returns {string} - Formatted date
     */
    function formatDate(dateStr) {
        if (!dateStr) return '-';
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch {
            return dateStr;
        }
    }

    // ============================================================================
    // Event Handlers Setup
    // ============================================================================

    /**
     * Initialize event listeners
     */
    function initEventListeners() {
        // Start Pipeline button
        const startBtn = document.getElementById('btn-start-pipeline');
        if (startBtn) {
            startBtn.addEventListener('click', async () => {
                const location = document.getElementById('location-input')?.value || 'Pimpri-Chinchwad, Pune, India';
                const count = parseInt(document.getElementById('count-input')?.value, 10) || 50;
                const categories = ['restaurant', 'clinic', 'salon', 'gym', 'shop'];

                await startPipeline(location, count, categories);
            });
        }

        // Stop Pipeline button
        const stopBtn = document.getElementById('btn-stop-pipeline');
        if (stopBtn) {
            stopBtn.addEventListener('click', () => {
                // Cancel current run via API
                if (state.currentRun?.id) {
                    fetch(`${API_BASE}/runs/${state.currentRun.id}/cancel`, { method: 'POST' })
                        .then(() => {
                            state.pipelineRunning = false;
                            showNotification('Pipeline stopped', '', 'info');
                        });
                }
            });
        }

        // Search input
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                searchLeads(e.target.value);
            });
        }

        // Status filter
        const statusFilter = document.getElementById('status-filter');
        if (statusFilter) {
            statusFilter.addEventListener('change', (e) => {
                filterLeads({ status: e.target.value || null });
            });
        }

        // Lead type filter
        const typeFilter = document.getElementById('type-filter');
        if (typeFilter) {
            typeFilter.addEventListener('change', (e) => {
                filterLeads({ lead_type: e.target.value || null });
            });
        }

        // Sortable column headers
        document.querySelectorAll('.sortable').forEach(el => {
            el.addEventListener('click', () => {
                sortByColumn(el.dataset.column);
            });
        });

        // Modal close on backdrop click
        const modal = document.getElementById('lead-modal');
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    closeModal();
                }
            });
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Escape to close modal
            if (e.key === 'Escape') {
                closeModal();
            }
        });
    }

    // ============================================================================
    // Initialization
    // ============================================================================

    /**
     * Initialize the dashboard
     */
    async function init() {
        console.log('Initializing Website Pitcher Dashboard...');

        // Connect to WebSocket
        connect();

        // Initialize event listeners
        initEventListeners();

        // Fetch initial data
        await Promise.all([
            fetchStats(),
            fetchLeads(),
            fetchRuns()
        ]);

        console.log('Dashboard initialized');
    }

    // ============================================================================
    // Public API
    // ============================================================================

    window.app = {
        // State access
        getState: () => ({ ...state }),

        // Connection
        connect,
        disconnect,

        // API calls
        fetchLeads,
        fetchStats,
        fetchLeadDetail,
        startPipeline,
        fetchRuns,

        // UI updates
        renderKPICards,
        renderLeadTable,
        renderPipelineSteps,

        // Modal
        openLeadModal,
        closeModal,

        // Filtering
        filterLeads,
        searchLeads,

        // Sorting
        sortByColumn,
        goToPage,

        // Notifications
        showNotification
    };

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();