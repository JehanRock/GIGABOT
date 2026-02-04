"""Interactive setup wizard for GigaBot."""

import os
import sys
from datetime import datetime
from getpass import getpass
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text

from nanobot import __version__, __logo__
from nanobot.config.loader import load_config, save_config, get_config_path
from nanobot.config.schema import Config
from nanobot.security.auth import hash_with_salt, generate_salt

console = Console()

# Provider configurations
PROVIDERS = [
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "description": "Access 200+ models through one API",
        "url": "https://openrouter.ai/keys",
        "key_prefix": "sk-or-",
        "api_base": "https://openrouter.ai/api/v1",
        "recommended": True,
        "models": [
            ("anthropic/claude-sonnet-4-5", "Fast, capable, cost-effective"),
            ("anthropic/claude-opus-4-5", "Most capable, higher cost"),
            ("openai/gpt-4o", "OpenAI's flagship model"),
            ("moonshot/kimi-k2.5", "Great for coding tasks"),
            ("google/gemini-2.0-flash", "Fast and affordable"),
        ],
    },
    {
        "id": "anthropic",
        "name": "Anthropic",
        "description": "Direct Claude API access",
        "url": "https://console.anthropic.com/",
        "key_prefix": "sk-ant-",
        "api_base": None,
        "recommended": False,
        "models": [
            ("claude-sonnet-4-5-20250514", "Fast, capable, cost-effective"),
            ("claude-opus-4-5-20250514", "Most capable, higher cost"),
        ],
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "description": "Direct GPT API access",
        "url": "https://platform.openai.com/api-keys",
        "key_prefix": "sk-",
        "api_base": None,
        "recommended": False,
        "models": [
            ("gpt-4o", "GPT-4 Omni - flagship model"),
            ("gpt-4o-mini", "Fast and affordable"),
            ("gpt-4-turbo", "Previous generation flagship"),
        ],
    },
    {
        "id": "moonshot",
        "name": "Moonshot",
        "description": "Kimi models - excellent for coding",
        "url": "https://platform.moonshot.cn/console/api-keys",
        "key_prefix": "",
        "api_base": "https://api.moonshot.cn/v1",
        "recommended": False,
        "models": [
            ("moonshot-v1-128k", "128K context, great for code"),
            ("moonshot-v1-32k", "32K context"),
        ],
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "description": "DeepSeek models - strong reasoning",
        "url": "https://platform.deepseek.com/",
        "key_prefix": "",
        "api_base": "https://api.deepseek.com/v1",
        "recommended": False,
        "models": [
            ("deepseek-chat", "General chat model"),
            ("deepseek-coder", "Specialized for coding"),
        ],
    },
]


class SetupWizard:
    """Interactive setup wizard for GigaBot."""
    
    def __init__(self, non_interactive: bool = False, reset: bool = False):
        self.non_interactive = non_interactive
        self.reset = reset
        self.config: Config | None = None
        self.provider: dict | None = None
        self.api_key: str = ""
        self.model: str = ""
        self.password: str = ""
        self.pin: str = ""
    
    def run(self) -> bool:
        """Run the setup wizard. Returns True if setup completed."""
        try:
            # Load existing config or create new
            config_path = get_config_path()
            
            if self.reset and config_path.exists():
                if self.non_interactive or Confirm.ask(
                    "[yellow]Reset existing configuration?[/yellow]",
                    default=False
                ):
                    self.config = Config()
                    console.print("[green]✓[/green] Configuration reset")
                else:
                    raise typer.Exit(0)
            else:
                self.config = load_config()
            
            # Check if already set up
            if self.config.security.auth.setup_complete and not self.reset:
                console.print("[yellow]GigaBot is already configured.[/yellow]")
                if not Confirm.ask("Run setup again?", default=False):
                    raise typer.Exit(0)
            
            # Run wizard steps
            self._welcome_screen()
            self._security_warning()
            self._select_provider()
            
            if self.provider and self.provider["id"] != "skip":
                self._enter_api_key()
                if self.api_key:
                    self._test_api_key()
                    self._select_model()
            
            self._setup_dashboard_auth()
            self._save_config()
            self._summary()
            
            return True
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Setup cancelled.[/yellow]")
            return False
        except typer.Exit:
            return False
    
    def _welcome_screen(self):
        """Display welcome screen."""
        console.print()
        console.print(Panel(
            f"[bold cyan]{__logo__} GigaBot Setup Wizard[/bold cyan]\n\n"
            f"Version: {__version__}\n\n"
            "This wizard will help you configure:\n"
            "  [green]•[/green] LLM Provider (API key)\n"
            "  [green]•[/green] Default model selection\n"
            "  [green]•[/green] Dashboard security",
            title="Welcome",
            border_style="cyan",
        ))
        
        if not self.non_interactive:
            Prompt.ask("\nPress Enter to continue", default="")
    
    def _security_warning(self):
        """Display security warning and get acknowledgment."""
        console.print()
        console.print(Panel(
            "[bold yellow]Security Notice[/bold yellow]\n\n"
            "GigaBot can execute tools and access files on your system.\n"
            "Please understand the security implications:\n\n"
            "[green]Recommended:[/green]\n"
            "  • Set a strong dashboard password\n"
            "  • Review tool permissions in settings\n"
            "  • Use sandbox mode for untrusted operations\n"
            "  • Keep API keys secure and rotate regularly",
            title="Security",
            border_style="yellow",
        ))
        
        if self.non_interactive:
            return
        
        if not Confirm.ask(
            "\n[bold]I understand and accept the risks[/bold]",
            default=False
        ):
            console.print("[red]You must accept the security notice to continue.[/red]")
            raise typer.Exit(1)
    
    def _select_provider(self):
        """Select LLM provider."""
        console.print()
        console.print(Panel(
            "[bold cyan]Select LLM Provider[/bold cyan]\n\n"
            "Choose the provider for your LLM API access.",
            title="Provider",
            border_style="cyan",
        ))
        
        # Check for existing provider
        existing_provider = self._detect_existing_provider()
        if existing_provider:
            console.print(f"\n[green]Existing provider detected: {existing_provider}[/green]")
            if Confirm.ask("Keep existing provider?", default=True):
                self.provider = next(
                    (p for p in PROVIDERS if p["id"] == existing_provider), None
                )
                self.api_key = self._get_existing_api_key(existing_provider)
                if self.api_key:
                    console.print(f"[green]✓[/green] Using existing API key ({self._mask_key(self.api_key)})")
                    return
        
        # Check environment variables
        env_key = self._check_env_api_keys()
        if env_key:
            provider_id, key = env_key
            console.print(f"\n[green]Found API key in environment: {provider_id.upper()}[/green]")
            if Confirm.ask(f"Use {provider_id.upper()} API key from environment?", default=True):
                self.provider = next((p for p in PROVIDERS if p["id"] == provider_id), None)
                self.api_key = key
                return
        
        # Display provider options
        table = Table(show_header=False, box=None)
        table.add_column("Num", style="dim", width=4)
        table.add_column("Provider", width=20)
        table.add_column("Description")
        
        for i, provider in enumerate(PROVIDERS, 1):
            name = provider["name"]
            if provider["recommended"]:
                name = f"[bold green]{name}[/bold green] (recommended)"
            table.add_row(str(i), name, provider["description"])
        
        table.add_row(str(len(PROVIDERS) + 1), "[dim]Skip[/dim]", "Configure later in dashboard")
        
        console.print()
        console.print(table)
        
        if self.non_interactive:
            # Default to OpenRouter in non-interactive mode
            self.provider = PROVIDERS[0]
            return
        
        choice = Prompt.ask(
            "\nSelect provider",
            choices=[str(i) for i in range(1, len(PROVIDERS) + 2)],
            default="1"
        )
        
        choice_idx = int(choice) - 1
        if choice_idx >= len(PROVIDERS):
            self.provider = {"id": "skip", "name": "Skip"}
            console.print("[yellow]Skipping provider setup. Configure in dashboard later.[/yellow]")
        else:
            self.provider = PROVIDERS[choice_idx]
    
    def _enter_api_key(self):
        """Enter and validate API key."""
        if self.api_key:
            return  # Already have key from env or existing config
        
        console.print()
        console.print(Panel(
            f"[bold cyan]Enter API Key[/bold cyan]\n\n"
            f"Provider: {self.provider['name']}\n"
            f"Get your key at: [link]{self.provider['url']}[/link]",
            title="API Key",
            border_style="cyan",
        ))
        
        if self.non_interactive:
            # Check environment variable
            env_var = f"{self.provider['id'].upper()}_API_KEY"
            self.api_key = os.environ.get(env_var, "")
            if not self.api_key:
                console.print(f"[red]Error: {env_var} not set in environment[/red]")
                raise typer.Exit(1)
            return
        
        while True:
            # Use getpass for secure input
            try:
                self.api_key = getpass("\nEnter API key (hidden): ").strip()
            except EOFError:
                self.api_key = Prompt.ask("\nEnter API key").strip()
            
            if not self.api_key:
                if Confirm.ask("Skip API key setup?", default=False):
                    self.provider = {"id": "skip", "name": "Skip"}
                    return
                continue
            
            # Basic validation
            if self.provider.get("key_prefix") and not self.api_key.startswith(self.provider["key_prefix"]):
                console.print(f"[yellow]Warning: Key doesn't start with expected prefix ({self.provider['key_prefix']})[/yellow]")
                if not Confirm.ask("Continue anyway?", default=True):
                    continue
            
            break
        
        console.print(f"[green]✓[/green] API key entered ({self._mask_key(self.api_key)})")
    
    def _test_api_key(self):
        """Test API key with a simple request."""
        console.print("\n[dim]Testing API connection...[/dim]")
        
        try:
            import httpx
            
            provider_id = self.provider["id"]
            
            if provider_id == "openrouter":
                # Test OpenRouter with models endpoint
                response = httpx.get(
                    "https://openrouter.ai/api/v1/auth/key",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json().get("data", {})
                    credits = data.get("limit_remaining")
                    if credits is not None:
                        console.print(f"[green]✓[/green] API key valid! Credits: ${credits:.2f}")
                    else:
                        console.print("[green]✓[/green] API key valid!")
                    return
                    
            elif provider_id == "anthropic":
                # Test Anthropic with a minimal request
                response = httpx.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "Hi"}]
                    },
                    timeout=10
                )
                if response.status_code in [200, 400]:  # 400 means auth worked but request was invalid
                    console.print("[green]✓[/green] API key valid!")
                    return
                    
            elif provider_id == "openai":
                # Test OpenAI
                response = httpx.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10
                )
                if response.status_code == 200:
                    console.print("[green]✓[/green] API key valid!")
                    return
            
            else:
                # Generic test - just accept the key
                console.print("[green]✓[/green] API key saved (not validated)")
                return
            
            # If we get here, validation failed
            console.print(f"[yellow]Warning: Could not validate API key (status {response.status_code})[/yellow]")
            if not self.non_interactive and not Confirm.ask("Continue anyway?", default=True):
                self.api_key = ""
                self._enter_api_key()
                
        except Exception as e:
            console.print(f"[yellow]Warning: Could not test API key: {e}[/yellow]")
            if not self.non_interactive and not Confirm.ask("Continue anyway?", default=True):
                self.api_key = ""
                self._enter_api_key()
    
    def _select_model(self):
        """Select default model."""
        if not self.provider or self.provider["id"] == "skip":
            return
        
        console.print()
        console.print(Panel(
            "[bold cyan]Select Default Model[/bold cyan]\n\n"
            "Choose your default model. You can change this later.",
            title="Model",
            border_style="cyan",
        ))
        
        models = self.provider.get("models", [])
        if not models:
            self.model = self.config.agents.defaults.model
            return
        
        table = Table(show_header=False, box=None)
        table.add_column("Num", style="dim", width=4)
        table.add_column("Model", width=35)
        table.add_column("Description")
        
        for i, (model_id, desc) in enumerate(models, 1):
            name = model_id
            if i == 1:
                name = f"[bold green]{model_id}[/bold green]"
            table.add_row(str(i), name, desc)
        
        console.print()
        console.print(table)
        
        if self.non_interactive:
            self.model = models[0][0]
            return
        
        choice = Prompt.ask(
            "\nSelect model",
            choices=[str(i) for i in range(1, len(models) + 1)],
            default="1"
        )
        
        self.model = models[int(choice) - 1][0]
        console.print(f"[green]✓[/green] Selected: {self.model}")
    
    def _setup_dashboard_auth(self):
        """Set up dashboard authentication."""
        console.print()
        console.print(Panel(
            "[bold cyan]Dashboard Security[/bold cyan]\n\n"
            "Set up password protection for the web dashboard.\n"
            "This prevents unauthorized access to GigaBot.",
            title="Security",
            border_style="cyan",
        ))
        
        if self.non_interactive:
            # Skip auth setup in non-interactive mode
            console.print("[yellow]Skipping dashboard auth in non-interactive mode[/yellow]")
            return
        
        if not Confirm.ask("\nEnable dashboard password protection?", default=True):
            console.print("[yellow]Dashboard will be accessible without authentication.[/yellow]")
            return
        
        # Get password
        while True:
            try:
                self.password = getpass("\nEnter dashboard password (min 8 chars): ").strip()
            except EOFError:
                self.password = Prompt.ask("\nEnter dashboard password (min 8 chars)").strip()
            
            if len(self.password) < 8:
                console.print("[red]Password must be at least 8 characters.[/red]")
                continue
            
            try:
                confirm = getpass("Confirm password: ").strip()
            except EOFError:
                confirm = Prompt.ask("Confirm password").strip()
            
            if self.password != confirm:
                console.print("[red]Passwords don't match.[/red]")
                continue
            
            break
        
        console.print("[green]✓[/green] Password set")
        
        # Optional PIN
        if Confirm.ask("\nEnable PIN for two-factor authentication?", default=False):
            while True:
                try:
                    self.pin = getpass("Enter 4-8 digit PIN: ").strip()
                except EOFError:
                    self.pin = Prompt.ask("Enter 4-8 digit PIN").strip()
                
                if not self.pin.isdigit() or not (4 <= len(self.pin) <= 8):
                    console.print("[red]PIN must be 4-8 digits.[/red]")
                    continue
                
                try:
                    confirm = getpass("Confirm PIN: ").strip()
                except EOFError:
                    confirm = Prompt.ask("Confirm PIN").strip()
                
                if self.pin != confirm:
                    console.print("[red]PINs don't match.[/red]")
                    continue
                
                break
            
            console.print("[green]✓[/green] PIN set")
    
    def _save_config(self):
        """Save configuration to file."""
        # Update provider config
        if self.provider and self.provider["id"] != "skip" and self.api_key:
            provider_id = self.provider["id"]
            provider_config = getattr(self.config.providers, provider_id)
            provider_config.api_key = self.api_key
            if self.provider.get("api_base"):
                provider_config.api_base = self.provider["api_base"]
        
        # Update default model
        if self.model:
            self.config.agents.defaults.model = self.model
        
        # Update auth config
        if self.password:
            salt = generate_salt()
            self.config.security.auth.password_hash = hash_with_salt(self.password, salt)
            self.config.security.auth.password_salt = salt
            self.config.security.auth.mode = "password"
            
            if self.pin:
                pin_salt = generate_salt()
                self.config.security.auth.pin_hash = hash_with_salt(self.pin, pin_salt)
                self.config.security.auth.pin_salt = pin_salt
                self.config.security.auth.require_pin = True
            else:
                self.config.security.auth.require_pin = False
        
        # Mark setup as complete
        self.config.security.auth.setup_complete = True
        
        # Save
        save_config(self.config)
        console.print(f"\n[green]✓[/green] Configuration saved to {get_config_path()}")
    
    def _summary(self):
        """Display setup summary."""
        console.print()
        
        table = Table(title="Setup Complete", show_header=False, border_style="green")
        table.add_column("Setting", style="cyan")
        table.add_column("Value")
        
        if self.provider and self.provider["id"] != "skip":
            table.add_row("Provider", self.provider["name"])
            if self.api_key:
                table.add_row("API Key", self._mask_key(self.api_key))
        else:
            table.add_row("Provider", "[yellow]Not configured[/yellow]")
        
        if self.model:
            table.add_row("Default Model", self.model)
        
        if self.password:
            auth_mode = "Password + PIN" if self.pin else "Password only"
            table.add_row("Dashboard Auth", f"[green]{auth_mode}[/green]")
        else:
            table.add_row("Dashboard Auth", "[yellow]Not enabled[/yellow]")
        
        table.add_row("Config Path", str(get_config_path()))
        
        console.print(table)
        console.print()
        console.print(f"[bold green]{__logo__} GigaBot is ready![/bold green]")
        console.print()
        console.print("Start the gateway with: [cyan]gigabot gateway[/cyan]")
        console.print("Or with Docker: [cyan]docker compose up -d[/cyan]")
    
    # Helper methods
    
    def _detect_existing_provider(self) -> str | None:
        """Detect which provider has an API key configured."""
        for provider in PROVIDERS:
            provider_config = getattr(self.config.providers, provider["id"], None)
            if provider_config and provider_config.api_key:
                return provider["id"]
        return None
    
    def _get_existing_api_key(self, provider_id: str) -> str:
        """Get existing API key for provider."""
        provider_config = getattr(self.config.providers, provider_id, None)
        if provider_config:
            return provider_config.api_key
        return ""
    
    def _check_env_api_keys(self) -> tuple[str, str] | None:
        """Check for API keys in environment variables."""
        env_vars = [
            ("openrouter", "OPENROUTER_API_KEY"),
            ("anthropic", "ANTHROPIC_API_KEY"),
            ("openai", "OPENAI_API_KEY"),
            ("moonshot", "MOONSHOT_API_KEY"),
            ("deepseek", "DEEPSEEK_API_KEY"),
        ]
        
        for provider_id, env_var in env_vars:
            value = os.environ.get(env_var, "").strip()
            if value:
                return (provider_id, value)
        
        return None
    
    def _mask_key(self, key: str) -> str:
        """Mask API key for display."""
        if len(key) <= 8:
            return "*" * len(key)
        return f"{key[:4]}...{key[-4:]}"


def run_setup_wizard(
    non_interactive: bool = False,
    reset: bool = False,
) -> bool:
    """Run the setup wizard."""
    wizard = SetupWizard(non_interactive=non_interactive, reset=reset)
    return wizard.run()
