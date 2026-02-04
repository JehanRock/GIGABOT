"""Agent tools module."""

from nanobot.agent.tools.base import Tool, BaseTool, ToolResult
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.dashboard import DashboardTool, DASHBOARD_TOOL_SCHEMA
from nanobot.agent.tools.document import DocumentGeneratorTool, ListTemplatesToolTool

__all__ = [
    "Tool",
    "BaseTool",
    "ToolResult",
    "ToolRegistry",
    "DashboardTool",
    "DASHBOARD_TOOL_SCHEMA",
    "DocumentGeneratorTool",
    "ListTemplatesToolTool",
]
