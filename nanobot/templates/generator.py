"""
Document generator for creating markdown documents from templates.

Uses Jinja2 for template rendering with auto-generated metadata.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.templates.registry import TemplateRegistry, get_template_registry


@dataclass
class GeneratedDocument:
    """A generated document."""
    
    name: str
    template_name: str
    content: str
    path: Path | None = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "template_name": self.template_name,
            "content": self.content,
            "path": str(self.path) if self.path else None,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


class DocumentGenerator:
    """
    Generator for creating documents from templates.
    
    Supports:
    - Jinja2-style template rendering
    - Auto-generated metadata (date, ID, etc.)
    - Automatic file saving with naming conventions
    """
    
    def __init__(
        self,
        registry: TemplateRegistry | None = None,
        output_dir: Path | None = None,
        auto_timestamp: bool = True,
    ):
        """
        Initialize the document generator.
        
        Args:
            registry: Template registry to use. Defaults to global registry.
            output_dir: Directory to save generated documents.
            auto_timestamp: Whether to auto-add timestamps to documents.
        """
        self.registry = registry or get_template_registry()
        self.output_dir = output_dir or Path("workspace/plans")
        self.auto_timestamp = auto_timestamp
        
        # Try to import Jinja2
        try:
            from jinja2 import Environment, BaseLoader, StrictUndefined
            self._jinja_env = Environment(
                loader=BaseLoader(),
                undefined=StrictUndefined,
                trim_blocks=True,
                lstrip_blocks=True,
            )
            self._has_jinja = True
        except ImportError:
            logger.warning("Jinja2 not installed. Using simple template substitution.")
            self._jinja_env = None
            self._has_jinja = False
    
    def generate(
        self,
        template_name: str,
        save: bool = True,
        filename: str | None = None,
        **field_values: Any,
    ) -> GeneratedDocument:
        """
        Generate a document from a template.
        
        Args:
            template_name: Name of the template to use.
            save: Whether to save the document to disk.
            filename: Custom filename (without extension). Auto-generated if not provided.
            **field_values: Values for template fields.
        
        Returns:
            GeneratedDocument with rendered content.
        
        Raises:
            ValueError: If template not found or required fields missing.
        """
        # Get template
        template = self.registry.get(template_name)
        if not template:
            available = ", ".join(self.registry.get_template_names())
            raise ValueError(
                f"Template '{template_name}' not found. Available: {available}"
            )
        
        # Validate required fields
        is_valid, missing = template.validate_fields(field_values)
        if not is_valid:
            raise ValueError(
                f"Missing required fields for '{template_name}': {', '.join(missing)}"
            )
        
        # Add auto-generated fields
        auto_fields = self._generate_auto_fields(template_name, field_values)
        all_fields = {**auto_fields, **field_values}
        
        # Render template
        content = self._render_template(template.content, all_fields)
        
        # Generate filename if not provided
        if filename is None:
            filename = self._generate_filename(template_name, field_values)
        
        # Create document object
        doc = GeneratedDocument(
            name=filename,
            template_name=template_name,
            content=content,
            metadata=all_fields,
        )
        
        # Save to disk
        if save:
            doc.path = self._save_document(doc)
        
        logger.info(f"Generated document: {filename} (template: {template_name})")
        return doc
    
    def _generate_auto_fields(
        self,
        template_name: str,
        field_values: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate automatic fields like date and ID."""
        auto = {}
        
        # Add date if not provided
        if "date" not in field_values and self.auto_timestamp:
            auto["date"] = datetime.now().strftime("%Y-%m-%d")
        
        # Add datetime if not provided
        if "datetime" not in field_values and self.auto_timestamp:
            auto["datetime"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Add document ID
        if "doc_id" not in field_values:
            auto["doc_id"] = str(uuid.uuid4())[:8]
        
        return auto
    
    def _render_template(self, content: str, fields: dict[str, Any]) -> str:
        """
        Render template content with field values.
        
        Args:
            content: Template content with placeholders.
            fields: Field values to substitute.
        
        Returns:
            Rendered content.
        """
        if self._has_jinja and self._jinja_env:
            return self._render_with_jinja(content, fields)
        else:
            return self._render_simple(content, fields)
    
    def _render_with_jinja(self, content: str, fields: dict[str, Any]) -> str:
        """Render using Jinja2."""
        try:
            template = self._jinja_env.from_string(content)
            return template.render(**fields)
        except Exception as e:
            logger.error(f"Jinja2 render error: {e}")
            # Fall back to simple rendering
            return self._render_simple(content, fields)
    
    def _render_simple(self, content: str, fields: dict[str, Any]) -> str:
        """
        Simple template rendering without Jinja2.
        
        Supports:
        - {{ field }} -> value
        - {{ field | default("value") }} -> value or default
        - {% for item in list %} ... {% endfor %} -> basic loop
        """
        result = content
        
        # Handle defaults: {{ field | default("value") }}
        default_pattern = r'\{\{\s*(\w+)\s*\|\s*default\s*\(\s*["\']([^"\']*)["\'\s*]\s*\)\s*\}\}'
        for match in re.finditer(default_pattern, result):
            field_name = match.group(1)
            default_value = match.group(2)
            value = fields.get(field_name, default_value)
            result = result.replace(match.group(0), str(value))
        
        # Handle simple for loops: {% for item in list %} ... {% endfor %}
        for_pattern = r'\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}'
        for match in re.finditer(for_pattern, result, re.DOTALL):
            item_name = match.group(1)
            list_name = match.group(2)
            body = match.group(3)
            
            items = fields.get(list_name, [])
            if not isinstance(items, list):
                items = [items]
            
            rendered_items = []
            for idx, item in enumerate(items, 1):
                item_result = body
                # Replace {{ item }} and {{ loop.index }}
                item_result = re.sub(
                    r'\{\{\s*' + item_name + r'\s*\}\}',
                    str(item),
                    item_result
                )
                item_result = re.sub(
                    r'\{\{\s*loop\.index\s*\}\}',
                    str(idx),
                    item_result
                )
                rendered_items.append(item_result.strip())
            
            result = result.replace(match.group(0), "\n".join(rendered_items))
        
        # Handle simple substitutions: {{ field }}
        simple_pattern = r'\{\{\s*(\w+)\s*\}\}'
        for match in re.finditer(simple_pattern, result):
            field_name = match.group(1)
            if field_name in fields:
                value = fields[field_name]
                # Handle lists
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                result = result.replace(match.group(0), str(value))
        
        return result
    
    def _generate_filename(
        self,
        template_name: str,
        field_values: dict[str, Any],
    ) -> str:
        """Generate a filename for the document."""
        parts = [template_name]
        
        # Add date
        if self.auto_timestamp:
            parts.append(datetime.now().strftime("%Y-%m-%d"))
        
        # Add identifier from common fields
        for key in ["task_name", "subject", "title", "name", "period"]:
            if key in field_values:
                # Slugify the value
                slug = self._slugify(str(field_values[key]))
                if slug:
                    parts.append(slug)
                    break
        
        return "_".join(parts)
    
    def _slugify(self, text: str) -> str:
        """Convert text to a URL-friendly slug."""
        # Convert to lowercase
        slug = text.lower()
        # Replace spaces and special chars with hyphens
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        # Remove leading/trailing hyphens
        slug = slug.strip("-")
        # Limit length
        return slug[:50]
    
    def _save_document(self, doc: GeneratedDocument) -> Path:
        """Save document to disk."""
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create full path
        path = self.output_dir / f"{doc.name}.md"
        
        # Handle conflicts
        if path.exists():
            base = doc.name
            counter = 1
            while path.exists():
                doc.name = f"{base}_{counter}"
                path = self.output_dir / f"{doc.name}.md"
                counter += 1
        
        # Write content
        path.write_text(doc.content, encoding="utf-8")
        logger.debug(f"Saved document to: {path}")
        
        return path
    
    def list_generated(self) -> list[Path]:
        """List all generated documents in the output directory."""
        if not self.output_dir.exists():
            return []
        return sorted(self.output_dir.glob("*.md"))
    
    def preview(
        self,
        template_name: str,
        **field_values: Any,
    ) -> str:
        """
        Preview a document without saving.
        
        Args:
            template_name: Name of the template.
            **field_values: Field values.
        
        Returns:
            Rendered content preview.
        """
        doc = self.generate(template_name, save=False, **field_values)
        return doc.content


# Global generator instance
_generator: DocumentGenerator | None = None


def get_document_generator(
    output_dir: Path | None = None,
) -> DocumentGenerator:
    """Get the global document generator instance."""
    global _generator
    if _generator is None:
        _generator = DocumentGenerator(output_dir=output_dir)
    return _generator
