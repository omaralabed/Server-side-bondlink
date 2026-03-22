"""CLI for Bondlink server"""

import sys
import asyncio
import click
from rich.console import Console
from rich.table import Table
from rich.live import Live
from datetime import datetime
import getpass

from server.core.config import Config
from server.core.auth import hash_password, generate_token
from server.core.database import Database

console = Console()


@click.group()
@click.option('--config', default=None, help='Configuration file path')
@click.pass_context
def cli(ctx, config):
    """Bondlink Server CLI"""
    ctx.ensure_object(dict)
    
    # Load configuration
    try:
        if config:
            ctx.obj['config'] = Config.load(config)
        else:
            ctx.obj['config'] = Config.load()
    except Exception as e:
        console.print(f"[red]Failed to load configuration: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.pass_context
def status(ctx):
    """Show server status"""
    config = ctx.obj['config']
    
    # Create table
    table = Table(title="Bondlink Server Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Host", config.server.host)
    table.add_row("Tunnel Port", str(config.server.tunnel_port))
    table.add_row("Web Port", str(config.server.web_port))
    table.add_row("API Port", str(config.server.api_port))
    table.add_row("Max Clients", str(config.server.max_clients))
    table.add_row("Database", config.database.url)
    
    console.print(table)


@cli.command()
@click.pass_context
def clients(ctx):
    """List all clients"""
    config = ctx.obj['config']
    
    async def _list_clients():
        db = Database(config.database)
        await db.initialize()
        
        clients = await db.list_clients()
        
        if not clients:
            console.print("[yellow]No clients found[/yellow]")
            return
        
        # Create table
        table = Table(title="Connected Clients")
        table.add_column("Client ID", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Tunnels", style="magenta")
        table.add_column("RX", style="blue")
        table.add_column("TX", style="blue")
        table.add_column("Last Seen", style="yellow")
        
        for client in clients:
            status_color = "green" if client.status == "connected" else "red"
            table.add_row(
                client.client_id,
                f"[{status_color}]{client.status}[/{status_color}]",
                str(len(client.tunnels)),
                format_bytes(client.total_rx_bytes),
                format_bytes(client.total_tx_bytes),
                client.last_seen.strftime("%Y-%m-%d %H:%M:%S")
            )
        
        console.print(table)
        await db.close()
    
    asyncio.run(_list_clients())


@cli.command()
@click.argument('client_id')
@click.pass_context
def client_info(ctx, client_id):
    """Show detailed client information"""
    config = ctx.obj['config']
    
    async def _client_info():
        db = Database(config.database)
        await db.initialize()
        
        client = await db.get_client_by_id(client_id)
        
        if not client:
            console.print(f"[red]Client {client_id} not found[/red]")
            return
        
        # Client info table
        table = Table(title=f"Client: {client_id}")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Status", client.status)
        table.add_row("Version", client.version or "N/A")
        table.add_row("Hostname", client.hostname or "N/A")
        table.add_row("OS", client.os_info or "N/A")
        table.add_row("Total RX", format_bytes(client.total_rx_bytes))
        table.add_row("Total TX", format_bytes(client.total_tx_bytes))
        table.add_row("RX Packets", str(client.total_rx_packets))
        table.add_row("TX Packets", str(client.total_tx_packets))
        table.add_row("Last Seen", client.last_seen.strftime("%Y-%m-%d %H:%M:%S"))
        
        console.print(table)
        
        # Tunnels table
        tunnels = await db.get_client_tunnels(client_id)
        
        if tunnels:
            console.print("\n")
            tunnels_table = Table(title="Tunnels")
            tunnels_table.add_column("WAN Interface", style="cyan")
            tunnels_table.add_column("Protocol", style="green")
            tunnels_table.add_column("Status", style="yellow")
            tunnels_table.add_column("RX", style="blue")
            tunnels_table.add_column("TX", style="blue")
            
            for tunnel in tunnels:
                status_color = "green" if tunnel.status == "connected" else "red"
                tunnels_table.add_row(
                    tunnel.wan_interface,
                    tunnel.protocol,
                    f"[{status_color}]{tunnel.status}[/{status_color}]",
                    format_bytes(tunnel.rx_bytes),
                    format_bytes(tunnel.tx_bytes)
                )
            
            console.print(tunnels_table)
        
        await db.close()
    
    asyncio.run(_client_info())


@cli.command()
@click.argument('client_id')
@click.option('--name', help='Client name')
@click.option('--description', help='Client description')
@click.pass_context
def add_client(ctx, client_id, name, description):
    """Add a new client token"""
    config = ctx.obj['config']
    
    # Generate token
    token = generate_token()
    
    console.print(f"\n[green]Generated token for client {client_id}:[/green]")
    console.print(f"[cyan]{token}[/cyan]\n")
    
    console.print("[yellow]Add this to your server configuration:[/yellow]")
    console.print(f"""
client_tokens:
  - token: "{token}"
    client_id: "{client_id}"
    description: "{description or name or client_id}"
""")


@cli.command()
@click.argument('username')
@click.option('--role', default='admin', help='User role (admin/user)')
@click.pass_context
def add_user(ctx, username, role):
    """Add a new web UI user"""
    config = ctx.obj['config']
    
    # Get password
    password = getpass.getpass("Enter password: ")
    password_confirm = getpass.getpass("Confirm password: ")
    
    if password != password_confirm:
        console.print("[red]Passwords do not match[/red]")
        return
    
    # Hash password
    password_hash = hash_password(password)
    
    console.print(f"\n[green]Generated password hash for user {username}:[/green]")
    console.print(f"[cyan]{password_hash}[/cyan]\n")
    
    console.print("[yellow]Add this to your server configuration:[/yellow]")
    console.print(f"""
web_auth:
  users:
    - username: "{username}"
      password_hash: "{password_hash}"
      role: "{role}"
""")


def format_bytes(bytes_val):
    """Format bytes to human readable"""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.2f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / 1024 / 1024:.2f} MB"
    else:
        return f"{bytes_val / 1024 / 1024 / 1024:.2f} GB"


if __name__ == "__main__":
    cli()
