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
# Onboard / Setup
# ============================================================================


@app.command()
def onboard():
    """Initialize GigaBot configuration and workspace."""
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
    console.print("  1. Add your API key to [cyan]~/.gigabot/config.yaml[/cyan]")
    console.print("     Get one at: https://openrouter.ai/keys")
    console.print("  2. Chat: [cyan]gigabot agent -m \"Hello!\"[/cyan]")
    console.print("\n[dim]For multi-channel setup (Telegram/Discord/WhatsApp), see the README[/dim]")




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


@app.command()
def gateway(
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
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
    
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    console.print(f"{__logo__} Starting GigaBot gateway on port {port}...")
    
    config = load_config()
    
    # Create components
    bus = MessageBus()
    
    # Create provider (supports OpenRouter, Anthropic, OpenAI)
    api_key = config.get_api_key()
    api_base = config.get_api_base()
    
    if not api_key:
        console.print("[red]Error: No API key configured.[/red]")
        console.print("Set one in ~/.nanobot/config.json under providers.openrouter.apiKey")
        raise typer.Exit(1)
    
    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=api_base,
        default_model=config.agents.defaults.model
    )
    
    # Create agent with tiered routing and swarm support
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
        return await agent.process_direct(prompt, session_key="heartbeat")
    
    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        on_heartbeat=on_heartbeat,
        interval_s=30 * 60,  # 30 minutes
        enabled=True
    )
    
    # Create channel manager
    channels = ChannelManager(config, bus)
    
    if channels.enabled_channels:
        console.print(f"[green]✓[/green] Channels enabled: {', '.join(channels.enabled_channels)}")
    else:
        console.print("[yellow]Warning: No channels enabled[/yellow]")
    
    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] Cron: {cron_status['jobs']} scheduled jobs")
    
    console.print(f"[green]✓[/green] Heartbeat: every 30m")
    
    async def run():
        try:
            await cron.start()
            await heartbeat.start()
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
            )
        except KeyboardInterrupt:
            console.print("\nShutting down...")
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()
    
    asyncio.run(run())




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


if __name__ == "__main__":
    app()
