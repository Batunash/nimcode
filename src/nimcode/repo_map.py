"""
Lightweight repository mapper.
Generates a tree-style overview of the project structure.
Used by watcher.py for Live Sync updates.
"""
import os
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Directories to always skip
IGNORE_DIRS = {
    ".git", ".nimcode", "__pycache__", "node_modules", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build", ".egg-info",
    ".idea", ".vscode", "env", ".env",
}

# File extensions to include in the map
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".rb",
    ".c", ".cpp", ".h", ".cs", ".php", ".swift", ".kt", ".scala",
    ".html", ".css", ".scss", ".vue", ".svelte",
    ".json", ".yaml", ".yml", ".toml", ".md", ".txt",
    ".sql", ".sh", ".bat", ".ps1", ".dockerfile",
}

MAX_FILES = 500  # Safety limit


class RepoMapper:
    def __init__(self, root_dir: str, max_depth: int = 6):
        self.root_dir = os.path.abspath(root_dir)
        self.max_depth = max_depth
        self._file_count = 0

    def generate_map(self) -> str:
        """Generates a tree-style string of the repository structure."""
        self._file_count = 0
        lines = [f"📁 {os.path.basename(self.root_dir)}/"]
        self._walk(self.root_dir, lines, prefix="", depth=0)
        
        if self._file_count >= MAX_FILES:
            lines.append(f"\n... (truncated at {MAX_FILES} files)")
        
        return "\n".join(lines)

    def _walk(self, directory: str, lines: List[str], prefix: str, depth: int) -> None:
        if depth >= self.max_depth or self._file_count >= MAX_FILES:
            return

        try:
            entries = sorted(os.listdir(directory))
        except PermissionError:
            return

        # Separate dirs and files
        dirs = []
        files = []
        for entry in entries:
            full_path = os.path.join(directory, entry)
            if os.path.isdir(full_path):
                if entry not in IGNORE_DIRS and not entry.startswith("."):
                    dirs.append(entry)
            else:
                ext = os.path.splitext(entry)[1].lower()
                if ext in CODE_EXTENSIONS or entry in {"Makefile", "Dockerfile", "Procfile", ".gitignore"}:
                    files.append(entry)

        all_entries = dirs + files
        for i, entry in enumerate(all_entries):
            is_last = (i == len(all_entries) - 1)
            connector = "└── " if is_last else "├── "
            
            full_path = os.path.join(directory, entry)
            
            if entry in dirs:
                lines.append(f"{prefix}{connector}📁 {entry}/")
                extension = "    " if is_last else "│   "
                self._walk(full_path, lines, prefix + extension, depth + 1)
            else:
                self._file_count += 1
                if self._file_count > MAX_FILES:
                    return
                size = os.path.getsize(full_path)
                size_str = _format_size(size)
                lines.append(f"{prefix}{connector}{entry} ({size_str})")
                
                # Context extraction
                symbols = _extract_symbols(full_path)
                if symbols:
                    sym_prefix = prefix + ("    " if is_last else "│   ")
                    for s_idx, sym in enumerate(symbols):
                        sym_conn = "└── " if s_idx == len(symbols) - 1 else "├── "
                        lines.append(f"{sym_prefix}{sym_conn}[dim]{sym}[/dim]")

def _format_size(size_bytes: int) -> str:
    """Formats file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"

import ast
import re
from typing import List

def _extract_symbols(file_path: str) -> List[str]:
    """Extracts classes and functions from code files for better LLM context."""
    symbols = []
    ext = os.path.splitext(file_path)[1].lower()
    
    if os.path.getsize(file_path) > 500 * 1024:
        return symbols # Skip huge files
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        if ext == ".py":
            try:
                tree = ast.parse(content)
                for node in tree.body:
                    if isinstance(node, ast.ClassDef):
                        symbols.append(f"class {node.name}")
                    elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                        symbols.append(f"def {node.name}()")
            except SyntaxError:
                pass
        elif ext in [".js", ".ts", ".jsx", ".tsx", ".rs", ".go"]:
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if not line: continue
                
                # Rust
                if ext == ".rs":
                    match = re.match(r'^(?:pub\s+)?(?:async\s+)?(?:fn|struct|enum|trait)\s+([a-zA-Z0-9_]+)', line)
                    if match: symbols.append(f"⚙️ {match.group(1)}")
                # JS/TS
                elif ext in [".js", ".ts", ".jsx", ".tsx"]:
                    match = re.match(r'^(?:export\s+)?(?:async\s+)?(?:function|class|interface|type)\s+([a-zA-Z0-9_]+)', line)
                    if match: symbols.append(f"🔹 {match.group(1)}")
                    match_const = re.match(r'^(?:export\s+)?const\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?\(', line)
                    if match_const: symbols.append(f"🔹 {match_const.group(1)}")
                # Go
                elif ext == ".go":
                    match = re.match(r'^func\s+(?:\[.*\]\s+)?(?:\([a-zA-Z0-9_\s*]+\)\s+)?([a-zA-Z0-9_]+)', line)
                    if match: symbols.append(f"🔸 {match.group(1)}")
                    match_type = re.match(r'^type\s+([a-zA-Z0-9_]+)\s+(?:struct|interface)', line)
                    if match_type: symbols.append(f"🔸 {match_type.group(1)}")
                    
    except Exception as e:
        logger.debug(f"Failed to extract symbols from {file_path}: {e}")
        
    # Cap symbols to avoid blowing up context
    if len(symbols) > 15:
        symbols = symbols[:15] + ["... (more)"]
    return symbols
