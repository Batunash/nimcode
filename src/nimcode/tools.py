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
            "ASTReplace": {
                "description": "Surgically replace a Python function or class by name. Avoids whitespace matching issues. (e.g. 'MyClass.my_method' or 'my_function')",
                "parameters": {
                    "file_path": {"type": "string", "description": "Path to the python file."},
                    "target_name": {"type": "string", "description": "Name of class or function to replace."},
                    "new_code": {"type": "string", "description": "The exact new code to replace the old AST node with."}
                },
                "required": ["file_path", "target_name", "new_code"]
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
                return cls._execute_bash(args["command"], cwd)
            elif tool_name == "Read":
                return cls._execute_read(args["file_path"], cwd)
            elif tool_name == "Write":
                return cls._execute_write(args["file_path"], args["content"], cwd)
            elif tool_name == "Edit":
                return cls._execute_edit(args["file_path"], args["old_string"], args["new_string"], cwd)
            elif tool_name == "ASTReplace":
                return cls._execute_ast_replace(args["file_path"], args["target_name"], args["new_code"], cwd)
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
            elif tool_name == "AskQuestion":
                return cls._execute_ask_question(args["question"], args.get("options", []))
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
    _FTS_DB = None
    
    @staticmethod
    def _backup_file(full_path: str, cwd: str):
        if not os.path.exists(full_path):
            return
        import time
        import shutil
        import json
        history_dir = os.path.join(cwd, ".nimcode", "history")
        os.makedirs(history_dir, exist_ok=True)
        ts = int(time.time() * 1000)
        basename = os.path.basename(full_path)
        backup_name = f"{ts}_{basename}.bak"
        backup_path = os.path.join(history_dir, backup_name)
        shutil.copy2(full_path, backup_path)
        
        index_path = os.path.join(history_dir, "index.json")
        index = []
        if os.path.exists(index_path):
            try:
                with open(index_path, "r") as f:
                    index = json.load(f)
            except:
                pass
        
        rel_path = os.path.relpath(full_path, cwd)
        index.append({"timestamp": ts, "original_path": rel_path, "backup_file": backup_name})
        with open(index_path, "w") as f:
            json.dump(index, f)
            
    @staticmethod
    def _execute_semantic_search(query: str) -> str:
        if ToolRegistry._FTS_DB is None:
            return "Error: Database not indexed. Ask the user to run /index first."
            
        try:
            import re
            clean_query = re.sub(r'[^\w\s]', ' ', query).strip()
            terms = [t for t in clean_query.split() if len(t) > 2]
            if not terms:
                return "Error: Query too short or invalid."
                
            fts_query = " OR ".join(terms)
            
            cursor = ToolRegistry._FTS_DB.execute(
                "SELECT path, snippet(files, 1, '>>>', '<<<', '...', 15) FROM files WHERE files MATCH ? ORDER BY rank LIMIT 10", 
                (fts_query,)
            )
            results = cursor.fetchall()
            
            if not results:
                return "No semantic matches found."
                
            out = []
            for path, snip in results:
                out.append(f"File: {path}\nSnippet: {snip}\n")
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
        
        import difflib
        old_lines = content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(old_lines, new_lines, fromfile=file_path, tofile=file_path))
        
        ToolRegistry._backup_file(full_path, cwd)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        return f"Successfully edited {file_path}.\nDiff:\n{diff}"

    @staticmethod
    def _execute_ast_replace(file_path: str, target_name: str, new_code: str, cwd: str) -> str:
        import ast
        full_path = os.path.join(cwd, file_path)
        if not os.path.exists(full_path):
            return f"Error: {file_path} not found."
            
        with open(full_path, "r", encoding="utf-8") as f:
            source = f.read()
            
        try:
            tree = ast.parse(source)
        except Exception as e:
            return f"Error parsing python file: {e}"
            
        parts = target_name.split(".")
        target_node = None
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if len(parts) == 1 and node.name == parts[0]:
                    target_node = node
                    break
                elif len(parts) == 2 and isinstance(node, ast.ClassDef) and node.name == parts[0]:
                    for child in node.body:
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == parts[1]:
                            target_node = child
                            break
                            
        if not target_node:
            return f"Error: Target '{target_name}' not found in AST."
            
        start_line = target_node.lineno - 1
        end_line = target_node.end_lineno
        
        if hasattr(target_node, 'decorator_list') and target_node.decorator_list:
            start_line = target_node.decorator_list[0].lineno - 1
            
        lines = source.splitlines(keepends=True)
        new_lines = new_code.splitlines(keepends=True)
        if not new_lines[-1].endswith('\n'):
            new_lines[-1] += '\n'
            
        lines[start_line:end_line] = new_lines
        new_source = "".join(lines)
        
        import difflib
        diff = "".join(difflib.unified_diff(source.splitlines(keepends=True), lines, fromfile=file_path, tofile=file_path))
        
        ToolRegistry._backup_file(full_path, cwd)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_source)
            
        return f"Successfully AST-replaced '{target_name}' in {file_path}.\nDiff:\n{diff}"

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
