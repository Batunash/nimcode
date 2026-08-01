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
                "description": "Read the contents of a file. For large files, use offset/limit to paginate instead of loading the whole file at once.",
                "parameters": {
                    "file_path": {"type": "string", "description": "Path to the file to read."},
                    "offset": {"type": "integer", "description": "1-based line number to start reading from. Omit to start at the beginning.", "default": 1},
                    "limit": {"type": "integer", "description": "Maximum number of lines to return. Omit for the whole file (may be large).", "default": 0}
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
            "Append": {
                "description": "Append content to the end of an existing file. Ideal for building large plans or documents chunk by chunk without hitting token limits.",
                "parameters": {
                    "file_path": {"type": "string", "description": "Path to the file."},
                    "content": {"type": "string", "description": "Content to append to the file. A newline is automatically added."}
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
            "ReplaceBlock": {
                "description": "Edit an existing file by replacing a block of lines. Solves whitespace and indentation issues by targeting exact line numbers.",
                "parameters": {
                    "file_path": {"type": "string", "description": "Path to the file."},
                    "start_line": {"type": "integer", "description": "The 1-based starting line number of the block to replace."},
                    "end_line": {"type": "integer", "description": "The 1-based ending line number of the block to replace (inclusive)."},
                    "replacement_content": {"type": "string", "description": "The content to insert in place of the specified lines."}
                },
                "required": ["file_path", "start_line", "end_line", "replacement_content"]
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
            },
            "GetCodeOutline": {
                "description": "Get the structural outline (functions, classes) of a code file with line numbers. Use this to quickly navigate large files.",
                "parameters": {
                    "file_path": {"type": "string", "description": "Path to the code file."}
                },
                "required": ["file_path"]
            },
                        "TaskCreate": {
                "description": "Create a new task in the task list.",
                "parameters": {
                    "task_id": {"type": "string", "description": "Unique ID for the task (e.g. '1.1')"},
                    "subject": {"type": "string", "description": "Short title of the task."},
                    "description": {"type": "string", "description": "Detailed description."}
                },
                "required": ["task_id", "subject", "description"]
            },
            "TaskUpdate": {
                "description": "Update the status of an existing task.",
                "parameters": {
                    "task_id": {"type": "string", "description": "ID of the task."},
                    "status": {"type": "string", "description": "One of: pending, in_progress, completed, failed."}
                },
                "required": ["task_id", "status"]
            },
            "TaskList": {
                "description": "List all current tasks and their statuses.",
                "parameters": {},
                "required": []
            },
            "InvokeQA": {
                "description": "Invoke the QA Verification Agent to test your code. MUST run before finishing.",
                "parameters": {
                    "instructions": {"type": "string", "description": "What should the QA agent verify?"}
                },
                "required": ["instructions"]
            },
            "DelegateTask": {
                "description": "Spawn a headless SubAgent in the background to solve a specific subtask. Useful for delegating work while you manage the big picture.",
                "parameters": {
                    "task_description": {"type": "string", "description": "A very specific, clear instruction for what the subagent should do."},
                    "target_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of files the subagent should focus on."
                    }
                },
                "required": ["task_description", "target_files"]
            },
            "CallMCP": {
                "description": "Call a tool provided by an external MCP server.",
                "parameters": {
                    "mcp_tool_name": {"type": "string", "description": "The exact name of the MCP tool to call."},
                    "mcp_tool_args": {"type": "object", "description": "The arguments for the MCP tool.", "default": {}}
                },
                "required": ["mcp_tool_name"]
            },
            "TestRunner": {
                "description": "Run a test suite and capture the output to verify code correctness.",
                "parameters": {
                    "command": {"type": "string", "description": "The test command (e.g., 'pytest', 'npm test', 'go test')"}
                },
                "required": ["command"]
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
                return cls._execute_read(args["file_path"], cwd, args.get("offset", 1), args.get("limit", 0))
            elif tool_name == "Write":
                return cls._execute_write(args["file_path"], args["content"], cwd)
            elif tool_name == "Append":
                return cls._execute_append(args["file_path"], args["content"], cwd)
            elif tool_name == "Replace":
                return cls._execute_replace(args["file_path"], args["replacements"], cwd)
            elif tool_name == "ReplaceBlock":
                return cls._execute_replace_block(args["file_path"], args["start_line"], args["end_line"], args["replacement_content"], cwd)
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
            elif tool_name == "GetCodeOutline":
                return cls._execute_get_code_outline(args["file_path"], cwd)
            elif tool_name == "TaskCreate":
                return cls._execute_task_create(args["task_id"], args["subject"], args["description"])
            elif tool_name == "TaskUpdate":
                return cls._execute_task_update(args["task_id"], args["status"])
            elif tool_name == "TaskList":
                return cls._execute_task_list()
            elif tool_name == "InvokeQA":
                return cls._execute_invoke_qa(args["instructions"], cwd)
            elif tool_name == "TestRunner":
                return cls._execute_test_runner(args["command"], cwd)
            else:
                raise ToolError(f"Tool {tool_name} is registered but execution is not implemented.")
        except Exception as e:
            if isinstance(e, ToolError):
                return f"ToolError: {str(e)}"
            return f"Error executing {tool_name}: {str(e)}"


    @staticmethod
    def _check_ast_deletion(old_content: str, new_content: str, file_path: str):
        if not file_path.endswith('.py'):
            return
            
        import ast
        try:
            old_tree = ast.parse(old_content)
            new_tree = ast.parse(new_content)
            
            def count_nodes(tree):
                return sum(1 for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
                
            old_count = count_nodes(old_tree)
            new_count = count_nodes(new_tree)
            
            if old_count > 0 and new_count < old_count:
                # If we lost more than 30% of the functions/classes or lost at least 2
                if (old_count - new_count) / old_count > 0.3 or (old_count - new_count) >= 2:
                    raise ToolError(f"Validation Error: Massive code deletion detected. AST dropped from {old_count} to {new_count} functions/classes. This usually indicates Context Amnesia (truncation). Fix your code.")
        except SyntaxError:
            pass

    @staticmethod
    def _check_lazy_code(content: str, file_path: str):
        if file_path.lower().endswith(('.md', '.txt', '.json', '.yaml', '.yml', '.csv', '.ini', '.toml')):
            return
        import re
        # Broad regex for // TO DO, // TODO, # TODO, // FIXME, etc. with flexible spaces
        if re.search(r'(?i)(?://|#)\s*(?:to\s*do|fix\s*me)', content):
            raise ToolError("Validation Error: Lazy code detected (TODO/FIXME). You must provide the full implementation.")
            
        # Semantic lazy patterns
        if re.search(r'(?i)(?:rest of|existing).*?(?:code|file).*?(?:remains|is unchanged|here)', content):
            raise ToolError("Validation Error: Lazy code detected ('rest of code remains' or similar). Do not skip code.")
            
        if re.search(r'(?i)(?:\.\.\.|…)\s*(?:existing|rest of|your)', content):
            raise ToolError("Validation Error: Lazy code detected ('... existing code' or similar). Do not skip code.")
            
        if re.search(r'(?i)(?:logic goes here|implement (?:this|the rest)|your code here|add your logic)', content):
            raise Exception("ToolError: Validation Error: Lazy code detected ('logic goes here' or similar). Do not use placeholders.")
            
        if re.search(r'(?i)(?://|#)\s*(?:unchanged|\.\.\.)', content) or re.search(r'(?m)^\s*\.\.\.\s*$', content):
            raise Exception("ToolError: Validation Error: Lazy code detected (ellipsis placeholder '...' or 'unchanged'). You must provide the full implementation.")

        # Mock Data Hunter
        if re.search(r'(?i)(?:lorem\s*ipsum|dummy\s*data|mockuser|return\s+true\s*;\s*//\s*placeholder)', content):
            raise Exception("ToolError: Validation Error: Mock data detected ('Lorem ipsum' or 'dummy data'). You must write the actual implementation with real data structures or database connections.")
        
        # Rust/Python stubs
        stub_patterns = ["todo!()", "unimplemented!()", "Insert code here", "pass\n", "PdfDocument::empty()", "return empty()"]
        for p in stub_patterns:
            if p in content:
                raise ToolError(f"Validation Error: Lazy code detected ('{p}'). You must provide the full implementation.")
                
        if file_path.endswith('.py'):
            import ast
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                        if len(node.body) == 1:
                            if isinstance(node.body[0], ast.Pass):
                                raise ToolError("Validation Error: Lazy code detected (empty function/class with 'pass'). You must provide the full implementation.")
                            elif isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and node.body[0].value.value is Ellipsis:
                                raise ToolError("Validation Error: Lazy code detected (empty function/class with '...'). You must provide the full implementation.")
            except SyntaxError:
                pass

    @staticmethod
    def _execute_task_create(task_id: str, subject: str, description: str) -> str:
        if len(description) < 150:
            raise Exception("ToolError: Validation Error: Task description is too short (under 150 characters). You must provide extremely detailed technical specs.")
        
        required_sections = ["Target Files", "Implementation Details", "Checklist"]
        missing = [sec for sec in required_sections if sec not in description]
        if missing:
            raise Exception(f"ToolError: Validation Error: Task description is missing required markdown sections: {missing}. Follow the Strict Plan Format.")
            
        desc_lower = description.lower()
        if "acceptance criteria" not in desc_lower and "test" not in desc_lower and "step" not in desc_lower:
            raise Exception("ToolError: Validation Error: Task description lacks quality. It MUST contain 'Acceptance Criteria', 'Test', or 'Step' definitions.")
            
        if task_id.endswith("-1") or task_id.endswith("1"):
            lower_subj = subject.lower()
            if "setup" not in lower_subj and "init" not in lower_subj and "scaffold" not in lower_subj and "create" not in lower_subj:
                raise Exception("ToolError: Validation Error: Task 1 MUST be initializing the framework (scaffolding) using standard CLI tools (e.g. npx create-react-app).")
                
        from .task_manager import TaskManager
        tm = TaskManager()
        return tm.create_task(task_id, subject, description)

    @staticmethod
    def _execute_task_update(task_id: str, status: str) -> str:
        if status == "completed":
            pass
            cwd = os.getcwd()

            # Architecture Validator
            if task_id.endswith("-1") or task_id.endswith("1"):
                if not any([os.path.exists(os.path.join(cwd, "package.json")), 
                            os.path.exists(os.path.join(cwd, "requirements.txt")),
                            os.path.exists(os.path.join(cwd, "Cargo.toml")),
                            os.path.exists(os.path.join(cwd, "pyproject.toml")),
                            os.path.exists(os.path.join(cwd, "go.mod"))]):
                    raise Exception(f"ToolError: Architecture Validator failed. Task {task_id} is a setup task, but no standard project files (package.json, requirements.txt, etc.) were found. Create the project skeleton first.")

            # Physical Blocker: Proof of Work & Coverage Enforcer
            log_dir = os.path.join(cwd, ".nimcode", "tasks")
            has_proof = False
            has_coverage_failure = False
            import re
            
            if os.path.exists(log_dir):
                for f in os.listdir(log_dir):
                    if f.endswith(".log"):
                        try:
                            with open(os.path.join(log_dir, f), "r", encoding="utf-8") as lf:
                                content = lf.read()
                                content_lower = content.lower()
                                if "test" in content_lower or "jest" in content_lower or "pytest" in content_lower or "build" in content_lower:
                                    has_proof = True
                                    
                                # Coverage Enforcer
                                cov_match = re.search(r'Lines\s*:\s*(\d+\.?\d*)%', content)
                                if not cov_match:
                                    cov_match = re.search(r'All files\s*\|\s*(\d+\.?\d*)', content)
                                if cov_match:
                                    cov_percent = float(cov_match.group(1))
                                    if cov_percent < 70.0:
                                        has_coverage_failure = True
                                        break
                        except:
                            pass
            
            qa_log = os.path.join(cwd, ".nimcode", "qa_results.txt")
            if os.path.exists(qa_log):
                has_proof = True
                
            if has_coverage_failure:
                raise Exception(f"ToolError: Test Coverage Enforcer blocked completion. Test coverage is below 70%. Write more tests before closing this task.")
                
            if not has_proof:
                raise Exception(f"ToolError: Cannot mark {task_id} as completed without proof of work. You must run tests via Bash tool first.")
                
        from .task_manager import TaskManager
        tm = TaskManager()
        return tm.update_task_status(task_id, status)

    @staticmethod
    def _execute_task_list() -> str:
        from .task_manager import TaskManager
        tm = TaskManager()
        return tm.list_tasks()

    @staticmethod
    def _execute_invoke_qa(instructions: str, cwd: str) -> str:
        from .agents.qa_agent import QAAgent
        qa = QAAgent(cwd=cwd)
        result = qa.run(instructions)
        pass
        os.makedirs(os.path.join(cwd, ".nimcode"), exist_ok=True)
        with open(os.path.join(cwd, ".nimcode", "qa_results.txt"), "w", encoding="utf-8") as f:
            f.write(result)
        return result

    _BACKGROUND_TASKS = {}
    
    @classmethod
    def _execute_bash(cls, command: str, cwd: str, background: bool = False) -> str:
        # Bash Command Blacklist
        cmd_lower = command.lower()
        import re
        if re.search(r'\b(rm\s+-r|rm\s+-rf|sudo|kill|killall|chmod\s+-r\s+777|curl|wget)\b', cmd_lower) or "cd .." in cmd_lower:
            raise Exception("ToolError: Security Blocker: Your bash command contains a blacklisted, dangerous pattern (rm -rf, sudo, kill, or cd out of bounds). Command execution blocked.")
            
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
            t_cmd = settings.get("timeout_command", 1200)
            t_cmd = None if t_cmd == 0 else t_cmd
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=t_cmd
            )
            out = result.stdout + "\n" + result.stderr
            out = out.strip()
            
            # Truncate if too long (simulating context limit protection)
            if len(out) > 10000:
                out = out[:5000] + f"\n...[TRUNCATED {len(out) - 10000} characters]...\n" + out[-5000:]
            
            return out if out else "Command executed successfully with no output."
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {t_cmd} seconds."
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
    def _execute_read(file_path: str, cwd: str, offset: int = 1, limit: int = 0) -> str:
        try:
            offset = max(1, int(offset))
            limit = max(0, int(limit))
        except ValueError:
            return "Error executing Read: 'offset' and 'limit' must be integers."

        
        full_path = os.path.join(cwd, file_path)
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    if len(f.readlines()) > 100:
                        raise ToolError(f"Validation Error: File {file_path} is too large (>100 lines) to overwrite completely. Use ReplaceBlock to edit specific lines and prevent Context Amnesia.")
            except:
                pass

        if not os.path.exists(full_path):
            raise ToolError(f"File not found: {file_path}")
        if os.path.isdir(full_path):
            raise ToolError(f"Path is a directory, not a file: {file_path}")

        mtime = os.path.getmtime(full_path)
        # Cache only the FULL, unpaginated file; paginated reads bypass cache to stay cheap.
        cache_key = full_path
        if offset <= 1 and limit == 0 and cache_key in ToolRegistry._FILE_CACHE:
            cached_mtime, cached_content = ToolRegistry._FILE_CACHE[cache_key]
            if cached_mtime == mtime:
                return cached_content

        with open(full_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()

        total = len(all_lines)

        # No limit → whole file (and cache it).
        if limit == 0:
            content = "".join(all_lines)
            ToolRegistry._FILE_CACHE[full_path] = (mtime, content)
            return content

        # Paginated read: slice lines, annotate with line numbers and a continuation hint.
        start_idx = offset - 1
        end_idx = min(start_idx + int(limit), total)
        selected = all_lines[start_idx:end_idx]

        out_lines = []
        for i, line in enumerate(selected, start=offset):
            # Strip the trailing newline since we add our own line-numbered line.
            out_lines.append(f"{i:>6}\t{line.rstrip(chr(10))}")

        body = "\n".join(out_lines)
        shown = end_idx - start_idx
        remaining = total - end_idx
        header = f"(showing lines {offset}-{end_idx} of {total}"
        if remaining > 0:
            header += f"; {remaining} more — pass offset={end_idx + 1} to continue)"
        else:
            header += ")"
        return f"{header}\n{body}"


    @staticmethod
    def _check_dependency_hallucination(content: str, file_path: str, cwd: str):
        if file_path.lower().endswith(('.md', '.txt', '.json', '.yaml', '.yml', '.csv', '.ini', '.toml')):
            return
        import re
        pass
        import json
        local_imports = re.findall(r'''(?:import|require).*?['"](\.[^'"]+)['"]''', content)
        for imp in local_imports:
            base_dir = os.path.dirname(os.path.join(cwd, file_path))
            target_path = os.path.normpath(os.path.join(base_dir, imp))
            if not any([os.path.exists(target_path), os.path.exists(target_path + ".js"), os.path.exists(target_path + ".ts"), os.path.exists(target_path + ".jsx"), os.path.exists(target_path + ".tsx"), os.path.exists(target_path + ".css")]):
                raise Exception(f"ToolError: You are trying to import '{imp}' but this file does not exist. Create it first.")

        # External Package Check
        external_imports = re.findall(r'''(?:import|require).*?['"]([^.\/][^'"]+)['"]''', content)
        if external_imports:
            pkg_path = os.path.join(cwd, "package.json")
            if os.path.exists(pkg_path):
                try:
                    with open(pkg_path, "r", encoding="utf-8") as f:
                        pkg = json.load(f)
                        deps = list(pkg.get("dependencies", {}).keys()) + list(pkg.get("devDependencies", {}).keys())
                        builtins = ["fs", "path", "os", "http", "https", "crypto", "child_process", "events", "util", "stream", "buffer", "url", "assert"]
                        for ext in external_imports:
                            ext_base = ext.split("/")[0]
                            if ext_base not in deps and ext_base not in builtins and not ext_base.startswith("node:"):
                                raise Exception(f"ToolError: Missing Dependency Blocker: Package '{ext_base}' is imported but NOT found in package.json. You MUST install it first using the Bash tool (e.g. `npm install {ext_base}`).")
                except Exception as e:
                    if "ToolError" in str(e): raise e

    @staticmethod
    def _check_api_hallucination(content: str, cwd: str):
        import re
        pass
        api_calls = re.findall(r'''(?:fetch|axios\.get|axios\.post|axios\.put|axios\.delete|requests\.get|requests\.post)\s*\(\s*['"](https?://[^/'"]+)''', content)
        if api_calls:
            api_log = os.path.join(cwd, ".nimcode", "api_checks.log")
            checked_apis = ""
            if os.path.exists(api_log):
                with open(api_log, "r", encoding="utf-8") as f:
                    checked_apis = f.read()
            for api in api_calls:
                if api not in checked_apis:
                    raise Exception(f"ToolError: Network Check Enforcer: You are using the API endpoint '{api}' but you haven't tested it yet. Use the Bash tool to test it (e.g. `curl -I {api} >> .nimcode/api_checks.log`) before writing the code.")

    @staticmethod
    def _check_syntax(file_path: str, full_path: str, backup_lines: list):
        import subprocess
        try:
            if file_path.endswith(".py"):
                subprocess.run(["python", "-m", "py_compile", full_path], check=True, capture_output=True, text=True)
            elif file_path.endswith(".js") or file_path.endswith(".jsx"):
                # if node is not installed, it will raise FileNotFoundError which we ignore
                subprocess.run(["node", "--check", full_path], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            if backup_lines:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.writelines(backup_lines)
            else:
                pass
                if os.path.exists(full_path):
                    os.remove(full_path)
            raise Exception(f"ToolError: Syntax Error detected in {file_path}. Code reverted. Details: {e.stderr or e.stdout}")
        except FileNotFoundError:
            pass

    @staticmethod
    def _execute_write(file_path: str, content: str, cwd: str) -> str:

        # Physical Blocker for Lazy Code
        ToolRegistry._check_lazy_code(content, file_path)

        # Dependency Hallucination Checker
        ToolRegistry._check_dependency_hallucination(content, file_path, cwd)
        ToolRegistry._check_api_hallucination(content, cwd)

        # Run Secret Scanner
        try:
            from .secret_scanner import SecretScanner
            findings = SecretScanner.scan(content)
            if findings:
                raise Exception(f"SecretScanner blocked write: {len(findings)} secrets detected ({', '.join(findings)})")
        except ImportError:
            pass
            
        full_path = os.path.join(cwd, file_path)
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    if len(f.readlines()) > 100:
                        raise Exception(f"ToolError: Validation Error: File {file_path} is too large (>100 lines) to overwrite completely. Use ReplaceBlock to edit specific lines and prevent Context Amnesia.")
            except:
                pass

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
            
        # Syntax Check Blocker
        ToolRegistry._check_syntax(file_path, full_path, old_lines)
            
        diff_str = f"\nDiff:\n{diff}" if diff else ""
        return f"Successfully wrote to {file_path}.{diff_str}"

    @staticmethod
    def _execute_append(file_path: str, content: str, cwd: str) -> str:
        # Physical Blocker for Lazy Code
        ToolRegistry._check_lazy_code(content, file_path)

        # Dependency Hallucination Checker
        ToolRegistry._check_dependency_hallucination(content, file_path, cwd)
        ToolRegistry._check_api_hallucination(content, cwd)

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

        ToolRegistry._backup_file(full_path, cwd)
        pass
        old_lines = []
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    old_lines = f.readlines()
            except:
                pass

        with open(full_path, "a", encoding="utf-8") as f:
            if not content.startswith("\n"):
                f.write("\n")
            f.write(content)
            
        # Syntax Check Blocker
        ToolRegistry._check_syntax(file_path, full_path, old_lines)
            
        return f"Successfully appended to {file_path}."

    @staticmethod
    def _execute_replace(file_path: str, replacements: list, cwd: str) -> str:
        
        full_path = os.path.join(cwd, file_path)
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    if len(f.readlines()) > 100:
                        raise ToolError(f"Validation Error: File {file_path} is too large (>100 lines) to overwrite completely. Use ReplaceBlock to edit specific lines and prevent Context Amnesia.")
            except:
                pass

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
                
            # Physical Blocker for Lazy Code
            ToolRegistry._check_lazy_code(new_str, file_path)

            # Dependency Hallucination Checker
            ToolRegistry._check_dependency_hallucination(new_str, file_path, cwd)
            ToolRegistry._check_api_hallucination(new_str, cwd)

            count = new_content.count(old_str)
            if count == 0:
                raise ToolError(f"Target string not found in file (or already replaced). Ensure exact whitespace match:\n{old_str}")
            elif count > 1:
                raise ToolError(f"Target string found {count} times. The old_string must be unique in the file to avoid ambiguous edits:\n{old_str}")
                
            new_content = new_content.replace(old_str, new_str, 1)
            applied += 1
            

        old_lines_count = len(content.splitlines())
        new_lines_count = len(new_content.splitlines())
        if old_lines_count > 0:
            deleted_ratio = (old_lines_count - new_lines_count) / old_lines_count
            if deleted_ratio > 0.3:
                raise Exception(f"ToolError: Security Blocker: Massive Deletion Guard. You are deleting {deleted_ratio*100:.1f}% of the file. This looks like a hallucination. Use ReplaceBlock to target specific lines carefully.")
        import difflib
        old_lines = content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(old_lines, new_lines, fromfile=file_path, tofile=file_path))
        
        ToolRegistry._backup_file(full_path, cwd)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        # Syntax Check Blocker
        ToolRegistry._check_syntax(file_path, full_path, old_lines)
            
        return f"Successfully applied {applied} replacements in {file_path}.\nDiff:\n{diff}"

    @staticmethod
    def _execute_replace_block(file_path: str, start_line: int, end_line: int, replacement_content: str, cwd: str) -> str:

        # Physical Blocker for Lazy Code
        ToolRegistry._check_lazy_code(replacement_content, file_path)

        # Dependency Hallucination Checker
        ToolRegistry._check_dependency_hallucination(replacement_content, file_path, cwd)
        ToolRegistry._check_api_hallucination(replacement_content, cwd)
        
        full_path = os.path.join(cwd, file_path)
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    if len(f.readlines()) > 100:
                        raise ToolError(f"Validation Error: File {file_path} is too large (>100 lines) to overwrite completely. Use ReplaceBlock to edit specific lines and prevent Context Amnesia.")
            except:
                pass

        if not os.path.exists(full_path):
            raise ToolError(f"File not found: {file_path}")
            
        with open(full_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        total_lines = len(lines)
        if start_line < 1 or start_line > total_lines:
            raise ToolError(f"start_line {start_line} is out of bounds (1-{total_lines}).")
        if end_line < start_line or end_line > total_lines:
            raise ToolError(f"end_line {end_line} is out of bounds or less than start_line.")
            
        # Run Secret Scanner
        try:
            from .secret_scanner import SecretScanner
            findings = SecretScanner.scan(replacement_content)
            if findings:
                raise ToolError(f"SecretScanner blocked replace: {len(findings)} secrets detected ({', '.join(findings)})")
        except ImportError:
            pass
            
        new_lines_to_insert = replacement_content.splitlines(keepends=True)
        if new_lines_to_insert and not new_lines_to_insert[-1].endswith('\n'):
            new_lines_to_insert[-1] += '\n'
            
        new_content_lines = lines[:start_line-1] + new_lines_to_insert + lines[end_line:]
        new_content = "".join(new_content_lines)
        
        ToolRegistry._check_ast_deletion("".join(lines), new_content, file_path)
        import difflib
        diff = "".join(difflib.unified_diff(lines, new_content_lines, fromfile=file_path, tofile=file_path))
        
        ToolRegistry._backup_file(full_path, cwd)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        # Syntax Check Blocker
        ToolRegistry._check_syntax(file_path, full_path, lines)
            
        return f"Successfully replaced lines {start_line}-{end_line} in {file_path}.\nDiff:\n{diff}"

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
            from .config import load_settings
            
            settings = load_settings()
            t_browser = settings.get("timeout_browser", 15000)
            t_browser = 0 if t_browser == 0 else t_browser
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=t_browser)
                
                screenshot_bytes = page.screenshot(type="jpeg", quality=50)
                b64_img = base64.b64encode(screenshot_bytes).decode('utf-8')
                
                text_content = page.evaluate("document.body.innerText")
                browser.close()
                
            pass
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

    @classmethod
    def _execute_get_code_outline(cls, file_path: str, cwd: str) -> str:
        """Extracts class/function signatures with line numbers."""
        import os, re
        
        full_path = os.path.join(cwd, file_path)
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    if len(f.readlines()) > 100:
                        raise ToolError(f"Validation Error: File {file_path} is too large (>100 lines) to overwrite completely. Use ReplaceBlock to edit specific lines and prevent Context Amnesia.")
            except:
                pass

        if not os.path.exists(full_path):
            return f"Error: File {file_path} not found."
            
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            outline = []
            pattern = re.compile(r"^\s*(def |class |function |const \w+\s*=\s*\(|type |func |struct |interface )")
            for i, line in enumerate(lines):
                if pattern.search(line):
                    outline.append(f"Line {i+1}: {line.strip()}")
                    
            if not outline:
                return f"No major structural blocks (functions/classes) found in {file_path} using generic regex."
            return "\n".join(outline)
        except Exception as e:
            return f"Error reading {file_path}: {e}"

    @classmethod
    def _execute_test_runner(cls, command: str, cwd: str) -> str:
        """Runs test commands safely and captures output."""
        import subprocess
        try:
            result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=60)
            output = f"Command: {command}\nExit Code: {result.returncode}\n"
            if result.stdout:
                output += f"\nSTDOUT:\n{result.stdout}"
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            return output
        except subprocess.TimeoutExpired:
            return f"Error: Test command '{command}' timed out after 60 seconds."
        except Exception as e:
            return f"Error running tests: {e}"
