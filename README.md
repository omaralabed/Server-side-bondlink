# Bondlink Server

**Multi-Client Bonding Router Server**

Bondlink Server is a high-performance VPS-based server that aggregates tunnels from multiple Bondlink client instances, providing centralized traffic routing, management, and monitoring.

## Features

- **Multi-Client Support**: Manages up to 50 concurrent Bondlink clients
- **Secure Authentication**: JWT-based Web UI authentication, token-based client authentication
- **Tunnel Aggregation**: Aggregates multiple WAN tunnels from each client
- **Packet Reordering**: Intelligent packet reordering buffer for out-of-order packets
- **Web UI Dashboard**: Professional, real-time monitoring dashboard with login
- **REST API**: Comprehensive API for programmatic management
- **Database Backend**: SQLite/PostgreSQL support for client tracking
- **Real-time Updates**: WebSocket-based real-time statistics
- **CLI Tools**: Command-line interface for server management

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Bondlink Server (VPS)                │
├─────────────────────────────────────────────────────┤
│                                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │   Client    │  │   Traffic    │  │  Database  │ │
│  │  Manager    │─▶│   Router     │  │            │ │
│  │             │  │              │  │            │ │
│  └─────────────┘  └──────────────┘  └────────────┘ │
│         │                 │                          │
│         │                 ▼                          │
│         │         ┌──────────────┐                  │
│         └────────▶│   Web API    │                  │
│                   │   + WebUI    │                  │
│                   └──────────────┘                  │
│                          │                           │
└──────────────────────────┼───────────────────────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
      ┌─────▼─────┐  ┌────▼────┐  ┌─────▼─────┐
      │ Client #1 │  │Client #2│  │ Client #N │
      │ (4 WANs)  │  │(4 WANs) │  │ (4 WANs)  │
      └───────────┘  └─────────┘  └───────────┘
```

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/bondlink-server.git
cd bondlink-server

# Run installation script
sudo bash scripts/install.sh
```

### Configuration

Edit `/etc/bondlink-server/server.yaml`:

```yaml
server:
  host: 0.0.0.0
  tunnel_port: 8443    # Port for client tunnels
  web_port: 80         # Web UI port
  api_port: 8080       # API port
  max_clients: 50

# Client authentication tokens
client_tokens:
  - token: "abc123def456..."
    client_id: "office-router"
    description: "Office location router"
  
  - token: "xyz789uvw012..."
    client_id: "warehouse-router"
    description: "Warehouse location router"

# Web UI authentication
web_auth:
  enabled: true
  secret_key: "your-jwt-secret-key-min-32-chars"
  algorithm: "HS256"
  token_expire_minutes: 1440
  
  users:
    - username: "admin"
      password_hash: "$2b$12$..."
      role: "admin"
```

### Starting the Server

```bash
# Start the service
sudo systemctl start bondlink-server

# Check status
sudo systemctl status bondlink-server

# View logs
sudo journalctl -u bondlink-server -f

# Enable auto-start
sudo systemctl enable bondlink-server
```

## Web UI

Access the Web UI at: `http://YOUR_SERVER_IP/`

### Features

- **Login Page**: Secure authentication with JWT tokens
- **Dashboard**: Real-time monitoring of all connected clients
- **Client Overview**: View each client's tunnels, bandwidth, and health
- **Statistics**: Server-wide packet routing statistics
- **Bandwidth Graphs**: Real-time upload/download graphs

### Screenshots

![Login Page](docs/screenshots/login.png)
![Dashboard](docs/screenshots/dashboard.png)

## API Documentation

### Authentication

All API endpoints require JWT authentication (except `/api/login`).

```bash
# Login
curl -X POST http://SERVER_IP:8080/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your_password"}'

# Response
{
  "access_token": "eyJ0eXAi...",
  "token_type": "bearer",
  "username": "admin",
  "role": "admin"
}

# Use token in subsequent requests
curl http://SERVER_IP:8080/api/status \
  -H "Authorization: Bearer eyJ0eXAi..."
```

### Endpoints

#### GET /api/status
Get server status and statistics.

```json
{
  "status": "running",
  "total_clients": 3,
  "active_clients": 3,
  "total_tunnels": 12,
  "router_stats": {
    "routed_packets": 1523041,
    "dropped_packets": 12,
    "reordered_packets": 305
  }
}
```

#### GET /api/clients
List all connected clients.

```json
{
  "clients": [
    {
      "client_id": "office-router",
      "active_tunnels": 4,
      "rx_bytes": 10485760,
      "tx_bytes": 5242880,
      "last_seen": 1234567890.123
    }
  ]
}
```

#### GET /api/clients/{client_id}
Get detailed information about a specific client.

#### GET /api/router/stats
Get traffic router statistics.

#### WebSocket /api/ws
Real-time updates WebSocket endpoint.

## CLI Usage

```bash
# Show server status
bondlink-server status

# List all clients
bondlink-server clients

# Show client details
bondlink-server client-info office-router

# Add new client
bondlink-server add-client warehouse-router --name "Warehouse" --description "Warehouse location"

# Add Web UI user
bondlink-server add-user john --role admin

# Show help
bondlink-server --help
```

## Configuration Reference

### Server Section

```yaml
server:
  host: 0.0.0.0              # Listen address
  tunnel_port: 8443          # Client tunnel port (UDP)
  web_port: 80               # Web UI port (HTTP)
  api_port: 8080             # API port (HTTP)
  max_clients: 50            # Maximum concurrent clients
```

### Tunnel Section

```yaml
tunnel:
  protocol: udp              # Tunnel protocol
  heartbeat_interval: 10     # Heartbeat interval (seconds)
  heartbeat_timeout_seconds: 30  # Timeout before disconnect
  encryption: true           # Enable tunnel encryption
```

### Routing Section

```yaml
routing:
  tun_interface: tun0        # TUN interface name
  tun_address: 10.100.0.1    # Server TUN IP
  tun_netmask: 255.255.255.0 # TUN netmask
  default_interface: eth0     # Default outbound interface
```

### Reordering Section

```yaml
reordering:
  enabled: true              # Enable packet reordering
  buffer_size: 1000          # Max packets in buffer
  timeout_ms: 100            # Reorder timeout (ms)
```

### Database Section

```yaml
database:
  url: "sqlite:///var/lib/bondlink-server/bondlink.db"
  # For PostgreSQL:
  # url: "postgresql://user:pass@localhost/bondlink"
  pool_size: 10
  max_overflow: 20
  echo: false
```

## Troubleshooting

### Server won't start

```bash
# Check logs
sudo journalctl -u bondlink-server -n 100

# Check configuration
bondlink-server status

# Verify ports are not in use
sudo netstat -tulpn | grep -E ':(80|8080|8443)'
```

### Client can't connect

1. Check firewall allows port 8443 (UDP)
2. Verify client token in server configuration
3. Check server logs for authentication errors
4. Ensure client is using correct server IP and port

### Web UI login fails

1. Verify password hash in configuration
2. Check JWT secret is set
3. Check browser console for errors
4. Clear browser cache/cookies

### Performance issues

1. Check database performance
2. Increase reordering buffer size
3. Monitor CPU/memory usage
4. Consider PostgreSQL for large deployments

## Security Considerations

1. **Change default credentials** immediately after installation
2. **Use strong JWT secrets** (minimum 32 characters)
3. **Use HTTPS** in production (configure reverse proxy)
4. **Firewall configuration**: Only expose necessary ports
5. **Regular updates**: Keep system and dependencies updated
6. **Unique client tokens**: Generate unique tokens for each client
7. **Monitor logs**: Check for authentication failures

## Performance Tuning

### For High Traffic (100+ Mbps per client)

```yaml
# Increase buffer sizes
reordering:
  buffer_size: 5000

# Database tuning
database:
  pool_size: 20
  max_overflow: 40

# System limits
# In /etc/security/limits.conf:
root soft nofile 65535
root hard nofile 65535
```

### For Many Clients (20+)

```yaml
server:
  max_clients: 100

database:
  # Use PostgreSQL for better concurrency
  url: "postgresql://user:pass@localhost/bondlink"
```

## Development

### Project Structure

```
bondlink-server/
├── server/
│   ├── core/
│   │   ├── config.py      # Configuration management
│   │   ├── logger.py      # Logging setup
│   │   ├── auth.py        # Authentication
│   │   └── database.py    # Database models
│   ├── network/
│   │   ├── client_manager.py   # Multi-client tunnel manager
│   │   └── traffic_router.py   # Packet routing
│   ├── api/
│   │   └── server.py      # FastAPI server
│   ├── daemon.py          # Main daemon
│   └── cli.py             # CLI interface
├── web/
│   ├── login.html         # Login page
│   ├── dashboard.html     # Dashboard page
│   └── static/
│       ├── css/styles.css # Styles
│       └── js/
│           ├── login.js   # Login logic
│           └── dashboard.js  # Dashboard logic
├── config/
│   └── server.yaml        # Configuration template
├── scripts/
│   ├── install.sh         # Installation script
│   └── bondlink-server.service  # Systemd unit
└── tests/                 # Unit tests
```

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run with coverage
pytest --cov=server tests/
```

## License

MIT License - see LICENSE file for details

## Support

- GitHub Issues: https://github.com/yourusername/bondlink-server/issues
- Documentation: https://docs.bondlink.io
- Email: support@bondlink.io

## Changelog

### v1.0.0 (2024-01-XX)
- Initial release
- Multi-client tunnel aggregation
- Web UI with authentication
- REST API
- CLI tools
- Database backend
- Packet reordering
