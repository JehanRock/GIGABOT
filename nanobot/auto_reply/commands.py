"""
Command detection and parsing for GigaBot auto-reply.

Supports:
- /commands from messages
- Inline directives
- Command registry with handlers
"""

import re
from typing import Any, Callable, Awaitable
from dataclasses import dataclass, field


@dataclass
class Command:
    """A parsed command."""
    name: str
    arguments: list[str] = field(default_factory=list)
    raw: str = ""
    
    @property
    def arg(self) -> str:
        """Get first argument or empty string."""
        return self.arguments[0] if self.arguments else ""
    
    @property
    def args_str(self) -> str:
        """Get all arguments as a single string."""
        return " ".join(self.arguments)


@dataclass
class ParsedMessage:
    """Message with extracted commands."""
    content: str  # Original message content
    commands: list[Command] = field(default_factory=list)
    clean_content: str = ""  # Content with commands removed
    metadata: dict[str, Any] = field(default_factory=dict)


# Type alias for command handlers
CommandHandler = Callable[[Command, dict[str, Any]], Awaitable[str | None]]


class CommandRegistry:
    """
    Registry for command handlers.
    
    Supports:
    - Multiple command aliases
    - Help text
    - Permission levels
    """
    
    # Built-in commands
    BUILTIN_COMMANDS = {
        "use": "Set model tier: /use daily_driver|coder|specialist",
        "think": "Set thinking depth: /think low|medium|high",
        "help": "Show available commands",
        "status": "Show bot status",
        "clear": "Clear conversation history",
        "model": "Show or change current model",
        "stop": "Stop current processing",
    }
    
    def __init__(self):
        self._handlers: dict[str, CommandHandler] = {}
        self._aliases: dict[str, str] = {}
        self._help: dict[str, str] = {}
        
        # Register built-in command help
        for cmd, help_text in self.BUILTIN_COMMANDS.items():
            self._help[cmd] = help_text
    
    def register(
        self,
        name: str,
        handler: CommandHandler,
        help_text: str = "",
        aliases: list[str] | None = None,
    ) -> None:
        """
        Register a command handler.
        
        Args:
            name: Primary command name.
            handler: Async function to handle the command.
            help_text: Help text for the command.
            aliases: Alternative names for the command.
        """
        self._handlers[name] = handler
        if help_text:
            self._help[name] = help_text
        
        if aliases:
            for alias in aliases:
                self._aliases[alias] = name
    
    def get_handler(self, command_name: str) -> CommandHandler | None:
        """Get handler for a command."""
        # Check direct match
        if command_name in self._handlers:
            return self._handlers[command_name]
        
        # Check aliases
        canonical = self._aliases.get(command_name)
        if canonical:
            return self._handlers.get(canonical)
        
        return None
    
    async def execute(
        self,
        command: Command,
        context: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Execute a command.
        
        Args:
            command: The parsed command.
            context: Optional context for the handler.
        
        Returns:
            Handler response or None.
        """
        handler = self.get_handler(command.name)
        if handler:
            return await handler(command, context or {})
        return None
    
    def get_help(self, command_name: str = "") -> str:
        """Get help text for a command or all commands."""
        if command_name:
            # Get canonical name if alias
            canonical = self._aliases.get(command_name, command_name)
            return self._help.get(canonical, f"No help for: {command_name}")
        
        # Return all commands
        lines = ["Available commands:"]
        for name, help_text in sorted(self._help.items()):
            lines.append(f"  /{name} - {help_text}")
        return "\n".join(lines)
    
    def list_commands(self) -> list[str]:
        """List all registered commands."""
        commands = set(self._handlers.keys())
        commands.update(self._help.keys())
        return sorted(commands)


def parse_command(text: str) -> Command | None:
    """
    Parse a single command from text.
    
    Commands start with / and may have arguments.
    
    Examples:
        /help -> Command(name="help")
        /use coder -> Command(name="use", arguments=["coder"])
        /think high -> Command(name="think", arguments=["high"])
    
    Args:
        text: Text that may contain a command.
    
    Returns:
        Parsed Command or None if no command found.
    """
    text = text.strip()
    
    # Must start with /
    if not text.startswith("/"):
        return None
    
    # Parse command and arguments
    parts = text[1:].split()
    if not parts:
        return None
    
    name = parts[0].lower()
    arguments = parts[1:] if len(parts) > 1 else []
    
    return Command(name=name, arguments=arguments, raw=text)


def parse_message(content: str) -> ParsedMessage:
    """
    Parse a message extracting all commands.
    
    Handles:
    - Commands at start of message
    - Inline commands (surrounded by text)
    - Multiple commands
    
    Args:
        content: Full message content.
    
    Returns:
        ParsedMessage with commands and clean content.
    """
    commands = []
    clean_parts = []
    
    # Pattern to find /command in text
    command_pattern = r'/(\w+)(?:\s+([^\n/]+?))?(?=\s*(?:/|$|\n))'
    
    last_end = 0
    for match in re.finditer(command_pattern, content):
        # Add text before command
        clean_parts.append(content[last_end:match.start()])
        
        name = match.group(1).lower()
        args_str = match.group(2) or ""
        arguments = args_str.split() if args_str else []
        
        commands.append(Command(
            name=name,
            arguments=arguments,
            raw=match.group(0),
        ))
        
        last_end = match.end()
    
    # Add remaining text
    clean_parts.append(content[last_end:])
    clean_content = "".join(clean_parts).strip()
    
    return ParsedMessage(
        content=content,
        commands=commands,
        clean_content=clean_content,
    )


def extract_inline_directives(content: str) -> dict[str, str]:
    """
    Extract inline directives from content.
    
    Inline directives look like:
    - [tier:coder]
    - [think:high]
    - [model:claude-opus-4-5]
    
    Args:
        content: Message content.
    
    Returns:
        Dictionary of directive name to value.
    """
    directives = {}
    
    pattern = r'\[(\w+):(\w+)\]'
    for match in re.finditer(pattern, content):
        name = match.group(1).lower()
        value = match.group(2)
        directives[name] = value
    
    return directives


# Global registry instance
_registry: CommandRegistry | None = None


def get_command_registry() -> CommandRegistry:
    """Get the global command registry."""
    global _registry
    if _registry is None:
        _registry = CommandRegistry()
        _register_default_handlers(_registry)
    return _registry


def _register_default_handlers(registry: CommandRegistry) -> None:
    """Register default command handlers."""
    
    async def handle_help(cmd: Command, ctx: dict) -> str:
        return registry.get_help(cmd.arg)
    
    async def handle_status(cmd: Command, ctx: dict) -> str:
        return "GigaBot is running."
    
    registry.register("help", handle_help, "Show available commands", ["?", "h"])
    registry.register("status", handle_status, "Show bot status")
