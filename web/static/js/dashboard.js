// Bondlink Server Dashboard - Real-time Data Visualization

class BondlinkServerDashboard {
    constructor() {
        // Bug fix: don't touch the DOM in the constructor — do it in init()
        // which is called from DOMContentLoaded
        this.ws = null;
        this.token    = localStorage.getItem('access_token');
        this.username = localStorage.getItem('username') || 'Admin';

        // Reconnect state — with backoff, same pattern as client app.js
        this.reconnectAttempts    = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay       = 3000;

        // Chart data history — pre-filled with zeros so the chart renders immediately
        this.downloadData = new Array(60).fill(0);
        this.uploadData   = new Array(60).fill(0);

        // Track previous cumulative byte counters so we can push a RATE (delta),
        // not the raw cumulative total, to the chart — fixes the "MB total vs Mbps" unit mismatch
        this._prevRx = null;
        this._prevTx = null;

        // Canvas contexts — set in init() after DOM is ready
        this.downloadCtx = null;
        this.uploadCtx   = null;
    }

    init() {
        // Bug fix: all DOM queries happen here, after DOMContentLoaded
        if (this._pollInterval) return;   // prevent double-init
        if (!this.token) {
            window.location.href = '/';
            return;
        }

        this.setupCharts();
        this.connectWebSocket();

        // Bug fix: fetchClients was never called on load — added here
        Promise.all([this.fetchStatus(), this.fetchClients()]);

        // Poll both every 5 seconds as fallback
        // Bug fix: store interval handle so double-init is prevented
        this._pollInterval = setInterval(() => {
            this.fetchStatus();
            this.fetchClients();
        }, 5000);
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl    = `${protocol}//${window.location.host}/api/ws`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;   // reset counter on successful connect
            this.updateStatus('connected');
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'update') this.updateDashboard(data);
            } catch (e) {
                console.warn('Received non-JSON WebSocket message:', event.data);
            }
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateStatus('error');
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateStatus('disconnected');
            this._reconnectWebSocket();
        };
    }

    // Bug fix: exponential backoff + permanent-lockout prevention (mirrors app.js)
    _reconnectWebSocket() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.warn('Max reconnect attempts reached. Will retry in 60 s.');
            setTimeout(() => {
                this.reconnectAttempts = 0;
                this.connectWebSocket();
            }, 60000);
            return;
        }
        this.reconnectAttempts++;
        const delay = Math.min(this.reconnectDelay * this.reconnectAttempts, 30000);
        console.log(`Reconnecting in ${delay}ms... (attempt ${this.reconnectAttempts})`);
        setTimeout(() => this.connectWebSocket(), delay);
    }

    async fetchStatus() {
        try {
            const response = await fetch('/api/status', {
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            if (response.status === 401) { this.logout(); return; }
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            this.updateServerStats(data);
        } catch (error) {
            console.error('Failed to fetch status:', error);
        }
    }

    async fetchClients() {
        try {
            const response = await fetch('/api/clients', {
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            if (response.status === 401) { this.logout(); return; }
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            this.updateClients(data.clients);
        } catch (error) {
            console.error('Failed to fetch clients:', error);
        }
    }

    updateDashboard(data) {
        if (data.router_stats) {
            const el = document.getElementById('routedPackets');
            if (el) el.textContent = this.formatNumber(data.router_stats.routed_packets);
        }

        if (data.clients) {
            // Bug fix: compute totals in a single pass, then update UI — eliminates double iteration
            let totalRx = 0, totalTx = 0;
            data.clients.forEach(c => {
                totalRx += c.rx_bytes || 0;
                totalTx += c.tx_bytes || 0;
            });
            this.updateClients(data.clients);

            // Bug fix: push RATE (delta MB/s since last update), not cumulative total.
            // Without this the chart shows ever-growing totals labelled as "Mbps".
            const MB = 1024 * 1024;
            const rxRate = this._prevRx !== null ? Math.max((totalRx - this._prevRx) / MB, 0) : 0;
            const txRate = this._prevTx !== null ? Math.max((totalTx - this._prevTx) / MB, 0) : 0;
            this._prevRx = totalRx;
            this._prevTx = totalTx;

            this.downloadData.push(rxRate);
            this.downloadData.shift();
            this.uploadData.push(txRate);
            this.uploadData.shift();

            this.updateCharts();
        }
    }

    updateServerStats(data) {
        // Bug fix: set() helper defined ONCE here at the top of the method,
        // not duplicated in multiple branches (was duplicated in updateClients previously).
        const set = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val;
        };
        set('totalClients',  data.total_clients  || 0);
        set('activeClients', data.active_clients || 0);
        set('totalTunnels',  data.total_tunnels  || 0);
        if (data.router_stats) {
            set('routedPackets', this.formatNumber(data.router_stats.routed_packets));
        }
    }

    updateClients(clients) {
        const grid = document.getElementById('clientsGrid');
        if (!grid) return;

        // Bug fix: set() helper defined ONCE at the top — no longer duplicated
        // in the empty-clients branch and the populated branch.
        const set = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val;
        };

        if (!clients || clients.length === 0) {
            grid.innerHTML = `
                <div style="grid-column:1/-1; text-align:center; padding:60px 20px; color:var(--text-muted);">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" style="margin-bottom:16px; opacity:0.4;">
                        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" stroke-width="1.5"/>
                        <circle cx="9" cy="7" r="4" stroke-width="1.5"/>
                    </svg>
                    <p>No clients connected</p>
                </div>`;
            set('totalClients', '0');
            set('activeClients', '0');
            set('totalTunnels', '0');
            return;
        }

        set('totalClients',  clients.length);
        set('activeClients', clients.filter(c => c.active_tunnels > 0).length);
        set('totalTunnels',  clients.reduce((s, c) => s + c.active_tunnels, 0));

        // Incremental update — only create card if it doesn't exist yet
        const existingIds = new Set(
            [...grid.querySelectorAll('[data-client-id]')].map(el => el.dataset.clientId)
        );
        const incomingIds = new Set(clients.map(c => c.client_id));

        // Remove cards for disconnected clients
        existingIds.forEach(id => {
            if (!incomingIds.has(id)) {
                const el = grid.querySelector(`[data-client-id="${CSS.escape(id)}"]`);
                if (el) el.remove();
            }
        });

        clients.forEach(client => {
            let card = grid.querySelector(`[data-client-id="${CSS.escape(client.client_id)}"]`);
            if (!card) {
                card = document.createElement('div');
                card.dataset.clientId = client.client_id;
                grid.appendChild(card);
            }
            this.renderClientCard(card, client);
        });
    }

    // Uses CSS classes that exist in styles.css (interface-card, health-status, etc.)
    renderClientCard(card, client) {
        const isActive    = client.active_tunnels > 0;
        const healthClass = isActive ? 'healthy' : 'down';
        const healthLabel = isActive ? 'ACTIVE'  : 'INACTIVE';

        card.className = `interface-card ${isActive ? 'active' : ''}`;

        card.innerHTML = `
            <div class="interface-header">
                <div class="interface-title-section">
                    <div class="interface-icon">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" stroke-width="2.5"/>
                            <circle cx="9" cy="7" r="4" stroke-width="2.5"/>
                            <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" stroke-width="2.5"/>
                        </svg>
                    </div>
                    <div class="interface-title-info">
                        <h3>${this.escapeHtml(client.client_id)}</h3>
                        <div class="interface-subtitle">${client.active_tunnels} tunnel${client.active_tunnels !== 1 ? 's' : ''} active</div>
                    </div>
                </div>
                <span class="health-status ${healthClass}">
                    <span class="health-dot"></span>
                    ${healthLabel}
                </span>
            </div>

            <div class="interface-body">
                <div class="interface-info-row">
                    <span class="info-label">Download</span>
                    <span class="info-value download" style="color:var(--primary)">${this.formatBytes(client.rx_bytes)}</span>
                </div>
                <div class="interface-info-row">
                    <span class="info-label">Upload</span>
                    <span class="info-value upload" style="color:var(--success)">${this.formatBytes(client.tx_bytes)}</span>
                </div>
                <div class="interface-info-row">
                    <span class="info-label">Packets</span>
                    <span class="info-value">${this.formatNumber((client.rx_packets || 0) + (client.tx_packets || 0))}</span>
                </div>
            </div>

            ${client.tunnels && client.tunnels.length > 0 ? `
            <div class="speed-chart-container">
                <div class="speed-label">Tunnels</div>
                ${client.tunnels.map(t => `
                <div class="interface-info-row">
                    <span class="info-label">${this.escapeHtml(t.wan_interface)}</span>
                    <span class="info-value">${this.formatBytes(t.rx_bytes)}</span>
                </div>`).join('')}
            </div>` : ''}
        `;
    }

    setupCharts() {
        const dlCanvas = document.getElementById('downloadGraph');
        const ulCanvas = document.getElementById('uploadGraph');
        if (dlCanvas) this.downloadCtx = dlCanvas.getContext('2d');
        if (ulCanvas) this.uploadCtx   = ulCanvas.getContext('2d');
    }

    updateCharts() {
        if (this.downloadCtx) this.drawChart(this.downloadCtx, this.downloadData, '#FF6B35', '#E85A2B');
        if (this.uploadCtx)   this.drawChart(this.uploadCtx,   this.uploadData,   '#7AC943', '#68B336');

        const latest = (arr) => arr[arr.length - 1] || 0;
        const dlEl = document.getElementById('serverDownload');
        const ulEl = document.getElementById('serverUpload');
        if (dlEl) dlEl.textContent = latest(this.downloadData).toFixed(2);
        if (ulEl) ulEl.textContent = latest(this.uploadData).toFixed(2);
    }

    drawChart(ctx, data, colorStart, colorEnd) {
        const canvas  = ctx.canvas;
        const width   = canvas.width;
        const height  = canvas.height;
        const padding = 10;

        ctx.clearRect(0, 0, width, height);

        // Bug fix: guard against data.length < 2 to avoid divide-by-zero on xStep
        if (data.length < 2) return;

        const max   = Math.max(...data, 1);
        // Use actual data length so line fills the canvas width correctly
        const xStep = (width - padding * 2) / Math.max(data.length - 1, 1);

        const gradient = ctx.createLinearGradient(0, 0, 0, height);
        gradient.addColorStop(0, colorStart + '50');
        gradient.addColorStop(1, colorEnd   + '00');

        ctx.beginPath();
        ctx.moveTo(padding, height - padding);
        data.forEach((v, i) => {
            ctx.lineTo(padding + i * xStep, height - padding - (v / max) * (height - padding * 2));
        });
        ctx.lineTo(padding + (data.length - 1) * xStep, height - padding);
        ctx.closePath();
        ctx.fillStyle = gradient;
        ctx.fill();

        ctx.beginPath();
        data.forEach((v, i) => {
            const x = padding + i * xStep;
            const y = height - padding - (v / max) * (height - padding * 2);
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        });
        ctx.strokeStyle = colorStart;
        ctx.lineWidth   = 2;
        ctx.lineCap     = 'round';
        ctx.lineJoin    = 'round';
        ctx.stroke();
    }

    updateStatus(status) {
        const badge = document.getElementById('serverStatus');
        if (!badge) return;

        badge.className = 'status-badge';
        const textEl = badge.querySelector('.status-text');

        if (status === 'connected') {
            badge.classList.add('connected');
            if (textEl) textEl.textContent = 'Running';
        } else if (status === 'error') {
            badge.classList.add('disconnected');
            if (textEl) textEl.textContent = 'Error';
        } else {
            badge.classList.add('disconnected');
            if (textEl) textEl.textContent = 'Disconnected';
        }
    }

    logout() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('username');
        localStorage.removeItem('role');
        if (this.ws) this.ws.close();
        window.location.href = '/';
    }

    formatBytes(bytes) {
        // Bug fix: guard against null, undefined, 0, and negative values
        if (!bytes || bytes <= 0) return '0 B';
        const k     = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i     = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    formatNumber(num) {
        if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
        if (num >= 1000)    return (num / 1000).toFixed(1)    + 'K';
        return Number.isInteger(num) ? num.toString() : num.toFixed(0);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Bug fix: instantiate and call init() after DOM is ready
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new BondlinkServerDashboard();
    dashboard.init();
});
