#!/usr/bin/env python3
"""Bondlink Server - Multi-Client Tunnel Aggregation Setup"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="bondlink-server",
    version="1.0.0",
    author="Bondlink Team",
    description="Production-ready VPS server for multi-client WAN bonding aggregation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/bondlink",
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Networking",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.10",
    install_requires=[
        "psutil>=5.9.8",
        "netifaces>=0.11.0",
        "pyroute2>=0.7.12",
        "aiohttp>=3.9.0",
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "pyyaml>=6.0.1",
        "structlog>=24.1.0",
        "cryptography>=42.0.0",
        "passlib[bcrypt]>=1.7.4",
        "python-jose[cryptography]>=3.3.0",
        "sqlalchemy>=2.0.25",
        "aiosqlite>=0.19.0",
        "click>=8.1.7",
        "rich>=13.7.0",
    ],
    entry_points={
        "console_scripts": [
            "bondlink-server=server.cli:main",
            "bondlink-server-daemon=server.daemon:main",
        ],
    },
)
