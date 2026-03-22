#!/bin/bash
# Bondlink Server Installation Script
# For Ubuntu 22.04/24.04

set -e

echo "=================================="
echo "Bondlink Server Installation"
echo "=================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root"
    exit 1
fi

# Detect Ubuntu version
if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [ "$ID" != "ubuntu" ]; then
        echo "Warning: This script is designed for Ubuntu. Your OS: $ID"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

echo "Step 1: Installing system dependencies..."
apt-get update
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    iptables \
    iproute2

echo ""
echo "Step 2: Creating directory structure..."
mkdir -p /opt/bondlink-server
mkdir -p /etc/bondlink-server
mkdir -p /var/log/bondlink-server
mkdir -p /opt/bondlink-server/web/static/{css,js}

echo ""
echo "Step 3: Copying files..."
cp -r server /opt/bondlink-server/
cp -r web/* /opt/bondlink-server/web/
cp requirements.txt /opt/bondlink-server/
cp setup.py /opt/bondlink-server/

echo ""
echo "Step 4: Creating Python virtual environment..."
cd /opt/bondlink-server
python3 -m venv venv

echo ""
echo "Step 5: Installing Python dependencies..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
./venv/bin/pip install -e .

echo ""
echo "Step 6: Generating configuration..."
if [ ! -f /etc/bondlink-server/server.yaml ]; then
    cp config/server.yaml /etc/bondlink-server/server.yaml
    
    # Generate secure JWT secret
    JWT_SECRET=$(openssl rand -hex 32)
    sed -i "s/your-secret-key-change-in-production-min-32-chars/$JWT_SECRET/" /etc/bondlink-server/server.yaml
    
    echo "Generated JWT secret: $JWT_SECRET"
    echo "Configuration file created at: /etc/bondlink-server/server.yaml"
    echo ""
    echo "IMPORTANT: Please edit the configuration file and:"
    echo "  1. Change default client tokens"
    echo "  2. Change default admin password"
    echo "  3. Configure network interfaces"
else
    echo "Configuration file already exists: /etc/bondlink-server/server.yaml"
fi

echo ""
echo "Step 7: Generating default admin password..."
ADMIN_PASSWORD=$(openssl rand -base64 12)
ADMIN_HASH=$(./venv/bin/python3 -c "from server.core.auth import hash_password; print(hash_password('$ADMIN_PASSWORD'))")

echo ""
echo "=========================================="
echo "Default Admin Credentials:"
echo "Username: admin"
echo "Password: $ADMIN_PASSWORD"
echo "=========================================="
echo ""
echo "Password hash (for config): $ADMIN_HASH"
echo ""
echo "IMPORTANT: Save these credentials securely!"
echo ""

echo ""
echo "Step 8: Installing systemd service..."
cat > /etc/systemd/system/bondlink-server.service << 'EOF'
[Unit]
Description=Bondlink Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/bondlink-server
Environment="PATH=/opt/bondlink-server/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/opt/bondlink-server/venv/bin/python3 -m server.daemon /etc/bondlink-server/server.yaml
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=bondlink-server

# Resource limits
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

echo ""
echo "Step 9: Enabling IP forwarding..."
sysctl -w net.ipv4.ip_forward=1
if ! grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf; then
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
fi

echo ""
echo "=================================="
echo "Installation Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "  1. Edit configuration: nano /etc/bondlink-server/server.yaml"
echo "  2. Update admin password hash in configuration"
echo "  3. Add client tokens to configuration"
echo "  4. Start the server: systemctl start bondlink-server"
echo "  5. Check status: systemctl status bondlink-server"
echo "  6. View logs: journalctl -u bondlink-server -f"
echo "  7. Enable auto-start: systemctl enable bondlink-server"
echo ""
echo "Web UI will be available at: http://YOUR_SERVER_IP:80"
echo "API will be available at: http://YOUR_SERVER_IP:8080"
echo ""
echo "Use the CLI tool:"
echo "  /opt/bondlink-server/venv/bin/bondlink-server --help"
echo ""
