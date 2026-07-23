from typing import List, Dict, Any, Optional
import os
import logging
from .nim_client import NimClient
from .lenient_parser import LenientParser
from .tools import ToolRegistry
from .permissions import PermissionEngine, PermissionMode
from .config import load_settings, save_global_setting
from .mcp_client import MCPManager
from .memory import MemoryManager

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are nimcode, an autonomous AI coding assistant.
You have access to a set of tools to read, write, and execute code.

CRITICAL INSTRUCTION FOR TOOL CALLING:
You must output exactly ONE tool call per turn, formatted exactly as a fenced XML block.
DO NOT use Markdown code blocks for the tool call. DO NOT output multiple tool calls in a single turn.

Format:
<tool_call>
{"tool": "ToolName", "args": {"arg1": "val1"}}
</tool_call>

Available Tools:
- Bash: {"tool": "Bash", "args": {"command": "string"}}
- Read: {"tool": "Read", "args": {"file_path": "string"}}
- Write: {"tool": "Write", "args": {"file_path": "string", "content": "string"}}
- Edit: {"tool": "Edit", "args": {"file_path": "string", "old_string": "string", "new_string": "string"}}
- Glob: {"tool": "Glob", "args": {"pattern": "string"}}
- Grep: {"tool": "Grep", "args": {"query": "string", "directory": "string"}}

Workspace Guidelines:
- When creating plans, store them inside the `.nimcode/plans/` directory (e.g., `.nimcode/plans/dino_game_plan.md`). Create this directory if it doesn't exist.
- When creating or learning new skills/memories, store them as markdown files inside the `.nimcode/skills/` directory.

When you have completely fulfilled the user's request and have no more tools to run, output the word TASK_COMPLETE.
"""

class Agent:
    def __init__(self, api_key: str, model: str = None, max_turns: int = 30, permission_mode: PermissionMode = PermissionMode.DEFAULT, max_tokens: int = 4000):
        # Load global settings
        self.settings = load_settings()
        self.model = model or self.settings.get("model", "meta/llama-3.1-70b-instruct")
        self.client = NimClient(api_key=api_key, model=self.model)
        
        # Initialize MCP Manager
        self.mcp = MCPManager(self.settings)
        
        # Base system prompt
        final_prompt = SYSTEM_PROMPT + self.mcp.get_system_prompt_additions()
        
        # Load skills if present
        skills_dir = os.path.join(os.getcwd(), ".nimcode", "skills")
        if os.path.exists(skills_dir) and os.path.isdir(skills_dir):
            loaded_skills = []
            for filename in os.listdir(skills_dir):
                if filename.endswith(".md"):
                    with open(os.path.join(skills_dir, filename), "r", encoding="utf-8") as f:
                        loaded_skills.append(f"--- SKILL: {filename} ---\n{f.read()}\n")
            if loaded_skills:
                final_prompt += "\n\nCRITICAL USER SKILLS & GUIDELINES:\n" + "\n".join(loaded_skills)
                logger.info(f"Loaded {len(loaded_skills)} custom skills from {skills_dir}")
                
        # Git context
        if os.path.exists(".git"):
            import subprocess
            try:
                branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
                status = subprocess.check_output(["git", "status", "-s"], text=True).strip()
                final_prompt += f"\n\nGIT CONTEXT:\nBranch: {branch}\nUncommitted changes:\n{status if status else 'None'}"
            except Exception as e:
                logger.error(f"Failed to load git context: {e}")

        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": final_prompt}
        ]
        self.max_turns = max_turns
        self.permission_engine = PermissionEngine(mode=permission_mode)
        self.memory = MemoryManager(max_tokens=max_tokens)

    def save_history(self):
        """Saves current conversation to NIMCODE.md"""
        try:
            import json
            with open("NIMCODE.md", "w", encoding="utf-8") as f:
                json.dump(self.messages, f)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def load_history(self):
        """Loads conversation from NIMCODE.md"""
        try:
            import json
            if os.path.exists("NIMCODE.md"):
                with open("NIMCODE.md", "r", encoding="utf-8") as f:
                    self.messages = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load history: {e}")

    async def _stream_response(self) -> str:
        from rich.live import Live
        from rich.markdown import Markdown
        from rich.console import Console
        
        c = Console()
        response_text = ""
        code_theme = self.settings.get("theme", "monokai")
        
        first_chunk = None
        
        with c.status("[bold cyan]🧠 NimCode is thinking...[/bold cyan]", spinner="dots"):
            iterator = self.client.chat(self.messages).__aiter__()
            try:
                first_chunk = await iterator.__anext__()
            except StopAsyncIteration:
                pass
            except KeyboardInterrupt:
                c.print("\n[yellow]Generation interrupted before starting.[/yellow]")
                return ""
                
        if first_chunk is None:
            return ""
            
        response_text = first_chunk
        
        with Live(Markdown(response_text, code_theme=code_theme), console=c, refresh_per_second=15) as live:
            try:
                async for chunk in iterator:
                    response_text += chunk
                    live.update(Markdown(response_text, code_theme=code_theme))
            except KeyboardInterrupt:
                live.update(Markdown(response_text + "\n\n*[yellow]Stream interrupted by user.[/yellow]*", code_theme=code_theme))
                c.print("\n[yellow]Generation interrupted.[/yellow]")
                
        # Approximate Token Tracker Update
        est_tokens = len(response_text) // 4
        if not hasattr(self, "session_tokens"):
            self.session_tokens = 0
        self.session_tokens += est_tokens
        
        # Approximate cost based on 70B typical rates ($3/1M tokens)
        cost = (self.session_tokens / 1000000) * 3.0
        c.print(f"[dim]Output est. tokens: {est_tokens} | Session Cost: ~${cost:.4f}[/dim]")
        
        # Context usage warning
        import json
        total_context_chars = sum(len(str(m.get("content", ""))) for m in self.messages)
        total_est_tokens = total_context_chars // 4
        max_context = 128000  # Assume standard Llama-3.1 128k context for now
        if total_est_tokens > max_context * 0.8:
            c.print("[bold yellow]⚠️ Context window is over 80% full. Consider running /compact or /clear.[/bold yellow]")
            
        return response_text

    async def run(self, initial_prompt: str = None) -> None:
        """Main execution loop for NimCode agent."""
        if hasattr(self.mcp, "connect_all"):
            await self.mcp.connect_all()
            
        if initial_prompt:
            self.messages.append({"role": "user", "content": initial_prompt})
        
        cwd = os.getcwd()
        turn = 0
        while turn < self.max_turns:
            turn += 1
            logger.info(f"--- Turn {turn} ---")
            
            # Compact context before calling API
            self.messages = self.memory.compact_context(self.messages)
            
            # We don't pass tools to the native API for fallback mode.
            # We expect the model to output <tool_call> block in the content.
            full_content = ""
            try:
                full_content = await self._stream_response()
            except Exception as e:
                logger.error(f"Error calling NIM API: {e}")
                break
            
            self.messages.append({"role": "assistant", "content": full_content})
            
            # Log turn to NIMCODE.md
            try:
                # We log the user's latest prompt, or the tool output
                last_user_msg = self.messages[-2].get("content", "") if len(self.messages) > 1 else ""
                MemoryManager.log_to_nimcode_md(turn, last_user_msg, full_content, cwd)
            except Exception as e:
                logger.error(f"Failed to log to NIMCODE.md: {e}")
            
            if "TASK_COMPLETE" in full_content:
                logger.info("Agent finished task.")
                break

            try:
                prose, tool_calls = LenientParser.process_model_response(full_content)
                
                if not tool_calls:
                    # Model responded with plain text but didn't say TASK_COMPLETE.
                    self.messages.append({"role": "user", "content": "Please continue. Use a tool or output TASK_COMPLETE."})
                    continue
                    
                # We execute the first tool call (ignoring others if it hallucinated multiple)
                tool_call = tool_calls[0]
                tool_name = tool_call.get("tool", "Unknown")
                
                logger.info(f"Checking permissions for tool: {tool_name}")
                if not self.permission_engine.check_permission(tool_call):
                    self.messages.append({
                        "role": "user",
                        "content": f"User explicitly denied permission to execute {tool_name}. Please choose another approach."
                    })
                    continue

                logger.info(f"Running tool: {tool_name}")
                from rich.console import Console
                c = Console()
                with c.status(f"[bold magenta]⚙️ Running {tool_name}...[/bold magenta]", spinner="bouncingBar"):
                    if not ToolRegistry.get_tool_schema(tool_name):
                        # Attempt MCP
                        try:
                            mcp_result = await self.mcp.call_tool_by_name(tool_name, tool_call.get("args", {}))
                            # mcp_result.content is a list of CallToolResult objects
                            result = "\n".join([str(c.text) for c in mcp_result.content if hasattr(c, 'text')])
                            if not result:
                                result = str(mcp_result)
                        except Exception as e:
                            result = f"Error executing MCP tool {tool_name}: {e}"
                    else:
                        result = ToolRegistry.execute(tool_call)
                        
                        # Auto-Linting
                        if tool_name in ["Write", "Edit"] and "Error" not in result:
                            file_path = tool_call.get("args", {}).get("file_path", "")
                            if file_path.endswith(".py"):
                                import subprocess
                                subprocess.run(["black", "-q", file_path], capture_output=True)
                            elif file_path.endswith((".js", ".ts", ".jsx", ".tsx")):
                                import subprocess
                                subprocess.run(["npx", "prettier", "--write", file_path], capture_output=True)
                
                # We simulate tool messages by adding a user message with the tool result.
                # In native mode this would be a "tool" role message, but for fallback mode, 
                # passing it as a user message makes it explicit.
                self.messages.append({
                    "role": "user", 
                    "content": f"Tool {tool_name} returned:\n{result}"
                })

            except Exception as e:
                logger.error(f"Error parsing/executing tool: {e}")
                self.messages.append({
                    "role": "user", 
                    "content": f"Your tool call was malformed or failed: {e}. Please fix the JSON syntax and try again."
                })
        
        if turn >= self.max_turns:
            logger.warning(f"Max turns ({self.max_turns}) reached.")
        
        self.save_history()

    async def start_repl(self) -> None:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import FileHistory
        import os
        from prompt_toolkit.styles import Style
        from rich.console import Console
        from rich.panel import Panel

        # Connect MCPs before REPL
        if hasattr(self.mcp, "connect_all"):
            await self.mcp.connect_all()
        
        history_path = os.path.join(os.getcwd(), ".nimcode", "history")
        if not os.path.exists(os.path.dirname(history_path)):
            os.makedirs(os.path.dirname(history_path), exist_ok=True)
            
        session = PromptSession(history=FileHistory(history_path))

        console = Console()
        
        # Build Dashboard Splash
        import subprocess
        project_name = os.path.basename(os.getcwd())
        branch = "Unknown"
        if os.path.exists(".git"):
            try:
                branch = subprocess.check_output(["git", "branch", "--show-current"], text=True, stderr=subprocess.DEVNULL).strip()
            except:
                pass
                
        splash_text = (
            f"[bold cyan]Project:[/bold cyan] {project_name}\n"
            f"[bold cyan]Branch:[/bold cyan] {branch}\n"
            f"[bold cyan]Model:[/bold cyan] {self.model}\n\n"
            f"Type [yellow]/help[/yellow] to see available commands."
        )
        console.print(Panel.fit(splash_text, title="[bold green]NimCode Agent[/bold green]", border_style="green"))

        style = Style.from_dict({
            'prompt': '#00aa00 bold',
        })
        session = PromptSession(style=style)
        
        while True:
            try:
                user_input = await session.prompt_async("NimCode> ")
                if user_input.lower() in ["/exit", "/quit"]:
                    self.save_history()
                    break
                elif user_input.strip() == "/help":
                    from rich.table import Table
                    table = Table(title="NimCode Commands", show_header=True, header_style="bold magenta")
                    table.add_column("Command", style="cyan", width=15)
                    table.add_column("Description", style="white")
                    
                    table.add_row("/help", "Show this help menu")
                    table.add_row("/plan", "Enter planning mode (safe mode)")
                    table.add_row("/code", "Enter coding mode (all tools enabled)")
                    table.add_row("/models", "Select NVIDIA NIM model")
                    table.add_row("/theme <name>", "Change syntax theme (e.g., monokai)")
                    table.add_row("/clear", "Clear current context history")
                    table.add_row("/compact", "Compact context to save tokens")
                    table.add_row("/commit", "Auto-generate git commit message")
                    table.add_row("/fix <cmd>", "Run command and fix errors automatically")
                    table.add_row("/testgen <file>", "Generate 100% coverage tests for a file")
                    table.add_row("/vision", "Capture screen and analyze with Vision AI")
                    table.add_row("/voice", "Speak to NimCode (records for 5 seconds)")
                    table.add_row("/index", "Index project files for Semantic Search")
                    table.add_row("/exit", "Exit NimCode")
                    
                    console.print(table)
                    continue
                elif user_input.strip() == "/clear":
                    self.messages = [self.messages[0]]
                    console.print("[yellow]Context cleared.[/yellow]")
                    continue
                elif user_input.strip() == "/compact":
                    self.messages = self.memory.compact_context(self.messages)
                    console.print("[yellow]Context compacted.[/yellow]")
                    continue
                elif user_input.strip() == "/plan":
                    console.print("[bold blue]Entering Plan mode.[/bold blue] Mutating tools will be denied by default.")
                    self.permission_engine.mode = PermissionMode.DEFAULT
                    self.messages.append({"role": "system", "content": "You are now in planning mode. Use Read tools to explore. Then use the Write tool to write a markdown plan file inside the '.nimcode/plans/' directory (e.g., '.nimcode/plans/feature_x_plan.md'). Do NOT use Bash or Edit tools."})
                    continue
                elif user_input.strip() == "/code":
                    console.print("[bold magenta]Entering Code mode.[/bold magenta] Standard permissions restored.")
                    self.messages.append({"role": "system", "content": "You are now in coding mode. You may use all available tools."})
                    continue
                elif user_input.strip().startswith("/theme"):
                    parts = user_input.strip().split()
                    if len(parts) > 1:
                        self.settings["theme"] = parts[1]
                        save_global_setting("theme", parts[1])
                        console.print(f"[green]Theme updated to '{parts[1]}'[/green]")
                    else:
                        console.print("[yellow]Usage: /theme <name> (e.g., /theme monokai)[/yellow]")
                    continue
                elif user_input.strip() == "/models":
                    console.print("[bold yellow]Fetching available models from NVIDIA NIM...[/bold yellow]")
                    models = await self.client.get_available_models()
                    for i, m in enumerate(models):
                        console.print(f"[{i+1}] {m}")
                    
                    selection = await session.prompt_async("Select a model by number (or press enter to cancel): ")
                    if selection.strip().isdigit():
                        idx = int(selection.strip()) - 1
                        if 0 <= idx < len(models):
                            selected_model = models[idx]
                            self.client.model = selected_model
                            self.model = selected_model
                            save_global_setting("model", selected_model)
                            console.print(f"[bold green]Model changed to: {selected_model}[/bold green]")
                        else:
                            console.print("[red]Invalid selection.[/red]")
                    else:
                        console.print("[yellow]Model selection cancelled.[/yellow]")
                    continue
                elif user_input.strip() == "/commit":
                    if not os.path.exists(".git"):
                        console.print("[red]Not a git repository.[/red]")
                        continue
                    console.print("[bold yellow]Generating commit message...[/bold yellow]")
                    import subprocess
                    diff = subprocess.check_output(["git", "diff", "--cached"], text=True)
                    if not diff:
                        diff = subprocess.check_output(["git", "diff"], text=True)
                    if not diff:
                        console.print("[yellow]No changes to commit.[/yellow]")
                        continue
                    prompt = f"Write a concise, professional git commit message for these changes:\n\n{diff[:3000]}\n\nOnly output the commit message string, nothing else."
                    msg = await self.client.chat_one_shot(prompt)
                    console.print(f"[bold green]Suggested Commit:[/bold green]\n{msg}")
                    console.print("\nTo commit, run: [bold cyan]git commit -m \"...\"[/bold cyan]")
                    continue
                elif user_input.strip().startswith("/testgen"):
                    parts = user_input.strip().split(" ", 1)
                    if len(parts) > 1:
                        filepath = parts[1]
                        if os.path.exists(filepath):
                            console.print(f"[bold cyan]Generating tests for {filepath}...[/bold cyan]")
                            prompt = f"Read the file `{filepath}` using the Read tool if necessary. Then write a comprehensive suite of unit tests for it with 100% coverage. Write the tests to a new file (e.g. `test_{os.path.basename(filepath)}` for Python). Make sure they pass."
                            await self.run(prompt)
                        else:
                            console.print(f"[red]File {filepath} not found.[/red]")
                    else:
                        console.print("[yellow]Usage: /testgen <filepath>[/yellow]")
                    continue
                elif user_input.strip().startswith("/fix"):
                    parts = user_input.strip().split(" ", 1)
                    if len(parts) < 2:
                        console.print("[yellow]Usage: /fix <command> (e.g. /fix pytest)[/yellow]")
                        continue
                    
                    cmd = parts[1]
                    console.print(f"[bold cyan]Running {cmd}...[/bold cyan]")
                    import subprocess
                    for attempt in range(3):
                        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                        if result.returncode == 0:
                            console.print("[bold green]Command passed![/bold green]")
                            break
                        else:
                            console.print(f"[bold red]Command failed (attempt {attempt+1}/3). Fixing...[/bold red]")
                            await self.run(f"The command `{cmd}` failed with exit code {result.returncode}.\nStderr: {result.stderr[-2000:]}\nStdout: {result.stdout[-2000:]}\nFix the code so it passes.")
                    continue
                
                # Check for aliases
                aliases = self.settings.get("aliases", {})
                first_word = user_input.strip().split()[0] if user_input.strip() else ""
                if first_word in aliases:
                    user_input = user_input.replace(first_word, aliases[first_word], 1)
                    console.print(f"[dim]Aliased to: {user_input}[/dim]")

                if user_input.strip().startswith("/config"):
                    parts = user_input.strip().split()
                    if len(parts) >= 3 and parts[1] == "set":
                        key = parts[2]
                        val = " ".join(parts[3:])
                        self.settings[key] = val
                        save_global_setting(key, val)
                        console.print(f"[bold green]✓ Setting '{key}' updated to '{val}'[/bold green]")
                    else:
                        console.print("[yellow]Usage: /config set <key> <value>[/yellow]")
                    continue
                elif user_input.strip().startswith("/alias"):
                    parts = user_input.strip().split("=", 1)
                    if len(parts) == 2:
                        name = parts[0].replace("/alias", "").strip()
                        cmd = parts[1].strip()
                        aliases = self.settings.get("aliases", {})
                        aliases[name] = cmd
                        self.settings["aliases"] = aliases
                        save_global_setting("aliases", aliases)
                        console.print(f"[bold green]✓ Alias '{name}' set to '{cmd}'[/bold green]")
                    else:
                        console.print("[yellow]Usage: /alias <name> = <command>[/yellow]")
                    continue
                elif user_input.strip().startswith("/add"):
                    parts = user_input.strip().split(" ", 1)
                    if len(parts) > 1:
                        filepath = parts[1]
                        try:
                            with open(filepath, "r", encoding="utf-8") as f:
                                content = f.read()
                            self.messages.append({"role": "system", "content": f"Pinned File ({filepath}):\n\n{content}"})
                            console.print(f"[bold green]✓ {filepath} pinned to context.[/bold green]")
                        except Exception as e:
                            console.print(f"[bold red]Failed to read {filepath}: {e}[/bold red]")
                    else:
                        console.print("[yellow]Usage: /add <filepath>[/yellow]")
                    continue
                elif user_input.strip().startswith("/rewind"):
                    parts = user_input.strip().split(" ", 1)
                    turns = 1
                    if len(parts) > 1 and parts[1].isdigit():
                        turns = int(parts[1])
                    
                    items_to_remove = turns * 2
                    if len(self.messages) > items_to_remove:
                        self.messages = self.messages[:-items_to_remove]
                        console.print(f"[bold green]⏪ Rewound {turns} turns.[/bold green]")
                    else:
                        self.messages = [self.messages[0]]
                        console.print("[bold green]⏪ Rewound to beginning.[/bold green]")
                    continue
                elif user_input.strip() == "/fork":
                    import subprocess
                    import time
                    branch_name = f"nimcode-fork-{int(time.time())}"
                    try:
                        subprocess.run(["git", "checkout", "-b", branch_name], check=True, capture_output=True)
                        console.print(f"[bold green]🔀 Forked conversation to new git branch: {branch_name}[/bold green]")
                    except subprocess.CalledProcessError:
                        console.print("[bold red]Failed to create branch. Are you in a git repo with commits?[/bold red]")
                    continue
                elif user_input.strip() == "/vision":
                    console.print("[bold cyan]👁️ Capturing screen...[/bold cyan]")
                    import pyautogui
                    import io
                    import base64
                    try:
                        screenshot = pyautogui.screenshot()
                        buffered = io.BytesIO()
                        screenshot.thumbnail((1920, 1080))
                        screenshot.save(buffered, format="JPEG", quality=80)
                        img_str = base64.b64encode(buffered.getvalue()).decode()
                        
                        console.print("[bold cyan]🧠 Analyzing image with Vision Model...[/bold cyan]")
                        vision_response = await self.client.chat_vision(img_str, "Describe what is on the screen in detail. If there is code, explain what it does or if there are any visible errors.")
                        console.print(f"\n[bold magenta]Vision Analysis:[/bold magenta]\n{vision_response}\n")
                        self.messages.append({"role": "system", "content": f"The user provided a screenshot. The vision model analyzed it as: {vision_response}"})
                    except Exception as e:
                        console.print(f"[bold red]Vision failed: {e}[/bold red]")
                    continue
                elif user_input.strip() == "/voice":
                    console.print("[bold cyan]🎤 Recording for 5 seconds... Speak now![/bold cyan]")
                    import sounddevice as sd
                    import soundfile as sf
                    import os
                    import speech_recognition as sr
                    try:
                        fs = 16000
                        seconds = 5
                        myrecording = sd.rec(int(seconds * fs), samplerate=fs, channels=1)
                        sd.wait()
                        console.print("[bold cyan]⏳ Processing audio...[/bold cyan]")
                        sf.write('temp_voice.wav', myrecording, fs)
                        
                        r = sr.Recognizer()
                        with sr.AudioFile('temp_voice.wav') as source:
                            audio = r.record(source)
                        try:
                            transcription = r.recognize_google(audio)
                            console.print(f"[bold green]🗣️ You said:[/bold green] {transcription}")
                            await self.run(transcription)
                        except sr.UnknownValueError:
                            console.print("[bold red]Could not understand audio.[/bold red]")
                    except Exception as e:
                        console.print(f"[bold red]Voice failed: {e}[/bold red]")
                    continue
                elif user_input.strip() == "/index":
                    console.print("[bold cyan]🔍 Indexing project files for Semantic Search...[/bold cyan]")
                    self.search_index = {}
                    import glob
                    import os
                    for ext in ["*.py", "*.js", "*.ts", "*.md"]:
                        for file in glob.glob(f"**/{ext}", recursive=True):
                            if "node_modules" in file or "venv" in file or ".git" in file:
                                continue
                            try:
                                with open(file, "r", encoding="utf-8") as f:
                                    self.search_index[file] = f.read()
                            except:
                                pass
                    console.print(f"[bold green]✓ Indexed {len(self.search_index)} files.[/bold green]")
                    # Expose the index as a string summary for the agent to know what's there
                    index_summary = ", ".join(self.search_index.keys())
                    self.messages.append({"role": "system", "content": f"Project is indexed. Available indexed files: {index_summary}"})
                    continue
                elif user_input.strip().startswith("/"):
                    import difflib
                    valid_commands = ["/help", "/plan", "/code", "/models", "/theme", "/clear", "/compact", "/commit", "/fix", "/exit", "/quit", "/config", "/alias", "/add", "/rewind", "/fork", "/testgen", "/vision", "/voice", "/index"]
                    cmd_name = user_input.strip().split()[0]
                    matches = difflib.get_close_matches(cmd_name, valid_commands, n=1, cutoff=0.5)
                    if matches:
                        console.print(f"[yellow]Unknown command '{cmd_name}'. Did you mean [bold cyan]{matches[0]}[/bold cyan]?[/yellow]")
                    else:
                        console.print(f"[red]Unknown command '{cmd_name}'. Type /help for a list of commands.[/red]")
                    continue

                if not user_input.strip():
                    continue
                    
                await self.run(user_input)
                
            except (EOFError, KeyboardInterrupt):
                break

