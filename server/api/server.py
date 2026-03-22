"""FastAPI server with authentication for Bondlink server"""

import asyncio
from typing import Dict, List, Optional, Set
from datetime import timedelta

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from server.core.config import Config
from server.core.auth import authenticate_user, create_access_token, verify_access_token, AuthenticationError
from server.core.database import Database
from server.core.logger import get_logger
from server.network.client_manager import ClientManager
from server.network.traffic_router import TrafficRouter

logger = get_logger(__name__)

security = HTTPBearer()


# Request/Response models
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class ClientStatus(BaseModel):
    client_id: str
    status: str
    tunnels: int
    rx_bytes: int
    tx_bytes: int
    last_seen: float


# Dependency for authentication
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    config: Config = None
) -> Dict[str, str]:
    """Verify JWT token and return user info
    
    Args:
        credentials: HTTP authorization credentials
        config: Server configuration
        
    Returns:
        User info dict
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        token = credentials.credentials
        payload = verify_access_token(token, config)
        
        username = payload.get("sub")
        if username is None:
            raise AuthenticationError("Invalid token payload")
        
        return {
            "username": username,
            "role": payload.get("role", "user")
        }
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


class ConnectionManager:
    """WebSocket connection manager"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        
    async def connect(self, websocket: WebSocket):
        """Connect a WebSocket client"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info("websocket_connected", total=len(self.active_connections))
        
    def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket client"""
        self.active_connections.discard(websocket)
        logger.info("websocket_disconnected", total=len(self.active_connections))
        
    async def broadcast(self, data: Dict):
        """Broadcast data to all connected clients"""
        dead_connections = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                dead_connections.add(connection)
        
        # Clean up dead connections
        for connection in dead_connections:
            self.disconnect(connection)


class BondlinkServerAPI:
    """Bondlink server API"""
    
    def __init__(self, config: Config, database: Database, 
                 client_manager: ClientManager, traffic_router: TrafficRouter):
        """Initialize API server
        
        Args:
            config: Server configuration
            database: Database instance
            client_manager: Client manager instance
            traffic_router: Traffic router instance
        """
        self.config = config
        self.database = database
        self.client_manager = client_manager
        self.traffic_router = traffic_router
        self.connection_manager = ConnectionManager()
        
        # Create FastAPI app
        self.app = FastAPI(
            title="Bondlink Server API",
            description="Multi-client bonding router server",
            version="1.0.0"
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Setup routes
        self._setup_routes()
        
    def _setup_routes(self):
        """Setup API routes"""
        
        # Public routes
        @self.app.post("/api/login", response_model=LoginResponse)
        async def login(request: LoginRequest):
            """Login endpoint"""
            user = authenticate_user(request.username, request.password, self.config)
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Create access token
            access_token = create_access_token(
                data={"sub": user["username"], "role": user["role"]},
                config=self.config
            )
            
            logger.info("user_logged_in", username=user["username"])
            
            return LoginResponse(
                access_token=access_token,
                username=user["username"],
                role=user["role"]
            )
        
        # Protected routes
        def get_config():
            return self.config
        
        @self.app.get("/api/status")
        async def get_status(user: Dict = Depends(lambda: get_current_user(config=self.config))):
            """Get server status"""
            clients = self.client_manager.get_all_clients_status()
            router_stats = self.traffic_router.get_statistics()
            
            return {
                "status": "running",
                "total_clients": len(clients),
                "active_clients": sum(1 for c in clients.values() if c["active_tunnels"] > 0),
                "total_tunnels": sum(c["active_tunnels"] for c in clients.values()),
                "router_stats": router_stats,
                "uptime": 0  # TODO: Track uptime
            }
        
        @self.app.get("/api/clients")
        async def get_clients(user: Dict = Depends(lambda: get_current_user(config=self.config))):
            """Get all clients"""
            clients = self.client_manager.get_all_clients_status()
            
            return {
                "clients": [
                    {
                        "client_id": client_id,
                        "active_tunnels": status["active_tunnels"],
                        "rx_bytes": status["rx_bytes"],
                        "tx_bytes": status["tx_bytes"],
                        "rx_packets": status["rx_packets"],
                        "tx_packets": status["tx_packets"],
                        "last_seen": status["last_seen"],
                        "tunnels": status["tunnels"]
                    }
                    for client_id, status in clients.items()
                ]
            }
        
        @self.app.get("/api/clients/{client_id}")
        async def get_client(client_id: str, user: Dict = Depends(lambda: get_current_user(config=self.config))):
            """Get specific client"""
            status = self.client_manager.get_client_status(client_id)
            
            if not status:
                raise HTTPException(status_code=404, detail="Client not found")
            
            return status
        
        @self.app.get("/api/router/stats")
        async def get_router_stats(user: Dict = Depends(lambda: get_current_user(config=self.config))):
            """Get router statistics"""
            return self.traffic_router.get_statistics()
        
        # WebSocket endpoint
        @self.app.websocket("/api/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates"""
            await self.connection_manager.connect(websocket)
            
            try:
                # Keep connection alive
                while True:
                    # Wait for messages (ping/pong)
                    try:
                        await asyncio.wait_for(websocket.receive_text(), timeout=30)
                    except asyncio.TimeoutError:
                        # Send keepalive
                        await websocket.send_json({"type": "keepalive"})
                        
            except WebSocketDisconnect:
                self.connection_manager.disconnect(websocket)
        
        # Serve static files and index
        @self.app.get("/")
        async def serve_index():
            """Serve index page"""
            return FileResponse("web/login.html")
        
        @self.app.get("/dashboard")
        async def serve_dashboard():
            """Serve dashboard page"""
            return FileResponse("web/dashboard.html")
    
    async def start_broadcast_loop(self):
        """Start broadcasting updates to WebSocket clients"""
        while True:
            try:
                await asyncio.sleep(1)
                
                # Get current status
                clients = self.client_manager.get_all_clients_status()
                router_stats = self.traffic_router.get_statistics()
                
                # Broadcast to all connected clients
                await self.connection_manager.broadcast({
                    "type": "update",
                    "timestamp": asyncio.get_event_loop().time(),
                    "clients": [
                        {
                            "client_id": client_id,
                            "active_tunnels": status["active_tunnels"],
                            "rx_bytes": status["rx_bytes"],
                            "tx_bytes": status["tx_bytes"],
                            "last_seen": status["last_seen"],
                        }
                        for client_id, status in clients.items()
                    ],
                    "router_stats": router_stats
                })
                
            except Exception as e:
                logger.error("broadcast_error", error=str(e))
