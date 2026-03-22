"""Main server daemon"""

import asyncio
import signal
import sys
from pathlib import Path

import uvicorn

from server.core.config import Config
from server.core.logger import setup_logging, get_logger
from server.core.database import Database
from server.network.client_manager import ClientManager
from server.network.traffic_router import TrafficRouter
from server.api.server import BondlinkServerAPI

logger = None


class BondlinkServer:
    """Main Bondlink server daemon"""
    
    def __init__(self, config_path: str):
        """Initialize server
        
        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        self.config = Config.load(config_path)
        
        # Setup logging
        global logger
        logger = setup_logging(self.config.logging)
        
        logger.info("bondlink_server_starting",
                   version="1.0.0",
                   config=config_path)
        
        # Initialize components
        self.database = Database(self.config.database)
        self.client_manager = ClientManager(self.config, self.database)
        self.traffic_router = TrafficRouter(self.config)
        self.api_server = BondlinkServerAPI(
            self.config,
            self.database,
            self.client_manager,
            self.traffic_router
        )
        
        self.running = False
        
    async def start(self):
        """Start the server"""
        logger.info("starting_server_components")
        
        try:
            # Initialize database
            await self.database.initialize()
            logger.info("database_initialized")
            
            # Start client manager
            await self.client_manager.start()
            
            # Start traffic router
            await self.traffic_router.start()
            
            # Start API broadcast loop
            asyncio.create_task(self.api_server.start_broadcast_loop())
            
            self.running = True
            logger.info("server_started")
            
            # Start API server (blocking)
            config = uvicorn.Config(
                self.api_server.app,
                host=self.config.server.host,
                port=self.config.server.web_port,
                log_level="info"
            )
            server = uvicorn.Server(config)
            await server.serve()
            
        except Exception as e:
            logger.error("server_start_error", error=str(e), exc_info=True)
            await self.stop()
            sys.exit(1)
    
    async def stop(self):
        """Stop the server"""
        if not self.running:
            return
        
        logger.info("stopping_server")
        self.running = False
        
        # Stop components
        await self.traffic_router.stop()
        await self.client_manager.stop()
        await self.database.close()
        
        logger.info("server_stopped")
    
    def handle_signal(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("signal_received", signal=signum)
        asyncio.create_task(self.stop())


def main(config_path: str = None):
    """Main entry point
    
    Args:
        config_path: Path to configuration file
    """
    # Find config file
    if config_path is None:
        config_path = Config._find_config_path()
    
    # Create server
    server = BondlinkServer(config_path)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, lambda s, f: asyncio.create_task(server.stop()))
    signal.signal(signal.SIGTERM, lambda s, f: asyncio.create_task(server.stop()))
    
    # Run server
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        pass
    finally:
        if server.running:
            asyncio.run(server.stop())


if __name__ == "__main__":
    import sys
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    main(config_path)
