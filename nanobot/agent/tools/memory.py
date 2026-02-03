"""
Memory tool for GigaBot agent.

Wraps the enhanced memory system's MemoryTool for use in the agent loop.
"""

from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool


class MemoryToolWrapper(Tool):
    """
    Tool wrapper for memory operations.
    
    Allows agents to explicitly search, store, and retrieve memories
    using the enhanced memory system with semantic search.
    """
    
    def __init__(self, workspace: Path):
        """
        Initialize the memory tool.
        
        Args:
            workspace: Path to the workspace directory.
        """
        self.workspace = workspace
        self._memory_tool = None  # Lazy initialization
    
    def _get_memory_tool(self):
        """Get or create the underlying memory tool."""
        if self._memory_tool is None:
            from nanobot.memory.search import MemoryTool
            self._memory_tool = MemoryTool(self.workspace)
        return self._memory_tool
    
    @property
    def name(self) -> str:
        return "memory"
    
    @property
    def description(self) -> str:
        return """Search and manage persistent memories.

Actions:
- search: Semantically search memories using a query
- add_daily: Add a memory to today's daily notes
- add_long_term: Add an important memory to long-term storage
- get_recent: Get memories from recent days

Use this tool to:
- Remember important information about the user or project
- Recall past conversations or decisions
- Store facts that should persist across sessions

Examples:
- Search: {"action": "search", "query": "user preferences for code style"}
- Add daily: {"action": "add_daily", "content": "User requested dark mode theme"}
- Add long-term: {"action": "add_long_term", "content": "User is a Python developer", "section": "User Info"}
- Get recent: {"action": "get_recent", "days": 3}"""
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "add_daily", "add_long_term", "get_recent"],
                    "description": "The memory action to perform"
                },
                "query": {
                    "type": "string",
                    "description": "Search query for search action (uses semantic matching)"
                },
                "content": {
                    "type": "string",
                    "description": "Content to store for add actions"
                },
                "section": {
                    "type": "string",
                    "description": "Section name for organizing long-term memories (e.g., 'User Info', 'Project Notes')"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back for get_recent action",
                    "default": 7
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Execute the memory action."""
        memory_tool = self._get_memory_tool()
        return await memory_tool.execute(**kwargs)
