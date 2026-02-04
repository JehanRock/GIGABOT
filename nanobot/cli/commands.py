"""CLI commands for GigaBot."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from nanobot import __version__, __logo__

app = typer.Typer(
    name="gigabot",
    help=f"{__logo__} GigaBot - Enterprise AI Assistant",
    no_args_is_help=True,
)

console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} GigaBot v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """GigaBot - Enterprise AI Assistant."""
    pass


# ============================================================================
# Setup / Onboard
# ============================================================================


@app.command()
def setup(
    non_interactive: bool = typer.Option(
        False, "--non-interactive", "-y",
        help="Run in non-interactive mode using environment variables"
    ),
    reset: bool = typer.Option(
        False, "--reset", "-r",
        help="Reset existing configuration"
    ),
):
    """Interactive setup wizard for GigaBot configuration."""
    from nanobot.cli.setup import run_setup_wizard
    
    success = run_setup_wizard(non_interactive=non_interactive, reset=reset)
    
    if success:
        if typer.confirm("\nStart GigaBot gateway now?", default=True):
            gateway()
    else:
        raise typer.Exit(1)


@app.command()
def onboard():
    """Initialize GigaBot configuration and workspace (legacy - use 'setup' instead)."""
    console.print("[yellow]Note: 'onboard' is deprecated. Use 'gigabot setup' for interactive wizard.[/yellow]\n")
    
    from nanobot.config.loader import get_config_path, save_config
    from nanobot.config.schema import Config
    from nanobot.utils.helpers import get_workspace_path
    
    config_path = get_config_path()
    
    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        if not typer.confirm("Overwrite?"):
            raise typer.Exit()
    
    # Create default config
    config = Config()
    save_config(config)
    console.print(f"[green]✓[/green] Created config at {config_path}")
    
    # Create workspace
    workspace = get_workspace_path()
    console.print(f"[green]✓[/green] Created workspace at {workspace}")
    
    # Create default bootstrap files
    _create_workspace_templates(workspace)
    
    console.print(f"\n{__logo__} GigaBot is ready!")
    console.print("\nNext steps:")
    console.print("  1. Run [cyan]gigabot setup[/cyan] for interactive configuration")
    console.print("  2. Or start with: [cyan]gigabot gateway[/cyan]")
    console.print("\n[dim]For full setup, run: gigabot setup[/dim]")




def _create_workspace_templates(workspace: Path):
    """Create default workspace template files."""
    templates = {
        "AGENTS.md": """# Agent Instructions

You are a helpful AI assistant. Be concise, accurate, and friendly.

## Guidelines

- Always explain what you're doing before taking actions
- Ask for clarification when the request is ambiguous
- Use tools to help accomplish tasks
- Remember important information in your memory files
""",
        "SOUL.md": """# Soul

I am GigaBot, an enterprise-grade AI assistant.

## Personality

- Helpful and professional
- Concise and accurate
- Proactive and reliable

## Values

- Accuracy over speed
- User privacy and security
- Transparency in actions
""",
        "USER.md": """# User

Information about the user goes here.

## Preferences

- Communication style: (casual/formal)
- Timezone: (your timezone)
- Language: (your preferred language)
""",
    }
    
    for filename, content in templates.items():
        file_path = workspace / filename
        if not file_path.exists():
            file_path.write_text(content)
            console.print(f"  [dim]Created {filename}[/dim]")
    
    # Create memory directory and MEMORY.md
    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)
    memory_file = memory_dir / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("""# Long-term Memory

This file stores important information that should persist across sessions.

## User Information

(Important facts about the user)

## Preferences

(User preferences learned over time)

## Important Notes

(Things to remember)
""")
        console.print("  [dim]Created memory/MEMORY.md[/dim]")


# ============================================================================
# Gateway / Server
# ============================================================================


def _check_setup_complete(config, force: bool = False) -> bool:
    """Check if setup is complete. Returns True if ready to start."""
    import os
    import sys
    
    # Check for API key in config or environment
    api_key = config.get_api_key()
    
    # Also check environment variables directly
    if not api_key:
        for env_var in ["OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"]:
            api_key = os.environ.get(env_var, "").strip()
            if api_key:
                break
    
    # If API key exists (from config or env), we can proceed
    # even if setup wasn't formally completed
    if api_key:
        if not config.security.auth.setup_complete:
            console.print("[dim]API key found. Skipping setup wizard.[/dim]")
        return True
    
    # No API key found - check if we can run interactively
    is_interactive = sys.stdin.isatty() and not force
    
    if not config.security.auth.setup_complete:
        console.print("[yellow]GigaBot has not been configured yet.[/yellow]")
        
        if is_interactive:
            console.print("\nRun [cyan]gigabot setup[/cyan] to configure GigaBot interactively.")
            console.print("Or use [cyan]--force[/cyan] to start anyway.\n")
            
            if typer.confirm("Run setup wizard now?", default=True):
                from nanobot.cli.setup import run_setup_wizard
                if not run_setup_wizard():
                    return False
                return True
            return False
        else:
            # Non-interactive mode (e.g., Docker)
            console.print("[red]Error: No API key configured.[/red]")
            console.print("\nSet one of these environment variables:")
            console.print("  - [cyan]OPENROUTER_API_KEY[/cyan]")
            console.print("  - [cyan]ANTHROPIC_API_KEY[/cyan]")
            console.print("  - [cyan]OPENAI_API_KEY[/cyan]")
            return False
    
    # Setup was completed but no API key
    console.print("[red]Error: No API key configured.[/red]")
    console.print("\nEither:")
    console.print("  1. Run [cyan]gigabot setup[/cyan] to configure interactively")
    console.print("  2. Set [cyan]OPENROUTER_API_KEY[/cyan] environment variable")
    console.print("  3. Edit [cyan]~/.nanobot/config.json[/cyan] directly")
    return False


@app.command()
def gateway(
    host: str = typer.Option("0.0.0.0", "--host", "-H", help="Host to bind to"),
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    force: bool = typer.Option(False, "--force", "-f", help="Start even if setup incomplete"),
):
    """Start the GigaBot gateway."""
    from nanobot.config.loader import load_config, get_data_dir
    from nanobot.bus.queue import MessageBus
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.agent.loop import AgentLoop
    from nanobot.channels.manager import ChannelManager
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronJob
    from nanobot.heartbeat.service import HeartbeatService
    from nanobot.nodes.manager import NodeManager, set_node_manager
    from nanobot.ui.server import UIServer
    
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    config = load_config()
    
    # Check setup status
    if not _check_setup_complete(config, force):
        raise typer.Exit(1)
    
    # Reload config in case setup was just run
    config = load_config()
    
    console.print(f"{__logo__} Starting GigaBot gateway on {host}:{port}...")
    
    # Create components
    bus = MessageBus()
    
    # Create provider (supports OpenRouter, Anthropic, OpenAI)
    api_key = config.get_api_key()
    api_base = config.get_api_base()
    
    provider = None
    if api_key:
        provider = LiteLLMProvider(
            api_key=api_key,
            api_base=api_base,
            default_model=config.agents.defaults.model
        )
        console.print(f"[green]✓[/green] LLM provider configured")
    else:
        console.print("[yellow]Warning: No API key configured - chat disabled[/yellow]")
        console.print("  Run [cyan]gigabot setup[/cyan] to configure API keys")
    
    # Create agent with tiered routing and swarm support (if provider available)
    agent = None
    if provider:
        agent = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=config.workspace_path,
            model=config.agents.defaults.model,
            config=config,  # Pass config for tiered routing and swarm
            max_iterations=config.agents.defaults.max_tool_iterations,
            brave_api_key=config.tools.web.search.api_key or None
        )
    
    # Create cron service
    async def on_cron_job(job: CronJob) -> str | None:
        """Execute a cron job through the agent."""
        if not agent:
            return "Agent not configured - no API key"
        response = await agent.process_direct(
            job.payload.message,
            session_key=f"cron:{job.id}"
        )
        # Optionally deliver to channel
        if job.payload.deliver and job.payload.to:
            from nanobot.bus.events import OutboundMessage
            await bus.publish_outbound(OutboundMessage(
                channel=job.payload.channel or "whatsapp",
                chat_id=job.payload.to,
                content=response or ""
            ))
        return response
    
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path, on_job=on_cron_job)
    
    # Create heartbeat service
    async def on_heartbeat(prompt: str) -> str:
        """Execute heartbeat through the agent."""
        if not agent:
            return "Agent not configured"
        return await agent.process_direct(prompt, session_key="heartbeat")
    
    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        on_heartbeat=on_heartbeat,
        interval_s=30 * 60,  # 30 minutes
        enabled=bool(agent)  # Only enable if agent is configured
    )
    
    # Create channel manager
    channels = ChannelManager(config, bus)
    
    # Create node manager if enabled
    node_manager: NodeManager | None = None
    if config.nodes.enabled:
        storage_path = Path(config.nodes.storage_path).expanduser()
        node_manager = NodeManager(
            storage_path=storage_path,
            auth_token=config.nodes.auth_token,
            auto_approve=config.nodes.auto_approve,
            ping_interval=config.nodes.ping_interval,
        )
        set_node_manager(node_manager)
        console.print(f"[green]✓[/green] Nodes system enabled")
    
    # Create UI server
    ui_server = UIServer(
        host=host,
        port=port,
        config=config,
        node_manager=node_manager,
        cron_service=cron,
    )
    
    # Set up config persistence handler
    from nanobot.config.loader import save_config as save_config_to_file
    
    def persist_config():
        """Save current config to file and initialize agent if API key is now available."""
        nonlocal agent, provider
        
        save_config_to_file(config)
        console.print("[dim]Config saved[/dim]")
        
        # Re-check API key and initialize agent if needed
        api_key = config.get_api_key()
        api_base = config.get_api_base()
        
        if not agent and api_key:
            console.print(f"[green]✓[/green] New API key detected, initializing agent...")
            
            provider = LiteLLMProvider(
                api_key=api_key,
                api_base=api_base,
                default_model=config.agents.defaults.model
            )
            
            agent = AgentLoop(
                bus=bus,
                provider=provider,
                workspace=config.workspace_path,
                model=config.agents.defaults.model,
                config=config,
                max_iterations=config.agents.defaults.max_tool_iterations,
                brave_api_key=config.tools.web.search.api_key or None
            )
            
            # Start the agent loop
            asyncio.create_task(agent.run())
            
            # Enable heartbeat if it was waiting for agent
            if not heartbeat.enabled:
                heartbeat.enabled = True
                asyncio.create_task(heartbeat.start())
                
            console.print(f"[green]✓[/green] Agent initialized and running")
    
    ui_server.set_save_config_handler(persist_config)
    
    # Set up chat handler
    async def handle_chat(
        message: str, 
        session_id: str, 
        model: str | None = None,
        thinking_level: str = "medium",
    ) -> str:
        if not agent:
            return "Chat is disabled - no API key configured. Go to Settings > Providers and enter your API key, then try again."
        return await agent.process_direct(
            message, 
            session_id,
            model=model,
            thinking_level=thinking_level,
        )
    
    ui_server.set_chat_handler(handle_chat)
    
    if channels.enabled_channels:
        console.print(f"[green]✓[/green] Channels enabled: {', '.join(channels.enabled_channels)}")
    else:
        console.print("[yellow]Info: No chat channels enabled (use dashboard for chat)[/yellow]")
    
    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] Cron: {cron_status['jobs']} scheduled jobs")
    
    console.print(f"[green]✓[/green] Heartbeat: every 30m")
    console.print(f"[green]✓[/green] Dashboard: http://{host}:{port}/")
    
    async def run():
        try:
            # Start UI server
            await ui_server.start()
            
            await cron.start()
            if agent:
                await heartbeat.start()
            
            # Start node manager if enabled
            if node_manager:
                await node_manager.start()
            
            # Start channels (this returns quickly if none enabled)
            asyncio.create_task(channels.start_all())
            
            # Start agent if available
            if agent:
                asyncio.create_task(agent.run())
            
            # Keep the server running
            console.print("\n[green]GigaBot is running. Press Ctrl+C to stop.[/green]\n")
            while True:
                await asyncio.sleep(1)
                    
        except KeyboardInterrupt:
            console.print("\nShutting down...")
        except asyncio.CancelledError:
            pass
        finally:
            if agent:
                heartbeat.stop()
            cron.stop()
            if agent:
                agent.stop()
            await channels.stop_all()
            await ui_server.stop()
            
            # Stop node manager
            if node_manager:
                await node_manager.stop()
    
    asyncio.run(run())


@app.command(name="gateway-v2")
def gateway_v2(
    host: str = typer.Option("0.0.0.0", "--host", "-H", help="Host to bind to"),
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload for development"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    force: bool = typer.Option(False, "--force", "-f", help="Start even if setup incomplete"),
):
    """Start the GigaBot gateway (FastAPI version with hot-reload support)."""
    import uvicorn
    from nanobot.config.loader import load_config
    from nanobot.server.main import create_app
    from nanobot.channels.manager import ChannelManager
    from nanobot.nodes.manager import NodeManager, set_node_manager
    
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    config = load_config()
    
    # Check setup status
    if not _check_setup_complete(config, force):
        raise typer.Exit(1)
    
    # Reload config in case setup was just run
    config = load_config()
    
    console.print(f"{__logo__} Starting GigaBot v2 gateway on {host}:{port}...")
    
    # Create channel manager
    from nanobot.bus.queue import MessageBus
    bus = MessageBus()
    channels = ChannelManager(config, bus)
    
    # Create node manager if enabled
    node_manager: NodeManager | None = None
    if config.nodes.enabled:
        storage_path = Path(config.nodes.storage_path).expanduser()
        node_manager = NodeManager(
            storage_path=storage_path,
            auth_token=config.nodes.auth_token,
            auto_approve=config.nodes.auto_approve,
            ping_interval=config.nodes.ping_interval,
        )
        set_node_manager(node_manager)
        console.print(f"[green]✓[/green] Nodes system enabled")
    
    # Create FastAPI app
    app_instance = create_app(
        config=config,
        workspace=config.workspace_path,
        channels=channels,
        node_manager=node_manager,
    )
    
    api_key = config.get_api_key()
    if api_key:
        console.print(f"[green]✓[/green] API key configured")
    else:
        console.print("[yellow]Warning: No API key configured - chat disabled[/yellow]")
        console.print("  Configure via Settings > Providers in the dashboard")
    
    if channels.enabled_channels:
        console.print(f"[green]✓[/green] Channels enabled: {', '.join(channels.enabled_channels)}")
    
    console.print(f"[green]✓[/green] Dashboard: http://{host}:{port}/")
    
    if reload:
        console.print(f"[green]✓[/green] Auto-reload enabled")
    
    console.print("\n[green]GigaBot v2 is starting. Press Ctrl+C to stop.[/green]\n")
    
    # Run with uvicorn
    uvicorn.run(
        app_instance,
        host=host,
        port=port,
        reload=reload,
        reload_dirs=["nanobot"] if reload else None,
        log_level="debug" if verbose else "info",
    )


# ============================================================================
# Agent Commands
# ============================================================================


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:default", "--session", "-s", help="Session ID"),
):
    """Interact with the agent directly."""
    from nanobot.config.loader import load_config
    from nanobot.bus.queue import MessageBus
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.agent.loop import AgentLoop
    
    config = load_config()
    
    api_key = config.get_api_key()
    api_base = config.get_api_base()
    
    if not api_key:
        console.print("[red]Error: No API key configured.[/red]")
        raise typer.Exit(1)
    
    bus = MessageBus()
    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=api_base,
        default_model=config.agents.defaults.model
    )
    
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        config=config,  # Pass config for tiered routing and swarm
        brave_api_key=config.tools.web.search.api_key or None
    )
    
    if message:
        # Single message mode
        async def run_once():
            response = await agent_loop.process_direct(message, session_id)
            console.print(f"\n{__logo__} {response}")
        
        asyncio.run(run_once())
    else:
        # Interactive mode
        console.print(f"{__logo__} Interactive mode (Ctrl+C to exit)\n")
        
        async def run_interactive():
            while True:
                try:
                    user_input = console.input("[bold blue]You:[/bold blue] ")
                    if not user_input.strip():
                        continue
                    
                    response = await agent_loop.process_direct(user_input, session_id)
                    console.print(f"\n{__logo__} {response}\n")
                except KeyboardInterrupt:
                    console.print("\nGoodbye!")
                    break
        
        asyncio.run(run_interactive())


# ============================================================================
# Channel Commands
# ============================================================================


channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")


@channels_app.command("status")
def channels_status():
    """Show channel status."""
    from nanobot.config.loader import load_config
    
    config = load_config()
    
    table = Table(title="Channel Status")
    table.add_column("Channel", style="cyan")
    table.add_column("Enabled", style="green")
    table.add_column("Bridge URL", style="yellow")
    
    wa = config.channels.whatsapp
    table.add_row(
        "WhatsApp",
        "✓" if wa.enabled else "✗",
        wa.bridge_url
    )
    
    console.print(table)


def _get_bridge_dir() -> Path:
    """Get the bridge directory, setting it up if needed."""
    import shutil
    import subprocess
    
    # User's bridge location
    user_bridge = Path.home() / ".nanobot" / "bridge"
    
    # Check if already built
    if (user_bridge / "dist" / "index.js").exists():
        return user_bridge
    
    # Check for npm
    if not shutil.which("npm"):
        console.print("[red]npm not found. Please install Node.js >= 18.[/red]")
        raise typer.Exit(1)
    
    # Find source bridge: first check package data, then source dir
    pkg_bridge = Path(__file__).parent / "bridge"  # nanobot/bridge (installed)
    src_bridge = Path(__file__).parent.parent.parent / "bridge"  # repo root/bridge (dev)
    
    source = None
    if (pkg_bridge / "package.json").exists():
        source = pkg_bridge
    elif (src_bridge / "package.json").exists():
        source = src_bridge
    
    if not source:
        console.print("[red]Bridge source not found.[/red]")
        console.print("Try reinstalling: pip install --force-reinstall nanobot")
        raise typer.Exit(1)
    
    console.print(f"{__logo__} Setting up bridge...")
    
    # Copy to user directory
    user_bridge.parent.mkdir(parents=True, exist_ok=True)
    if user_bridge.exists():
        shutil.rmtree(user_bridge)
    shutil.copytree(source, user_bridge, ignore=shutil.ignore_patterns("node_modules", "dist"))
    
    # Install and build
    try:
        console.print("  Installing dependencies...")
        subprocess.run(["npm", "install"], cwd=user_bridge, check=True, capture_output=True)
        
        console.print("  Building...")
        subprocess.run(["npm", "run", "build"], cwd=user_bridge, check=True, capture_output=True)
        
        console.print("[green]✓[/green] Bridge ready\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Build failed: {e}[/red]")
        if e.stderr:
            console.print(f"[dim]{e.stderr.decode()[:500]}[/dim]")
        raise typer.Exit(1)
    
    return user_bridge


@channels_app.command("login")
def channels_login():
    """Link device via QR code."""
    import subprocess
    
    bridge_dir = _get_bridge_dir()
    
    console.print(f"{__logo__} Starting bridge...")
    console.print("Scan the QR code to connect.\n")
    
    try:
        subprocess.run(["npm", "start"], cwd=bridge_dir, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Bridge failed: {e}[/red]")
    except FileNotFoundError:
        console.print("[red]npm not found. Please install Node.js.[/red]")


# ============================================================================
# Cron Commands
# ============================================================================

cron_app = typer.Typer(help="Manage scheduled tasks")
app.add_typer(cron_app, name="cron")


@cron_app.command("list")
def cron_list(
    all: bool = typer.Option(False, "--all", "-a", help="Include disabled jobs"),
):
    """List scheduled jobs."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    jobs = service.list_jobs(include_disabled=all)
    
    if not jobs:
        console.print("No scheduled jobs.")
        return
    
    table = Table(title="Scheduled Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Schedule")
    table.add_column("Status")
    table.add_column("Next Run")
    
    import time
    for job in jobs:
        # Format schedule
        if job.schedule.kind == "every":
            sched = f"every {(job.schedule.every_ms or 0) // 1000}s"
        elif job.schedule.kind == "cron":
            sched = job.schedule.expr or ""
        else:
            sched = "one-time"
        
        # Format next run
        next_run = ""
        if job.state.next_run_at_ms:
            next_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(job.state.next_run_at_ms / 1000))
            next_run = next_time
        
        status = "[green]enabled[/green]" if job.enabled else "[dim]disabled[/dim]"
        
        table.add_row(job.id, job.name, sched, status, next_run)
    
    console.print(table)


@cron_app.command("add")
def cron_add(
    name: str = typer.Option(..., "--name", "-n", help="Job name"),
    message: str = typer.Option(..., "--message", "-m", help="Message for agent"),
    every: int = typer.Option(None, "--every", "-e", help="Run every N seconds"),
    cron_expr: str = typer.Option(None, "--cron", "-c", help="Cron expression (e.g. '0 9 * * *')"),
    at: str = typer.Option(None, "--at", help="Run once at time (ISO format)"),
    deliver: bool = typer.Option(False, "--deliver", "-d", help="Deliver response to channel"),
    to: str = typer.Option(None, "--to", help="Recipient for delivery"),
):
    """Add a scheduled job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronSchedule
    
    # Determine schedule type
    if every:
        schedule = CronSchedule(kind="every", every_ms=every * 1000)
    elif cron_expr:
        schedule = CronSchedule(kind="cron", expr=cron_expr)
    elif at:
        import datetime
        dt = datetime.datetime.fromisoformat(at)
        schedule = CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))
    else:
        console.print("[red]Error: Must specify --every, --cron, or --at[/red]")
        raise typer.Exit(1)
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    job = service.add_job(
        name=name,
        schedule=schedule,
        message=message,
        deliver=deliver,
        to=to,
    )
    
    console.print(f"[green]✓[/green] Added job '{job.name}' ({job.id})")


@cron_app.command("remove")
def cron_remove(
    job_id: str = typer.Argument(..., help="Job ID to remove"),
):
    """Remove a scheduled job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    if service.remove_job(job_id):
        console.print(f"[green]✓[/green] Removed job {job_id}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("enable")
def cron_enable(
    job_id: str = typer.Argument(..., help="Job ID"),
    disable: bool = typer.Option(False, "--disable", help="Disable instead of enable"),
):
    """Enable or disable a job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    job = service.enable_job(job_id, enabled=not disable)
    if job:
        status = "disabled" if disable else "enabled"
        console.print(f"[green]✓[/green] Job '{job.name}' {status}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("run")
def cron_run(
    job_id: str = typer.Argument(..., help="Job ID to run"),
    force: bool = typer.Option(False, "--force", "-f", help="Run even if disabled"),
):
    """Manually run a job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    async def run():
        return await service.run_job(job_id, force=force)
    
    if asyncio.run(run()):
        console.print(f"[green]✓[/green] Job executed")
    else:
        console.print(f"[red]Failed to run job {job_id}[/red]")


# ============================================================================
# Security Commands
# ============================================================================

security_app = typer.Typer(help="Security management commands")
app.add_typer(security_app, name="security")


@security_app.command("audit")
def security_audit(
    deep: bool = typer.Option(False, "--deep", "-d", help="Run deep checks (includes network probes)"),
    fix: bool = typer.Option(False, "--fix", "-f", help="Auto-fix issues where possible"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Run security audit on configuration."""
    from nanobot.config.loader import get_config_path
    from nanobot.utils.helpers import get_workspace_path
    from nanobot.security.audit import run_audit, AuditSeverity
    
    config_path = get_config_path()
    workspace = get_workspace_path()
    
    results, summary, fixes = run_audit(config_path, workspace, deep=deep, auto_fix=fix)
    
    if json_output:
        import json
        output = {
            "results": [
                {
                    "check": r.check_name,
                    "passed": r.passed,
                    "severity": r.severity.value,
                    "message": r.message,
                    "details": r.details,
                    "fix_suggestion": r.fix_suggestion,
                }
                for r in results
            ],
            "summary": summary,
            "fixes_applied": fixes,
        }
        console.print(json.dumps(output, indent=2))
        return
    
    console.print(f"\n{__logo__} GigaBot Security Audit\n")
    
    # Display results
    severity_styles = {
        AuditSeverity.CRITICAL: "[bold red]CRITICAL[/bold red]",
        AuditSeverity.ERROR: "[red]ERROR[/red]",
        AuditSeverity.WARNING: "[yellow]WARNING[/yellow]",
        AuditSeverity.INFO: "[dim]INFO[/dim]",
    }
    
    for result in results:
        status = "[green]✓[/green]" if result.passed else "[red]✗[/red]"
        severity = severity_styles.get(result.severity, result.severity.value)
        console.print(f"  {status} {result.check_name}: {result.message}")
        if not result.passed and result.fix_suggestion:
            console.print(f"      [dim]Fix: {result.fix_suggestion}[/dim]")
    
    # Summary
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Score: {summary['score']}%")
    console.print(f"  Passed: {summary['passed']}/{summary['total_checks']}")
    if summary['critical'] > 0:
        console.print(f"  [bold red]Critical issues: {summary['critical']}[/bold red]")
    if summary['errors'] > 0:
        console.print(f"  [red]Errors: {summary['errors']}[/red]")
    if summary['warnings'] > 0:
        console.print(f"  [yellow]Warnings: {summary['warnings']}[/yellow]")
    
    # Fixes applied
    if fixes:
        console.print(f"\n[green]Fixes applied:[/green]")
        for fix_msg in fixes:
            console.print(f"  ✓ {fix_msg}")


@security_app.command("generate-token")
def security_generate_token(
    length: int = typer.Option(32, "--length", "-l", help="Token length"),
    save: bool = typer.Option(False, "--save", "-s", help="Save to config"),
):
    """Generate a secure authentication token."""
    from nanobot.security.auth import generate_token
    from nanobot.config.loader import load_config, save_config
    
    token = generate_token(length)
    
    if save:
        config = load_config()
        config.security.auth.mode = "token"
        config.security.auth.token = token
        save_config(config)
        console.print(f"[green]✓[/green] Token saved to config")
        console.print(f"[dim]Token: {token[:8]}...{token[-4:]}[/dim]")
    else:
        console.print(f"Token: {token}")
        console.print(f"\n[dim]Use --save to save to config automatically[/dim]")


@security_app.command("hash-password")
def security_hash_password(
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True, help="Password to hash"),
    save: bool = typer.Option(False, "--save", "-s", help="Save hash to config"),
):
    """Hash a password for authentication."""
    from nanobot.security.auth import hash_password
    from nanobot.config.loader import load_config, save_config
    
    password_hash = hash_password(password)
    
    if save:
        config = load_config()
        config.security.auth.mode = "password"
        config.security.auth.password_hash = password_hash
        save_config(config)
        console.print(f"[green]✓[/green] Password hash saved to config")
    else:
        console.print(f"Hash: {password_hash}")
        console.print(f"\n[dim]Use --save to save to config automatically[/dim]")


@security_app.command("status")
def security_status():
    """Show security configuration status."""
    from nanobot.config.loader import load_config
    
    config = load_config()
    sec = config.security
    
    console.print(f"\n{__logo__} GigaBot Security Status\n")
    
    # Authentication
    auth_mode = sec.auth.mode
    auth_status = "[green]✓[/green]" if auth_mode != "none" else "[yellow]⚠[/yellow]"
    console.print(f"[bold]Authentication:[/bold]")
    console.print(f"  {auth_status} Mode: {auth_mode}")
    if auth_mode == "token":
        has_token = bool(sec.auth.token)
        console.print(f"  {'[green]✓[/green]' if has_token else '[red]✗[/red]'} Token configured: {has_token}")
    
    # Tool Policy
    console.print(f"\n[bold]Tool Policy:[/bold]")
    console.print(f"  Allow: {', '.join(sec.tool_policy.allow)}")
    if sec.tool_policy.deny:
        console.print(f"  Deny: {', '.join(sec.tool_policy.deny)}")
    if sec.tool_policy.require_approval:
        console.print(f"  Require approval: {', '.join(sec.tool_policy.require_approval)}")
    
    # Sandbox
    console.print(f"\n[bold]Sandbox:[/bold]")
    sandbox_status = "[green]✓[/green]" if sec.sandbox.mode != "off" else "[dim]off[/dim]"
    console.print(f"  {sandbox_status} Mode: {sec.sandbox.mode}")
    console.print(f"  Workspace access: {sec.sandbox.workspace_access}")
    
    # Encryption
    console.print(f"\n[bold]Encryption:[/bold]")
    console.print(f"  Config: {'[green]✓[/green]' if sec.encryption.encrypt_config else '[dim]off[/dim]'}")
    console.print(f"  Memory: {'[green]✓[/green]' if sec.encryption.encrypt_memory else '[dim]off[/dim]'}")
    console.print(f"  Sessions: {'[green]✓[/green]' if sec.encryption.encrypt_sessions else '[dim]off[/dim]'}")


# ============================================================================
# Status Commands
# ============================================================================


@app.command()
def status():
    """Show GigaBot status."""
    from nanobot.config.loader import load_config, get_config_path
    from nanobot.utils.helpers import get_workspace_path
    
    config_path = get_config_path()
    workspace = get_workspace_path()
    
    console.print(f"{__logo__} GigaBot Status\n")
    
    console.print(f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}")
    
    if config_path.exists():
        config = load_config()
        console.print(f"Model: {config.agents.defaults.model}")
        
        # Check API keys
        has_openrouter = bool(config.providers.openrouter.api_key)
        has_anthropic = bool(config.providers.anthropic.api_key)
        has_openai = bool(config.providers.openai.api_key)
        has_moonshot = bool(config.providers.moonshot.api_key)
        has_deepseek = bool(config.providers.deepseek.api_key)
        has_vllm = bool(config.providers.vllm.api_base)
        
        console.print(f"\n[bold]Providers:[/bold]")
        console.print(f"  OpenRouter: {'[green]✓[/green]' if has_openrouter else '[dim]not set[/dim]'}")
        console.print(f"  Anthropic: {'[green]✓[/green]' if has_anthropic else '[dim]not set[/dim]'}")
        console.print(f"  OpenAI: {'[green]✓[/green]' if has_openai else '[dim]not set[/dim]'}")
        console.print(f"  Moonshot: {'[green]✓[/green]' if has_moonshot else '[dim]not set[/dim]'}")
        console.print(f"  DeepSeek: {'[green]✓[/green]' if has_deepseek else '[dim]not set[/dim]'}")
        vllm_status = f"[green]✓ {config.providers.vllm.api_base}[/green]" if has_vllm else "[dim]not set[/dim]"
        console.print(f"  vLLM/Local: {vllm_status}")
        
        # Tiered routing status
        if config.agents.tiered_routing.enabled:
            console.print(f"\n[bold]Tiered Routing:[/bold] [green]enabled[/green]")
            console.print(f"  Fallback tier: {config.agents.tiered_routing.fallback_tier}")
        
        # Security status
        console.print(f"\n[bold]Security:[/bold]")
        auth_mode = config.security.auth.mode
        console.print(f"  Auth: {auth_mode} {'[green]✓[/green]' if auth_mode != 'none' else '[yellow]⚠[/yellow]'}")
        console.print(f"  Sandbox: {config.security.sandbox.mode}")


# ============================================================================
# Approval Commands
# ============================================================================

approvals_app = typer.Typer(help="Manage pending approvals")
app.add_typer(approvals_app, name="approvals")


@approvals_app.command("list")
def approvals_list():
    """List pending approvals."""
    from nanobot.security.approval import get_approval_manager
    
    manager = get_approval_manager()
    pending = manager.get_pending()
    
    if not pending:
        console.print("[dim]No pending approvals[/dim]")
        return
    
    table = Table(title="Pending Approvals")
    table.add_column("ID", style="cyan")
    table.add_column("Tool", style="green")
    table.add_column("Command", style="yellow", max_width=50)
    table.add_column("Requester", style="blue")
    table.add_column("Expires", style="red")
    
    import time
    for approval in pending:
        command = str(approval.arguments.get("command", ""))[:50]
        expires_in = int(approval.expires_at - time.time())
        expires_str = f"{expires_in}s" if expires_in > 0 else "expired"
        
        table.add_row(
            approval.id,
            approval.tool_name,
            command,
            approval.requester,
            expires_str,
        )
    
    console.print(table)


@approvals_app.command("approve")
def approvals_approve(
    approval_id: str = typer.Argument(help="ID of the approval"),
    reason: str = typer.Option("", help="Reason for approval"),
):
    """Approve a pending request."""
    from nanobot.security.approval import get_approval_manager
    
    async def _approve():
        manager = get_approval_manager()
        success = await manager.approve(approval_id, "cli", reason)
        return success
    
    success = asyncio.run(_approve())
    
    if success:
        console.print(f"[green]✓[/green] Approved: {approval_id}")
    else:
        console.print(f"[red]✗[/red] Failed to approve: {approval_id}")


@approvals_app.command("deny")
def approvals_deny(
    approval_id: str = typer.Argument(help="ID of the approval"),
    reason: str = typer.Option("Denied by user", help="Reason for denial"),
):
    """Deny a pending request."""
    from nanobot.security.approval import get_approval_manager
    
    async def _deny():
        manager = get_approval_manager()
        success = await manager.deny(approval_id, "cli", reason)
        return success
    
    success = asyncio.run(_deny())
    
    if success:
        console.print(f"[green]✓[/green] Denied: {approval_id}")
    else:
        console.print(f"[red]✗[/red] Failed to deny: {approval_id}")


@approvals_app.command("show")
def approvals_show(
    approval_id: str = typer.Argument(help="ID of the approval"),
):
    """Show details of an approval."""
    from nanobot.security.approval import get_approval_manager
    import time
    
    manager = get_approval_manager()
    approval = manager.get_approval(approval_id)
    
    if not approval:
        console.print(f"[red]Approval not found: {approval_id}[/red]")
        return
    
    console.print(f"\n[bold]Approval: {approval.id}[/bold]")
    console.print(f"  Status: {approval.status.value}")
    console.print(f"  Tool: {approval.tool_name}")
    console.print(f"  Requester: {approval.requester}")
    console.print(f"  Reason: {approval.reason}")
    console.print(f"\n[bold]Arguments:[/bold]")
    for key, value in approval.arguments.items():
        console.print(f"  {key}: {value}")
    
    if approval.decided_by:
        console.print(f"\n[bold]Decision:[/bold]")
        console.print(f"  By: {approval.decided_by}")
        console.print(f"  Reason: {approval.decision_reason}")


# ============================================================================
# Swarm Commands
# ============================================================================

swarm_app = typer.Typer(help="Multi-agent swarm execution")
app.add_typer(swarm_app, name="swarm")


@swarm_app.command("run")
def swarm_run(
    objective: str = typer.Argument(..., help="The objective to accomplish"),
    pattern: str = typer.Option("research", "--pattern", "-p", 
                                help="Swarm pattern: research, code, review, brainstorm"),
    workers: int = typer.Option(5, "--workers", "-w", help="Maximum number of workers"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Execute a multi-agent swarm task."""
    from nanobot.config.loader import load_config
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.swarm.orchestrator import SwarmOrchestrator, SwarmConfig
    
    config = load_config()
    
    api_key = config.get_api_key()
    api_base = config.get_api_base()
    
    if not api_key:
        console.print("[red]Error: No API key configured.[/red]")
        raise typer.Exit(1)
    
    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=api_base,
        default_model=config.agents.defaults.model
    )
    
    swarm_config = SwarmConfig(
        enabled=True,
        max_workers=workers,
        worker_model=config.agents.swarm.worker_model,
        orchestrator_model=config.agents.swarm.orchestrator_model,
    )
    
    orchestrator = SwarmOrchestrator(
        config=swarm_config,
        provider=provider,
        workspace=config.workspace_path,
    )
    
    console.print(f"{__logo__} Executing swarm with pattern: [cyan]{pattern}[/cyan]")
    console.print(f"  Objective: {objective[:80]}{'...' if len(objective) > 80 else ''}")
    console.print(f"  Workers: {workers}")
    console.print("")
    
    async def run_swarm():
        return await orchestrator.execute(
            objective=objective,
            pattern=pattern,
        )
    
    result = asyncio.run(run_swarm())
    
    console.print("\n[bold]Result:[/bold]")
    console.print(result)


@swarm_app.command("patterns")
def swarm_patterns():
    """List available swarm patterns with descriptions."""
    from nanobot.swarm.patterns import PATTERNS
    
    console.print(f"\n{__logo__} [bold]Available Swarm Patterns[/bold]\n")
    
    for name, pattern in PATTERNS.items():
        console.print(f"[cyan]{name}[/cyan]")
        console.print(f"  {pattern.description}")
        
        # Show task flow
        tasks = pattern.generate_tasks("example", "")
        if tasks:
            console.print("  [dim]Flow:[/dim]", end="")
            task_names = [t.id for t in tasks]
            console.print(f" [dim]{' → '.join(task_names)}[/dim]")
        console.print("")


@swarm_app.command("test")
def swarm_test(
    message: str = typer.Argument(..., help="Message to test swarm trigger"),
):
    """Test if a message would trigger swarm execution."""
    from nanobot.routing.classifier import TaskClassifier
    from nanobot.agent.swarm_trigger import should_use_swarm, get_complexity_score, auto_select_pattern
    from nanobot.config.loader import load_config
    
    config = load_config()
    
    # Classify the message
    classifier = TaskClassifier()
    classification = classifier.classify(message)
    
    # Get complexity analysis
    score, factors = get_complexity_score(message, classification)
    
    # Check if swarm would trigger
    would_swarm, pattern = should_use_swarm(message, classification, config.agents.swarm)
    
    console.print(f"\n{__logo__} [bold]Swarm Trigger Analysis[/bold]\n")
    console.print(f"Message: {message[:100]}{'...' if len(message) > 100 else ''}")
    console.print(f"\n[bold]Classification:[/bold]")
    console.print(f"  Task Type: {classification.task_type.value}")
    console.print(f"  Tier: {classification.tier}")
    console.print(f"  Confidence: {classification.confidence:.0%}")
    
    console.print(f"\n[bold]Complexity Score:[/bold] {score}")
    if factors:
        for factor in factors:
            console.print(f"  + {factor}")
    
    threshold = getattr(config.agents.swarm, 'complexity_threshold', 3)
    console.print(f"\n[bold]Threshold:[/bold] {threshold}")
    
    if would_swarm:
        console.print(f"\n[green]✓ Would trigger swarm[/green]")
        console.print(f"  Pattern: {pattern}")
    else:
        console.print(f"\n[yellow]✗ Would NOT trigger swarm[/yellow]")
        console.print(f"  (Score {score} < threshold {threshold})")


# ============================================================================
# Routing Commands
# ============================================================================

routing_app = typer.Typer(help="Tiered model routing")
app.add_typer(routing_app, name="routing")


@routing_app.command("status")
def routing_status():
    """Show routing configuration and tier status."""
    from nanobot.config.loader import load_config
    
    config = load_config()
    routing = config.agents.tiered_routing
    
    console.print(f"\n{__logo__} [bold]Tiered Routing Status[/bold]\n")
    
    status = "[green]enabled[/green]" if routing.enabled else "[dim]disabled[/dim]"
    console.print(f"Status: {status}")
    console.print(f"Fallback Tier: {routing.fallback_tier}")
    
    if routing.classifier_model:
        console.print(f"Classifier Model: {routing.classifier_model}")
    
    console.print("\n[bold]Tiers:[/bold]")
    for tier_name, tier_config in routing.tiers.items():
        console.print(f"\n  [cyan]{tier_name}[/cyan]")
        console.print(f"    Models: {', '.join(tier_config.models)}")
        console.print(f"    Triggers: {', '.join(tier_config.triggers)}")


@routing_app.command("test")
def routing_test(
    message: str = typer.Argument(..., help="Message to test routing"),
):
    """Test which tier/model would be selected for a message."""
    from nanobot.routing.classifier import TaskClassifier, classify_by_keywords, classify_by_heuristics
    from nanobot.routing.router import create_default_router
    from nanobot.config.loader import load_config
    
    config = load_config()
    
    # Create classifier and router
    classifier = TaskClassifier()
    classification = classifier.classify(message)
    
    # Use config router if enabled, otherwise default
    if config.agents.tiered_routing.enabled:
        from nanobot.routing.router import create_router_from_config
        router = create_router_from_config(config)
    else:
        router = create_default_router()
    
    decision = router.route(message)
    
    console.print(f"\n{__logo__} [bold]Routing Analysis[/bold]\n")
    console.print(f"Message: {message[:100]}{'...' if len(message) > 100 else ''}")
    
    console.print(f"\n[bold]Classification:[/bold]")
    console.print(f"  Task Type: {decision.classification.task_type.value}")
    console.print(f"  Confidence: {decision.classification.confidence:.0%}")
    console.print(f"  Keywords: {', '.join(decision.classification.keywords_matched[:3]) if decision.classification.keywords_matched else 'none'}")
    console.print(f"  Reasoning: {decision.classification.reasoning}")
    
    console.print(f"\n[bold]Routing Decision:[/bold]")
    console.print(f"  Tier: [cyan]{decision.tier}[/cyan]")
    console.print(f"  Model: [green]{decision.model}[/green]")
    
    if decision.fallback_used:
        console.print(f"  [yellow]Fallback: {decision.fallback_reason}[/yellow]")


# ============================================================================
# Team Commands (Persona-Based Hierarchy)
# ============================================================================

team_app = typer.Typer(help="Agent team management (persona-based hierarchy)")
app.add_typer(team_app, name="team")


@team_app.command("status")
def team_status():
    """Show team composition and status."""
    from nanobot.config.loader import load_config
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.swarm.team import AgentTeam
    
    config = load_config()
    
    console.print(f"\n{__logo__} [bold]Agent Team Status[/bold]\n")
    
    team_config = config.agents.team
    status = "[green]enabled[/green]" if team_config.enabled else "[dim]disabled[/dim]"
    console.print(f"Team Status: {status}")
    console.print(f"QA Gate: {'enabled' if team_config.qa_gate_enabled else 'disabled'}")
    console.print(f"Audit Gate: {'enabled' if team_config.audit_gate_enabled else 'disabled'}")
    console.print(f"Audit Threshold: {team_config.audit_threshold}")
    
    console.print("\n[bold]Team Roles:[/bold]")
    for role_id, role_config in team_config.roles.items():
        status_icon = "[green]●[/green]" if role_config.enabled else "[dim]○[/dim]"
        model = role_config.model or "(default)"
        console.print(f"  {status_icon} [cyan]{role_id}[/cyan]: {model}")


@team_app.command("roles")
def team_roles():
    """List all available roles with details."""
    from nanobot.swarm.roles import DEFAULT_ROLES, get_hierarchy
    
    console.print(f"\n{__logo__} [bold]Available Team Roles[/bold]\n")
    
    hierarchy = get_hierarchy()
    
    for role_id, role in DEFAULT_ROLES.items():
        console.print(f"[cyan]{role.title}[/cyan] ({role_id})")
        console.print(f"  Model: {role.model}")
        console.print(f"  Authority: {'★' * role.authority_level}{'☆' * (5 - role.authority_level)}")
        if role.reports_to:
            console.print(f"  Reports to: {role.reports_to}")
        console.print(f"  Capabilities:")
        for cap in role.capabilities[:3]:
            console.print(f"    - {cap}")
        
        # Show direct reports
        if role_id in hierarchy:
            console.print(f"  Direct reports: {', '.join(hierarchy[role_id])}")
        console.print("")


@team_app.command("assign")
def team_assign(
    task: str = typer.Argument(..., help="Task to assign"),
):
    """Test which role would be assigned a task."""
    from nanobot.config.loader import load_config
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.swarm.team import AgentTeam
    
    config = load_config()
    
    api_key = config.get_api_key()
    api_base = config.get_api_base()
    
    if not api_key:
        console.print("[red]Error: No API key configured.[/red]")
        raise typer.Exit(1)
    
    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=api_base,
        default_model=config.agents.defaults.model
    )
    
    team = AgentTeam(
        provider=provider,
        workspace=config.workspace_path,
        config=config.agents.team,
    )
    
    async def run_assign():
        return await team.assign_task(task)
    
    assignment = asyncio.run(run_assign())
    
    console.print(f"\n{__logo__} [bold]Task Assignment[/bold]\n")
    console.print(f"Task: {task[:80]}{'...' if len(task) > 80 else ''}")
    console.print(f"\n[bold]Assignment:[/bold]")
    console.print(f"  Role: [cyan]{assignment.role_id}[/cyan]")
    console.print(f"  Reason: {assignment.reason}")


@team_app.command("deliberate")
def team_deliberate(
    question: str = typer.Argument(..., help="Question to deliberate on"),
    context: str = typer.Option("", "--context", "-c", help="Additional context"),
):
    """Run a team deliberation session."""
    from nanobot.config.loader import load_config
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.swarm.orchestrator import TeamOrchestrator
    
    config = load_config()
    
    api_key = config.get_api_key()
    api_base = config.get_api_base()
    
    if not api_key:
        console.print("[red]Error: No API key configured.[/red]")
        raise typer.Exit(1)
    
    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=api_base,
        default_model=config.agents.defaults.model
    )
    
    orchestrator = TeamOrchestrator(
        provider=provider,
        workspace=config.workspace_path,
        config=config.agents.team,
    )
    
    console.print(f"\n{__logo__} Consulting team on: [cyan]{question[:60]}...[/cyan]\n")
    
    async def run_deliberate():
        return await orchestrator.execute(question, mode="deliberate", context=context)
    
    result = asyncio.run(run_deliberate())
    console.print(result)


# ============================================================================
# Reach and Done Commands (Team Interaction Modes)
# ============================================================================

@app.command("reach")
def reach_goal(
    goal: str = typer.Argument(..., help="Goal to discuss with the team"),
    context: str = typer.Option("", "--context", "-c", help="Additional context"),
):
    """
    Discuss a goal with the team (deliberation mode).
    
    The team will provide opinions and present options for your consideration.
    Use this for strategic decisions where you want input before proceeding.
    """
    from nanobot.config.loader import load_config
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.swarm.orchestrator import TeamOrchestrator
    
    config = load_config()
    
    if not config.agents.team.enabled:
        console.print("[yellow]Warning: Team not enabled in config. Enabling temporarily.[/yellow]")
    
    api_key = config.get_api_key()
    api_base = config.get_api_base()
    
    if not api_key:
        console.print("[red]Error: No API key configured.[/red]")
        raise typer.Exit(1)
    
    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=api_base,
        default_model=config.agents.defaults.model
    )
    
    orchestrator = TeamOrchestrator(
        provider=provider,
        workspace=config.workspace_path,
        config=config.agents.team,
    )
    
    console.print(f"\n{__logo__} [bold]Reaching Goal[/bold]\n")
    console.print(f"Goal: {goal}")
    console.print("\nConsulting team members...\n")
    
    async def run_reach():
        return await orchestrator.execute(goal, mode="deliberate", context=context)
    
    result = asyncio.run(run_reach())
    console.print(result)


@app.command("done")
def get_done(
    task: str = typer.Argument(..., help="Task to complete"),
    context: str = typer.Option("", "--context", "-c", help="Additional context"),
    pattern: str = typer.Option(None, "--pattern", "-p", help="Workflow pattern to use"),
):
    """
    Delegate a task to the team (execution mode).
    
    The team will assign, execute, and review the task automatically.
    Use this when you want something completed without detailed planning.
    """
    from nanobot.config.loader import load_config
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.swarm.orchestrator import TeamOrchestrator
    
    config = load_config()
    
    if not config.agents.team.enabled:
        console.print("[yellow]Warning: Team not enabled in config. Enabling temporarily.[/yellow]")
    
    api_key = config.get_api_key()
    api_base = config.get_api_base()
    
    if not api_key:
        console.print("[red]Error: No API key configured.[/red]")
        raise typer.Exit(1)
    
    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=api_base,
        default_model=config.agents.defaults.model
    )
    
    orchestrator = TeamOrchestrator(
        provider=provider,
        workspace=config.workspace_path,
        config=config.agents.team,
    )
    
    console.print(f"\n{__logo__} [bold]Getting It Done[/bold]\n")
    console.print(f"Task: {task}")
    console.print("\nAssigning to team...\n")
    
    async def run_done():
        return await orchestrator.execute(task, mode="execute", context=context, pattern=pattern)
    
    result = asyncio.run(run_done())
    console.print(result)


# ============================================================================
# Profile Commands (Model Profiler / HR Interview System)
# ============================================================================

profile_app = typer.Typer(help="Model profiler - HR-style model interviews")
app.add_typer(profile_app, name="profile")


@profile_app.command("interview")
def profile_interview(
    model: str = typer.Argument(..., help="Model to interview (e.g., anthropic/claude-sonnet-4-5)"),
    quick: bool = typer.Option(False, "--quick", "-q", help="Quick assessment (subset of tests)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
):
    """Interview a model to create a capability profile."""
    from nanobot.config.loader import load_config
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.profiler.interviewer import ModelInterviewer
    from nanobot.profiler.registry import ModelRegistry
    
    config = load_config()
    
    api_key = config.get_api_key()
    api_base = config.get_api_base()
    
    if not api_key:
        console.print("[red]Error: No API key configured.[/red]")
        raise typer.Exit(1)
    
    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=api_base,
        default_model=config.agents.defaults.model
    )
    
    interviewer_model = config.agents.profiler.interviewer_model
    storage_path = Path(config.agents.profiler.storage_path).expanduser()
    
    interviewer = ModelInterviewer(
        provider=provider,
        interviewer_model=interviewer_model,
        workspace=config.workspace_path,
    )
    
    registry = ModelRegistry(storage_path=storage_path)
    
    console.print(f"\n{__logo__} [bold]Model Profiler - Interview Session[/bold]")
    console.print(f"  Candidate: [cyan]{model}[/cyan]")
    console.print(f"  Interviewer: {interviewer_model}")
    console.print("")
    
    def progress_callback(current: int, total: int, test_name: str):
        if verbose:
            console.print(f"  [{current}/{total}] {test_name}...")
    
    async def run_interview():
        if quick:
            return await interviewer.quick_assessment(model, progress_callback)
        return await interviewer.interview(model, progress_callback=progress_callback)
    
    console.print("Running tests...\n")
    profile = asyncio.run(run_interview())
    
    # Save profile
    registry.save_profile(profile)
    
    # Display results
    console.print(profile.format_summary())
    console.print(f"\n[green]✓[/green] Profile saved to {storage_path / 'models.json'}")


@profile_app.command("assess")
def profile_assess(
    model: str = typer.Argument(..., help="Model to assess"),
):
    """Quick assessment of a model (subset of critical tests)."""
    # Delegate to interview with --quick flag
    profile_interview(model=model, quick=True, verbose=False)


@profile_app.command("show")
def profile_show(
    model: str = typer.Argument(..., help="Model ID to show"),
):
    """Show a model's capability profile."""
    from nanobot.config.loader import load_config
    from nanobot.profiler.registry import ModelRegistry
    
    config = load_config()
    storage_path = Path(config.agents.profiler.storage_path).expanduser()
    registry = ModelRegistry(storage_path=storage_path)
    
    profile = registry.get_profile(model)
    
    if not profile:
        console.print(f"[red]No profile found for: {model}[/red]")
        console.print(f"\nRun: gigabot profile interview {model}")
        raise typer.Exit(1)
    
    console.print(f"\n{__logo__} {profile.format_summary()}")
    
    # Show guardrail recommendations
    console.print("\n[bold]Guardrail Recommendations:[/bold]")
    g = profile.guardrails
    console.print(f"  Needs structured output: {'Yes' if g.needs_structured_output else 'No'}")
    console.print(f"  Needs explicit format: {'Yes' if g.needs_explicit_format else 'No'}")
    console.print(f"  Needs tool examples: {'Yes' if g.needs_tool_examples else 'No'}")
    console.print(f"  Needs step-by-step: {'Yes' if g.needs_step_by_step else 'No'}")
    console.print(f"  Avoid parallel tools: {'Yes' if g.avoid_parallel_tools else 'No'}")
    console.print(f"  Max reliable context: {g.max_reliable_context:,} tokens")
    console.print(f"  Recommended temperature: {g.recommended_temperature}")
    console.print(f"  Tool retry limit: {g.tool_call_retry_limit}")


@profile_app.command("list")
def profile_list():
    """List all profiled models."""
    from nanobot.config.loader import load_config
    from nanobot.profiler.registry import ModelRegistry
    
    config = load_config()
    storage_path = Path(config.agents.profiler.storage_path).expanduser()
    registry = ModelRegistry(storage_path=storage_path)
    
    profiles = registry.get_all_profiles()
    
    if not profiles:
        console.print("[dim]No profiled models yet.[/dim]")
        console.print("\nRun: gigabot profile interview <model-id>")
        return
    
    console.print(f"\n{__logo__} [bold]Profiled Models[/bold]\n")
    
    table = Table()
    table.add_column("Model", style="cyan")
    table.add_column("Overall", style="green")
    table.add_column("Tool", style="yellow")
    table.add_column("Code", style="blue")
    table.add_column("Reasoning", style="magenta")
    table.add_column("Interviewed", style="dim")
    
    for model_id, profile in profiles.items():
        caps = profile.capabilities
        table.add_row(
            model_id,
            f"{profile.get_overall_score():.2f}",
            f"{caps.tool_calling_accuracy:.2f}",
            f"{caps.code_generation:.2f}",
            f"{caps.reasoning_depth:.2f}",
            profile.interviewed_at.strftime("%Y-%m-%d"),
        )
    
    console.print(table)


@profile_app.command("recommend")
def profile_recommend(
    role: str = typer.Option(None, "--role", "-r", help="Role to get recommendations for"),
    task: str = typer.Option(None, "--task", "-t", help="Task type to get recommendations for"),
    top: int = typer.Option(5, "--top", "-n", help="Number of recommendations"),
):
    """Get model recommendations for a role or task."""
    from nanobot.config.loader import load_config
    from nanobot.profiler.registry import ModelRegistry
    
    config = load_config()
    storage_path = Path(config.agents.profiler.storage_path).expanduser()
    registry = ModelRegistry(storage_path=storage_path)
    
    if not role and not task:
        console.print("[red]Error: Specify --role or --task[/red]")
        raise typer.Exit(1)
    
    console.print(f"\n{__logo__} [bold]Model Recommendations[/bold]\n")
    
    if role:
        console.print(f"For role: [cyan]{role}[/cyan]\n")
        recommendations = registry.get_role_recommendations(role, top_n=top)
        
        if not recommendations:
            console.print("[dim]No profiled models available.[/dim]")
            return
        
        table = Table()
        table.add_column("Model", style="cyan")
        table.add_column("Suitability", style="green")
        table.add_column("Reasoning")
        
        for model_id, score, reasoning in recommendations:
            indicator = "✓" if score >= 0.7 else "~" if score >= 0.5 else "✗"
            table.add_row(
                model_id,
                f"{indicator} {score:.2f}",
                reasoning[:50] + "..." if len(reasoning) > 50 else reasoning,
            )
        
        console.print(table)
    
    if task:
        console.print(f"For task type: [cyan]{task}[/cyan]\n")
        
        best = registry.get_best_model_for_task(task)
        if best:
            console.print(f"[green]Recommended:[/green] {best}")
        else:
            console.print("[dim]No suitable model found for this task type.[/dim]")


@profile_app.command("compare")
def profile_compare(
    models: list[str] = typer.Argument(..., help="Models to compare (space-separated)"),
):
    """Compare multiple models side by side."""
    from nanobot.config.loader import load_config
    from nanobot.profiler.registry import ModelRegistry
    
    config = load_config()
    storage_path = Path(config.agents.profiler.storage_path).expanduser()
    registry = ModelRegistry(storage_path=storage_path)
    
    # Check all models have profiles
    missing = [m for m in models if not registry.get_profile(m)]
    if missing:
        console.print(f"[red]Missing profiles for: {', '.join(missing)}[/red]")
        console.print("\nRun 'gigabot profile interview <model>' first.")
        raise typer.Exit(1)
    
    console.print(f"\n{__logo__} [bold]Model Comparison[/bold]\n")
    comparison = registry.format_comparison(models)
    console.print(comparison)


@profile_app.command("refresh")
def profile_refresh(
    max_age: int = typer.Option(30, "--max-age", help="Max profile age in days"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Just show what would be refreshed"),
):
    """Re-interview stale profiles."""
    from nanobot.config.loader import load_config
    from nanobot.profiler.registry import ModelRegistry
    
    config = load_config()
    storage_path = Path(config.agents.profiler.storage_path).expanduser()
    registry = ModelRegistry(storage_path=storage_path)
    
    stale = registry.get_stale_profiles(max_age_days=max_age)
    
    if not stale:
        console.print("[green]All profiles are up to date.[/green]")
        return
    
    console.print(f"\n{__logo__} [bold]Stale Profiles (>{max_age} days)[/bold]\n")
    
    for model_id in stale:
        profile = registry.get_profile(model_id)
        age = (profile.interviewed_at.now() - profile.interviewed_at).days if profile else 0
        console.print(f"  [cyan]{model_id}[/cyan] ({age} days old)")
    
    if dry_run:
        console.print(f"\n[dim]Run without --dry-run to re-interview these models.[/dim]")
        return
    
    # Re-interview each
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.profiler.interviewer import ModelInterviewer
    
    api_key = config.get_api_key()
    api_base = config.get_api_base()
    
    if not api_key:
        console.print("[red]Error: No API key configured.[/red]")
        raise typer.Exit(1)
    
    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=api_base,
        default_model=config.agents.defaults.model
    )
    
    interviewer = ModelInterviewer(
        provider=provider,
        interviewer_model=config.agents.profiler.interviewer_model,
        workspace=config.workspace_path,
    )
    
    async def refresh_all():
        for model_id in stale:
            console.print(f"\n  Re-interviewing {model_id}...")
            try:
                profile = await interviewer.quick_assessment(model_id)
                registry.save_profile(profile)
                console.print(f"    [green]✓[/green] Updated (score: {profile.get_overall_score():.2f})")
            except Exception as e:
                console.print(f"    [red]✗[/red] Failed: {e}")
    
    asyncio.run(refresh_all())
    console.print("\n[green]Refresh complete.[/green]")


# ============================================================================
# Daemon Commands
# ============================================================================

daemon_app = typer.Typer(help="Manage GigaBot as a system service")
app.add_typer(daemon_app, name="daemon")


@daemon_app.command("install")
def daemon_install(
    start_on_boot: bool = typer.Option(True, help="Start on system boot"),
):
    """Install GigaBot as a system service."""
    from nanobot.daemon import get_daemon_manager, DaemonConfig
    
    config = DaemonConfig(start_on_boot=start_on_boot)
    manager = get_daemon_manager()
    manager.config = config
    
    if manager.install():
        console.print("[green]✓[/green] Service installed successfully")
        console.print(f"  Platform: {manager.platform}")
        if start_on_boot:
            console.print("  Will start on boot")
        console.print("\nStart with: gigabot daemon start")
    else:
        console.print("[red]✗[/red] Failed to install service")
        console.print("  You may need administrator/sudo privileges")


@daemon_app.command("uninstall")
def daemon_uninstall():
    """Uninstall the system service."""
    from nanobot.daemon import get_daemon_manager
    
    manager = get_daemon_manager()
    
    if manager.uninstall():
        console.print("[green]✓[/green] Service uninstalled")
    else:
        console.print("[red]✗[/red] Failed to uninstall service")


@daemon_app.command("status")
def daemon_status():
    """Check service status."""
    from nanobot.daemon import get_daemon_manager
    
    manager = get_daemon_manager()
    status = manager.status()
    info = manager.get_info()
    
    console.print(f"\n[bold]GigaBot Service Status[/bold]")
    console.print(f"  Platform: {info['platform']}")
    console.print(f"  Service name: {info['service_name']}")
    
    status_color = {
        "running": "green",
        "stopped": "yellow",
        "not_installed": "dim",
        "failed": "red",
    }.get(status.value, "white")
    
    console.print(f"  Status: [{status_color}]{status.value}[/{status_color}]")


@daemon_app.command("start")
def daemon_start():
    """Start the service."""
    from nanobot.daemon import get_daemon_manager
    
    manager = get_daemon_manager()
    
    if manager.start():
        console.print("[green]✓[/green] Service started")
    else:
        console.print("[red]✗[/red] Failed to start service")


@daemon_app.command("stop")
def daemon_stop():
    """Stop the service."""
    from nanobot.daemon import get_daemon_manager
    
    manager = get_daemon_manager()
    
    if manager.stop():
        console.print("[green]✓[/green] Service stopped")
    else:
        console.print("[red]✗[/red] Failed to stop service")


@daemon_app.command("restart")
def daemon_restart():
    """Restart the service."""
    from nanobot.daemon import get_daemon_manager
    
    manager = get_daemon_manager()
    
    if manager.restart():
        console.print("[green]✓[/green] Service restarted")
    else:
        console.print("[red]✗[/red] Failed to restart service")


@daemon_app.command("logs")
def daemon_logs(
    lines: int = typer.Option(50, help="Number of lines to show"),
):
    """View service logs."""
    from nanobot.daemon import get_daemon_manager
    
    manager = get_daemon_manager()
    logs = manager.logs(lines)
    
    if logs:
        console.print(logs)
    else:
        console.print("[dim]No logs available[/dim]")


# ============================================================================
# Memory Commands
# ============================================================================

memory_app = typer.Typer(help="Deep memory system management")
app.add_typer(memory_app, name="memory")


@memory_app.command("status")
def memory_status():
    """Show memory system status."""
    from nanobot.config.loader import load_config
    
    config = load_config()
    workspace = config.workspace_path
    
    console.print("\n[bold]Memory System Status[/bold]")
    console.print(f"  Enabled: {'yes' if config.agents.memory.enabled else 'no'}")
    console.print(f"  Vector search: {'yes' if config.agents.memory.vector_search else 'no'}")
    console.print(f"  Context memories: {config.agents.memory.context_memories}")
    
    # Check memory directory
    memory_dir = workspace / "memory"
    if memory_dir.exists():
        daily_files = list(memory_dir.glob("????-??-??.md"))
        long_term_file = memory_dir / "MEMORY.md"
        vector_file = memory_dir / "vectors.json"
        
        console.print(f"\n[bold]Storage[/bold]")
        console.print(f"  Daily notes: {len(daily_files)} files")
        console.print(f"  Long-term memory: {'exists' if long_term_file.exists() else 'not created'}")
        console.print(f"  Vector index: {'exists' if vector_file.exists() else 'not created'}")
        
        # Show recent memories
        if daily_files:
            recent = sorted(daily_files, reverse=True)[:3]
            console.print(f"\n[bold]Recent Daily Notes[/bold]")
            for f in recent:
                console.print(f"  - {f.stem}")
    else:
        console.print(f"\n[dim]Memory directory not created yet[/dim]")


@memory_app.command("search")
def memory_search(
    query: str = typer.Argument(..., help="Search query"),
    top_k: int = typer.Option(5, "-k", "--top-k", help="Number of results"),
):
    """Search memories semantically."""
    from nanobot.config.loader import load_config
    from nanobot.memory.search import search_memories
    
    config = load_config()
    workspace = config.workspace_path
    
    console.print(f"\nSearching for: [bold]{query}[/bold]\n")
    
    try:
        results = search_memories(
            query=query,
            workspace=workspace,
            k=top_k,
            vector_weight=config.agents.memory.vector_weight,
        )
        
        if not results:
            console.print("[dim]No relevant memories found[/dim]")
            return
        
        console.print(f"Found {len(results)} relevant memories:\n")
        
        for i, result in enumerate(results, 1):
            source = result.entry.source.replace("_", " ").title()
            console.print(f"[bold]{i}. [{source}][/bold] (score: {result.combined_score:.2f})")
            
            # Show score breakdown
            console.print(f"   Vector: {result.vector_score:.2f} | Keyword: {result.keyword_score:.2f} | Recency: {result.recency_score:.2f}")
            
            # Show content preview
            content = result.entry.content[:200].replace("\n", " ")
            console.print(f"   {content}...")
            console.print()
            
    except Exception as e:
        console.print(f"[red]Search failed: {e}[/red]")


@memory_app.command("reindex")
def memory_reindex():
    """Rebuild the vector index for all memories."""
    from nanobot.config.loader import load_config
    from nanobot.agent.context import ContextBuilder
    
    config = load_config()
    workspace = config.workspace_path
    
    console.print("Reindexing memories...")
    
    try:
        context = ContextBuilder(
            workspace=workspace,
            enable_vector_search=True,
        )
        
        count = context.reindex_memories()
        console.print(f"[green]✓[/green] Indexed {count} memory entries")
        
    except Exception as e:
        console.print(f"[red]Reindex failed: {e}[/red]")


@memory_app.command("stats")
def memory_stats():
    """Show memory statistics."""
    from nanobot.config.loader import load_config
    from nanobot.memory.store import MemoryStore
    
    config = load_config()
    workspace = config.workspace_path
    
    try:
        store = MemoryStore(workspace)
        entries = store.get_all_entries()
        
        console.print("\n[bold]Memory Statistics[/bold]\n")
        console.print(f"  Total entries: {len(entries)}")
        
        # Count by source
        sources: dict[str, int] = {}
        for entry in entries:
            sources[entry.source] = sources.get(entry.source, 0) + 1
        
        console.print("\n[bold]By Source[/bold]")
        for source, count in sorted(sources.items()):
            console.print(f"  {source}: {count}")
        
        # Show total content size
        total_chars = sum(len(e.content) for e in entries)
        console.print(f"\n  Total content: ~{total_chars // 1000}k characters")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


# ============================================================================
# Tool Health Commands
# ============================================================================

tools_app = typer.Typer(help="Tool health and self-heal management")
app.add_typer(tools_app, name="tools")


@tools_app.command("health")
def tools_health():
    """Show tool health and circuit breaker status."""
    from nanobot.config.loader import load_config
    from nanobot.agent.tool_manager import ToolCallManager, RetryConfig, CircuitBreakerConfig
    from nanobot.agent.tools.registry import ToolRegistry
    
    config = load_config()
    
    console.print("\n[bold]Self-Heal Configuration[/bold]")
    console.print(f"  Tool retry: {'enabled' if config.agents.self_heal.tool_retry_enabled else 'disabled'}")
    console.print(f"  Max retries: {config.agents.self_heal.max_tool_retries}")
    console.print(f"  Circuit breaker: {'enabled' if config.agents.self_heal.circuit_breaker_enabled else 'disabled'}")
    console.print(f"  Threshold: {config.agents.self_heal.circuit_breaker_threshold} failures")
    console.print(f"  Cooldown: {config.agents.self_heal.circuit_breaker_cooldown}s")
    
    # Show registered tools
    registry = ToolRegistry()
    # Register default tools to show what's available
    from nanobot.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
    from nanobot.agent.tools.shell import ExecTool
    from nanobot.agent.tools.web import WebSearchTool, WebFetchTool
    
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
    registry.register(ListDirTool())
    registry.register(ExecTool())
    registry.register(WebSearchTool())
    registry.register(WebFetchTool())
    
    console.print(f"\n[bold]Registered Tools[/bold]")
    for name in sorted(registry.tool_names):
        console.print(f"  - {name}")


@tools_app.command("advisor-status")
def tools_advisor_status():
    """Show tool advisor statistics."""
    from nanobot.config.loader import load_config
    from nanobot.agent.tool_advisor import ToolAdvisor
    from pathlib import Path
    
    config = load_config()
    storage_path = Path(config.agents.tool_reinforcement.advisor_storage_path).expanduser()
    
    advisor = ToolAdvisor(storage_path=storage_path)
    summary = advisor.get_summary()
    
    console.print("\n[bold]Tool Advisor Statistics[/bold]")
    console.print(f"  Tracked combinations: {summary['total_combinations']}")
    console.print(f"  Unique models: {summary['unique_models']}")
    console.print(f"  Unique tools: {summary['unique_tools']}")
    console.print(f"  Total calls: {summary['total_calls']}")
    console.print(f"  Overall success rate: {summary['overall_success_rate']:.1%}")
    
    # Show problematic combinations
    problematic = advisor.get_problematic_combinations(min_calls=5, max_success_rate=0.5)
    
    if problematic:
        console.print("\n[bold yellow]Problematic Combinations[/bold yellow]")
        for model_id, tool_name, success_rate, calls in problematic[:5]:
            console.print(f"  {model_id} + {tool_name}: {success_rate:.1%} ({calls} calls)")


@tools_app.command("leaderboard")
def tools_leaderboard(
    tool: str = typer.Argument(..., help="Tool name to show leaderboard for"),
    top_n: int = typer.Option(5, "-n", help="Number of top models to show"),
):
    """Show best models for a specific tool."""
    from nanobot.config.loader import load_config
    from nanobot.agent.tool_advisor import ToolAdvisor
    from pathlib import Path
    
    config = load_config()
    storage_path = Path(config.agents.tool_reinforcement.advisor_storage_path).expanduser()
    
    advisor = ToolAdvisor(storage_path=storage_path)
    leaderboard = advisor.get_tool_leaderboard(tool, top_n=top_n)
    
    if not leaderboard:
        console.print(f"[dim]No data for tool '{tool}'[/dim]")
        return
    
    console.print(f"\n[bold]Top Models for '{tool}'[/bold]\n")
    
    for i, (model_id, success_rate, total_calls) in enumerate(leaderboard, 1):
        bar = "█" * int(success_rate * 10) + "░" * (10 - int(success_rate * 10))
        console.print(f"  {i}. {model_id}")
        console.print(f"     {bar} {success_rate:.1%} ({total_calls} calls)")


@tools_app.command("reset-circuits")
def tools_reset_circuits():
    """Reset all circuit breakers."""
    from nanobot.config.loader import load_config
    from nanobot.agent.tool_manager import ToolCallManager
    from nanobot.agent.tools.registry import ToolRegistry
    
    console.print("Resetting circuit breakers...")
    
    # Note: This would need to connect to a running agent
    # For now, just show a message
    console.print("[yellow]Note: Circuit breakers are per-session.[/yellow]")
    console.print("To reset, restart the agent or use the API.")


# ============================================================================
# Node Commands (Gateway-side node management)
# ============================================================================

nodes_app = typer.Typer(help="Manage connected nodes for remote execution")
app.add_typer(nodes_app, name="nodes")


@nodes_app.command("list")
def nodes_list(
    connected: bool = typer.Option(False, "--connected", "-c", help="Only show connected nodes"),
):
    """List all registered nodes."""
    from nanobot.config.loader import load_config
    from nanobot.nodes.manager import NodeManager
    from nanobot.nodes.protocol import NodeStatus
    
    config = load_config()
    
    if not config.nodes.enabled:
        console.print("[yellow]Warning: Nodes not enabled in config[/yellow]")
        console.print("Set nodes.enabled = true in config to use nodes")
    
    storage_path = Path(config.nodes.storage_path).expanduser()
    manager = NodeManager(storage_path=storage_path)
    
    nodes = manager.list_nodes(connected_only=connected)
    
    if not nodes:
        console.print("[dim]No nodes registered[/dim]")
        return
    
    table = Table(title="Registered Nodes")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Status")
    table.add_column("Platform")
    table.add_column("IP Address")
    table.add_column("Last Seen", style="dim")
    
    for node in nodes:
        status_color = {
            NodeStatus.CONNECTED: "green",
            NodeStatus.PAIRED: "yellow",
            NodeStatus.PENDING: "blue",
            NodeStatus.DISCONNECTED: "dim",
        }.get(node.status, "white")
        
        status_str = f"[{status_color}]{node.status.value}[/{status_color}]"
        
        last_seen = ""
        if node.last_seen:
            last_seen = node.last_seen.strftime("%Y-%m-%d %H:%M")
        
        table.add_row(
            node.id[:8] + "...",
            node.display_name,
            status_str,
            node.platform,
            node.ip_address,
            last_seen,
        )
    
    console.print(table)


@nodes_app.command("pending")
def nodes_pending():
    """Show nodes pending approval."""
    from nanobot.config.loader import load_config
    from nanobot.nodes.manager import NodeManager
    
    config = load_config()
    storage_path = Path(config.nodes.storage_path).expanduser()
    manager = NodeManager(storage_path=storage_path)
    
    pending = manager.list_pending()
    
    if not pending:
        console.print("[dim]No pending approval requests[/dim]")
        return
    
    table = Table(title="Pending Approval Requests")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Platform")
    table.add_column("IP Address")
    table.add_column("Capabilities", style="dim")
    
    for node in pending:
        caps = ", ".join(node.get_capability_names()[:3])
        table.add_row(
            node.id[:8] + "...",
            node.display_name,
            node.platform,
            node.ip_address,
            caps,
        )
    
    console.print(table)
    console.print("\nUse 'gigabot nodes approve <id>' to approve")


@nodes_app.command("approve")
def nodes_approve(
    node_id: str = typer.Argument(..., help="Node ID (or prefix) to approve"),
):
    """Approve a pending node."""
    from nanobot.config.loader import load_config
    from nanobot.nodes.manager import NodeManager
    
    config = load_config()
    storage_path = Path(config.nodes.storage_path).expanduser()
    manager = NodeManager(storage_path=storage_path)
    
    # Find node by ID or prefix
    node = manager.get_node(node_id)
    if not node:
        # Try prefix match
        for n in manager.list_nodes():
            if n.id.startswith(node_id):
                node = n
                break
    
    if not node:
        console.print(f"[red]Node not found: {node_id}[/red]")
        raise typer.Exit(1)
    
    async def _approve():
        return await manager.approve_node(node.id)
    
    if asyncio.run(_approve()):
        console.print(f"[green]✓[/green] Approved node: {node.display_name} ({node.id[:8]}...)")
    else:
        console.print(f"[red]Failed to approve node[/red]")


@nodes_app.command("reject")
def nodes_reject(
    node_id: str = typer.Argument(..., help="Node ID (or prefix) to reject"),
    reason: str = typer.Option("Rejected by admin", help="Reason for rejection"),
):
    """Reject a pending node."""
    from nanobot.config.loader import load_config
    from nanobot.nodes.manager import NodeManager
    
    config = load_config()
    storage_path = Path(config.nodes.storage_path).expanduser()
    manager = NodeManager(storage_path=storage_path)
    
    # Find node by ID or prefix
    node = manager.get_node(node_id)
    if not node:
        for n in manager.list_nodes():
            if n.id.startswith(node_id):
                node = n
                break
    
    if not node:
        console.print(f"[red]Node not found: {node_id}[/red]")
        raise typer.Exit(1)
    
    async def _reject():
        return await manager.reject_node(node.id, reason)
    
    if asyncio.run(_reject()):
        console.print(f"[green]✓[/green] Rejected node: {node.display_name}")
    else:
        console.print(f"[red]Failed to reject node[/red]")


@nodes_app.command("status")
def nodes_status():
    """Show detailed node status."""
    from nanobot.config.loader import load_config
    from nanobot.nodes.manager import NodeManager
    from nanobot.nodes.protocol import NodeStatus
    
    config = load_config()
    
    console.print(f"\n[bold]Nodes System Status[/bold]")
    console.print(f"  Enabled: {'yes' if config.nodes.enabled else 'no'}")
    console.print(f"  Auth token: {'set' if config.nodes.auth_token else 'not set'}")
    console.print(f"  Auto-approve: {'yes' if config.nodes.auto_approve else 'no'}")
    console.print(f"  Ping interval: {config.nodes.ping_interval}s")
    
    storage_path = Path(config.nodes.storage_path).expanduser()
    manager = NodeManager(storage_path=storage_path)
    
    nodes = manager.list_nodes()
    
    console.print(f"\n[bold]Node Summary[/bold]")
    console.print(f"  Total nodes: {len(nodes)}")
    
    by_status = {}
    for node in nodes:
        by_status[node.status] = by_status.get(node.status, 0) + 1
    
    for status, count in by_status.items():
        console.print(f"  {status.value}: {count}")


@nodes_app.command("invoke")
def nodes_invoke(
    node: str = typer.Option(..., "--node", "-n", help="Node ID or name"),
    command: str = typer.Option(..., "--command", "-c", help="Command to invoke (e.g., system.run)"),
    params: str = typer.Option("{}", "--params", "-p", help="JSON parameters"),
    timeout: int = typer.Option(30, "--timeout", "-t", help="Timeout in seconds"),
):
    """Invoke a command on a node."""
    import json as json_module
    from nanobot.config.loader import load_config
    from nanobot.nodes.manager import NodeManager
    
    config = load_config()
    storage_path = Path(config.nodes.storage_path).expanduser()
    manager = NodeManager(storage_path=storage_path)
    
    # Find node
    node_info = manager.get_node(node)
    if not node_info:
        node_info = manager.get_node_by_name(node)
    if not node_info:
        for n in manager.list_nodes():
            if n.id.startswith(node):
                node_info = n
                break
    
    if not node_info:
        console.print(f"[red]Node not found: {node}[/red]")
        raise typer.Exit(1)
    
    try:
        params_dict = json_module.loads(params)
    except json_module.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON params: {e}[/red]")
        raise typer.Exit(1)
    
    console.print(f"Invoking [cyan]{command}[/cyan] on [green]{node_info.display_name}[/green]...")
    
    async def _invoke():
        return await manager.invoke(
            node_id=node_info.id,
            command=command,
            params=params_dict,
            timeout_ms=timeout * 1000,
        )
    
    result = asyncio.run(_invoke())
    
    if result.success:
        console.print(f"\n[green]✓[/green] Success ({result.duration_ms:.0f}ms)")
        console.print(f"\n{result.result}")
    else:
        console.print(f"\n[red]✗[/red] Failed: {result.error}")
        if result.error_code:
            console.print(f"  Error code: {result.error_code}")


@nodes_app.command("run")
def nodes_run(
    command: str = typer.Argument(..., help="Shell command to run"),
    node: str = typer.Option(None, "--node", "-n", help="Node ID or name (uses default if not specified)"),
    cwd: str = typer.Option(None, "--cwd", help="Working directory"),
    timeout: int = typer.Option(60, "--timeout", "-t", help="Timeout in seconds"),
):
    """Run a shell command on a node (shorthand for invoke system.run)."""
    import json as json_module
    from nanobot.config.loader import load_config
    from nanobot.nodes.manager import NodeManager
    
    config = load_config()
    storage_path = Path(config.nodes.storage_path).expanduser()
    manager = NodeManager(storage_path=storage_path)
    
    # Find target node
    if node:
        node_info = manager.get_node(node)
        if not node_info:
            node_info = manager.get_node_by_name(node)
        if not node_info:
            for n in manager.list_nodes():
                if n.id.startswith(node):
                    node_info = n
                    break
    else:
        node_info = manager.get_default_node()
    
    if not node_info:
        console.print(f"[red]No node available[/red]")
        raise typer.Exit(1)
    
    params = {"command": command}
    if cwd:
        params["cwd"] = cwd
    params["timeout"] = timeout
    
    console.print(f"Running on [green]{node_info.display_name}[/green]: {command[:50]}...")
    
    async def _invoke():
        return await manager.invoke(
            node_id=node_info.id,
            command="system.run",
            params=params,
            timeout_ms=timeout * 1000,
        )
    
    result = asyncio.run(_invoke())
    
    if result.success:
        result_data = result.result or {}
        stdout = result_data.get("stdout", "")
        stderr = result_data.get("stderr", "")
        exit_code = result_data.get("exit_code", 0)
        
        if stdout:
            console.print(stdout)
        if stderr:
            console.print(f"[yellow]{stderr}[/yellow]")
        if exit_code != 0:
            console.print(f"[dim]Exit code: {exit_code}[/dim]")
    else:
        console.print(f"[red]Failed: {result.error}[/red]")


# ============================================================================
# Node Host Commands (Run as a node host)
# ============================================================================

node_app = typer.Typer(help="Run as a node host (connect to gateway)")
app.add_typer(node_app, name="node")


@node_app.command("run")
def node_run(
    host: str = typer.Option(..., "--host", "-h", help="Gateway host address"),
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    display_name: str = typer.Option("", "--display-name", "-n", help="Node display name"),
    token: str = typer.Option("", "--token", "-t", help="Authentication token"),
    tls: bool = typer.Option(False, "--tls", help="Use TLS (wss://)"),
    no_ssl_verify: bool = typer.Option(False, "--no-ssl-verify", help="Disable SSL certificate verification"),
    ssl_fingerprint: str = typer.Option("", "--ssl-fingerprint", help="SHA256 fingerprint for certificate pinning"),
):
    """Run as a node host, connecting to a gateway."""
    from nanobot.nodes.host import run_node_host
    
    console.print(f"{__logo__} Starting node host...")
    console.print(f"  Gateway: {host}:{port}")
    console.print(f"  TLS: {'yes' if tls else 'no'}")
    if no_ssl_verify:
        console.print("  [yellow]SSL verification: disabled[/yellow]")
    
    asyncio.run(run_node_host(
        gateway_host=host,
        gateway_port=port,
        token=token,
        display_name=display_name,
        use_tls=tls,
        ssl_verify=not no_ssl_verify,
        ssl_fingerprint=ssl_fingerprint,
    ))


@node_app.command("install")
def node_install(
    host: str = typer.Option(..., "--host", "-h", help="Gateway host address"),
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    display_name: str = typer.Option("", "--display-name", "-n", help="Node display name"),
    token: str = typer.Option("", "--token", "-t", help="Authentication token"),
    tls: bool = typer.Option(False, "--tls", help="Use TLS (wss://)"),
):
    """Install node host as a system service."""
    import json as json_module
    
    # Save config
    config_path = Path.home() / ".gigabot" / "node.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    protocol = "wss" if tls else "ws"
    gateway_url = f"{protocol}://{host}:{port}/ws/nodes"
    
    config_data = {
        "gateway_url": gateway_url,
        "token": token,
        "display_name": display_name,
    }
    config_path.write_text(json_module.dumps(config_data, indent=2))
    
    console.print(f"[green]✓[/green] Node config saved to {config_path}")
    console.print("\nTo install as a service, you need to:")
    console.print("  1. Create a systemd service (Linux) or launchd plist (macOS)")
    console.print(f"  2. Run: gigabot node run --host {host} --port {port}")
    console.print("\nExample systemd service:")
    console.print(f"""
[Unit]
Description=GigaBot Node Host
After=network.target

[Service]
Type=simple
User={Path.home().name}
ExecStart=/usr/local/bin/gigabot node run --host {host} --port {port}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
""")


@node_app.command("status")
def node_status():
    """Show node host status and configuration."""
    import json as json_module
    
    config_path = Path.home() / ".gigabot" / "node.json"
    
    console.print("\n[bold]Node Host Configuration[/bold]")
    
    if config_path.exists():
        data = json_module.loads(config_path.read_text())
        console.print(f"  Config file: {config_path}")
        console.print(f"  Gateway URL: {data.get('gateway_url', 'not set')}")
        console.print(f"  Display name: {data.get('display_name', 'auto')}")
        console.print(f"  Token: {'set' if data.get('token') else 'not set'}")
        console.print(f"  Node ID: {data.get('node_id', 'not generated')[:16]}...")
    else:
        console.print(f"  [dim]No config found at {config_path}[/dim]")
    
    # Check approvals
    approvals_path = Path.home() / ".gigabot" / "exec-approvals.json"
    if approvals_path.exists():
        data = json_module.loads(approvals_path.read_text())
        entries = data.get("entries", [])
        console.print(f"\n[bold]Exec Approvals[/bold]")
        console.print(f"  Entries: {len(entries)}")
        console.print(f"  Default allow: {data.get('allow_by_default', False)}")
    else:
        console.print(f"\n[dim]No exec approvals configured[/dim]")


@node_app.command("allowlist")
def node_allowlist(
    action: str = typer.Argument(..., help="Action: add, remove, list"),
    pattern: str = typer.Argument(None, help="Pattern to add/remove"),
    deny: bool = typer.Option(False, "--deny", "-d", help="Add as deny pattern (with 'add')"),
    regex: bool = typer.Option(False, "--regex", "-r", help="Pattern is regex (with 'add')"),
):
    """Manage exec allowlist for this node."""
    from nanobot.nodes.approvals import ExecApprovalManager
    
    manager = ExecApprovalManager()
    
    if action == "list":
        entries = manager.list_entries()
        
        console.print("\n[bold]Exec Allowlist[/bold]")
        console.print(f"  Default allow: {manager.allow_by_default}")
        console.print(f"  Use default safe: {manager.use_default_safe}")
        console.print(f"  Use default deny: {manager.use_default_deny}")
        
        if entries:
            console.print("\n[bold]Custom Entries[/bold]")
            for entry in entries:
                entry_type = "[green]ALLOW[/green]" if entry.allow else "[red]DENY[/red]"
                pattern_type = "(regex)" if entry.is_regex else ""
                console.print(f"  {entry_type} {entry.pattern} {pattern_type}")
        else:
            console.print("\n[dim]No custom entries[/dim]")
    
    elif action == "add":
        if not pattern:
            console.print("[red]Pattern required for 'add'[/red]")
            raise typer.Exit(1)
        
        if deny:
            manager.add_deny(pattern, is_regex=regex, added_by="cli")
            console.print(f"[green]✓[/green] Added deny pattern: {pattern}")
        else:
            manager.add_allow(pattern, is_regex=regex, added_by="cli")
            console.print(f"[green]✓[/green] Added allow pattern: {pattern}")
    
    elif action == "remove":
        if not pattern:
            console.print("[red]Pattern required for 'remove'[/red]")
            raise typer.Exit(1)
        
        if manager.remove(pattern):
            console.print(f"[green]✓[/green] Removed pattern: {pattern}")
        else:
            console.print(f"[yellow]Pattern not found: {pattern}[/yellow]")
    
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Use: list, add, remove")


# ============================================================================
# Intent Commands (Proactive AI - Intent Tracking)
# ============================================================================

intent_app = typer.Typer(help="Intent tracking for proactive AI")
app.add_typer(intent_app, name="intent")


@intent_app.command("history")
def intent_history(
    days: int = typer.Option(30, "--days", "-d", help="Days of history to show"),
    category: str = typer.Option(None, "--category", "-c", help="Filter by category"),
    user_id: str = typer.Option("default", "--user", "-u", help="User ID"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max entries to show"),
):
    """View recent intent history."""
    from nanobot.config.loader import load_config
    from nanobot.intent.tracker import IntentTracker
    
    config = load_config()
    
    tracker = IntentTracker(
        workspace=config.workspace_path,
        provider=None,  # Don't need provider for reading history
    )
    
    intents = tracker.get_history(user_id=user_id, days=days, category=category)
    
    console.print(f"\n{__logo__} [bold]Intent History[/bold]")
    console.print(f"  User: {user_id} | Days: {days}")
    if category:
        console.print(f"  Category filter: {category}")
    console.print("")
    
    if not intents:
        console.print("[dim]No intents found.[/dim]")
        return
    
    table = Table()
    table.add_column("Time", style="dim")
    table.add_column("Category", style="cyan")
    table.add_column("Goal", no_wrap=False)
    table.add_column("Status", style="green")
    
    for intent in intents[:limit]:
        time_str = intent.created_at.strftime("%m-%d %H:%M")
        status = "✓" if intent.completed_at else "⋯"
        table.add_row(
            time_str,
            intent.category,
            intent.inferred_goal[:60] + "..." if len(intent.inferred_goal) > 60 else intent.inferred_goal,
            status,
        )
    
    console.print(table)
    console.print(f"\n[dim]Showing {min(len(intents), limit)} of {len(intents)} intents[/dim]")


@intent_app.command("patterns")
def intent_patterns(
    user_id: str = typer.Option("default", "--user", "-u", help="User ID"),
    refresh: bool = typer.Option(False, "--refresh", "-r", help="Re-analyze patterns"),
):
    """Show discovered patterns in user behavior."""
    from nanobot.config.loader import load_config
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.intent.tracker import IntentTracker
    
    config = load_config()
    
    provider = None
    if refresh:
        api_key = config.get_api_key()
        if api_key:
            provider = LiteLLMProvider(
                api_key=api_key,
                api_base=config.get_api_base(),
                default_model=config.agents.intent_tracking.analysis_model,
            )
    
    tracker = IntentTracker(
        workspace=config.workspace_path,
        provider=provider,
        model=config.agents.intent_tracking.analysis_model,
    )
    
    console.print(f"\n{__logo__} [bold]Intent Patterns[/bold]")
    console.print(f"  User: {user_id}")
    
    if refresh:
        console.print("\n[dim]Analyzing patterns...[/dim]")
        
        async def analyze():
            return await tracker.analyze_patterns(user_id=user_id)
        
        patterns = asyncio.run(analyze())
    else:
        patterns = tracker._load_patterns()
    
    if not patterns:
        console.print("\n[dim]No patterns discovered yet.[/dim]")
        console.print("Use --refresh to analyze intent history")
        return
    
    console.print("")
    
    for pattern in patterns:
        console.print(f"[cyan]{pattern.pattern_type}[/cyan]")
        console.print(f"  {pattern.description}")
        console.print(f"  Confidence: {pattern.confidence:.0%} | Frequency: {pattern.frequency}")
        console.print("")


@intent_app.command("predict")
def intent_predict(
    user_id: str = typer.Option("default", "--user", "-u", help="User ID"),
):
    """Predict likely upcoming user intents."""
    from nanobot.config.loader import load_config
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.intent.tracker import IntentTracker
    
    config = load_config()
    
    api_key = config.get_api_key()
    if not api_key:
        console.print("[red]Error: No API key configured.[/red]")
        raise typer.Exit(1)
    
    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=config.get_api_base(),
        default_model=config.agents.intent_tracking.analysis_model,
    )
    
    tracker = IntentTracker(
        workspace=config.workspace_path,
        provider=provider,
        model=config.agents.intent_tracking.analysis_model,
    )
    
    console.print(f"\n{__logo__} [bold]Intent Predictions[/bold]")
    console.print(f"  User: {user_id}")
    console.print("\n[dim]Analyzing patterns...[/dim]")
    
    async def predict():
        return await tracker.predict_next_intent(user_id=user_id)
    
    predictions = asyncio.run(predict())
    
    if not predictions:
        console.print("\n[dim]Not enough data for predictions.[/dim]")
        console.print("Continue using GigaBot to build intent history")
        return
    
    console.print("\n[bold]Predicted Next Actions:[/bold]")
    
    for i, pred in enumerate(predictions, 1):
        console.print(f"\n{i}. [cyan]{pred.predicted_goal}[/cyan]")
        console.print(f"   Category: {pred.category} | Confidence: {pred.confidence:.0%}")
        console.print(f"   [dim]{pred.reasoning}[/dim]")


@intent_app.command("stats")
def intent_stats(
    user_id: str = typer.Option("default", "--user", "-u", help="User ID"),
):
    """Show intent tracking statistics."""
    from nanobot.config.loader import load_config
    from nanobot.intent.tracker import IntentTracker
    
    config = load_config()
    
    tracker = IntentTracker(
        workspace=config.workspace_path,
        provider=None,
    )
    
    stats = tracker.get_stats(user_id=user_id)
    
    console.print(f"\n{__logo__} [bold]Intent Statistics[/bold]")
    console.print(f"  User: {user_id}\n")
    
    console.print(f"  Total intents: {stats['total_intents']}")
    console.print(f"  Recurring intents: {stats['recurring_intents']}")
    console.print(f"  Completion rate: {stats['completion_rate']:.0%}")
    console.print(f"  Average satisfaction: {stats['average_satisfaction']:.0%}")
    console.print(f"  Patterns discovered: {stats['patterns_discovered']}")
    
    console.print("\n[bold]Category Distribution:[/bold]")
    for cat, count in sorted(stats['category_distribution'].items(), key=lambda x: -x[1]):
        bar = "█" * min(count, 20)
        console.print(f"  {cat:15} {bar} {count}")


# ============================================================================
# Memory Evolution Commands (extends memory_app defined above)
# ============================================================================


@memory_app.command("evolve")
def memory_evolve(
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview without making changes"),
):
    """Run memory evolution cycle (promote, decay, archive, cross-reference)."""
    from nanobot.config.loader import load_config
    from nanobot.memory.store import MemoryStore
    from nanobot.memory.evolution import MemoryEvolution
    
    config = load_config()
    
    store = MemoryStore(config.workspace_path)
    evolution = MemoryEvolution(
        store=store,
        vector_store=None,  # Would need to initialize if consolidation needed
        config=config.agents.memory_evolution.model_dump() if hasattr(config.agents, 'memory_evolution') else None,
    )
    
    console.print(f"\n{__logo__} [bold]Memory Evolution[/bold]")
    if dry_run:
        console.print("[yellow]DRY RUN - no changes will be made[/yellow]")
    console.print("")
    
    async def run_evolution():
        return await evolution.evolve(
            dry_run=dry_run,
            auto_promote=config.agents.memory_evolution.auto_promote if hasattr(config.agents, 'memory_evolution') else True,
            auto_decay=config.agents.memory_evolution.auto_expire if hasattr(config.agents, 'memory_evolution') else True,
            auto_archive=config.agents.memory_evolution.auto_archive if hasattr(config.agents, 'memory_evolution') else True,
        )
    
    report = asyncio.run(run_evolution())
    
    console.print("[bold]Evolution Report:[/bold]")
    console.print(f"  Promoted: {len(report.promoted)} memories")
    console.print(f"  Decayed: {len(report.decayed)} memories")
    console.print(f"  Archived: {len(report.archived)} memories")
    console.print(f"  Cross-refs added: {report.cross_refs_added}")
    console.print(f"  Consolidated: {report.consolidated}")
    console.print(f"\n[dim]Duration: {report.duration_ms:.0f}ms[/dim]")


@memory_app.command("evolution-stats")
def memory_evolution_stats():
    """Show memory evolution statistics (promotion, decay, cross-refs)."""
    from nanobot.config.loader import load_config
    from nanobot.memory.store import MemoryStore
    from nanobot.memory.evolution import MemoryEvolution
    
    config = load_config()
    
    store = MemoryStore(config.workspace_path)
    evolution = MemoryEvolution(store=store, vector_store=None)
    
    stats = evolution.get_stats()
    
    console.print(f"\n{__logo__} [bold]Memory Evolution Statistics[/bold]\n")
    
    console.print(f"  Total entries: {stats['total_entries']}")
    console.print(f"  Active entries: {stats['active_entries']}")
    console.print(f"  Archived entries: {stats['archived_entries']}")
    console.print(f"  Cross-references: {stats['total_cross_references']}")
    
    console.print("\n[bold]Importance Distribution:[/bold]")
    dist = stats['importance_distribution']
    console.print(f"  High (>0.7):   {'█' * min(dist['high'], 30)} {dist['high']}")
    console.print(f"  Medium:        {'█' * min(dist['medium'], 30)} {dist['medium']}")
    console.print(f"  Low (<0.3):    {'█' * min(dist['low'], 30)} {dist['low']}")
    
    console.print("\n[bold]Evolution Status:[/bold]")
    console.print(f"  Promoted memories: {stats['promoted_memories']}")
    console.print(f"  Decayed memories: {stats['decayed_memories']}")
    console.print(f"  Total accesses: {stats['total_accesses']}")
    console.print(f"  Avg accesses/entry: {stats['average_accesses_per_entry']:.1f}")


@memory_app.command("promote")
def memory_promote(
    entry_id: str = typer.Argument(..., help="Memory entry ID to promote"),
    reason: str = typer.Option("manual", "--reason", "-r", help="Reason for promotion"),
):
    """Manually promote a memory's importance."""
    from nanobot.config.loader import load_config
    from nanobot.memory.store import MemoryStore
    from nanobot.memory.evolution import MemoryEvolution
    
    config = load_config()
    
    store = MemoryStore(config.workspace_path)
    evolution = MemoryEvolution(store=store, vector_store=None)
    
    async def promote():
        return await evolution.promote_memory(entry_id, reason)
    
    success = asyncio.run(promote())
    
    if success:
        console.print(f"[green]✓[/green] Promoted memory: {entry_id}")
        console.print(f"  Reason: {reason}")
    else:
        console.print(f"[red]Failed to promote: {entry_id}[/red]")
        console.print("  Memory may be archived or not found")


@memory_app.command("archive")
def memory_archive(
    days: int = typer.Option(90, "--days", "-d", help="Archive entries not accessed in N days"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview without archiving"),
):
    """Archive old, unused memories."""
    from nanobot.config.loader import load_config
    from nanobot.memory.store import MemoryStore
    from nanobot.memory.evolution import MemoryEvolution
    
    config = load_config()
    
    store = MemoryStore(config.workspace_path)
    evolution = MemoryEvolution(store=store, vector_store=None)
    
    console.print(f"\n{__logo__} [bold]Memory Archive[/bold]")
    console.print(f"  Archiving entries not accessed in {days} days")
    if dry_run:
        console.print("[yellow]DRY RUN - no changes will be made[/yellow]")
    console.print("")
    
    # Temporarily set the archive days
    original_days = evolution.ARCHIVE_INACTIVE_DAYS
    evolution.ARCHIVE_INACTIVE_DAYS = days
    
    async def run_archive():
        return await evolution._run_archive(dry_run=dry_run)
    
    try:
        archived = asyncio.run(run_archive())
    finally:
        evolution.ARCHIVE_INACTIVE_DAYS = original_days
    
    if archived:
        console.print(f"[green]✓[/green] Archived {len(archived)} memories")
        for entry_id in archived[:10]:
            console.print(f"  - {entry_id}")
        if len(archived) > 10:
            console.print(f"  ... and {len(archived) - 10} more")
    else:
        console.print("[dim]No memories to archive.[/dim]")


@memory_app.command("cross-ref")
def memory_crossref(
    entry_id: str = typer.Argument(..., help="Memory entry ID to cross-reference"),
):
    """Show and create cross-references for a memory entry."""
    from nanobot.config.loader import load_config
    from nanobot.memory.store import MemoryStore
    from nanobot.memory.evolution import MemoryEvolution
    
    config = load_config()
    
    store = MemoryStore(config.workspace_path)
    evolution = MemoryEvolution(store=store, vector_store=None)
    
    # Get existing refs
    evo_data = store.get_evolution_data(entry_id)
    existing_refs = evo_data.get("cross_references", [])
    
    console.print(f"\n{__logo__} [bold]Memory Cross-References[/bold]")
    console.print(f"  Entry: {entry_id}\n")
    
    if existing_refs:
        console.print("[bold]Existing References:[/bold]")
        for ref_id in existing_refs:
            console.print(f"  → {ref_id}")
    else:
        console.print("[dim]No existing cross-references[/dim]")
    
    # Find new ones
    console.print("\n[dim]Finding related memories...[/dim]")
    
    async def find_refs():
        return await evolution.cross_reference(entry_id)
    
    new_refs = asyncio.run(find_refs())
    new_refs = [r for r in new_refs if r not in existing_refs]
    
    if new_refs:
        console.print(f"\n[green]Added {len(new_refs)} new references:[/green]")
        for ref_id in new_refs:
            console.print(f"  + {ref_id}")
    else:
        console.print("\n[dim]No new related memories found[/dim]")


# ============================================================================
# Cost Optimization Commands (Phase 5B)
# ============================================================================

cost_app = typer.Typer(help="Cost optimization and budget management")
app.add_typer(cost_app, name="cost")


@cost_app.command("report")
def cost_report(
    period: str = typer.Option("week", "--period", "-p", help="Period: day, week, month"),
):
    """Show usage and cost report."""
    from nanobot.config.loader import load_config
    from nanobot.tracking.tokens import TokenTracker
    from nanobot.tracking.optimizer import CostOptimizer
    from nanobot.tracking.cache import ResponseCache
    
    config = load_config()
    
    # Initialize tracker
    tracker_path = config.workspace_path / "tracking" / "tokens.json"
    tracker = TokenTracker(
        storage_path=tracker_path,
        daily_budget_usd=config.agents.cost_optimization.daily_budget_usd if hasattr(config.agents, 'cost_optimization') else 0,
        weekly_budget_usd=config.agents.cost_optimization.weekly_budget_usd if hasattr(config.agents, 'cost_optimization') else 0,
    )
    
    # Initialize cache if enabled
    cache = None
    if hasattr(config.agents, 'cost_optimization') and config.agents.cost_optimization.response_caching:
        cache_path = Path(config.agents.cost_optimization.cache_storage_path).expanduser()
        if cache_path.exists():
            cache = ResponseCache(storage_path=cache_path)
    
    # Initialize optimizer
    optimizer = CostOptimizer(tracker=tracker, cache=cache)
    
    console.print(f"\n{__logo__} [bold]Cost Report ({period})[/bold]\n")
    
    # Get stats based on period
    if period == "day":
        stats = tracker.get_daily_stats()
        cost = tracker.estimate_cost(stats)
    else:  # week
        stats = tracker.get_weekly_stats()
        cost = tracker.estimate_cost(stats)
    
    console.print(f"  [bold]Tokens Used:[/bold]")
    console.print(f"    Prompt:     {stats.prompt_tokens:,}")
    console.print(f"    Completion: {stats.completion_tokens:,}")
    console.print(f"    Total:      {stats.total_tokens:,}")
    console.print(f"    Requests:   {stats.request_count}")
    
    console.print(f"\n  [bold]Estimated Cost:[/bold] ${cost:.4f}")
    
    # Budget status
    if optimizer.daily_budget_usd > 0 or optimizer.weekly_budget_usd > 0:
        console.print(f"\n  [bold]Budget Status:[/bold]")
        within_budget, alert = optimizer.check_budget()
        if alert:
            console.print(f"    [yellow]{alert}[/yellow]")
        else:
            console.print(f"    [green]Within budget[/green]")
    
    # Model breakdown
    if stats.model_usage:
        console.print(f"\n  [bold]By Model:[/bold]")
        for model, tokens in sorted(stats.model_usage.items(), key=lambda x: x[1], reverse=True)[:5]:
            pct = tokens / stats.total_tokens * 100 if stats.total_tokens > 0 else 0
            console.print(f"    {model}: {tokens:,} ({pct:.1f}%)")


@cost_app.command("cache-stats")
def cost_cache_stats():
    """Show response cache statistics."""
    from nanobot.config.loader import load_config
    from nanobot.tracking.cache import ResponseCache
    
    config = load_config()
    
    if not hasattr(config.agents, 'cost_optimization') or not config.agents.cost_optimization.response_caching:
        console.print("[yellow]Response caching is not enabled[/yellow]")
        raise typer.Exit(1)
    
    cache_path = Path(config.agents.cost_optimization.cache_storage_path).expanduser()
    if not cache_path.exists():
        console.print("[dim]No cache data found yet[/dim]")
        raise typer.Exit()
    
    cache = ResponseCache(storage_path=cache_path)
    stats = cache.get_stats()
    
    console.print(f"\n{__logo__} [bold]Response Cache Statistics[/bold]\n")
    
    console.print(f"  Total entries:   {stats.total_entries}")
    console.print(f"  Cache hits:      {stats.total_hits}")
    console.print(f"  Cache misses:    {stats.total_misses}")
    console.print(f"  Hit rate:        {stats.hit_rate:.1%}")
    console.print(f"  Tokens saved:    {stats.total_tokens_saved:,}")
    console.print(f"  Evictions:       {stats.total_evictions}")
    
    if stats.oldest_entry:
        console.print(f"\n  Oldest entry:    {stats.oldest_entry.strftime('%Y-%m-%d %H:%M')}")
    if stats.newest_entry:
        console.print(f"  Newest entry:    {stats.newest_entry.strftime('%Y-%m-%d %H:%M')}")
    
    # Estimated savings
    estimated_savings = (stats.total_tokens_saved / 1_000_000) * 1.0  # ~$1/1M tokens
    console.print(f"\n  [green]Estimated savings: ${estimated_savings:.4f}[/green]")
    
    # Recent entries
    entries = cache.get_entries(limit=5)
    if entries:
        console.print("\n  [bold]Recent Cache Entries:[/bold]")
        for e in entries:
            console.print(f"    [{e['hash']}] {e['preview'][:40]}... ({e['hits']} hits)")


@cost_app.command("optimize")
def cost_optimize():
    """Get optimization suggestions to reduce costs."""
    from nanobot.config.loader import load_config
    from nanobot.tracking.tokens import TokenTracker
    from nanobot.tracking.optimizer import CostOptimizer
    from nanobot.tracking.cache import ResponseCache
    
    config = load_config()
    
    # Initialize components
    tracker_path = config.workspace_path / "tracking" / "tokens.json"
    tracker = TokenTracker(storage_path=tracker_path)
    
    cache = None
    if hasattr(config.agents, 'cost_optimization') and config.agents.cost_optimization.response_caching:
        cache_path = Path(config.agents.cost_optimization.cache_storage_path).expanduser()
        if cache_path.exists():
            cache = ResponseCache(storage_path=cache_path)
    
    optimizer = CostOptimizer(tracker=tracker, cache=cache)
    suggestions = optimizer.get_optimization_suggestions()
    
    console.print(f"\n{__logo__} [bold]Cost Optimization Suggestions[/bold]\n")
    
    if not suggestions:
        console.print("[green]✓ No optimization suggestions - usage looks efficient![/green]")
        raise typer.Exit()
    
    for i, s in enumerate(suggestions, 1):
        priority_color = {"high": "red", "medium": "yellow", "low": "dim"}.get(s.priority, "white")
        console.print(f"  [{priority_color}]{s.priority.upper()}[/{priority_color}] {s.title}")
        console.print(f"       {s.description}")
        console.print(f"       [bold]Action:[/bold] {s.action}")
        if s.estimated_usd > 0:
            console.print(f"       [green]Potential savings: ${s.estimated_usd:.4f}[/green]")
        console.print("")


@cost_app.command("budget")
def cost_budget(
    daily: float = typer.Option(None, "--daily", "-d", help="Set daily budget (USD)"),
    weekly: float = typer.Option(None, "--weekly", "-w", help="Set weekly budget (USD)"),
):
    """View or set budget limits."""
    from nanobot.config.loader import load_config, save_config
    
    config = load_config()
    
    if not hasattr(config.agents, 'cost_optimization'):
        console.print("[yellow]Cost optimization config not found[/yellow]")
        raise typer.Exit(1)
    
    cost_config = config.agents.cost_optimization
    
    if daily is None and weekly is None:
        # Just show current budgets
        console.print(f"\n{__logo__} [bold]Budget Configuration[/bold]\n")
        
        daily_display = f"${cost_config.daily_budget_usd:.2f}" if cost_config.daily_budget_usd > 0 else "Unlimited"
        weekly_display = f"${cost_config.weekly_budget_usd:.2f}" if cost_config.weekly_budget_usd > 0 else "Unlimited"
        
        console.print(f"  Daily budget:   {daily_display}")
        console.print(f"  Weekly budget:  {weekly_display}")
        console.print(f"  Alert at:       {cost_config.alert_threshold:.0%}")
        console.print(f"  Auto-downgrade: {'Yes' if cost_config.auto_downgrade_on_budget else 'No'}")
    else:
        # Update budgets
        if daily is not None:
            cost_config.daily_budget_usd = daily
        if weekly is not None:
            cost_config.weekly_budget_usd = weekly
        
        save_config(config)
        console.print(f"[green]✓[/green] Budget updated!")
        if daily is not None:
            console.print(f"  Daily: ${daily:.2f}")
        if weekly is not None:
            console.print(f"  Weekly: ${weekly:.2f}")


@cost_app.command("clear-cache")
def cost_clear_cache():
    """Clear the response cache."""
    from nanobot.config.loader import load_config
    from nanobot.tracking.cache import ResponseCache
    
    config = load_config()
    
    if not hasattr(config.agents, 'cost_optimization') or not config.agents.cost_optimization.response_caching:
        console.print("[yellow]Response caching is not enabled[/yellow]")
        raise typer.Exit(1)
    
    cache_path = Path(config.agents.cost_optimization.cache_storage_path).expanduser()
    if not cache_path.exists():
        console.print("[dim]No cache to clear[/dim]")
        raise typer.Exit()
    
    cache = ResponseCache(storage_path=cache_path)
    stats = cache.get_stats()
    
    if not typer.confirm(f"Clear {stats.total_entries} cache entries?"):
        raise typer.Exit()
    
    count = cache.invalidate()
    cache.save()
    
    console.print(f"[green]✓[/green] Cleared {count} cache entries")


# ============================================================================
# Proactive Engine Commands (Phase 5B)
# ============================================================================

proactive_app = typer.Typer(help="Proactive AI engine management")
app.add_typer(proactive_app, name="proactive")


@proactive_app.command("status")
def proactive_status():
    """Show proactive engine status."""
    from nanobot.config.loader import load_config
    from nanobot.proactive.engine import ProactiveEngine
    
    config = load_config()
    
    if not hasattr(config.agents, 'proactive') or not config.agents.proactive.enabled:
        console.print("[yellow]Proactive engine is not enabled[/yellow]")
        raise typer.Exit(1)
    
    engine = ProactiveEngine(
        workspace=config.workspace_path,
        max_daily_actions=config.agents.proactive.max_daily_actions,
        require_confirmation=config.agents.proactive.require_confirmation,
        enable_reminders=config.agents.proactive.enable_reminders,
        enable_suggestions=config.agents.proactive.enable_suggestions,
        enable_automation=config.agents.proactive.enable_automation,
        enable_insights=config.agents.proactive.enable_insights,
        enable_anticipation=config.agents.proactive.enable_anticipation,
        min_acceptance_rate=config.agents.proactive.min_acceptance_rate,
        automation_allowlist=config.agents.proactive.automation_allowlist,
    )
    
    status = engine.get_status()
    
    console.print(f"\n{__logo__} [bold]Proactive Engine Status[/bold]\n")
    
    console.print("  [bold]Enabled Action Types:[/bold]")
    for action_type, enabled in status["enabled_types"].items():
        icon = "[green]✓[/green]" if enabled else "[red]✗[/red]"
        console.print(f"    {icon} {action_type}")
    
    console.print(f"\n  Max daily actions: {status['max_daily_actions']}")
    console.print(f"  Require confirmation: {status['require_confirmation']}")
    console.print(f"  Min acceptance rate: {status['min_acceptance_rate']:.0%}")
    console.print(f"  Pending actions: {status['pending_actions']}")
    console.print(f"\n  Intent tracker: {'Connected' if status['has_intent_tracker'] else 'Not connected'}")
    console.print(f"  Memory evolution: {'Connected' if status['has_memory_evolution'] else 'Not connected'}")


@proactive_app.command("pending")
def proactive_pending(
    user: str = typer.Option("default", "--user", "-u", help="User ID to filter"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max entries to show"),
):
    """List pending proactive actions."""
    from nanobot.config.loader import load_config
    from nanobot.proactive.engine import ProactiveEngine
    
    config = load_config()
    
    if not hasattr(config.agents, 'proactive'):
        console.print("[yellow]Proactive engine is not enabled[/yellow]")
        raise typer.Exit(1)
    
    engine = ProactiveEngine(workspace=config.workspace_path)
    actions = engine.get_pending_actions(user_id=user)[:limit]
    
    console.print(f"\n{__logo__} [bold]Pending Proactive Actions[/bold]\n")
    
    if not actions:
        console.print("[dim]No pending actions[/dim]")
        raise typer.Exit()
    
    table = Table()
    table.add_column("ID", style="dim")
    table.add_column("Type")
    table.add_column("Priority")
    table.add_column("Title")
    table.add_column("Status")
    
    for action in actions:
        priority_color = "red" if action.priority > 0.7 else "yellow" if action.priority > 0.4 else "dim"
        table.add_row(
            action.id[:8],
            action.type.value,
            f"[{priority_color}]{action.priority:.1f}[/{priority_color}]",
            action.title[:40],
            action.status.value,
        )
    
    console.print(table)


@proactive_app.command("approve")
def proactive_approve(
    action_id: str = typer.Argument(..., help="Action ID to approve"),
    feedback: str = typer.Option("", "--feedback", "-f", help="Optional feedback"),
):
    """Approve a pending proactive action."""
    from nanobot.config.loader import load_config
    from nanobot.proactive.engine import ProactiveEngine
    
    config = load_config()
    engine = ProactiveEngine(workspace=config.workspace_path)
    
    # Find action
    action = engine.get_action(action_id)
    if not action:
        # Try partial match
        for a in engine.get_pending_actions():
            if a.id.startswith(action_id):
                action = a
                break
    
    if not action:
        console.print(f"[red]Action not found: {action_id}[/red]")
        raise typer.Exit(1)
    
    if engine.mark_accepted(action.id, feedback):
        console.print(f"[green]✓[/green] Approved action: {action.title}")
        if action.type.value == "automation":
            console.print("  [dim]Automation will be executed[/dim]")
    else:
        console.print(f"[red]Failed to approve action[/red]")


@proactive_app.command("dismiss")
def proactive_dismiss(
    action_id: str = typer.Argument(..., help="Action ID to dismiss"),
    feedback: str = typer.Option("", "--feedback", "-f", help="Optional feedback"),
):
    """Dismiss a pending proactive action."""
    from nanobot.config.loader import load_config
    from nanobot.proactive.engine import ProactiveEngine
    
    config = load_config()
    engine = ProactiveEngine(workspace=config.workspace_path)
    
    # Find action
    action = engine.get_action(action_id)
    if not action:
        for a in engine.get_pending_actions():
            if a.id.startswith(action_id):
                action = a
                break
    
    if not action:
        console.print(f"[red]Action not found: {action_id}[/red]")
        raise typer.Exit(1)
    
    if engine.mark_dismissed(action.id, feedback):
        console.print(f"[yellow]✗[/yellow] Dismissed action: {action.title}")
    else:
        console.print(f"[red]Failed to dismiss action[/red]")


@proactive_app.command("stats")
def proactive_stats():
    """Show proactive action statistics."""
    from nanobot.config.loader import load_config
    from nanobot.proactive.engine import ProactiveEngine
    
    config = load_config()
    engine = ProactiveEngine(workspace=config.workspace_path)
    
    stats = engine.get_action_stats()
    
    console.print(f"\n{__logo__} [bold]Proactive Action Statistics[/bold]\n")
    
    console.print(f"  Total actions:    {stats['total_actions']}")
    console.print(f"  Pending:          {stats['pending_actions']}")
    console.print(f"  Delivered:        {stats['total_delivered']}")
    console.print(f"  Accepted:         {stats['total_accepted']}")
    console.print(f"  Dismissed:        {stats['total_dismissed']}")
    console.print(f"  Expired:          {stats['total_expired']}")
    console.print(f"\n  [bold]Acceptance rate:[/bold] {stats['acceptance_rate']}")
    
    if stats['by_type']:
        console.print("\n  [bold]By Action Type:[/bold]")
        for action_type, type_stats in stats['by_type'].items():
            console.print(f"    {action_type}: {type_stats['acceptance_rate']} acceptance")
    
    trigger_stats = stats.get('triggers', {})
    console.print(f"\n  [bold]Triggers:[/bold]")
    console.print(f"    Total:   {trigger_stats.get('total_triggers', 0)}")
    console.print(f"    Enabled: {trigger_stats.get('enabled_triggers', 0)}")
    console.print(f"    Fires:   {trigger_stats.get('total_fires', 0)}")


# Trigger subcommands
trigger_app = typer.Typer(help="Manage proactive triggers")
proactive_app.add_typer(trigger_app, name="trigger")


@trigger_app.command("list")
def trigger_list():
    """List all triggers."""
    from nanobot.config.loader import load_config
    from nanobot.proactive.triggers import TriggerManager
    
    config = load_config()
    manager = TriggerManager(config.workspace_path / "proactive")
    
    triggers = manager.list_triggers(enabled_only=False)
    
    console.print(f"\n{__logo__} [bold]Proactive Triggers[/bold]\n")
    
    if not triggers:
        console.print("[dim]No triggers configured[/dim]")
        raise typer.Exit()
    
    table = Table()
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Condition")
    table.add_column("Enabled")
    table.add_column("Fires")
    
    for t in triggers:
        enabled_str = "[green]✓[/green]" if t.enabled else "[red]✗[/red]"
        table.add_row(
            t.id,
            t.name,
            t.type.value,
            t.condition[:30],
            enabled_str,
            str(t.fire_count),
        )
    
    console.print(table)


@trigger_app.command("add")
def trigger_add(
    name: str = typer.Argument(..., help="Trigger name"),
    schedule: str = typer.Argument(..., help="Cron expression (e.g., '0 9 * * *' for 9 AM daily)"),
    title: str = typer.Option("Reminder", "--title", "-t", help="Action title"),
    content: str = typer.Option("", "--content", "-c", help="Action content"),
    user: str = typer.Option("", "--user", "-u", help="User scope (empty = global)"),
):
    """Add a schedule-based trigger."""
    from nanobot.config.loader import load_config
    from nanobot.proactive.triggers import TriggerManager, create_schedule_trigger
    
    config = load_config()
    manager = TriggerManager(config.workspace_path / "proactive")
    
    trigger = create_schedule_trigger(
        name=name,
        cron_expr=schedule,
        action_template={
            "type": "reminder",
            "title": title,
            "content": content or f"Scheduled: {name}",
        },
        user_id=user,
    )
    
    trigger_id = manager.add_trigger(trigger)
    console.print(f"[green]✓[/green] Created trigger: {trigger_id}")
    console.print(f"  Name: {name}")
    console.print(f"  Schedule: {schedule}")


@trigger_app.command("remove")
def trigger_remove(
    trigger_id: str = typer.Argument(..., help="Trigger ID to remove"),
):
    """Remove a trigger."""
    from nanobot.config.loader import load_config
    from nanobot.proactive.triggers import TriggerManager
    
    config = load_config()
    manager = TriggerManager(config.workspace_path / "proactive")
    
    if manager.remove_trigger(trigger_id):
        console.print(f"[green]✓[/green] Removed trigger: {trigger_id}")
    else:
        console.print(f"[red]Trigger not found: {trigger_id}[/red]")


@trigger_app.command("enable")
def trigger_enable(
    trigger_id: str = typer.Argument(..., help="Trigger ID"),
    disable: bool = typer.Option(False, "--disable", "-d", help="Disable instead of enable"),
):
    """Enable or disable a trigger."""
    from nanobot.config.loader import load_config
    from nanobot.proactive.triggers import TriggerManager
    
    config = load_config()
    manager = TriggerManager(config.workspace_path / "proactive")
    
    enabled = not disable
    if manager.enable_trigger(trigger_id, enabled):
        status = "enabled" if enabled else "disabled"
        console.print(f"[green]✓[/green] Trigger {trigger_id} {status}")
    else:
        console.print(f"[red]Trigger not found: {trigger_id}[/red]")


if __name__ == "__main__":
    app()
