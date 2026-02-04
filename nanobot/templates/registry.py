"""
Template registry for document generation.

Loads and manages document templates from the templates/documents/ directory.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class DocumentTemplate:
    """A document template definition."""
    
    name: str
    description: str
    required_fields: list[str] = field(default_factory=list)
    optional_fields: list[str] = field(default_factory=list)
    content: str = ""
    path: Path | None = None
    
    def validate_fields(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate that all required fields are present in the data.
        
        Args:
            data: The field values to validate.
        
        Returns:
            Tuple of (is_valid, missing_fields).
        """
        missing = [f for f in self.required_fields if f not in data]
        return len(missing) == 0, missing
    
    def get_all_fields(self) -> list[str]:
        """Get all fields (required + optional)."""
        return self.required_fields + self.optional_fields


class TemplateRegistry:
    """
    Registry for document templates.
    
    Loads templates from the documents/ subdirectory and provides
    access to them by name.
    """
    
    def __init__(self, templates_dir: Path | None = None):
        """
        Initialize the template registry.
        
        Args:
            templates_dir: Path to templates directory. Defaults to 
                          nanobot/templates/documents/
        """
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "documents"
        
        self.templates_dir = templates_dir
        self._templates: dict[str, DocumentTemplate] = {}
        self._loaded = False
    
    def load(self, force: bool = False) -> None:
        """
        Load all templates from the templates directory.
        
        Args:
            force: If True, reload even if already loaded.
        """
        if self._loaded and not force:
            return
        
        self._templates.clear()
        
        if not self.templates_dir.exists():
            logger.warning(f"Templates directory not found: {self.templates_dir}")
            self._loaded = True
            return
        
        for template_file in self.templates_dir.glob("*.md"):
            try:
                template = self._load_template_file(template_file)
                if template:
                    self._templates[template.name] = template
                    logger.debug(f"Loaded template: {template.name}")
            except Exception as e:
                logger.error(f"Failed to load template {template_file}: {e}")
        
        self._loaded = True
        logger.info(f"Loaded {len(self._templates)} document templates")
    
    def _load_template_file(self, path: Path) -> DocumentTemplate | None:
        """
        Load a single template file.
        
        Args:
            path: Path to the template file.
        
        Returns:
            DocumentTemplate or None if parsing fails.
        """
        content = path.read_text(encoding="utf-8")
        
        # Parse YAML frontmatter
        frontmatter, body = self._parse_frontmatter(content)
        
        if not frontmatter:
            logger.warning(f"Template {path.name} has no frontmatter")
            return None
        
        name = frontmatter.get("name", path.stem)
        description = frontmatter.get("description", "")
        required_fields = frontmatter.get("required_fields", [])
        optional_fields = frontmatter.get("optional_fields", [])
        
        # Ensure fields are lists
        if isinstance(required_fields, str):
            required_fields = [required_fields]
        if isinstance(optional_fields, str):
            optional_fields = [optional_fields]
        
        return DocumentTemplate(
            name=name,
            description=description,
            required_fields=required_fields,
            optional_fields=optional_fields,
            content=body,
            path=path,
        )
    
    def _parse_frontmatter(self, content: str) -> tuple[dict[str, Any], str]:
        """
        Parse YAML frontmatter from markdown content.
        
        Args:
            content: Full markdown content with frontmatter.
        
        Returns:
            Tuple of (frontmatter_dict, body_content).
        """
        if not content.startswith("---"):
            return {}, content
        
        # Find the closing ---
        match = re.match(r"^---\n(.*?)\n---\n?", content, re.DOTALL)
        if not match:
            return {}, content
        
        frontmatter_text = match.group(1)
        body = content[match.end():]
        
        # Simple YAML parsing (supports basic key: value and lists)
        frontmatter: dict[str, Any] = {}
        current_key = None
        current_list: list[str] = []
        
        for line in frontmatter_text.split("\n"):
            line = line.rstrip()
            
            # Check if it's a list item
            if line.startswith("  - "):
                if current_key:
                    current_list.append(line[4:].strip())
                continue
            
            # Save previous list if any
            if current_key and current_list:
                frontmatter[current_key] = current_list
                current_list = []
            
            # Parse key: value
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                
                if value:
                    # Handle quoted strings
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    frontmatter[key] = value
                else:
                    # Value on next lines (probably a list)
                    current_key = key
        
        # Save final list if any
        if current_key and current_list:
            frontmatter[current_key] = current_list
        
        return frontmatter, body.strip()
    
    def get(self, name: str) -> DocumentTemplate | None:
        """
        Get a template by name.
        
        Args:
            name: Template name.
        
        Returns:
            DocumentTemplate or None if not found.
        """
        self.load()
        return self._templates.get(name)
    
    def list_templates(self) -> list[DocumentTemplate]:
        """
        List all available templates.
        
        Returns:
            List of DocumentTemplate objects.
        """
        self.load()
        return list(self._templates.values())
    
    def get_template_names(self) -> list[str]:
        """
        Get names of all available templates.
        
        Returns:
            List of template names.
        """
        self.load()
        return list(self._templates.keys())
    
    def get_template_summary(self) -> str:
        """
        Get a formatted summary of all templates.
        
        Returns:
            Formatted string listing all templates with descriptions.
        """
        self.load()
        
        if not self._templates:
            return "No templates available."
        
        lines = ["Available templates:", ""]
        for template in self._templates.values():
            lines.append(f"- **{template.name}**: {template.description}")
            if template.required_fields:
                lines.append(f"  Required: {', '.join(template.required_fields)}")
        
        return "\n".join(lines)


# Global registry instance
_registry: TemplateRegistry | None = None


def get_template_registry() -> TemplateRegistry:
    """Get the global template registry instance."""
    global _registry
    if _registry is None:
        _registry = TemplateRegistry()
    return _registry
