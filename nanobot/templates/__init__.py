"""
Document template system for GigaBot.

Provides template-based document generation for:
- Surgical Plans (code modification instructions)
- Status Reports
- Analysis Documents
- Task Summaries
"""

from nanobot.templates.registry import (
    DocumentTemplate,
    TemplateRegistry,
    get_template_registry,
)
from nanobot.templates.generator import (
    DocumentGenerator,
    GeneratedDocument,
    get_document_generator,
)

__all__ = [
    "DocumentTemplate",
    "TemplateRegistry",
    "get_template_registry",
    "DocumentGenerator",
    "GeneratedDocument",
    "get_document_generator",
]
