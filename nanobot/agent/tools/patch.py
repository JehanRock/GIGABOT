"""
Multi-file patch tool for GigaBot.

Provides atomic multi-file changes:
- Apply patches across multiple files
- Unified diff format support
- Rollback on failure
"""

import os
import re
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

from nanobot.agent.tools.base import BaseTool


@dataclass
class FilePatch:
    """A patch for a single file."""
    path: str
    hunks: list[dict[str, Any]] = field(default_factory=list)
    is_new: bool = False
    is_delete: bool = False
    original_content: str = ""  # For rollback


@dataclass
class PatchResult:
    """Result of applying a patch."""
    success: bool
    message: str
    files_modified: list[str] = field(default_factory=list)
    files_created: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class PatchTool(BaseTool):
    """
    Multi-file patch tool.
    
    Supports:
    - Applying unified diff patches
    - Creating new files
    - Deleting files
    - Atomic operations with rollback
    """
    
    name = "apply_patch"
    description = """Apply multi-file patches atomically.
    
The patch format is a simplified unified diff:

```
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -10,5 +10,6 @@
 context line
-removed line
+added line
 context line
```

For new files, use:
```
--- /dev/null
+++ b/path/to/newfile.py
@@ -0,0 +1,5 @@
+line 1
+line 2
```

For file deletion, use:
```
--- a/path/to/file.py
+++ /dev/null
```
"""
    
    parameters = {
        "type": "object",
        "properties": {
            "patch": {
                "type": "string",
                "description": "The patch content in unified diff format"
            },
            "dry_run": {
                "type": "boolean",
                "description": "If true, validate without applying",
                "default": False
            },
            "base_path": {
                "type": "string",
                "description": "Base path for relative file paths"
            }
        },
        "required": ["patch"]
    }
    
    def __init__(self, workspace: str = ""):
        self.workspace = workspace
    
    async def execute(self, **kwargs: Any) -> str:
        """Execute patch application."""
        patch_content = kwargs.get("patch", "")
        dry_run = kwargs.get("dry_run", False)
        base_path = kwargs.get("base_path", self.workspace)
        
        if not patch_content:
            return "Error: Patch content required"
        
        try:
            # Parse the patch
            patches = self._parse_patch(patch_content)
            
            if not patches:
                return "Error: No valid patches found in input"
            
            # Validate all patches first
            for patch in patches:
                error = self._validate_patch(patch, base_path)
                if error:
                    return f"Validation error: {error}"
            
            if dry_run:
                files = [p.path for p in patches]
                return f"Dry run successful. Would modify {len(patches)} files: {', '.join(files)}"
            
            # Apply patches
            result = self._apply_patches(patches, base_path)
            
            return self._format_result(result)
            
        except Exception as e:
            return f"Patch error: {str(e)}"
    
    def _parse_patch(self, content: str) -> list[FilePatch]:
        """Parse unified diff format into FilePatch objects."""
        patches = []
        current_patch = None
        current_hunk = None
        
        lines = content.split("\n")
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # New file header
            if line.startswith("--- "):
                if current_patch:
                    if current_hunk:
                        current_patch.hunks.append(current_hunk)
                    patches.append(current_patch)
                
                old_path = self._extract_path(line[4:])
                
                # Get new path from next line
                if i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
                    new_path = self._extract_path(lines[i + 1][4:])
                    i += 1
                else:
                    new_path = old_path
                
                current_patch = FilePatch(
                    path=new_path if new_path != "/dev/null" else old_path,
                    is_new=(old_path == "/dev/null"),
                    is_delete=(new_path == "/dev/null"),
                )
                current_hunk = None
            
            # Hunk header
            elif line.startswith("@@") and current_patch:
                if current_hunk:
                    current_patch.hunks.append(current_hunk)
                
                # Parse hunk header: @@ -start,count +start,count @@
                match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
                if match:
                    current_hunk = {
                        "old_start": int(match.group(1)),
                        "old_count": int(match.group(2) or 1),
                        "new_start": int(match.group(3)),
                        "new_count": int(match.group(4) or 1),
                        "lines": [],
                    }
            
            # Hunk content
            elif current_hunk is not None:
                if line.startswith("+") or line.startswith("-") or line.startswith(" "):
                    current_hunk["lines"].append(line)
                elif line.strip() == "":
                    # Empty context line
                    current_hunk["lines"].append(" ")
            
            i += 1
        
        # Don't forget the last patch
        if current_patch:
            if current_hunk:
                current_patch.hunks.append(current_hunk)
            patches.append(current_patch)
        
        return patches
    
    def _extract_path(self, path_str: str) -> str:
        """Extract clean path from diff path string."""
        path_str = path_str.strip()
        
        # Remove a/ or b/ prefix
        if path_str.startswith("a/") or path_str.startswith("b/"):
            path_str = path_str[2:]
        
        return path_str
    
    def _validate_patch(self, patch: FilePatch, base_path: str) -> str | None:
        """Validate a patch can be applied. Returns error message or None."""
        full_path = Path(base_path) / patch.path if base_path else Path(patch.path)
        
        if patch.is_new:
            if full_path.exists():
                return f"File already exists: {patch.path}"
            # Check parent directory exists
            if not full_path.parent.exists():
                return f"Parent directory does not exist: {full_path.parent}"
        
        elif patch.is_delete:
            if not full_path.exists():
                return f"File to delete does not exist: {patch.path}"
        
        else:
            if not full_path.exists():
                return f"File to patch does not exist: {patch.path}"
        
        return None
    
    def _apply_patches(self, patches: list[FilePatch], base_path: str) -> PatchResult:
        """Apply all patches with rollback on failure."""
        result = PatchResult(success=True, message="")
        applied_patches: list[FilePatch] = []
        
        try:
            for patch in patches:
                full_path = Path(base_path) / patch.path if base_path else Path(patch.path)
                
                # Store original for rollback
                if full_path.exists():
                    patch.original_content = full_path.read_text()
                
                if patch.is_new:
                    self._create_file(full_path, patch)
                    result.files_created.append(patch.path)
                
                elif patch.is_delete:
                    full_path.unlink()
                    result.files_deleted.append(patch.path)
                
                else:
                    self._apply_hunks(full_path, patch)
                    result.files_modified.append(patch.path)
                
                applied_patches.append(patch)
            
            total = len(result.files_modified) + len(result.files_created) + len(result.files_deleted)
            result.message = f"Successfully applied {total} file changes"
            
        except Exception as e:
            # Rollback
            result.success = False
            result.message = f"Failed to apply patch: {str(e)}"
            result.errors.append(str(e))
            
            self._rollback(applied_patches, base_path)
        
        return result
    
    def _create_file(self, path: Path, patch: FilePatch) -> None:
        """Create a new file from patch."""
        lines = []
        for hunk in patch.hunks:
            for line in hunk["lines"]:
                if line.startswith("+"):
                    lines.append(line[1:])
        
        path.write_text("\n".join(lines))
    
    def _apply_hunks(self, path: Path, patch: FilePatch) -> None:
        """Apply hunks to existing file."""
        content = path.read_text()
        lines = content.split("\n")
        
        # Apply hunks in reverse order (to preserve line numbers)
        for hunk in reversed(patch.hunks):
            old_start = hunk["old_start"] - 1  # 0-indexed
            
            # Build new lines for this section
            new_lines = []
            for line in hunk["lines"]:
                if line.startswith("+"):
                    new_lines.append(line[1:])
                elif line.startswith(" "):
                    new_lines.append(line[1:])
                # Skip lines starting with "-"
            
            # Replace the old section
            old_count = hunk["old_count"]
            lines[old_start:old_start + old_count] = new_lines
        
        path.write_text("\n".join(lines))
    
    def _rollback(self, patches: list[FilePatch], base_path: str) -> None:
        """Rollback applied patches."""
        for patch in reversed(patches):
            full_path = Path(base_path) / patch.path if base_path else Path(patch.path)
            
            try:
                if patch.is_new and full_path.exists():
                    full_path.unlink()
                elif patch.is_delete and patch.original_content:
                    full_path.write_text(patch.original_content)
                elif patch.original_content:
                    full_path.write_text(patch.original_content)
            except Exception:
                pass  # Best effort rollback
    
    def _format_result(self, result: PatchResult) -> str:
        """Format patch result for output."""
        lines = [result.message, ""]
        
        if result.files_created:
            lines.append(f"Created: {', '.join(result.files_created)}")
        if result.files_modified:
            lines.append(f"Modified: {', '.join(result.files_modified)}")
        if result.files_deleted:
            lines.append(f"Deleted: {', '.join(result.files_deleted)}")
        
        if result.errors:
            lines.append("")
            lines.append("Errors:")
            for error in result.errors:
                lines.append(f"  - {error}")
        
        return "\n".join(lines)
