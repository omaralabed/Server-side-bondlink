"""Multi-client tunnel connection manager"""

import asyncio
import struct
import time
from typing import Dict, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime

from server.core.config import Config
from server.core.auth import authenticate_client
from server.core.database import Database
from server.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ClientConnection:
    """Active client connection"""
    client_id: str
    tunnels: Dict[str, 'TunnelConnection']  # tunnel_id -> tunnel
    last_seen: float
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_packets: int = 0
    tx_packets: int = 0
    
    def get_active_tunnel_count(self) -> int:
        """Get number of active tunnels"""
        return sum(1 for t in self.tunnels.values() if t.active)


@dataclass
class TunnelConnection:
    """Active tunnel connection"""
    tunnel_id: str
    client_id: str
    wan_interface: str
    address: Tuple[str, int]
    protocol: str
    connected_at: float
    last_heartbeat: float
    active: bool = True
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_packets: int = 0
    tx_packets: int = 0
    sequence: int = 0  # Last received sequence number


class ClientManager:
    """Multi-client connection manager"""
    
    def __init__(self, config: Config, database: Database):
        """Initialize client manager
        
        Args:
            config: Server configuration
            database: Database instance
        """
        self.config = config
        self.database = database
        self.clients: Dict[str, ClientConnection] = {}  # client_id -> connection
        self.tunnel_map: Dict[Tuple[str, int], str] = {}  # (host, port) -> tunnel_id
        self.lock = asyncio.Lock()
        
        # UDP socket for receiving tunnels
        self.sock = None
        self.running = False
        
        # Statistics
        self.total_rx_bytes = 0
        self.total_tx_bytes = 0
        self.total_clients = 0
        
    async def start(self):
        """Start the client manager"""
        logger.info("starting_client_manager", 
                   host=self.config.server.host,
                   port=self.config.server.tunnel_port)
        
        # Create UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setblocking(False)
        self.sock.bind((self.config.server.host, self.config.server.tunnel_port))
        
        self.running = True
        
        # Start background tasks
        asyncio.create_task(self._receive_loop())
        asyncio.create_task(self._heartbeat_monitor())
        asyncio.create_task(self._statistics_updater())
        
        logger.info("client_manager_started")
    
    async def stop(self):
        """Stop the client manager"""
        logger.info("stopping_client_manager")
        self.running = False
        
        # Disconnect all clients
        async with self.lock:
            for client_id in list(self.clients.keys()):
                await self._disconnect_client(client_id)
        
        if self.sock:
            self.sock.close()
        
        logger.info("client_manager_stopped")
    
    async def _receive_loop(self):
        """Receive packets from clients"""
        loop = asyncio.get_event_loop()
        
        while self.running:
            try:
                # Receive packet
                data, addr = await loop.sock_recvfrom(self.sock, 65535)
                
                # Process packet
                await self._process_packet(data, addr)
                
            except Exception as e:
                logger.error("receive_error", error=str(e))
                await asyncio.sleep(0.1)
    
    async def _process_packet(self, data: bytes, addr: Tuple[str, int]):
        """Process received packet
        
        Args:
            data: Packet data
            addr: Source address
        """
        try:
            # Parse packet header: type (1 byte) + tunnel_id (16 bytes) + sequence (4 bytes)
            if len(data) < 21:
                logger.warning("short_packet", length=len(data), addr=addr)
                return
            
            packet_type = data[0]
            tunnel_id = data[1:17].decode('utf-8').strip('\x00')
            sequence = struct.unpack('!I', data[17:21])[0]
            payload = data[21:]
            
            # Handle packet types
            if packet_type == 0x01:  # AUTH
                await self._handle_auth(tunnel_id, payload, addr)
            elif packet_type == 0x02:  # HEARTBEAT
                await self._handle_heartbeat(tunnel_id, addr)
            elif packet_type == 0x03:  # DATA
                await self._handle_data(tunnel_id, sequence, payload, addr)
            else:
                logger.warning("unknown_packet_type", type=packet_type, addr=addr)
                
        except Exception as e:
            logger.error("packet_processing_error", error=str(e), addr=addr)
    
    async def _handle_auth(self, tunnel_id: str, payload: bytes, addr: Tuple[str, int]):
        """Handle authentication packet
        
        Args:
            tunnel_id: Tunnel ID
            payload: Payload data (contains token and wan_interface)
            addr: Source address
        """
        try:
            # Parse payload: token (64 bytes) + wan_interface (16 bytes)
            if len(payload) < 80:
                logger.warning("short_auth_payload", length=len(payload), addr=addr)
                return
            
            token = payload[:64].decode('utf-8').strip('\x00')
            wan_interface = payload[64:80].decode('utf-8').strip('\x00')
            
            # Authenticate client
            client_id = authenticate_client(token, self.config)
            
            if not client_id:
                logger.warning("authentication_failed", tunnel_id=tunnel_id, addr=addr)
                # Send NACK
                response = struct.pack('!B', 0xFF)  # NACK
                await asyncio.get_event_loop().sock_sendto(self.sock, response, addr)
                return
            
            # Check max clients
            if len(self.clients) >= self.config.server.max_clients and client_id not in self.clients:
                logger.warning("max_clients_reached", client_id=client_id)
                response = struct.pack('!B', 0xFF)  # NACK
                await asyncio.get_event_loop().sock_sendto(self.sock, response, addr)
                return
            
            async with self.lock:
                # Create client connection if needed
                if client_id not in self.clients:
                    self.clients[client_id] = ClientConnection(
                        client_id=client_id,
                        tunnels={},
                        last_seen=time.time()
                    )
                    self.total_clients += 1
                    
                    # Create in database
                    await self.database.create_client(client_id)
                    logger.info("client_connected", client_id=client_id)
                
                client = self.clients[client_id]
                
                # Create tunnel connection
                tunnel = TunnelConnection(
                    tunnel_id=tunnel_id,
                    client_id=client_id,
                    wan_interface=wan_interface,
                    address=addr,
                    protocol="udp",
                    connected_at=time.time(),
                    last_heartbeat=time.time()
                )
                
                client.tunnels[tunnel_id] = tunnel
                self.tunnel_map[addr] = tunnel_id
                client.last_seen = time.time()
                
                # Update database
                await self.database.update_client_status(client_id, "connected")
                await self.database.create_tunnel(
                    client_id=client_id,
                    tunnel_id=tunnel_id,
                    wan_interface=wan_interface,
                    protocol="udp",
                    local_address=self.config.server.host,
                    local_port=self.config.server.tunnel_port,
                    remote_address=addr[0],
                    remote_port=addr[1],
                    status="connected"
                )
                
                logger.info("tunnel_connected", 
                          client_id=client_id,
                          tunnel_id=tunnel_id,
                          wan_interface=wan_interface,
                          addr=addr)
            
            # Send ACK
            response = struct.pack('!B', 0x00)  # ACK
            await asyncio.get_event_loop().sock_sendto(self.sock, response, addr)
            
        except Exception as e:
            logger.error("auth_error", error=str(e), addr=addr)
    
    async def _handle_heartbeat(self, tunnel_id: str, addr: Tuple[str, int]):
        """Handle heartbeat packet
        
        Args:
            tunnel_id: Tunnel ID
            addr: Source address
        """
        async with self.lock:
            if addr not in self.tunnel_map:
                logger.warning("unknown_tunnel_heartbeat", tunnel_id=tunnel_id, addr=addr)
                return
            
            mapped_tunnel_id = self.tunnel_map[addr]
            
            # Find client and tunnel
            for client in self.clients.values():
                if mapped_tunnel_id in client.tunnels:
                    tunnel = client.tunnels[mapped_tunnel_id]
                    tunnel.last_heartbeat = time.time()
                    client.last_seen = time.time()
                    
                    # Send heartbeat response
                    response = struct.pack('!B', 0x02)  # HEARTBEAT
                    await asyncio.get_event_loop().sock_sendto(self.sock, response, addr)
                    return
    
    async def _handle_data(self, tunnel_id: str, sequence: int, payload: bytes, addr: Tuple[str, int]):
        """Handle data packet
        
        Args:
            tunnel_id: Tunnel ID
            sequence: Packet sequence number
            payload: Packet payload
            addr: Source address
        """
        async with self.lock:
            if addr not in self.tunnel_map:
                return
            
            mapped_tunnel_id = self.tunnel_map[addr]
            
            # Find client and tunnel
            for client in self.clients.values():
                if mapped_tunnel_id in client.tunnels:
                    tunnel = client.tunnels[mapped_tunnel_id]
                    tunnel.last_heartbeat = time.time()
                    tunnel.rx_bytes += len(payload)
                    tunnel.rx_packets += 1
                    tunnel.sequence = sequence
                    
                    client.last_seen = time.time()
                    client.rx_bytes += len(payload)
                    client.rx_packets += 1
                    
                    self.total_rx_bytes += len(payload)
                    
                    # Forward to traffic router
                    # (Will be implemented in traffic_router.py)
                    return
    
    async def _heartbeat_monitor(self):
        """Monitor tunnel heartbeats and disconnect stale tunnels"""
        while self.running:
            try:
                await asyncio.sleep(5)
                
                current_time = time.time()
                timeout = self.config.tunnel.heartbeat_timeout_seconds
                
                async with self.lock:
                    # Check each client
                    for client_id in list(self.clients.keys()):
                        client = self.clients[client_id]
                        
                        # Check each tunnel
                        for tunnel_id in list(client.tunnels.keys()):
                            tunnel = client.tunnels[tunnel_id]
                            
                            # Check if tunnel is stale
                            if current_time - tunnel.last_heartbeat > timeout:
                                logger.warning("tunnel_timeout",
                                             client_id=client_id,
                                             tunnel_id=tunnel_id,
                                             last_heartbeat=tunnel.last_heartbeat)
                                
                                # Mark tunnel as inactive
                                tunnel.active = False
                                del self.tunnel_map[tunnel.address]
                                
                                # Update database
                                await self.database.update_tunnel_status(tunnel_id, "disconnected")
                        
                        # Remove inactive tunnels
                        client.tunnels = {
                            tid: t for tid, t in client.tunnels.items() if t.active
                        }
                        
                        # Disconnect client if no active tunnels
                        if not client.tunnels:
                            await self._disconnect_client(client_id)
                            
            except Exception as e:
                logger.error("heartbeat_monitor_error", error=str(e))
    
    async def _disconnect_client(self, client_id: str):
        """Disconnect a client
        
        Args:
            client_id: Client ID
        """
        if client_id in self.clients:
            client = self.clients[client_id]
            
            # Remove tunnel mappings
            for tunnel in client.tunnels.values():
                if tunnel.address in self.tunnel_map:
                    del self.tunnel_map[tunnel.address]
            
            # Update database
            await self.database.update_client_status(client_id, "disconnected")
            
            del self.clients[client_id]
            logger.info("client_disconnected", client_id=client_id)
    
    async def _statistics_updater(self):
        """Update client statistics in database"""
        while self.running:
            try:
                await asyncio.sleep(60)  # Update every minute
                
                async with self.lock:
                    for client in self.clients.values():
                        # Calculate rates (simple average over last minute)
                        rx_rate = client.rx_bytes / 60.0
                        tx_rate = client.tx_bytes / 60.0
                        
                        # Add to database
                        await self.database.add_client_stats(
                            client_id=client.client_id,
                            rx_rate=rx_rate,
                            tx_rate=tx_rate,
                            total_rx_bytes=client.rx_bytes,
                            total_tx_bytes=client.tx_bytes,
                            active_tunnels=client.get_active_tunnel_count()
                        )
                        
            except Exception as e:
                logger.error("statistics_updater_error", error=str(e))
    
    def get_client_status(self, client_id: str) -> Optional[Dict]:
        """Get client status
        
        Args:
            client_id: Client ID
            
        Returns:
            Client status dict or None
        """
        if client_id not in self.clients:
            return None
        
        client = self.clients[client_id]
        
        tunnels = []
        for tunnel in client.tunnels.values():
            tunnels.append({
                "tunnel_id": tunnel.tunnel_id,
                "wan_interface": tunnel.wan_interface,
                "address": tunnel.address,
                "active": tunnel.active,
                "rx_bytes": tunnel.rx_bytes,
                "tx_bytes": tunnel.tx_bytes,
                "rx_packets": tunnel.rx_packets,
                "tx_packets": tunnel.tx_packets,
            })
        
        return {
            "client_id": client.client_id,
            "tunnels": tunnels,
            "active_tunnels": client.get_active_tunnel_count(),
            "rx_bytes": client.rx_bytes,
            "tx_bytes": client.tx_bytes,
            "rx_packets": client.rx_packets,
            "tx_packets": client.tx_packets,
            "last_seen": client.last_seen,
        }
    
    def get_all_clients_status(self) -> Dict[str, Dict]:
        """Get status of all clients
        
        Returns:
            Dict of client_id -> status
        """
        return {
            client_id: self.get_client_status(client_id)
            for client_id in self.clients.keys()
        }


# Import socket
import socket
