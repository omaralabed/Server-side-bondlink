"""Configuration management for Bondlink server"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ClientToken:
    """Client authentication token configuration"""
    token: str
    client_id: str
    description: str = ""


@dataclass
class ServerConfig:
    """Server listening configuration"""
    host: str
    tunnel_port: int
    web_port: int
    api_port: int
    client_tokens: List[ClientToken] = field(default_factory=list)


@dataclass
class WebUser:
    """Web UI user configuration"""
    username: str
    password_hash: str
    role: str = "admin"


@dataclass
class WebAuthConfig:
    """Web UI authentication configuration"""
    enabled: bool = True
    users: List[WebUser] = field(default_factory=list)
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60


@dataclass
class TunnelConfig:
    """Tunnel configuration"""
    protocol: str = "udp"
    mtu: int = 1400
    encryption: bool = True
    compression: bool = False
    send_buffer_size: int = 2097152
    recv_buffer_size: int = 2097152
    client_timeout: int = 30
    heartbeat_interval: int = 10
    max_clients: int = 50


@dataclass
class RoutingConfig:
    """Traffic routing configuration"""
    enable_forwarding: bool = True
    enable_masquerading: bool = True
    default_interface: str = "eth0"
    load_balance_mode: str = "round_robin"


@dataclass
class ReorderingConfig:
    """Packet reordering configuration"""
    enabled: bool = True
    buffer_size: int = 1000
    max_delay_ms: int = 100


@dataclass
class DatabaseConfig:
    """Database configuration"""
    type: str = "sqlite"
    path: str = "/var/lib/bondlink/server.db"
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    file: str = "/var/log/bondlink/server.log"
    max_size_mb: int = 100
    backup_count: int = 5
    console: bool = True
    format: str = "json"


@dataclass
class MonitoringConfig:
    """Monitoring configuration"""
    prometheus_enabled: bool = True
    prometheus_port: int = 9091
    stats_interval: int = 10
    keep_stats_days: int = 30


@dataclass
class SystemConfig:
    """System configuration"""
    run_as_user: str = "root"
    pid_file: str = "/var/run/bondlink/server.pid"
    max_bandwidth_mbps: int = 0
    max_tunnels_per_client: int = 10


class Config:
    """Main server configuration class"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration
        
        Args:
            config_path: Path to configuration file. If None, uses default locations.
        """
        self.config_path = self._find_config_path(config_path)
        self._raw_config: Dict[str, Any] = {}
        self.load()
        
    def _find_config_path(self, config_path: Optional[str] = None) -> Path:
        """Find configuration file path
        
        Args:
            config_path: Explicit config path or None to search default locations
            
        Returns:
            Path to configuration file
        """
        if config_path:
            return Path(config_path)
            
        # Search order: CWD, /etc/bondlink, package config dir
        search_paths = [
            Path.cwd() / "config" / "server.yaml",
            Path("/etc/bondlink/server.yaml"),
            Path(__file__).parent.parent.parent / "config" / "server.yaml",
        ]
        
        for path in search_paths:
            if path.exists():
                return path
                
        # Return default path even if it doesn't exist
        return search_paths[0]
    
    def load(self) -> None:
        """Load configuration from file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
            
        with open(self.config_path, "r") as f:
            self._raw_config = yaml.safe_load(f)
            
        # Parse configuration sections
        self.server = self._parse_server()
        self.web_auth = self._parse_web_auth()
        self.tunnel = self._parse_tunnel()
        self.routing = self._parse_routing()
        self.reordering = self._parse_reordering()
        self.database = self._parse_database()
        self.logging = self._parse_logging()
        self.monitoring = self._parse_monitoring()
        self.system = self._parse_system()
        
    def _parse_server(self) -> ServerConfig:
        """Parse server configuration"""
        server = self._raw_config.get("server", {})
        
        # Parse client tokens
        tokens = []
        for token_data in server.get("client_tokens", []):
            tokens.append(ClientToken(
                token=token_data.get("token", ""),
                client_id=token_data.get("client_id", ""),
                description=token_data.get("description", "")
            ))
        
        return ServerConfig(
            host=server.get("host", "0.0.0.0"),
            tunnel_port=server.get("tunnel_port", 8443),
            web_port=server.get("web_port", 80),
            api_port=server.get("api_port", 8080),
            client_tokens=tokens
        )
    
    def _parse_web_auth(self) -> WebAuthConfig:
        """Parse web authentication configuration"""
        auth = self._raw_config.get("web_auth", {})
        
        # Parse users
        users = []
        for user_data in auth.get("users", []):
            users.append(WebUser(
                username=user_data.get("username", ""),
                password_hash=user_data.get("password_hash", ""),
                role=user_data.get("role", "admin")
            ))
        
        return WebAuthConfig(
            enabled=auth.get("enabled", True),
            users=users,
            jwt_secret=auth.get("jwt_secret", ""),
            jwt_algorithm=auth.get("jwt_algorithm", "HS256"),
            access_token_expire_minutes=auth.get("access_token_expire_minutes", 60)
        )
    
    def _parse_tunnel(self) -> TunnelConfig:
        """Parse tunnel configuration"""
        tunnel = self._raw_config.get("tunnel", {})
        return TunnelConfig(
            protocol=tunnel.get("protocol", "udp"),
            mtu=tunnel.get("mtu", 1400),
            encryption=tunnel.get("encryption", True),
            compression=tunnel.get("compression", False),
            send_buffer_size=tunnel.get("send_buffer_size", 2097152),
            recv_buffer_size=tunnel.get("recv_buffer_size", 2097152),
            client_timeout=tunnel.get("client_timeout", 30),
            heartbeat_interval=tunnel.get("heartbeat_interval", 10),
            max_clients=tunnel.get("max_clients", 50)
        )
    
    def _parse_routing(self) -> RoutingConfig:
        """Parse routing configuration"""
        routing = self._raw_config.get("routing", {})
        return RoutingConfig(
            enable_forwarding=routing.get("enable_forwarding", True),
            enable_masquerading=routing.get("enable_masquerading", True),
            default_interface=routing.get("default_interface", "eth0"),
            load_balance_mode=routing.get("load_balance_mode", "round_robin")
        )
    
    def _parse_reordering(self) -> ReorderingConfig:
        """Parse reordering configuration"""
        reorder = self._raw_config.get("reordering", {})
        return ReorderingConfig(
            enabled=reorder.get("enabled", True),
            buffer_size=reorder.get("buffer_size", 1000),
            max_delay_ms=reorder.get("max_delay_ms", 100)
        )
    
    def _parse_database(self) -> DatabaseConfig:
        """Parse database configuration"""
        db = self._raw_config.get("database", {})
        return DatabaseConfig(
            type=db.get("type", "sqlite"),
            path=db.get("path", "/var/lib/bondlink/server.db"),
            host=db.get("host"),
            port=db.get("port"),
            database=db.get("database"),
            username=db.get("username"),
            password=db.get("password")
        )
    
    def _parse_logging(self) -> LoggingConfig:
        """Parse logging configuration"""
        logging = self._raw_config.get("logging", {})
        return LoggingConfig(
            level=logging.get("level", "INFO"),
            file=logging.get("file", "/var/log/bondlink/server.log"),
            max_size_mb=logging.get("max_size_mb", 100),
            backup_count=logging.get("backup_count", 5),
            console=logging.get("console", True),
            format=logging.get("format", "json")
        )
    
    def _parse_monitoring(self) -> MonitoringConfig:
        """Parse monitoring configuration"""
        monitoring = self._raw_config.get("monitoring", {})
        return MonitoringConfig(
            prometheus_enabled=monitoring.get("prometheus_enabled", True),
            prometheus_port=monitoring.get("prometheus_port", 9091),
            stats_interval=monitoring.get("stats_interval", 10),
            keep_stats_days=monitoring.get("keep_stats_days", 30)
        )
    
    def _parse_system(self) -> SystemConfig:
        """Parse system configuration"""
        system = self._raw_config.get("system", {})
        return SystemConfig(
            run_as_user=system.get("run_as_user", "root"),
            pid_file=system.get("pid_file", "/var/run/bondlink/server.pid"),
            max_bandwidth_mbps=system.get("max_bandwidth_mbps", 0),
            max_tunnels_per_client=system.get("max_tunnels_per_client", 10)
        )
    
    def validate(self) -> List[str]:
        """Validate configuration
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Validate client tokens
        if not self.server.client_tokens:
            errors.append("At least one client token is required")
        
        for token in self.server.client_tokens:
            if not token.token or token.token.startswith("CHANGE_ME"):
                errors.append(f"Invalid token for client {token.client_id}")
            if not token.client_id:
                errors.append("Client ID is required for all tokens")
        
        # Validate web auth
        if self.web_auth.enabled:
            if not self.web_auth.jwt_secret or self.web_auth.jwt_secret.startswith("CHANGE_ME"):
                errors.append("JWT secret must be set to a secure value")
            if not self.web_auth.users:
                errors.append("At least one web user is required when authentication is enabled")
        
        return errors
    
    def get_client_id_by_token(self, token: str) -> Optional[str]:
        """Get client ID by authentication token
        
        Args:
            token: Authentication token
            
        Returns:
            Client ID or None if not found
        """
        for client_token in self.server.client_tokens:
            if client_token.token == token:
                return client_token.client_id
        return None
