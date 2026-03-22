"""Traffic routing and packet reordering"""

import asyncio
import struct
import socket
from typing import Dict, List, Optional, Deque
from collections import deque, defaultdict
from dataclasses import dataclass

from server.core.config import Config
from server.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PacketBuffer:
    """Packet in reordering buffer"""
    sequence: int
    data: bytes
    received_at: float
    tunnel_id: str


class TrafficRouter:
    """Traffic router with packet reordering"""
    
    def __init__(self, config: Config):
        """Initialize traffic router
        
        Args:
            config: Server configuration
        """
        self.config = config
        
        # Reordering buffers (per client)
        self.buffers: Dict[str, Deque[PacketBuffer]] = defaultdict(deque)
        self.expected_sequence: Dict[str, int] = defaultdict(int)
        
        # TUN interface for routing
        self.tun_fd = None
        self.running = False
        
        # Statistics
        self.routed_packets = 0
        self.dropped_packets = 0
        self.reordered_packets = 0
        
    async def start(self):
        """Start the traffic router"""
        logger.info("starting_traffic_router",
                   interface=self.config.routing.tun_interface)
        
        # Create TUN interface
        await self._create_tun_interface()
        
        self.running = True
        
        # Start background tasks
        asyncio.create_task(self._process_tun_packets())
        asyncio.create_task(self._flush_buffers())
        
        logger.info("traffic_router_started")
    
    async def stop(self):
        """Stop the traffic router"""
        logger.info("stopping_traffic_router")
        self.running = False
        
        if self.tun_fd:
            self.tun_fd.close()
        
        logger.info("traffic_router_stopped")
    
    async def _create_tun_interface(self):
        """Create TUN interface"""
        # This would use pyroute2 or similar to create TUN interface
        # For now, placeholder
        logger.info("tun_interface_created",
                   interface=self.config.routing.tun_interface,
                   address=self.config.routing.tun_address,
                   netmask=self.config.routing.tun_netmask)
    
    async def route_packet(self, client_id: str, tunnel_id: str, sequence: int, data: bytes):
        """Route a packet from a client tunnel
        
        Args:
            client_id: Client ID
            tunnel_id: Tunnel ID
            sequence: Packet sequence number
            data: Packet data
        """
        try:
            if not self.config.reordering.enabled:
                # No reordering, forward immediately
                await self._forward_packet(data)
                self.routed_packets += 1
                return
            
            # Add to reordering buffer
            buffer = self.buffers[client_id]
            expected = self.expected_sequence[client_id]
            
            if sequence == expected:
                # In-order packet, forward immediately
                await self._forward_packet(data)
                self.routed_packets += 1
                self.expected_sequence[client_id] = expected + 1
                
                # Check if we can forward buffered packets
                await self._flush_client_buffer(client_id)
                
            elif sequence > expected:
                # Out-of-order packet, buffer it
                buffer.append(PacketBuffer(
                    sequence=sequence,
                    data=data,
                    received_at=asyncio.get_event_loop().time(),
                    tunnel_id=tunnel_id
                ))
                
                # Keep buffer sorted by sequence
                buffer = deque(sorted(buffer, key=lambda p: p.sequence))
                self.buffers[client_id] = buffer
                
                # Check buffer size
                if len(buffer) > self.config.reordering.buffer_size:
                    # Drop oldest packet
                    dropped = buffer.popleft()
                    self.dropped_packets += 1
                    logger.warning("buffer_overflow",
                                 client_id=client_id,
                                 dropped_sequence=dropped.sequence)
            else:
                # Duplicate or old packet, drop it
                self.dropped_packets += 1
                logger.debug("duplicate_packet",
                           client_id=client_id,
                           sequence=sequence,
                           expected=expected)
                
        except Exception as e:
            logger.error("routing_error", error=str(e), client_id=client_id)
    
    async def _flush_client_buffer(self, client_id: str):
        """Flush buffered packets for a client
        
        Args:
            client_id: Client ID
        """
        buffer = self.buffers[client_id]
        expected = self.expected_sequence[client_id]
        
        # Forward contiguous packets
        while buffer and buffer[0].sequence == expected:
            packet = buffer.popleft()
            await self._forward_packet(packet.data)
            self.routed_packets += 1
            self.reordered_packets += 1
            expected += 1
        
        self.expected_sequence[client_id] = expected
    
    async def _flush_buffers(self):
        """Periodically flush stale buffered packets"""
        while self.running:
            try:
                await asyncio.sleep(0.1)
                
                current_time = asyncio.get_event_loop().time()
                timeout = self.config.reordering.timeout_ms / 1000.0
                
                for client_id in list(self.buffers.keys()):
                    buffer = self.buffers[client_id]
                    
                    # Check for timed-out packets
                    while buffer and (current_time - buffer[0].received_at) > timeout:
                        packet = buffer.popleft()
                        
                        # Forward packet even if out of order
                        await self._forward_packet(packet.data)
                        self.routed_packets += 1
                        
                        # Update expected sequence
                        if packet.sequence >= self.expected_sequence[client_id]:
                            self.expected_sequence[client_id] = packet.sequence + 1
                        
                        logger.debug("packet_timeout",
                                   client_id=client_id,
                                   sequence=packet.sequence)
                        
            except Exception as e:
                logger.error("buffer_flush_error", error=str(e))
    
    async def _forward_packet(self, data: bytes):
        """Forward packet to TUN interface
        
        Args:
            data: Packet data
        """
        # Write to TUN interface
        # For now, placeholder
        pass
    
    async def _process_tun_packets(self):
        """Process packets from TUN interface (outbound)"""
        while self.running:
            try:
                # Read from TUN interface
                # For now, placeholder
                await asyncio.sleep(0.001)
                
            except Exception as e:
                logger.error("tun_read_error", error=str(e))
    
    def get_statistics(self) -> Dict:
        """Get routing statistics
        
        Returns:
            Statistics dict
        """
        return {
            "routed_packets": self.routed_packets,
            "dropped_packets": self.dropped_packets,
            "reordered_packets": self.reordered_packets,
            "buffer_usage": {
                client_id: len(buffer)
                for client_id, buffer in self.buffers.items()
            }
        }
