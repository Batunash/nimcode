import os
import ast
import logging

logger = logging.getLogger(__name__)

class RepoMapper:
    def __init__(self, root_dir="."):
        self.root_dir = os.path.abspath(root_dir)
        self.exclude_dirs = {".git", ".nimcode", "__pycache__", "venv", "env", "node_modules", "tests"}

    def _parse_python_file(self, filepath: str) -> str:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content)
            
            lines = []
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    lines.append(f"  class {node.name}:")
                    for child in node.body:
                        if isinstance(child, ast.FunctionDef):
                            lines.append(f"    def {child.name}(...)")
                elif isinstance(node, ast.FunctionDef):
                    lines.append(f"  def {node.name}(...)")
            
            if lines:
                return "\n".join(lines)
            return "  (No classes or top-level functions)"
        except SyntaxError:
            return "  (Syntax Error)"
        except Exception as e:
            return f"  (Error reading file: {e})"

    def generate_map(self) -> str:
        map_lines = []
        map_lines.append(f"Repository Map for: {self.root_dir}\n")
        
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.root_dir)
                    map_lines.append(f"FILE: {rel_path}")
                    
                    file_map = self._parse_python_file(full_path)
                    map_lines.append(file_map)
                    map_lines.append("")
                    
        return "\n".join(map_lines)
