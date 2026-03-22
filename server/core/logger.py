"""Logging setup for Bondlink server"""

import os
import sys
import logging
import structlog
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

from server.core.config import LoggingConfig


def setup_logging(config: LoggingConfig) -> structlog.BoundLogger:
    """Setup structured logging with rotation
    
    Args:
        config: Logging configuration
        
    Returns:
        Configured structlog logger
    """
    # Create log directory if it doesn't exist
    log_file = Path(config.file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure log level
    log_level = getattr(logging, config.level.upper(), logging.INFO)
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        handlers=[]
    )
    
    # Setup file handler with rotation
    file_handler = RotatingFileHandler(
        config.file,
        maxBytes=config.max_size_mb * 1024 * 1024,
        backupCount=config.backup_count,
    )
    file_handler.setLevel(log_level)
    
    handlers = [file_handler]
    
    # Add console handler if enabled
    if config.console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        handlers.append(console_handler)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    for handler in handlers:
        root_logger.addHandler(handler)
    
    # Configure structlog
    if config.format == "json":
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    return structlog.get_logger()


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """Get a logger instance
    
    Args:
        name: Logger name (optional)
        
    Returns:
        Structlog logger instance
    """
    return structlog.get_logger(name)
