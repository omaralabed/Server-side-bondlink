"""Bondlink Server - Multi-Client Tunnel Aggregation"""

__version__ = "1.0.0"
__author__ = "Bondlink Team"
__description__ = "Production-ready VPS server for multi-client WAN bonding aggregation"

from server.core.config import Config
from server.core.logger import setup_logging

__all__ = ["Config", "setup_logging"]
