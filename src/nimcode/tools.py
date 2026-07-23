import os
import subprocess
import glob
import re
import shlex
from typing import Dict, Any, List, Optional

class ToolError(Exception):
    pass

class ToolRegistry:
    @staticmethod
    def get_tool_schema(tool_name: str) -> Optional[Dict[str, Any]]:
        schemas = {
            "Bash": {
                "description": "Execute a shell command. Use this for running tests, git commands, etc.",
                "parameters": {
                    "command": {"type": "string", "description": "The shell command to execute."}
                },
                "required": ["command"]
            },
            "Read": {
                "description": "Read the contents of a file.",
                "parameters": {
                    "file_path": {"type": "string", "description": "Path to the file to read."}
                },
                "required": ["file_path"]
            },
            "Write": {
                "description": "Create a new file or completely overwrite an existing one.",
                "parameters": {
                    "file_path": {"type": "string", "description": "Path to the file."},
                    "content": {"type": "string", "description": "Full new content of the file."}
                },
                "required": ["file_path", "content"]
            },
            "Edit": {
                "description": "Edit an existing file by replacing an exact string. old_string must be unique.",
                "parameters": {
                    "file_path": {"type": "string", "description": "Path to the file."},
                    "old_string": {"type": "string", "description": "The exact string to replace, including whitespaces."},
                    "new_string": {"type": "string", "description": "The string to replace it with."}
                },
                "required": ["file_path", "old_string", "new_string"]
            },
            "ReadArchitecture": {
                "description": "Output a fast folder tree to understand project structure.",
                "parameters": {
                    "directory": {"type": "string", "description": "Directory to scan (default: '.')"}
                },
                "required": []
            },
            "SymbolSearch": {
                "description": "Search for a class or function definition across the codebase.",
                "parameters": {
                    "symbol_name": {"type": "string", "description": "The exact name of the class or function to find."},
                    "directory": {"type": "string", "description": "Directory to search in."}
                },
                "required": ["symbol_name", "directory"]
            },
            "Glob": {
                "description": "Find files by pattern.",
                "parameters": {
                    "pattern": {"type": "string", "description": "Glob pattern (e.g., src/**/*.py)"}
                },
                "required": ["pattern"]
            },
            "Grep": {
                "description": "Search for text inside files.",
                "parameters": {
                    "query": {"type": "string", "description": "The text or regex to search for."},
                    "directory": {"type": "string", "description": "Directory to search in."}
                },
                "required": ["query", "directory"]
            }
        }
        return schemas.get(tool_name)

    @classmethod
    def validate_tool_call(cls, tool_call: Dict[str, Any]) -> None:
        """Validates tool name and required arguments."""
        if not isinstance(tool_call, dict):
            raise ValueError("Tool call must be a dictionary.")
        
        tool_name = tool_call.get("tool")
        if not tool_name:
            raise ValueError("Missing 'tool' key in tool call.")
            
        args = tool_call.get("args", {})
        if not isinstance(args, dict):
            raise ValueError("'args' must be a dictionary.")
            
        schema = cls.get_tool_schema(tool_name)
        if not schema:
            raise ValueError(f"Unknown tool: '{tool_name}'")
            
        for req in schema.get("required", []):
            if req not in args:
                raise ValueError(f"Tool '{tool_name}' missing required argument '{req}'")

    @classmethod
    def execute(cls, tool_call: Dict[str, Any], cwd: str = ".") -> str:
        """Executes the tool call and returns the output as a string."""
        cls.validate_tool_call(tool_call)
        
        tool_name = tool_call["tool"]
        args = tool_call["args"]
        
        try:
            if tool_name == "Bash":
                return cls._execute_bash(args["command"], cwd)
            elif tool_name == "Read":
                return cls._execute_read(args["file_path"], cwd)
            elif tool_name == "Write":
                return cls._execute_write(args["file_path"], args["content"], cwd)
            elif tool_name == "Edit":
                return cls._execute_edit(args["file_path"], args["old_string"], args["new_string"], cwd)
            elif tool_name == "Glob":
                return cls._execute_glob(args["pattern"], cwd)
            elif tool_name == "Grep":
                return cls._execute_grep(args["query"], args["directory"], cwd)
            elif tool_name == "ReadArchitecture":
                return cls._execute_read_architecture(args.get("directory", "."), cwd)
            elif tool_name == "SymbolSearch":
                return cls._execute_symbol_search(args["symbol_name"], args["directory"], cwd)
            else:
                raise ToolError(f"Tool {tool_name} is registered but execution is not implemented.")
        except Exception as e:
            if isinstance(e, ToolError):
                return f"ToolError: {str(e)}"
            return f"Error executing {tool_name}: {str(e)}"

    @staticmethod
    def _execute_bash(command: str, cwd: str) -> str:
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120
            )
            out = result.stdout + "\n" + result.stderr
            out = out.strip()
            
            # Truncate if too long (simulating context limit protection)
            if len(out) > 10000:
                out = out[:5000] + f"\n...[TRUNCATED {len(out) - 10000} characters]...\n" + out[-5000:]
            
            return out if out else "Command executed successfully with no output."
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 120 seconds."
        except Exception as e:
            return f"Error running bash: {e}"

    _FILE_CACHE = {}

    @staticmethod
    def _execute_read(file_path: str, cwd: str) -> str:
        full_path = os.path.join(cwd, file_path)
        if not os.path.exists(full_path):
            raise ToolError(f"File not found: {file_path}")
        if os.path.isdir(full_path):
            raise ToolError(f"Path is a directory, not a file: {file_path}")
            
        mtime = os.path.getmtime(full_path)
        if full_path in ToolRegistry._FILE_CACHE:
            cached_mtime, cached_content = ToolRegistry._FILE_CACHE[full_path]
            if cached_mtime == mtime:
                return cached_content
                
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
            ToolRegistry._FILE_CACHE[full_path] = (mtime, content)
            return content

    @staticmethod
    def _execute_write(file_path: str, content: str, cwd: str) -> str:
        full_path = os.path.join(cwd, file_path)
        os.makedirs(os.path.dirname(os.path.abspath(full_path)) or ".", exist_ok=True)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"

    @staticmethod
    def _execute_edit(file_path: str, old_string: str, new_string: str, cwd: str) -> str:
        full_path = os.path.join(cwd, file_path)
        if not os.path.exists(full_path):
            raise ToolError(f"File not found: {file_path}")
            
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        count = content.count(old_string)
        if count == 0:
            raise ToolError(f"old_string not found in file. Make sure exact whitespace is matched.")
        elif count > 1:
            raise ToolError(f"old_string found {count} times. The old_string must be unique in the file to avoid ambiguous edits.")
            
        new_content = content.replace(old_string, new_string, 1)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        return f"Successfully edited {file_path}"

    @staticmethod
    def _execute_glob(pattern: str, cwd: str) -> str:
        # We need to support recursive globbing
        results = glob.glob(os.path.join(cwd, pattern), recursive=True)
        
        if not results:
            return "No files found matching pattern."
            
        relative_results = [os.path.relpath(p, cwd) for p in results]
        return "\n".join(relative_results)

    @staticmethod
    def _execute_grep(query: str, directory: str, cwd: str) -> str:
        full_dir = os.path.join(cwd, directory)
        if not os.path.exists(full_dir):
            raise ToolError(f"Directory not found: {directory}")
            
        # Using git grep or standard recursive regex search
        # We will use Python's re module across files if ripgrep isn't guaranteed.
        results = []
        try:
            regex = re.compile(query)
            for root, _, files in os.walk(full_dir):
                # Skip .git and venv to avoid huge searches
                if '.git' in root or 'venv' in root or '__pycache__' in root:
                    continue
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                            for i, line in enumerate(lines):
                                if regex.search(line):
                                    rel_path = os.path.relpath(file_path, cwd)
                                    results.append(f"{rel_path}:{i+1}:{line.strip()}")
                    except Exception:
                        pass
        except re.error as e:
            raise ToolError(f"Invalid regex query: {e}")
            
        if not results:
            return "No matches found."
            
        return "\n".join(results[:100]) # Cap at 100 results

    @staticmethod
    def _execute_read_architecture(directory: str, cwd: str) -> str:
        """Fast tree-like directory structure output."""
        full_dir = os.path.join(cwd, directory)
        if not os.path.exists(full_dir):
            raise ToolError(f"Directory not found: {directory}")
            
        output = []
        for root, dirs, files in os.walk(full_dir):
            if '.git' in dirs: dirs.remove('.git')
            if 'venv' in dirs: dirs.remove('venv')
            if '__pycache__' in dirs: dirs.remove('__pycache__')
            if 'node_modules' in dirs: dirs.remove('node_modules')
            
            level = root.replace(full_dir, '').count(os.sep)
            indent = ' ' * 4 * level
            output.append(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                output.append(f"{subindent}{f}")
                
            if len(output) > 2000:
                output.append("... [TRUNCATED DUE TO SIZE] ...")
                break
                
        return "\n".join(output)

    @staticmethod
    def _execute_symbol_search(symbol_name: str, directory: str, cwd: str) -> str:
        """Search for class/function definition using regex heuristics."""
        full_dir = os.path.join(cwd, directory)
        
        # We look for "class SymbolName" or "def symbol_name" or "function symbolName"
        regexes = [
            re.compile(r"^\s*class\s+" + re.escape(symbol_name) + r"\b"),
            re.compile(r"^\s*def\s+" + re.escape(symbol_name) + r"\b"),
            re.compile(r"^\s*function\s+" + re.escape(symbol_name) + r"\b"),
            re.compile(r"^\s*(const|let|var)\s+" + re.escape(symbol_name) + r"\s*=\s*(\(|function)"),
            re.compile(r"^\s*" + re.escape(symbol_name) + r"\s*:\s*function"),
        ]
        
        results = []
        for root, _, files in os.walk(full_dir):
            if '.git' in root or 'venv' in root or 'node_modules' in root:
                continue
            for file in files:
                if not file.endswith((".py", ".js", ".ts", ".java", ".cpp", ".c", ".h", ".cs", ".go", ".rs")):
                    continue
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                        for i, line in enumerate(lines):
                            for regex in regexes:
                                if regex.search(line):
                                    rel_path = os.path.relpath(file_path, cwd)
                                    # Get some context around the match
                                    start = max(0, i - 2)
                                    end = min(len(lines), i + 5)
                                    context = "".join(lines[start:end])
                                    results.append(f"Match in {rel_path}:{i+1}:\n{context}\n{'-'*40}")
                                    break
                except Exception:
                    pass
                    
        if not results:
            return f"No definition found for symbol '{symbol_name}'."
        return "\n".join(results[:10]) # Cap at 10 matches

