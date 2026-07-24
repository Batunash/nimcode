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
                "description": "Execute a shell command. Use this for running tests, checking git status, running scripts.",
                "parameters": {
                    "command": {"type": "string", "description": "The bash command to run."},
                    "background": {"type": "boolean", "description": "Run in background without blocking. Returns a task ID.", "default": False}
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
            "Replace": {
                "description": "Edit an existing file by replacing exact strings. Allows multiple non-contiguous edits in one call.",
                "parameters": {
                    "file_path": {"type": "string", "description": "Path to the file."},
                    "replacements": {
                        "type": "array",
                        "description": "List of replacements to apply.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "old_string": {"type": "string", "description": "The exact string to replace, including whitespaces."},
                                "new_string": {"type": "string", "description": "The string to replace it with."}
                            },
                            "required": ["old_string", "new_string"]
                        }
                    }
                },
                "required": ["file_path", "replacements"]
            },
            "StartTerminal": {
                "description": "Start a persistent interactive terminal session. Useful for running long-lived commands or commands that prompt for user input (y/n).",
                "parameters": {
                    "command": {"type": "string", "description": "The command to run."},
                    "term_id": {"type": "string", "description": "A unique identifier for this terminal session."}
                },
                "required": ["command", "term_id"]
            },
            "TerminalInput": {
                "description": "Send input (keystrokes) to a running interactive terminal.",
                "parameters": {
                    "term_id": {"type": "string", "description": "The ID of the running terminal."},
                    "text": {"type": "string", "description": "The text to type into the terminal (newline will be appended automatically)."}
                },
                "required": ["term_id", "text"]
            },
            "BrowseWeb": {
                "description": "Navigate to a URL using a headless browser, take a screenshot, and use Llama 3.2 Vision to analyze the page against your goal.",
                "parameters": {
                    "url": {"type": "string", "description": "The website URL to visit (e.g. http://localhost:3000)."},
                    "goal": {"type": "string", "description": "What you want the Vision model to look for (e.g. 'Is the button misaligned?')."}
                },
                "required": ["url", "goal"]
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
            "SemanticSearch": {
                "description": "Semantically search the codebase for concepts using BM25 ranking. ONLY WORKS IF /index HAS BEEN RUN.",
                "parameters": {
                    "query": {"type": "string", "description": "The concept to search for (e.g. 'user authentication handling')"}
                },
                "required": ["query"]
            },
            "ReadActiveEditor": {
                "description": "Reads the content of the currently active file in the user's VS Code editor. Only works inside the VS Code extension.",
                "parameters": {},
                "required": []
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
            },
            "AskQuestion": {
                "description": "Ask the user a multiple-choice or text question using an interactive terminal modal.",
                "parameters": {
                    "question": {"type": "string", "description": "The question to ask."},
                    "options": {
                        "type": "array", 
                        "items": {"type": "string"},
                        "description": "Optional list of choices. If empty, the user provides a free-text answer."
                    }
                },
                "required": ["question"]
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
                return cls._execute_bash(args["command"], cwd, args.get("background", False))
            elif tool_name == "Read":
                return cls._execute_read(args["file_path"], cwd)
            elif tool_name == "Write":
                return cls._execute_write(args["file_path"], args["content"], cwd)
            elif tool_name == "Replace":
                return cls._execute_replace(args["file_path"], args["replacements"], cwd)
            elif tool_name == "StartTerminal":
                return cls._execute_start_terminal(args["command"], args["term_id"], cwd)
            elif tool_name == "TerminalInput":
                return cls._execute_terminal_input(args["term_id"], args["text"])
            elif tool_name == "BrowseWeb":
                return cls._execute_browse_web(args["url"], args["goal"])
            elif tool_name == "Glob":
                return cls._execute_glob(args["pattern"], cwd)
            elif tool_name == "Grep":
                return cls._execute_grep(args["query"], args["directory"], cwd)
            elif tool_name == "ReadArchitecture":
                return cls._execute_read_architecture(args.get("directory", "."), cwd)
            elif tool_name == "SymbolSearch":
                return cls._execute_symbol_search(args["symbol_name"], args["directory"], cwd)
            elif tool_name == "SemanticSearch":
                return cls._execute_semantic_search(args["query"])
            elif tool_name == "ReadActiveEditor":
                return cls._execute_read_active_editor(cwd)
            elif tool_name == "AskQuestion":
                return cls._execute_ask_question(args["question"], args.get("options", []))
            else:
                raise ToolError(f"Tool {tool_name} is registered but execution is not implemented.")
        except Exception as e:
            if isinstance(e, ToolError):
                return f"ToolError: {str(e)}"
            return f"Error executing {tool_name}: {str(e)}"

    _BACKGROUND_TASKS = {}
    
    @classmethod
    def _execute_bash(cls, command: str, cwd: str, background: bool = False) -> str:
        from .config import load_settings
        settings = load_settings()
        if settings.get("sandbox_mode", False):
            # Sandbox the command in Docker
            escaped_cmd = command.replace('"', '\\"')
            command = f'docker run --rm -v "{cwd}:/workspace" -w /workspace python:3.11-slim bash -c "{escaped_cmd}"'
            

        if background:
            import uuid
            task_id = str(uuid.uuid4())[:8]
            
            # Open file for stdout/stderr
            log_file = os.path.join(cwd, ".nimcode", "tasks", f"{task_id}.log")
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            f = open(log_file, "w", encoding="utf-8")
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                stdout=f,
                stderr=subprocess.STDOUT,
                text=True
            )
            cls._BACKGROUND_TASKS[task_id] = {
                "process": process,
                "command": command,
                "log_file": log_file,
                "file_handle": f
            }
            return f"Started task '{task_id}' in the background. Check logs at {log_file}. Use /tasks to manage."
            
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=1200
            )
            out = result.stdout + "\n" + result.stderr
            out = out.strip()
            
            # Truncate if too long (simulating context limit protection)
            if len(out) > 10000:
                out = out[:5000] + f"\n...[TRUNCATED {len(out) - 10000} characters]...\n" + out[-5000:]
            
            return out if out else "Command executed successfully with no output."
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 1200 seconds."
        except Exception as e:
            return f"Error running bash: {e}"

    _FILE_CACHE = {}
    _FTS_DB = None
    
    @staticmethod
    def _backup_file(full_path: str, cwd: str):
        if not os.path.exists(full_path):
            return
        import time
        import shutil
        import json
        
        backup_dir = os.path.join(cwd, ".nimcode", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        ts = int(time.time() * 1000)
        basename = os.path.basename(full_path)
        backup_name = f"{ts}_{basename}.bak"
        backup_path = os.path.join(backup_dir, backup_name)
        shutil.copy2(full_path, backup_path)
        
        index_path = os.path.join(backup_dir, "index.json")
        index = []
        if os.path.exists(index_path):
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    index = json.load(f)
            except:
                pass
        
        rel_path = os.path.relpath(full_path, cwd)
        index.append({"timestamp": ts, "original_path": rel_path, "backup_file": backup_name})
        
        # Keep only last 50 backups to save space
        if len(index) > 50:
            oldest = index.pop(0)
            oldest_file = os.path.join(backup_dir, oldest["backup_file"])
            if os.path.exists(oldest_file):
                os.remove(oldest_file)
                
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f)

    @staticmethod
    def _execute_undo(cwd: str) -> str:
        import shutil
        import json
        backup_dir = os.path.join(cwd, ".nimcode", "backups")
        index_path = os.path.join(backup_dir, "index.json")
        
        if not os.path.exists(index_path):
            return "Error: No backup history found."
            
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
        except Exception as e:
            return f"Error reading backup index: {e}"
            
        if not index:
            return "Error: No backups available to undo."
            
        last_backup = index.pop()
        backup_file_path = os.path.join(backup_dir, last_backup["backup_file"])
        target_path = os.path.join(cwd, last_backup["original_path"])
        
        if not os.path.exists(backup_file_path):
            # Try to save index anyway
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f)
            return f"Error: Backup file {last_backup['backup_file']} is missing."
            
        try:
            shutil.copy2(backup_file_path, target_path)
            os.remove(backup_file_path)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f)
            return f"Successfully reverted '{last_backup['original_path']}' to its previous state."
        except Exception as e:
            return f"Error restoring backup: {e}"
            
    _RAG_INDEXER = None
    
    @staticmethod
    def _execute_semantic_search(query: str) -> str:
        try:
            if ToolRegistry._RAG_INDEXER is None:
                from .rag import LightweightRAG
                ToolRegistry._RAG_INDEXER = LightweightRAG(os.getcwd())
                ToolRegistry._RAG_INDEXER.build_index()
                
            results = ToolRegistry._RAG_INDEXER.search(query, top_k=5)
            
            if not results:
                return "No semantic matches found."
                
            out = []
            for path, score, snip in results:
                out.append(f"File: {path} (Score: {score:.2f})\nSnippet: {snip}\n")
            return "\n".join(out)
        except Exception as e:
            return f"Search error: {e}"

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
        # Run Secret Scanner
        try:
            from .secret_scanner import SecretScanner
            findings = SecretScanner.scan(content)
            if findings:
                raise ToolError(f"SecretScanner blocked write: {len(findings)} secrets detected ({', '.join(findings)})")
        except ImportError:
            pass
            
        full_path = os.path.join(cwd, file_path)
        os.makedirs(os.path.dirname(os.path.abspath(full_path)) or ".", exist_ok=True)
        
        import difflib
        old_lines = []
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    old_lines = f.readlines()
            except:
                pass
                
        new_lines = content.splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(old_lines, new_lines, fromfile=file_path, tofile=file_path))
        
        ToolRegistry._backup_file(full_path, cwd)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        diff_str = f"\nDiff:\n{diff}" if diff else ""
        return f"Successfully wrote to {file_path}.{diff_str}"

    @staticmethod
    def _execute_replace(file_path: str, replacements: list, cwd: str) -> str:
        full_path = os.path.join(cwd, file_path)
        if not os.path.exists(full_path):
            raise ToolError(f"File not found: {file_path}")
            
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        new_content = content
        
        # Run Secret Scanner
        try:
            from .secret_scanner import SecretScanner
            all_replacements = " ".join([rep.get("new_string", "") for rep in replacements])
            findings = SecretScanner.scan(all_replacements)
            if findings:
                raise ToolError(f"SecretScanner blocked replace: {len(findings)} secrets detected ({', '.join(findings)})")
        except ImportError:
            pass
            
        applied = 0
        
        for rep in replacements:
            old_str = rep.get("old_string")
            new_str = rep.get("new_string")
            if old_str is None or new_str is None:
                raise ToolError("Each replacement must contain 'old_string' and 'new_string'.")
                
            count = new_content.count(old_str)
            if count == 0:
                raise ToolError(f"Target string not found in file (or already replaced). Ensure exact whitespace match:\n{old_str}")
            elif count > 1:
                raise ToolError(f"Target string found {count} times. The old_string must be unique in the file to avoid ambiguous edits:\n{old_str}")
                
            new_content = new_content.replace(old_str, new_str, 1)
            applied += 1
            
        import difflib
        old_lines = content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(old_lines, new_lines, fromfile=file_path, tofile=file_path))
        
        ToolRegistry._backup_file(full_path, cwd)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        return f"Successfully applied {applied} replacements in {file_path}.\nDiff:\n{diff}"

    @staticmethod
    def _execute_glob(pattern: str, cwd: str) -> str:
        # We need to support recursive globbing
        results = glob.glob(os.path.join(cwd, pattern), recursive=True)
        
        if not results:
            return "No files found matching pattern."
            
        relative_results = [os.path.relpath(p, cwd) for p in results]
        return "\n".join(relative_results)

    _ACTIVE_TERMINALS = {}
    
    @staticmethod
    def _execute_start_terminal(command: str, term_id: str, cwd: str) -> str:
        if term_id in ToolRegistry._ACTIVE_TERMINALS:
            return f"Terminal '{term_id}' already running."
            
        import subprocess
        import threading
        import queue
        
        try:
            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            q = queue.Queue()
            def read_output():
                try:
                    for line in iter(proc.stdout.readline, ''):
                        q.put(line)
                except:
                    pass
                try:
                    proc.stdout.close()
                except:
                    pass
                
            t = threading.Thread(target=read_output, daemon=True)
            t.start()
            
            ToolRegistry._ACTIVE_TERMINALS[term_id] = {
                "proc": proc,
                "queue": q,
                "thread": t
            }
            
            import time
            time.sleep(1)
            
            out = ""
            while not q.empty():
                out += q.get_nowait()
                
            return f"Started terminal '{term_id}'. Initial Output:\n{out}"
        except Exception as e:
            return f"Failed to start terminal: {e}"

    @staticmethod
    def _execute_terminal_input(term_id: str, text: str) -> str:
        if term_id not in ToolRegistry._ACTIVE_TERMINALS:
            return f"Terminal '{term_id}' not found."
            
        term = ToolRegistry._ACTIVE_TERMINALS[term_id]
        proc = term["proc"]
        q = term["queue"]
        
        if proc.poll() is not None:
            del ToolRegistry._ACTIVE_TERMINALS[term_id]
            return f"Terminal '{term_id}' has exited with code {proc.returncode}."
            
        try:
            if not text.endswith('\n'):
                text += '\n'
            proc.stdin.write(text)
            proc.stdin.flush()
            
            import time
            time.sleep(1.5)
            
            out = ""
            while not q.empty():
                out += q.get_nowait()
                
            return f"Input sent. Output:\n{out}"
        except Exception as e:
            return f"Failed to send input: {e}"

    @staticmethod
    def _execute_browse_web(url: str, goal: str) -> str:
        try:
            from playwright.sync_api import sync_playwright
            import base64
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=15000)
                
                screenshot_bytes = page.screenshot(type="jpeg", quality=50)
                b64_img = base64.b64encode(screenshot_bytes).decode('utf-8')
                
                text_content = page.evaluate("document.body.innerText")
                browser.close()
                
            import os
            import json
            settings_path = os.path.join(os.getcwd(), ".nimcode", "settings.json")
            api_key = os.environ.get("NVIDIA_API_KEY")
            if os.path.exists(settings_path):
                with open(settings_path, "r") as f:
                    settings = json.load(f)
                    api_key = settings.get("nvidia_api_key", api_key)
                    
            if not api_key:
                return "Failed: No NVIDIA API key found."
                
            from .nim_client import NimClient
            import asyncio
            client = NimClient(api_key=api_key)
            vision_prompt = f"Analyze this webpage screenshot to help with the goal: '{goal}'. Here is the text content for context:\n{text_content[:2000]}..."
            
            result = asyncio.run(client.chat_vision(b64_img, vision_prompt))
            return f"Visual Analysis of {url}:\n{result}"
        except Exception as e:
            return f"Failed to browse web: {e}"

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

    @staticmethod
    def _execute_ask_question(question: str, options: List[str]) -> str:
        from rich.console import Console
        from rich.panel import Panel
        from rich.prompt import Prompt
        import sys
        
        c = Console()
        c.print()
        c.print(Panel(f"[bold cyan]NimCode Question:[/bold cyan]\n{question}", border_style="cyan"))
        
        if not sys.stdin.isatty():
            return "Running non-interactive. Assuming default answer or empty string."
            
        if options:
            for i, opt in enumerate(options):
                c.print(f"  [bold yellow][{i+1}][/bold yellow] {opt}")
            while True:
                ans = Prompt.ask("Select an option number")
                if ans.isdigit() and 1 <= int(ans) <= len(options):
                    return f"User selected: {options[int(ans)-1]}"
                c.print("[red]Invalid selection.[/red]")
        else:
            ans = Prompt.ask("[bold yellow]Your answer[/bold yellow]")
            return f"User answered: {ans}"

    @staticmethod
    def _execute_read_active_editor(cwd: str) -> str:
        import sys
        import time
        import json
        
        # Trigger the VS Code extension by emitting a special JSON payload
        msg = {"type": "vscode_action", "action": "read_active_editor"}
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()
        
        # Wait for the file to be written by the extension
        target_path = os.path.join(cwd, ".nimcode", ".active_editor")
        
        max_retries = 20
        for _ in range(max_retries):
            time.sleep(0.1)
            if os.path.exists(target_path):
                try:
                    with open(target_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    # Clean up the file
                    try:
                        os.remove(target_path)
                    except:
                        pass
                        
                    if not data.get("path"):
                        return "No active editor found in VS Code."
                        
                    return f"Active File: {data['path']}\n\nContent:\n{data['content']}"
                except Exception:
                    pass
                    
        return "Timed out waiting for VS Code extension. Make sure NimCode is running inside VS Code."
