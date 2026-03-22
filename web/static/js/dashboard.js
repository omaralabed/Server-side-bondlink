// Dashboard JavaScript

class BondlinkServerDashboard {
    constructor() {
        this.ws = null;
        this.token = localStorage.getItem('access_token');
        this.username = localStorage.getItem('username') || 'Admin';
        
        // Chart data
        this.downloadData = new Array(60).fill(0);
        this.uploadData = new Array(60).fill(0);
        
        // DOM elements
        this.serverStatus = document.getElementById('serverStatus');
        this.usernameEl = document.getElementById('username');
        this.logoutBtn = document.getElementById('logoutBtn');
        
        this.totalClients = document.getElementById('totalClients');
        this.activeClients = document.getElementById('activeClients');
        this.totalTunnels = document.getElementById('totalTunnels');
        this.routedPackets = document.getElementById('routedPackets');
        
        this.downloadRate = document.getElementById('downloadRate');
        this.uploadRate = document.getElementById('uploadRate');
        this.downloadChart = document.getElementById('downloadChart');
        this.uploadChart = document.getElementById('uploadChart');
        
        this.clientsList = document.getElementById('clientsList');
        this.noClients = document.getElementById('noClients');
        
        // Initialize
        this.init();
    }
    
    init() {
        // Check authentication
        if (!this.token) {
            window.location.href = '/';
            return;
        }
        
        // Set username
        this.usernameEl.textContent = this.username;
        
        // Setup event listeners
        this.logoutBtn.addEventListener('click', () => this.logout());
        
        // Setup charts
        this.setupCharts();
        
        // Connect WebSocket
        this.connectWebSocket();
        
        // Initial data fetch
        this.fetchStatus();
    }
    
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/ws`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.updateStatus('connected');
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'update') {
                this.updateDashboard(data);
            }
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateStatus('error');
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateStatus('disconnected');
            
            // Reconnect after 5 seconds
            setTimeout(() => this.connectWebSocket(), 5000);
        };
    }
    
    async fetchStatus() {
        try {
            const response = await fetch('/api/status', {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });
            
            if (response.status === 401) {
                this.logout();
                return;
            }
            
            if (!response.ok) {
                throw new Error('Failed to fetch status');
            }
            
            const data = await response.json();
            this.updateServerStats(data);
            
        } catch (error) {
            console.error('Failed to fetch status:', error);
        }
    }
    
    async fetchClients() {
        try {
            const response = await fetch('/api/clients', {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });
            
            if (response.status === 401) {
                this.logout();
                return;
            }
            
            if (!response.ok) {
                throw new Error('Failed to fetch clients');
            }
            
            const data = await response.json();
            this.updateClients(data.clients);
            
        } catch (error) {
            console.error('Failed to fetch clients:', error);
        }
    }
    
    updateDashboard(data) {
        // Update server stats
        if (data.router_stats) {
            this.routedPackets.textContent = this.formatNumber(data.router_stats.routed_packets);
        }
        
        // Update clients
        if (data.clients) {
            this.updateClients(data.clients);
            
            // Calculate total bandwidth
            let totalRx = 0;
            let totalTx = 0;
            
            data.clients.forEach(client => {
                totalRx += client.rx_bytes || 0;
                totalTx += client.tx_bytes || 0;
            });
            
            // Update charts (simplified rate calculation)
            this.downloadData.push(totalRx / 1024 / 1024);
            this.downloadData.shift();
            
            this.uploadData.push(totalTx / 1024 / 1024);
            this.uploadData.shift();
            
            this.updateCharts();
        }
    }
    
    updateServerStats(data) {
        this.totalClients.textContent = data.total_clients || 0;
        this.activeClients.textContent = data.active_clients || 0;
        this.totalTunnels.textContent = data.total_tunnels || 0;
        
        if (data.router_stats) {
            this.routedPackets.textContent = this.formatNumber(data.router_stats.routed_packets);
        }
    }
    
    updateClients(clients) {
        if (!clients || clients.length === 0) {
            this.clientsList.innerHTML = '';
            this.noClients.style.display = 'block';
            this.totalClients.textContent = '0';
            this.activeClients.textContent = '0';
            this.totalTunnels.textContent = '0';
            return;
        }
        
        this.noClients.style.display = 'none';
        
        // Update counts
        this.totalClients.textContent = clients.length;
        this.activeClients.textContent = clients.filter(c => c.active_tunnels > 0).length;
        this.totalTunnels.textContent = clients.reduce((sum, c) => sum + c.active_tunnels, 0);
        
        // Update client cards
        this.clientsList.innerHTML = clients.map(client => this.renderClientCard(client)).join('');
    }
    
    renderClientCard(client) {
        return `
            <div class="client-card glass-card">
                <div class="client-header">
                    <div class="client-id">${this.escapeHtml(client.client_id)}</div>
                    <div class="client-status ${client.active_tunnels > 0 ? 'active' : ''}">
                        ${client.active_tunnels > 0 ? 'Active' : 'Inactive'}
                    </div>
                </div>
                
                <div class="client-stats">
                    <div class="client-stat">
                        <div class="client-stat-label">Tunnels</div>
                        <div class="client-stat-value">${client.active_tunnels}</div>
                    </div>
                    <div class="client-stat">
                        <div class="client-stat-label">Download</div>
                        <div class="client-stat-value">${this.formatBytes(client.rx_bytes)}</div>
                    </div>
                    <div class="client-stat">
                        <div class="client-stat-label">Upload</div>
                        <div class="client-stat-value">${this.formatBytes(client.tx_bytes)}</div>
                    </div>
                    <div class="client-stat">
                        <div class="client-stat-label">Packets</div>
                        <div class="client-stat-value">${this.formatNumber(client.rx_packets + client.tx_packets)}</div>
                    </div>
                </div>
                
                ${client.tunnels && client.tunnels.length > 0 ? `
                    <div class="tunnels-list">
                        ${client.tunnels.map(tunnel => `
                            <div class="tunnel-item">
                                <div class="tunnel-name">${this.escapeHtml(tunnel.wan_interface)}</div>
                                <div class="tunnel-status">
                                    <span class="tunnel-dot"></span>
                                    <span>${this.formatBytes(tunnel.rx_bytes)}</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
            </div>
        `;
    }
    
    setupCharts() {
        this.downloadCtx = this.downloadChart.getContext('2d');
        this.uploadCtx = this.uploadChart.getContext('2d');
        
        // Set canvas size
        this.downloadChart.width = this.downloadChart.offsetWidth;
        this.downloadChart.height = 100;
        this.uploadChart.width = this.uploadChart.offsetWidth;
        this.uploadChart.height = 100;
    }
    
    updateCharts() {
        this.drawChart(this.downloadCtx, this.downloadData, '#00d4ff');
        this.drawChart(this.uploadCtx, this.uploadData, '#ff6b35');
        
        // Update rates
        const latestDownload = this.downloadData[this.downloadData.length - 1];
        const latestUpload = this.uploadData[this.uploadData.length - 1];
        
        this.downloadRate.textContent = `${latestDownload.toFixed(2)} MB/s`;
        this.uploadRate.textContent = `${latestUpload.toFixed(2)} MB/s`;
    }
    
    drawChart(ctx, data, color) {
        const canvas = ctx.canvas;
        const width = canvas.width;
        const height = canvas.height;
        const padding = 10;
        
        // Clear canvas
        ctx.clearRect(0, 0, width, height);
        
        // Find max value for scaling
        const max = Math.max(...data, 1);
        
        // Draw gradient
        const gradient = ctx.createLinearGradient(0, 0, 0, height);
        gradient.addColorStop(0, color + '40');
        gradient.addColorStop(1, color + '00');
        
        // Draw area
        ctx.beginPath();
        ctx.moveTo(padding, height - padding);
        
        data.forEach((value, index) => {
            const x = padding + (index / (data.length - 1)) * (width - padding * 2);
            const y = height - padding - (value / max) * (height - padding * 2);
            ctx.lineTo(x, y);
        });
        
        ctx.lineTo(width - padding, height - padding);
        ctx.closePath();
        ctx.fillStyle = gradient;
        ctx.fill();
        
        // Draw line
        ctx.beginPath();
        data.forEach((value, index) => {
            const x = padding + (index / (data.length - 1)) * (width - padding * 2);
            const y = height - padding - (value / max) * (height - padding * 2);
            
            if (index === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });
        
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.stroke();
    }
    
    updateStatus(status) {
        this.serverStatus.className = 'status-badge';
        
        if (status === 'connected') {
            this.serverStatus.classList.add('connected');
            this.serverStatus.querySelector('.status-text').textContent = 'Connected';
        } else if (status === 'error') {
            this.serverStatus.querySelector('.status-text').textContent = 'Error';
        } else {
            this.serverStatus.querySelector('.status-text').textContent = 'Disconnected';
        }
    }
    
    logout() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('username');
        localStorage.removeItem('role');
        
        if (this.ws) {
            this.ws.close();
        }
        
        window.location.href = '/';
    }
    
    formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize dashboard
const dashboard = new BondlinkServerDashboard();
