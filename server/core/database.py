"""Database models and session management"""

import asyncio
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from server.core.config import DatabaseConfig

Base = declarative_base()


class Client(Base):
    """Client model"""
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(200))
    description = Column(Text)
    status = Column(String(50), default="disconnected")  # disconnected, connected, active
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Client info
    version = Column(String(50))
    hostname = Column(String(200))
    os_info = Column(String(200))
    
    # Statistics
    total_rx_bytes = Column(Integer, default=0)
    total_tx_bytes = Column(Integer, default=0)
    total_rx_packets = Column(Integer, default=0)
    total_tx_packets = Column(Integer, default=0)
    
    # Relationships
    tunnels = relationship("Tunnel", back_populates="client", cascade="all, delete-orphan")
    stats = relationship("ClientStats", back_populates="client", cascade="all, delete-orphan")


class Tunnel(Base):
    """Tunnel model"""
    __tablename__ = "tunnels"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    tunnel_id = Column(String(100), unique=True, index=True, nullable=False)
    
    # Tunnel info
    wan_interface = Column(String(100))
    protocol = Column(String(20))  # udp, tcp
    local_address = Column(String(100))
    local_port = Column(Integer)
    remote_address = Column(String(100))
    remote_port = Column(Integer)
    
    # Status
    status = Column(String(50), default="disconnected")
    connected_at = Column(DateTime)
    disconnected_at = Column(DateTime)
    last_heartbeat = Column(DateTime)
    
    # Statistics
    rx_bytes = Column(Integer, default=0)
    tx_bytes = Column(Integer, default=0)
    rx_packets = Column(Integer, default=0)
    tx_packets = Column(Integer, default=0)
    packet_loss = Column(Float, default=0.0)
    latency_ms = Column(Float, default=0.0)
    
    # Relationships
    client = relationship("Client", back_populates="tunnels")


class ClientStats(Base):
    """Client statistics snapshots"""
    __tablename__ = "client_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Bandwidth (bytes per second)
    rx_rate = Column(Float, default=0.0)
    tx_rate = Column(Float, default=0.0)
    
    # Total traffic
    total_rx_bytes = Column(Integer, default=0)
    total_tx_bytes = Column(Integer, default=0)
    
    # Tunnel count
    active_tunnels = Column(Integer, default=0)
    
    # Relationships
    client = relationship("Client", back_populates="stats")


class Database:
    """Database manager"""
    
    def __init__(self, config: DatabaseConfig):
        """Initialize database
        
        Args:
            config: Database configuration
        """
        self.config = config
        self.engine = None
        self.async_session = None
        
    async def initialize(self):
        """Initialize database connection and create tables"""
        # Create database directory if needed
        db_path = Path(self.config.url.replace("sqlite:///", "").replace("sqlite+aiosqlite:///", ""))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert sqlite URL to async
        if self.config.url.startswith("sqlite://"):
            db_url = self.config.url.replace("sqlite://", "sqlite+aiosqlite://")
        else:
            db_url = self.config.url
        
        # Create async engine
        self.engine = create_async_engine(
            db_url,
            echo=self.config.echo,
            pool_size=self.config.pool_size,
            max_overflow=self.config.max_overflow,
        )
        
        # Create session factory
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        # Create tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def close(self):
        """Close database connection"""
        if self.engine:
            await self.engine.dispose()
    
    def get_session(self) -> AsyncSession:
        """Get a database session
        
        Returns:
            Async database session
        """
        return self.async_session()
    
    # Client operations
    async def get_client_by_id(self, client_id: str) -> Optional[Client]:
        """Get client by ID
        
        Args:
            client_id: Client ID
            
        Returns:
            Client or None
        """
        async with self.get_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Client).where(Client.client_id == client_id)
            )
            return result.scalar_one_or_none()
    
    async def create_client(self, client_id: str, name: str = None, description: str = None) -> Client:
        """Create a new client
        
        Args:
            client_id: Client ID
            name: Client name
            description: Client description
            
        Returns:
            Created client
        """
        async with self.get_session() as session:
            client = Client(
                client_id=client_id,
                name=name or client_id,
                description=description
            )
            session.add(client)
            await session.commit()
            await session.refresh(client)
            return client
    
    async def update_client_status(self, client_id: str, status: str, **kwargs):
        """Update client status
        
        Args:
            client_id: Client ID
            status: New status
            **kwargs: Additional fields to update
        """
        async with self.get_session() as session:
            from sqlalchemy import select, update
            
            values = {"status": status, "last_seen": datetime.utcnow()}
            values.update(kwargs)
            
            await session.execute(
                update(Client).where(Client.client_id == client_id).values(**values)
            )
            await session.commit()
    
    async def list_clients(self) -> List[Client]:
        """List all clients
        
        Returns:
            List of clients
        """
        async with self.get_session() as session:
            from sqlalchemy import select
            result = await session.execute(select(Client))
            return result.scalars().all()
    
    # Tunnel operations
    async def create_tunnel(self, client_id: str, tunnel_id: str, **kwargs) -> Tunnel:
        """Create a new tunnel
        
        Args:
            client_id: Client ID
            tunnel_id: Tunnel ID
            **kwargs: Additional tunnel fields
            
        Returns:
            Created tunnel
        """
        async with self.get_session() as session:
            from sqlalchemy import select
            
            # Get client
            result = await session.execute(
                select(Client).where(Client.client_id == client_id)
            )
            client = result.scalar_one()
            
            # Create tunnel
            tunnel = Tunnel(
                client_id=client.id,
                tunnel_id=tunnel_id,
                **kwargs
            )
            session.add(tunnel)
            await session.commit()
            await session.refresh(tunnel)
            return tunnel
    
    async def update_tunnel_status(self, tunnel_id: str, status: str, **kwargs):
        """Update tunnel status
        
        Args:
            tunnel_id: Tunnel ID
            status: New status
            **kwargs: Additional fields to update
        """
        async with self.get_session() as session:
            from sqlalchemy import update
            
            values = {"status": status, "last_heartbeat": datetime.utcnow()}
            if status == "connected":
                values["connected_at"] = datetime.utcnow()
            elif status == "disconnected":
                values["disconnected_at"] = datetime.utcnow()
            
            values.update(kwargs)
            
            await session.execute(
                update(Tunnel).where(Tunnel.tunnel_id == tunnel_id).values(**values)
            )
            await session.commit()
    
    async def get_client_tunnels(self, client_id: str) -> List[Tunnel]:
        """Get all tunnels for a client
        
        Args:
            client_id: Client ID
            
        Returns:
            List of tunnels
        """
        async with self.get_session() as session:
            from sqlalchemy import select
            
            result = await session.execute(
                select(Tunnel)
                .join(Client)
                .where(Client.client_id == client_id)
            )
            return result.scalars().all()
    
    # Statistics operations
    async def add_client_stats(self, client_id: str, rx_rate: float, tx_rate: float, 
                              total_rx_bytes: int, total_tx_bytes: int, active_tunnels: int):
        """Add client statistics snapshot
        
        Args:
            client_id: Client ID
            rx_rate: RX rate (bytes/sec)
            tx_rate: TX rate (bytes/sec)
            total_rx_bytes: Total RX bytes
            total_tx_bytes: Total TX bytes
            active_tunnels: Number of active tunnels
        """
        async with self.get_session() as session:
            from sqlalchemy import select
            
            # Get client
            result = await session.execute(
                select(Client).where(Client.client_id == client_id)
            )
            client = result.scalar_one()
            
            # Create stats
            stats = ClientStats(
                client_id=client.id,
                rx_rate=rx_rate,
                tx_rate=tx_rate,
                total_rx_bytes=total_rx_bytes,
                total_tx_bytes=total_tx_bytes,
                active_tunnels=active_tunnels
            )
            session.add(stats)
            await session.commit()
