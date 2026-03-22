# Bondlink Server - Quick Start Guide

Get your Bondlink Server up and running in 10 minutes!

## Prerequisites

- Ubuntu 22.04 or 24.04 server (VPS)
- Root access
- Public IP address
- At least 2GB RAM, 1 CPU core

## Step 1: Install

```bash
# Download and run installation script
wget https://raw.githubusercontent.com/yourusername/bondlink-server/main/scripts/install.sh
sudo bash install.sh
```

The installer will:
- Install system dependencies
- Create directory structure
- Install Python dependencies
- Generate secure JWT secret
- Create default admin credentials
- Set up systemd service

**Save the admin credentials displayed at the end!**

## Step 2: Add Client Tokens

Generate a token for your first client:

```bash
/opt/bondlink-server/venv/bin/bondlink-server add-client my-router --description "My home router"
```

Copy the generated token and configuration snippet.

## Step 3: Update Configuration

Edit `/etc/bondlink-server/server.yaml`:

```bash
sudo nano /etc/bondlink-server/server.yaml
```

Add the client token:

```yaml
client_tokens:
  - token: "YOUR_GENERATED_TOKEN_HERE"
    client_id: "my-router"
    description: "My home router"
```

Update the admin password hash (from installation output):

```yaml
web_auth:
  users:
    - username: "admin"
      password_hash: "ADMIN_HASH_FROM_INSTALL"
      role: "admin"
```

## Step 4: Configure Firewall

```bash
# Allow Web UI (port 80)
sudo ufw allow 80/tcp

# Allow API (port 8080)
sudo ufw allow 8080/tcp

# Allow client tunnels (port 8443 UDP)
sudo ufw allow 8443/udp

# Enable firewall if not already enabled
sudo ufw enable
```

## Step 5: Start the Server

```bash
# Start the service
sudo systemctl start bondlink-server

# Check status
sudo systemctl status bondlink-server

# If successful, enable auto-start
sudo systemctl enable bondlink-server
```

## Step 6: Access Web UI

1. Open browser: `http://YOUR_SERVER_IP/`
2. Login with admin credentials from installation
3. You should see the dashboard (no clients connected yet)

## Step 7: Connect Your First Client

On your Bondlink client machine, update the configuration:

```yaml
# /etc/bondlink/client.yaml
server:
  host: YOUR_SERVER_IP
  port: 8443
  token: "YOUR_GENERATED_TOKEN_HERE"
```

Restart the client:

```bash
sudo systemctl restart bondlink-client
```

## Step 8: Verify Connection

Back in the server Web UI, you should now see:
- Client connected
- Tunnels established
- Bandwidth statistics updating

## Troubleshooting

### Server logs
```bash
sudo journalctl -u bondlink-server -f
```

### Check connectivity
```bash
# From client, test if server port is reachable
nc -vuz YOUR_SERVER_IP 8443
```

### Common issues

**"Address already in use" on port 80:**
```bash
# Check what's using port 80
sudo lsof -i :80

# Stop conflicting service (e.g., Apache)
sudo systemctl stop apache2
```

**"Permission denied" binding to port 80:**
- The service runs as root (see systemd unit)
- Check if selinux/apparmor is blocking it

**Client can't connect:**
1. Verify firewall allows UDP 8443
2. Check client token matches server config
3. Verify server public IP is correct

## Next Steps

### Add More Clients

For each additional client:

```bash
# Generate token
bondlink-server add-client client-name --description "Description"

# Add to server config
sudo nano /etc/bondlink-server/server.yaml

# Restart server
sudo systemctl restart bondlink-server
```

### Add Web UI Users

```bash
bondlink-server add-user john --role admin
```

Copy the password hash to config and restart.

### Monitor Performance

```bash
# Server status
bondlink-server status

# List clients
bondlink-server clients

# Client details
bondlink-server client-info my-router

# View logs
sudo journalctl -u bondlink-server -f
```

### Enable HTTPS (Production)

Use nginx as reverse proxy:

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://127.0.0.1:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /api/ws {
        proxy_pass http://127.0.0.1:80;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Performance Tips

### For high traffic:

```yaml
# In server.yaml
reordering:
  buffer_size: 5000  # Increase buffer

database:
  pool_size: 20      # More connections
```

### For many clients:

```yaml
server:
  max_clients: 100   # Increase limit

database:
  # Switch to PostgreSQL for better performance
  url: "postgresql://user:pass@localhost/bondlink"
```

## Support

- Documentation: README.md
- Issues: GitHub Issues
- CLI help: `bondlink-server --help`

## Summary

Your Bondlink Server is now running! 🎉

- **Web UI**: http://YOUR_SERVER_IP/
- **API**: http://YOUR_SERVER_IP:8080/api/
- **Tunnel Port**: UDP 8443

Connect your Bondlink clients using the generated tokens and start bonding!
