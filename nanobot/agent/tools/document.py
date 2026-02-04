"""
Document generation tool for creating structured markdown documents.

Enables agents to generate documents from templates for:
- Surgical Plans (code modification instructions)
- Status Reports
- Analysis Documents
- Task Summaries
"""

import json
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool


class DocumentGeneratorTool(Tool):
    """
    Tool for generating structured markdown documents from templates.
    
    This tool allows agents to create well-formatted documents
    that can be used to communicate with other agents (like Claude Code)
    or to document work.
    """
    
    def __init__(self, output_dir: Path | str | None = None):
        """
        Initialize the document generator tool.
        
        Args:
            output_dir: Directory to save generated documents.
                       Defaults to workspace/plans/
        """
        self._output_dir = Path(output_dir) if output_dir else None
        self._generator = None
        self._registry = None
    
    def _ensure_initialized(self) -> None:
        """Lazy initialization of generator and registry."""
        if self._generator is None:
            from nanobot.templates import (
                get_document_generator,
                get_template_registry,
            )
            self._registry = get_template_registry()
            self._generator = get_document_generator(output_dir=self._output_dir)
    
    @property
    def name(self) -> str:
        return "generate_document"
    
    @property
    def description(self) -> str:
        return """Generate a structured markdown document from a template.

Available templates:
- surgical_plan: Code modification instructions for Claude Code
  Required: task_name, diagnosis, files (list), steps (list)
  Optional: surgeon, chief, test_criteria, rollback_plan, priority

- status_report: Periodic project status updates
  Required: period, completed (list)
  Optional: in_progress (list), blockers (list), next_steps (list), highlights

- analysis: Code or system analysis document
  Required: subject, findings
  Optional: recommendations (list), affected_components (list), severity

- task_summary: Completed task documentation
  Required: task, outcome
  Optional: approach, files_changed (list), lessons_learned, follow_up_items (list)

Example for surgical_plan:
{
    "template": "surgical_plan",
    "task_name": "Fix Authentication Bug",
    "diagnosis": "JWT tokens are expiring prematurely due to incorrect timezone handling",
    "files": ["nanobot/auth/jwt.py", "nanobot/auth/service.py"],
    "steps": [
        "Update JWT token creation to use UTC timestamps",
        "Add timezone conversion in token validation",
        "Update tests to verify timezone handling"
    ],
    "test_criteria": "Run pytest tests/test_auth.py - all must pass"
}
"""
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "template": {
                    "type": "string",
                    "description": "Template name: surgical_plan, status_report, analysis, or task_summary",
                    "enum": ["surgical_plan", "status_report", "analysis", "task_summary"],
                },
                "save": {
                    "type": "boolean",
                    "description": "Whether to save the document to disk (default: true)",
                    "default": True,
                },
                "filename": {
                    "type": "string",
                    "description": "Custom filename (without .md extension). Auto-generated if not provided.",
                },
                # Surgical Plan fields
                "task_name": {
                    "type": "string",
                    "description": "Name of the task (for surgical_plan)",
                },
                "diagnosis": {
                    "type": "string",
                    "description": "Problem description (for surgical_plan, analysis)",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of files to modify (for surgical_plan)",
                },
                "steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Procedure steps (for surgical_plan)",
                },
                "test_criteria": {
                    "type": "string",
                    "description": "Test requirements (for surgical_plan)",
                },
                "rollback_plan": {
                    "type": "string",
                    "description": "Rollback instructions (for surgical_plan)",
                },
                "surgeon": {
                    "type": "string",
                    "description": "Who will execute the plan (default: Claude Code)",
                },
                "chief": {
                    "type": "string",
                    "description": "Who created the plan (default: GigaBot)",
                },
                "priority": {
                    "type": "string",
                    "description": "Priority level: Low, Normal, High, Critical",
                },
                # Status Report fields
                "period": {
                    "type": "string",
                    "description": "Report period (for status_report)",
                },
                "completed": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Completed items (for status_report)",
                },
                "in_progress": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Items in progress (for status_report)",
                },
                "blockers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Current blockers (for status_report)",
                },
                "next_steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Next steps (for status_report)",
                },
                # Analysis fields
                "subject": {
                    "type": "string",
                    "description": "Subject of analysis (for analysis)",
                },
                "findings": {
                    "type": "string",
                    "description": "Analysis findings (for analysis)",
                },
                "recommendations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Recommendations (for analysis)",
                },
                "affected_components": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Affected components (for analysis)",
                },
                "severity": {
                    "type": "string",
                    "description": "Severity: Informational, Low, Medium, High, Critical",
                },
                # Task Summary fields
                "task": {
                    "type": "string",
                    "description": "Task description (for task_summary)",
                },
                "outcome": {
                    "type": "string",
                    "description": "Task outcome (for task_summary)",
                },
                "approach": {
                    "type": "string",
                    "description": "Approach taken (for task_summary)",
                },
                "files_changed": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files changed (for task_summary)",
                },
                "lessons_learned": {
                    "type": "string",
                    "description": "Lessons learned (for task_summary)",
                },
                "follow_up_items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Follow-up items (for task_summary)",
                },
            },
            "required": ["template"],
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """
        Generate a document from a template.
        
        Args:
            **kwargs: Template name and field values.
        
        Returns:
            Success message with path, or error message.
        """
        self._ensure_initialized()
        
        template_name = kwargs.pop("template", None)
        if not template_name:
            return "Error: 'template' is required. Available: surgical_plan, status_report, analysis, task_summary"
        
        save = kwargs.pop("save", True)
        filename = kwargs.pop("filename", None)
        
        # Filter out None values
        field_values = {k: v for k, v in kwargs.items() if v is not None}
        
        try:
            doc = self._generator.generate(
                template_name=template_name,
                save=save,
                filename=filename,
                **field_values,
            )
            
            if save and doc.path:
                return f"Document generated successfully.\n\nPath: {doc.path}\n\nPreview (first 500 chars):\n{doc.content[:500]}..."
            else:
                return f"Document preview:\n\n{doc.content}"
                
        except ValueError as e:
            return f"Error generating document: {e}"
        except Exception as e:
            return f"Unexpected error: {e}"


class ListTemplatesToolTool(Tool):
    """Tool to list available document templates."""
    
    @property
    def name(self) -> str:
        return "list_document_templates"
    
    @property
    def description(self) -> str:
        return "List all available document templates with their descriptions and required fields."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """List available templates."""
        from nanobot.templates import get_template_registry
        
        registry = get_template_registry()
        return registry.get_template_summary()
