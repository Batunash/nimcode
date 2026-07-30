import os
import sys
import asyncio
import shutil
import json
import logging
from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns
from rich.table import Table
from rich.live import Live
from rich.markdown import Markdown

from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers.python import PythonLexer
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import radiolist_dialog

from .config import save_global_setting
from .permissions import PermissionMode

class NimcodeREPL:
    def __init__(self, agent):
        self.agent = agent
        
    @property
    def client(self):
        return self.agent.client
        
    @property
    def permission_engine(self):
        return self.agent.permission_engine
        
    @property
    def memory(self):
        return self.agent.memory
        
    @property
    def messages(self):
        return self.agent.messages
        
    @messages.setter
    def messages(self, value):
        self.agent.messages = value

    @property
    def model(self):
        return self.agent.model

    @model.setter
    def model(self, value):
        self.agent.model = value
        self.client.model = value
        
    @property
    def settings(self):
        return self.agent.settings

    @property
    def analytics(self):
        return self.agent.analytics


    @property
    def mcp(self):
        return self.agent.mcp

    async def start_repl(self) -> None:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import FileHistory
        import os
        from prompt_toolkit.styles import Style

        # Connect MCPs before REPL
        if hasattr(self.agent.mcp, "connect_all"):
            await self.agent.mcp.connect_all()
            
        # Load Plugins
        from .plugin_manager import PluginManager
        self.plugin_manager = PluginManager()
        
        history_path = os.path.join(os.getcwd(), ".nimcode", "history")
        if not os.path.exists(os.path.dirname(history_path)):
            os.makedirs(os.path.dirname(history_path), exist_ok=True)
            
        session = PromptSession(history=FileHistory(history_path))

        console = Console()
        
        self.update_available = None
        async def check_update():
            from .updater import AutoUpdater
            latest = await AutoUpdater.check_for_update()
            if latest:
                self.update_available = latest
        
        import asyncio
        asyncio.create_task(check_update())
        
        # --- Project Trust Check ---
        cwd = os.getcwd()
        trusted_projects = self.settings.get("trusted_projects", [])
        if cwd not in trusted_projects:
            console.print("\nQuick safety check: Is this a project you created or one you trust? (Like your own code, a well-known open source project, or work from your team). If not, take a moment to review what's in this folder first.\n")
            console.print("NimCode'll be able to read, edit, and execute files here.\n")
            console.print("[dim]Security guide[/dim]\n")
            try:
                ans = input("> 1. Yes, I trust this folder (y/n) [y]: ").strip().lower()
                if not ans or ans == 'y' or ans == '1' or ans == 'yes':
                    trusted_projects.append(cwd)
                    self.settings["trusted_projects"] = trusted_projects
                    save_global_setting("trusted_projects", trusted_projects)
                    self.permission_engine.mode = PermissionMode.BYPASS
                    console.print("[green]√ Folder trusted.[/green]\n")
                else:
                    console.print("[yellow]Folder not trusted. Prompts will be required.[/yellow]\n")
            except (EOFError, KeyboardInterrupt):
                pass
        else:
            self.permission_engine.mode = PermissionMode.BYPASS
            
        # Build Dashboard Splash
        from rich.table import Table
        from rich.box import ROUNDED
        
        table = Table(box=None, show_header=False, expand=True, padding=(0, 2))
        table.add_column("Left", justify="center", ratio=1)
        table.add_column("Right", ratio=2)
        
        logo = (
            "[bold green]   ███╗   ██╗   [/bold green]\n"
            "[bold green]   ████╗  ██║   [/bold green]\n"
            "[bold green]   ██╔██╗ ██║   [/bold green]\n"
            "[bold green]   ██║╚██╗██║   [/bold green]\n"
            "[bold green]   ██║ ╚████║   [/bold green]\n"
            "[bold green]   ╚═╝  ╚═══╝   [/bold green]"
        )
        
        import os
        import subprocess
        import shutil
        
        cwd_short = os.getcwd()
        if len(cwd_short) > 40:
            cwd_short = "..." + cwd_short[-37:]
            
        try:
            branch = subprocess.check_output(["git", "branch", "--show-current"], stderr=subprocess.DEVNULL).decode().strip()
            branch_info = f" [green]({branch})[/green]"
        except Exception:
            branch_info = ""
            
        try:
            _, _, free = shutil.disk_usage(os.getcwd())
            disk_gb = free // (2**30)
            disk_info = f"\n[dim]Disk Free: {disk_gb} GB[/dim]"
        except Exception:
            disk_info = ""
            
        try:
            import coverage
            cov = coverage.Coverage()
            cov.load()
            import sys, os
            # We must suppress the report output
            with open(os.devnull, 'w') as f:
                total_cov = cov.report(file=f)
            bar_len = 10
            filled = int(bar_len * (total_cov / 100))
            bar = "█" * filled + "░" * (bar_len - filled)
            
            # Determine color based on coverage
            cov_color = "red" if total_cov < 50 else "yellow" if total_cov < 80 else "green"
            coverage_info = f"\n[dim]Test Coverage:[/dim] [{cov_color}][{bar}] {total_cov:.1f}%[/{cov_color}]"
        except Exception:
            coverage_info = ""
            
        left_content = f"\n[bold white]Welcome back![/bold white]\n\n{logo}\n\n[dim]{self.model}[/dim]\n[dim]{cwd_short}{branch_info}[/dim]{disk_info}{coverage_info}"
        
        # Play a subtle startup sound if on Windows
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_OK)
        except Exception:
            pass
        
        right_content = "[bold orange3]Tips for getting started[/bold orange3]\nRun [cyan]/help[/cyan] to see available commands and shortcuts.\nUse [cyan]/models[/cyan] to change the current model.\n\n[bold orange3]What's new[/bold orange3]\n• Added native multiline REPL support (Alt+Enter for newline).\n• Reverted to classic UI.\n• More robust JSON parsing for tools."
        
        table.add_row(left_content, right_content)
        panel = Panel(table, title="[bold orange3]NimCode v0.2.0[/bold orange3]", border_style="orange3", box=ROUNDED, title_align="left")
        console.print(panel)
        console.print()

        style = Style.from_dict({
            'prompt': '#00ffff bold',
            'bottom-toolbar': '#999999 bg:#1e1e1e',
            'toolbar_title': '#ffffff bg:#5c2d91 bold',
            'toolbar_text': '#cccccc bg:#1e1e1e',
            'toolbar_shortcut': '#888888 bg:#2d2d2d',
            
            # Claude Code inspired Autocompletion Menu
            'completion-menu': 'bg:#2b2b2b #eeeeee',
            'completion-menu.completion': 'bg:#2b2b2b #eeeeee',
            'completion-menu.completion.current': 'bg:#5c2d91 #ffffff bold',
            'scrollbar.background': 'bg:#1e1e1e',
            'scrollbar.button': 'bg:#5c2d91',
            
            # Auto-suggestion (greyed out ghost text)
            'auto-suggestion': '#666666 italic',
        })
        
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.keys import Keys
        
        kb = KeyBindings()
        
        @kb.add(Keys.Enter)
        def _(event):
            event.current_buffer.validate_and_handle()
            
        @kb.add(Keys.Escape, Keys.Enter)
        def _(event):
            event.current_buffer.insert_text('\n')
            
        @kb.add('c-p')
        def _(event):
            event.current_buffer.text = '/plan'
            event.current_buffer.validate_and_handle()
            
        @kb.add('c-g')
        def _(event):
            event.current_buffer.text = '/guardian'
            event.current_buffer.validate_and_handle()
            
        def bottom_toolbar():
            tokens = getattr(self, 'session_tokens', 0)
            cost = (tokens / 1000000) * 3.0
            mode = self.permission_engine.mode.value
            effort = getattr(self, 'effort', 'Medium')
            
            goal_ui = ""
            if getattr(self, 'goal_total_steps', 0) > 0:
                pct = int((getattr(self, 'goal_current_step', 0) / getattr(self, 'goal_total_steps', 1)) * 100)
                filled = int(10 * (pct / 100))
                bar = "█" * filled + "░" * (10 - filled)
                goal_ui = f" | Goal: [{bar}] {pct}% "
                
            update_str = f" | Update Available: v{self.update_available} (Type /update)" if getattr(self, 'update_available', None) else ""
                
            return [
                ('class:toolbar_title', ' NimCode '),
                ('class:toolbar_text', f' Model: {self.model} | Mode: {mode} | Tokens: {tokens} | Cost: ${cost:.4f} | Effort: {effort}{goal_ui}{update_str}'),
                ('class:toolbar_shortcut', ' [Alt+Enter] multiline '),
            ]
        from prompt_toolkit.completion import Completer, Completion, PathCompleter
        
        class SlashCompleter(Completer):
            def __init__(self, plugin_commands=[]):
                self.commands = [
                    '/help', '/plan', '/code', '/models', '/theme', '/clear', '/compact', 
                    '/commit', '/fix', '/testgen', '/vision', '/voice', '/index', '/exit', 
                    '/quit', '/learn', '/cost', '/effort', '/thinking', '/add', '/research', 
                    '/swarm', '/tdd', '/mcp', '/rewind', '/fork', '/grill-me', '/teleport', 
                    '/buddy', '/ultraplan', '/bughunter', '/security-review', '/doctor', 
                    '/permissions', '/graph', '/guardian', '/thinkback', '/autofix-pr', 
                    '/terraform-god', '/sql-tune', '/decompile'
                ]
                # Add dynamic plugin commands
                self.commands.extend([f"/{cmd}" for cmd in plugin_commands])
                self.subcommands = {
                    '/theme': ['monokai', 'dracula', 'nord', 'github'],
                    '/effort': ['Low', 'Medium', 'High'],
                    '/mcp': ['install'],
                    '/permissions': ['auto', 'bypass', 'default']
                }
                self.path_completer = PathCompleter()

            def get_completions(self, document, complete_event):
                text = document.text_before_cursor
                parts = text.split()
                
                if not parts:
                    return

                if len(parts) == 1 or (len(parts) == 2 and text.endswith(' ')):
                    if not text.endswith(' '):
                        word = parts[0]
                        for c in self.commands:
                            if c.startswith(word):
                                yield Completion(c, start_position=-len(word))
                    else:
                        cmd = parts[0]
                        if cmd in self.subcommands:
                            for sub in self.subcommands[cmd]:
                                yield Completion(sub, start_position=0)
                        elif cmd in ['/testgen', '/add', '/teleport', '/decompile']:
                            yield from self.path_completer.get_completions(document, complete_event)
                            
                elif len(parts) >= 2:
                    cmd = parts[0]
                    word = parts[-1] if not text.endswith(' ') else ''
                    
                    if cmd in self.subcommands:
                        for sub in self.subcommands[cmd]:
                            if sub.startswith(word):
                                yield Completion(sub, start_position=-len(word))
                    elif cmd in ['/testgen', '/add', '/teleport', '/decompile']:
                        yield from self.path_completer.get_completions(document, complete_event)

        command_completer = SlashCompleter(self.plugin_manager.get_command_names())
        
        from prompt_toolkit.lexers import PygmentsLexer
        from pygments.lexers.shell import BashLexer
        from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
            
        session = PromptSession(
            style=style, 
            key_bindings=kb, 
            multiline=True, 
            bottom_toolbar=bottom_toolbar, 
            completer=command_completer,
            lexer=PygmentsLexer(BashLexer),
            auto_suggest=AutoSuggestFromHistory()
        )
        
        from .watcher import WorkspaceWatcher
        watcher = WorkspaceWatcher(self.agent, os.getcwd())
        watcher.start()
        
        while True:
            try:
                user_input = await session.prompt_async("❯ ")
                if user_input.lower() in ["/exit", "/quit"]:
                    self.agent.save_history()
                    watcher.stop()
                    break
                
                user_input = user_input.strip()
                if user_input.lower() in ["help", "quit", "exit", "clear"]:
                    user_input = "/" + user_input.lower()

                if user_input == "/help":
                    from rich.table import Table
                    table = Table(title="NimCode Commands", show_header=True, header_style="bold magenta")
                    table.add_column("Command", style="cyan", width=15)
                    table.add_column("Description", style="white")
                    
                    table.add_row("/help", "Show this help menu")
                    table.add_row("/plan", "Enter planning mode (safe mode)")
                    table.add_row("/code", "Enter coding mode (all tools enabled)")
                    table.add_row("/trust", "Enter trust mode (runs all tools without permission)")
                    table.add_row("/untrust", "Disable trust mode (ask for permission)")
                    table.add_row("/models", "Select NVIDIA NIM model")
                    table.add_row("/theme <name>", "Change syntax theme (e.g., monokai)")
                    table.add_row("/clear", "Clear current context history")
                    table.add_row("/compact", "Compact context to save tokens")
                    table.add_row("/commit", "Auto-generate git commit message")
                    table.add_row("/map", "Generate semantic project architecture map")
                    table.add_row("/context", "View and manage loaded context window")
                    table.add_row("/undo", "Undo the last file edit made by Nimcode")
                    table.add_row("/delegate <role> <task>", "Spawn a sub-agent to handle a task")
                    table.add_row("/review", "Code review all unstaged git changes")
                    table.add_row("/fix <cmd>", "Run command and fix errors automatically")
                    table.add_row("/testgen <file>", "Generate 100% coverage tests for a file")
                    table.add_row("/vision", "Capture screen and analyze with Vision AI")
                    table.add_row("/voice", "Speak to NimCode (records for 5 seconds)")
                    table.add_row("/index", "Index project files for Semantic Search")
                    table.add_row("/exit", "Exit NimCode")
                    
                    # Add plugin commands to help
                    plugin_cmds = self.plugin_manager.get_command_names()
                    if plugin_cmds:
                        table.add_row("---", "---")
                        for pcmd in plugin_cmds:
                            table.add_row(f"/{pcmd}", "(Plugin Command)")
                    
                    console.print(table)
                    continue
                elif user_input.strip().startswith("/theme"):
                    parts = user_input.strip().split()
                    if len(parts) > 1:
                        new_theme = parts[1]
                        self.settings["theme"] = new_theme
                        save_global_setting("theme", new_theme)
                        console.print(f"[bold green]✨ Theme changed to '{new_theme}'.[/bold green]")
                    else:
                        current = self.settings.get("theme", "monokai")
                        console.print(f"[bold]Current theme:[/bold] {current}")
                        console.print("[dim]Usage: /theme <theme_name>[/dim]")
                    continue
                elif user_input.strip() == "/clear":
                    self.messages = [self.messages[0]]
                    console.print("[yellow]Context cleared.[/yellow]")
                    continue
                elif user_input.strip() == "/context":
                    from rich.table import Table
                    ctx_table = Table(title="Loaded Context Window", show_header=True, header_style="bold cyan")
                    ctx_table.add_column("Index", style="dim", width=5)
                    ctx_table.add_column("Role", style="magenta", width=10)
                    ctx_table.add_column("Content Snippet", style="white")
                    ctx_table.add_column("Est. Tokens", justify="right", style="green", width=12)
                    
                    total_tokens = 0
                    for i, msg in enumerate(self.messages):
                        content_str = str(msg.get("content", ""))
                        snippet = content_str[:60].replace("\n", " ") + ("..." if len(content_str) > 60 else "")
                        tokens = len(content_str) // 4
                        total_tokens += tokens
                        ctx_table.add_row(str(i), msg.get("role", "unknown"), snippet, f"{tokens:,}")
                        
                    console.print(ctx_table)
                    console.print(f"[bold]Total Context Size:[/bold] {total_tokens:,} tokens (Approx {(total_tokens/128000)*100:.1f}% of 128k limit)")
                    console.print("[dim]Use /compact to compress history or /clear to reset.[/dim]")
                    continue
                elif user_input.strip() == "/compact":
                    self.messages = self.memory.compact_context(self.messages)
                    console.print("[yellow]Context compacted.[/yellow]")
                    continue
                elif user_input.strip() == "/undo":
                    from .tools import ToolRegistry
                    result = ToolRegistry._execute_undo(os.getcwd())
                    if result.startswith("Successfully"):
                        console.print(f"[bold green]✨ {result}[/bold green]")
                    else:
                        console.print(f"[bold red]{result}[/bold red]")
                    continue
                elif user_input.strip() == "/plan":
                    # Save current mode so /code can restore it when leaving plan mode.
                    if not getattr(self, "_in_plan_mode", False):
                        self._pre_plan_mode = self.permission_engine.mode
                    self._in_plan_mode = True
                    # Respect /trust: never downgrade BYPASS. Otherwise AUTO = safe reads free, writes restricted.
                    if self.permission_engine.mode != PermissionMode.BYPASS:
                        self.permission_engine.mode = PermissionMode.AUTO
                    console.print("[bold blue]Entering Plan mode.[/bold blue] Read tools are free; mutating tools (Bash/Edit/Write) are restricted.")
                    self.messages.append({"role": "system", "content": (
                        "You are now in PLANNING MODE.\n"
                        "1. Identify the task type: Is it a 'Bug Fix / Minor Feature' OR a 'From-Scratch / Major Architecture' task?\n"
                        "2. IF it is a 'Bug Fix / Minor Feature':\n"
                        "   - Write the plan directly to '.nimcode/plans/<name_timestamp>.md'.\n"
                        "   - Use this strict technical structure: # Title, ## Context, ## Root Cause Analysis, ## Execution Plan (file-by-file with line numbers/snippets), ## Verification.\n"
                        "3. IF it is a 'From-Scratch / Major Architecture' task:\n"
                        "   - Work AUTONOMOUSLY in a loop using your file-writing tools. Do NOT ask the user for approval.\n"
                        "   - Step A: Explore the project/SDDs.\n"
                        "   - Step B: Write a 'Master Architecture Document' to '.nimcode/plans/<name>_master.md' (Tech Stack, Repo Structure, DB Schema, High-level Phase list).\n"
                        "   - Step C: For EACH Phase, autonomously write a SEPARATE, EXTREMELY DETAILED execution plan file (e.g. '.nimcode/plans/<name>_phase1.md'). Each phase plan must include exact file paths, pseudo-code for every function, and strict step-by-step logic. Do this in a continuous tool-use loop.\n"
                        "   - Step D: After writing all phase files, overwrite '.nimcode/active_plan.txt' with the master plan's path.\n"
                        "4. General Rules:\n"
                        "   - Quote real names, modules, and requirements. Do not invent generic projects.\n"
                        "   - NEVER output a generic software-lifecycle template (Phase1: MVP / Design / Development) unless instructed. Focus on code, DB schemas, and technical choices.\n"
                        "   - After writing any plan file, overwrite '.nimcode/active_plan.txt' with the file's path."
                    )})
                    continue
                elif user_input.strip().startswith("/teleport"):
                    parts = user_input.strip().split(" ", 1)
                    if len(parts) > 1:
                        target = parts[1].strip()
                        try:
                            os.chdir(target)
                            console.print(f"[bold green]✨ Teleported context to: {os.getcwd()}[/bold green]")
                        except Exception as e:
                            console.print(f"[red]Teleport failed: {e}[/red]")
                    else:
                        console.print("[yellow]Usage: /teleport <path>[/yellow]")
                    continue
                elif user_input.strip().startswith("/buddy"):
                    console.print("[bold blue]🤖 Buddy spawned. It is now watching your context.[/bold blue]")
                    self.messages.append({"role": "system", "content": "You are now operating in Buddy Mode. You should act as an observant pair programmer. Point out improvements proactively without making changes directly unless asked."})
                    continue
                elif user_input.strip().startswith("/ultraplan"):
                    task = user_input[len("/ultraplan"):].strip()
                    if not task:
                        console.print("[yellow]Usage: /ultraplan <task>[/yellow]")
                        continue
                    console.print("[bold magenta]🧠 Generating Ultraplan (Dependency Graph)...[/bold magenta]")
                    self.messages.append({"role": "user", "content": f"Generate a master ultra-detailed, dependency-graphed execution plan for the following task. Ensure step-by-step logical isolation:\n\nTask: {task}"})
                    user_input = task # Flow into the execution loop
                elif user_input.strip() == "/map":
                    console.print("[bold magenta]🗺️ Generating Semantic Project Map...[/bold magenta]")
                    import os
                    from pathlib import Path
                    
                    def generate_tree(dir_path, prefix=""):
                        tree_str = ""
                        path = Path(dir_path)
                        items = sorted([p for p in path.iterdir() if p.name not in ['.git', '__pycache__', 'venv', 'node_modules', '.nimcode']], key=lambda x: (not x.is_dir(), x.name))
                        
                        for i, item in enumerate(items):
                            is_last = (i == len(items) - 1)
                            connector = "└── " if is_last else "├── "
                            tree_str += f"{prefix}{connector}{item.name}\n"
                            if item.is_dir():
                                extension = "    " if is_last else "│   "
                                tree_str += generate_tree(item, prefix + extension)
                        return tree_str
                        
                    raw_tree = generate_tree(os.getcwd())
                    prompt = f"Analyze the following directory tree and add a very brief (1-line) semantic description next to each important file explaining what it does. Format the output back as a tree using rich text formatting (e.g. `├── repl.py [dim]- main TUI loop[/dim]`). Only output the tree.\n\nTree:\n{raw_tree}"
                    
                    self.messages.append({"role": "user", "content": prompt})
                    user_input = prompt # Flow into the execution loop
                elif user_input.strip() == "/review":
                    import subprocess
                    console.print("[bold magenta]🔍 Preparing Code Review...[/bold magenta]")
                    diff_unstaged = subprocess.run(["git", "diff"], capture_output=True, text=True).stdout or ""
                    diff_staged = subprocess.run(["git", "diff", "--staged"], capture_output=True, text=True).stdout or ""
                    full_diff = diff_staged + "\n" + diff_unstaged
                    if not full_diff.strip():
                        console.print("[yellow]No git changes found to review.[/yellow]")
                        continue
                        
                    prompt = f"You are a Principal Software Engineer conducting a thorough code review. Please review the following git diff. Point out bugs, security issues, performance bottlenecks, and bad practices. Be brutal but constructive.\n\nDiff:\n{full_diff}"
                    self.messages.append({"role": "user", "content": prompt})
                    user_input = prompt # Flow into execution loop
                elif user_input.strip().startswith("/bughunter"):
                    console.print("[bold red]🐛 BugHunter activated. Aggressive static analysis enabled.[/bold red]")
                    self.messages.append({"role": "system", "content": "You are BugHunter. Analyze the codebase deeply. Look for subtle edge cases, off-by-one errors, race conditions, type misalignments, and memory leaks. Use the grep tool to find 'TODO' and 'FIXME' tags."})
                    continue
                elif user_input.strip() == "/security-review":
                    console.print("[bold red]🛡️ Initiating Security Review...[/bold red]")
                    self.messages.append({"role": "user", "content": "Please perform a comprehensive security review of the project. Look for hardcoded secrets, injection vulnerabilities, path traversals, and insecure dependencies. Use SemanticSearch, Read, and Glob tools."})
                    user_input = "Start the security review."
                elif user_input.strip() == "/doctor":
                    console.print("[bold cyan]🩺 Running Environment Doctor...[/bold cyan]")
                    import platform, sys, os
                    console.print(f"OS: {platform.system()} {platform.release()}")
                    console.print(f"Python: {sys.version.split()[0]}")
                    console.print(f"CWD: {os.getcwd()}")
                    console.print(f"Model: {self.model}")
                    console.print(f"MCP Servers: {len(self.agent.settings.get('mcp_servers', {}))}")
                    console.print(f"Permissions: {self.permission_engine.mode.value}")
                    self.messages.append({"role": "user", "content": "I just ran the /doctor command to diagnose the environment. Please use the Bash tool to verify the presence of git, docker, node, and python packages, and report back on my project's health."})
                    user_input = "Analyze environment."
                elif user_input.strip().startswith("/permissions"):
                    parts = user_input.strip().split()
                    if len(parts) > 1 and parts[1].lower() in ["auto", "bypass", "default"]:
                        mode_str = parts[1].lower()
                        self.permission_engine.mode = PermissionMode(mode_str)
                        console.print(f"[bold green]✓ Permission mode set to: {mode_str}[/bold green]")
                    else:
                        console.print("[yellow]Usage: /permissions [auto|bypass|default][/yellow]")
                    continue
                elif user_input.strip() == "/graph":
                    console.print("[bold magenta]🗺️ Generating Architectural Map...[/bold magenta]")
                    self.messages.append({"role": "user", "content": "Please run the ReadArchitecture tool on the root directory. Then, generate a detailed Mermaid graph representing the project's components and write it to '.nimcode/architecture.md'."})
                    user_input = "Generate architecture graph."
                elif user_input.strip() == "/guardian":
                    console.print("[bold cyan]🛡️ Application Guardian Activated.[/bold cyan] Agent is now aggressively protecting main branch.")
                    self.messages.append({"role": "system", "content": "You are the Application Guardian. Your sole priority is preventing regressions. Before making any code changes, ensure you write a test first. If a user asks for a breaking change, warn them aggressively."})
                    continue
                elif user_input.strip() == "/thinkback":
                    console.print("[bold blue]⏪ Agent Replay (Thinkback)[/bold blue]")
                    from rich.table import Table
                    table = Table(title="Session History")
                    table.add_column("Turn", style="cyan")
                    table.add_column("Role", style="yellow")
                    table.add_column("Tokens (est.)", style="green")
                    table.add_column("Preview", style="dim", max_width=60)
                    turn_num = 0
                    for msg in self.messages[1:]:  # Skip system prompt
                        role = msg.get("role", "?")
                        content = str(msg.get("content", ""))
                        est_tokens = len(content) // 4 + 1
                        preview = content[:80].replace("\n", " ")
                        if len(content) > 80:
                            preview += "..."
                        if role == "user":
                            turn_num += 1
                        table.add_row(str(turn_num), role, str(est_tokens), preview)
                    if turn_num == 0:
                        console.print("[dim]No conversation history yet.[/dim]")
                    else:
                        console.print(table)
                        total_tokens = sum(len(str(m.get("content", ""))) // 4 + 1 for m in self.messages)
                        console.print(f"[dim]Total messages: {len(self.messages)} | Est. total tokens: {total_tokens}[/dim]")
                    continue
                elif user_input.strip().startswith("/fix"):
                    parts = user_input.strip().split(" ", 1)
                    if len(parts) > 1:
                        fix_cmd = parts[1]
                        console.print(f"[bold red]🔧 Auto-Fixer Loop Started for: {fix_cmd}[/bold red]")
                        
                        # Temporarily elevate permissions for the auto-fix loop
                        self.agent.permission_engine.mode = PermissionMode.BYPASS
                        self.agent.max_turns = 50
                        self.is_autofix = True
                        
                        prompt = f"Run the following command using the Bash tool: `{fix_cmd}`. If it fails, carefully read the error output, use the Edit or Write tools to fix the code, and then run the command again. Repeat this process until the command returns exit code 0. Once it passes, output TASK_COMPLETE."
                        user_input = prompt
                    else:
                        console.print("[yellow]Usage: /fix <command> (e.g. /fix pytest)[/yellow]")
                        continue
                elif user_input.strip() == "/autofix-pr":
                    console.print("[bold green]🔧 Pull Request Auto-Fixer...[/bold green]")
                    self.messages.append({"role": "user", "content": "Use the Bash tool to run 'gh pr view --json url,body,comments,files' to analyze the current pull request. Then fix any issues mentioned in the PR comments."})
                    user_input = "Fix PR issues."
                elif user_input.strip() == "/terraform-god":
                    console.print("[bold cyan]☁️ Terraform God Mode Activated[/bold cyan]")
                    self.messages.append({"role": "user", "content": "I need you to auto-provision cloud infrastructure. Please generate best-practice Terraform code for a scalable, secure, and highly-available deployment based on my project's architecture."})
                    user_input = "Write terraform code."
                elif user_input.strip() == "/sql-tune":
                    console.print("[bold yellow]🛢️ Database Telepathy (SQL Auto-Tuning) Activated[/bold yellow]")
                    self.messages.append({"role": "user", "content": "I need you to analyze my database queries for performance. Please use tools to find SQL queries in my code, analyze execution plans (if you can run EXPLAIN), and propose optimized rewrites with missing indexes."})
                    user_input = "Tune SQL queries."
                elif user_input.strip().startswith("/decompile"):
                    target = user_input.split("/decompile", 1)[1].strip()
                    console.print(f"[bold red]🔬 Reverse Engineering Mode. Target: {target}[/bold red]")
                    self.messages.append({"role": "user", "content": f"Please use the Bash tool to run 'objdump', 'strings', or 'radare2' on {target} and explain its control flow and any embedded secrets."})
                    user_input = "Decompile binary."
                elif user_input.strip() == "/grill-me":
                    console.print("[bold red]🔥 Entering Interrogation Mode. NimCode will now grill you about your code! 🔥[/bold red]")
                    self.messages.append({"role": "user", "content": "I want to refine my design. Please use the 'AskQuestion' tool to interrogate me about edge cases, architecture, and requirements for what I'm currently working on. Ask one focused question at a time, then wait for my reply before asking the next."})
                    # Do not continue, let it fall through to process the message and call the tool
                    user_input = "Please start asking questions."
                elif user_input.strip() == "/code":
                    console.print("[bold magenta]Entering Code mode.[/bold magenta] Standard permissions restored.")
                    # Restore the permission mode that was active before /plan downgraded it.
                    if getattr(self, "_in_plan_mode", False) and hasattr(self, "_pre_plan_mode"):
                        self.permission_engine.mode = self._pre_plan_mode
                        self._in_plan_mode = False
                    self.messages.append({"role": "system", "content": "You are now in coding mode. You may use all available tools."})
                    continue
                elif user_input.strip() == "/trust":
                    self.agent.permission_engine.mode = PermissionMode.BYPASS
                    self.agent.max_turns = 0  # 0 = unlimited (agent.py loop: `while max_turns == 0 or turn < max_turns`)
                    console.print("[bold red]🚨 TRUST MODE ACTIVATED: NimCode will now run all tools without asking for permission and has NO TURN LIMIT! 🚨[/bold red]")
                    continue
                elif user_input.strip() == "/untrust":
                    self.agent.permission_engine.mode = PermissionMode.DEFAULT
                    self.agent.max_turns = self.settings.get("max_turns", 200)
                    console.print("[bold green]🛡️ Trust mode disabled. NimCode will ask for permission and turn limits are restored.[/bold green]")
                    continue
                elif user_input.strip().startswith("/theme"):
                    parts = user_input.strip().split()
                    if len(parts) > 1:
                        self.settings["theme"] = parts[1]
                        save_global_setting("theme", parts[1])
                        console.print(f"[green]Theme updated to '{parts[1]}'[/green]")
                    else:
                        from rich.table import Table
                        from rich.prompt import Prompt
                        
                        themes = ['monokai', 'dracula', 'nord', 'github']
                        table = Table(title="🎨 Available Syntax Themes", show_header=True, header_style="bold magenta")
                        table.add_column("ID", style="cyan", width=4)
                        table.add_column("Theme Name", style="white")
                        
                        for idx, t in enumerate(themes, 1):
                            table.add_row(str(idx), t)
                            
                        console.print(table)
                        
                        choice = Prompt.ask("Select a theme by ID", choices=[str(i) for i in range(1, len(themes) + 1)], default="1")
                        if choice:
                            selected_theme = themes[int(choice) - 1]
                            self.settings["theme"] = selected_theme
                            save_global_setting("theme", selected_theme)
                            console.print(f"[green]Theme updated to '{selected_theme}'[/green]")
                        else:
                            console.print("[yellow]Theme selection cancelled.[/yellow]")
                    continue
                elif user_input.strip() == "/sandbox":
                    current = self.settings.get("sandbox_mode", False)
                    new_val = not current
                    self.settings["sandbox_mode"] = new_val
                    save_global_setting("sandbox_mode", new_val)
                    if new_val:
                        console.print("[bold green]🛡️ Docker Sandbox Mode ENABLED.[/bold green] Bash commands will run in an isolated container.")
                    else:
                        console.print("[bold yellow]⚠️ Docker Sandbox Mode DISABLED.[/bold yellow] Bash commands will run natively on the host.")
                    continue
                elif user_input.strip() == "/cost":
                    summary = self.analytics.get_summary()
                    table = Table(title="💰 API Cost & Usage Summary")
                    table.add_column("Period", justify="left", style="cyan", no_wrap=True)
                    table.add_column("Prompt Tokens", justify="right", style="magenta")
                    table.add_column("Completion Tokens", justify="right", style="green")
                    table.add_column("Cost (USD)", justify="right", style="yellow")
                    
                    t_day = summary["today"]
                    t_tot = summary["total"]
                    
                    table.add_row("Today", f"{t_day['prompt_tokens']:,}", f"{t_day['completion_tokens']:,}", f"${t_day['cost_usd']:.4f}")
                    table.add_row("All Time", f"{t_tot['prompt_tokens']:,}", f"{t_tot['completion_tokens']:,}", f"${t_tot['cost_usd']:.4f}")
                    
                    console.print(table)
                    continue
                elif user_input.strip() == "/effort":
                    summary = self.analytics.get_summary()
                    t_tot = summary["total"]
                    total_tokens = t_tot['prompt_tokens'] + t_tot['completion_tokens']
                    
                    # Heuristics for effort saved
                    # Assume 1 human keystroke = 0.5s, 1 token ~ 4 keystrokes
                    human_seconds = total_tokens * 4 * 0.5
                    hours_saved = human_seconds / 3600
                    
                    table = Table(title="🚀 ROI & Effort Saved")
                    table.add_column("Metric", style="cyan")
                    table.add_column("Value", style="green")
                    
                    table.add_row("Total AI Tokens Generated", f"{total_tokens:,}")
                    table.add_row("Est. Human Keystrokes", f"{total_tokens * 4:,}")
                    table.add_row("Est. Time Saved (Hours)", f"{hours_saved:.1f} hrs")
                    
                    if hours_saved > 40:
                        table.add_row("Milestone", "🎉 You saved a full work week!")
                        
                    console.print(table)
                    continue
                elif user_input.strip().startswith("/models"):
                    args = user_input.split()[1:]
                    if args and args[0] == "local":
                        base_url = args[1] if len(args) > 1 else "http://localhost:11434/v1"
                        self.client.is_local = True
                        self.client.base_url = base_url
                        save_global_setting("is_local", True)
                        save_global_setting("base_url", base_url)
                        console.print(f"[bold green]Switched to LOCAL models (Base URL: {base_url})[/bold green]")
                    elif args and args[0] == "nim":
                        self.client.is_local = False
                        self.client.base_url = "https://integrate.api.nvidia.com/v1"
                        save_global_setting("is_local", False)
                        save_global_setting("base_url", "https://integrate.api.nvidia.com/v1")
                        console.print("[bold green]Switched to NVIDIA NIM models[/bold green]")
                        
                    console.print(f"[bold yellow]Fetching available models...[/bold yellow]")
                    try:
                        models = await self.client.get_available_models()
                        if not models:
                            console.print("[red]No models returned from API.[/red]")
                            continue
                            
                        from rich.table import Table
                        from rich.prompt import Prompt
                        
                        table = Table(title="🤖 Available Models", show_header=True, header_style="bold magenta")
                        table.add_column("ID", style="cyan", width=4)
                        table.add_column("Model Name", style="white")
                        
                        for idx, m in enumerate(models, 1):
                            table.add_row(str(idx), m)
                            
                        console.print(table)
                        
                        choice = Prompt.ask("Select a model by ID (or press Enter to cancel)", choices=[str(i) for i in range(1, len(models) + 1)] + [""], default="")
                        
                        if choice:
                            selected_model = models[int(choice) - 1]
                            self.client.model = selected_model
                            self.model = selected_model
                            save_global_setting("model", selected_model)
                            console.print(f"[bold green]Model changed to: {selected_model}[/bold green]")
                        else:
                            console.print("[yellow]Model selection cancelled.[/yellow]")
                    except Exception as e:
                        console.print(f"[bold red]Failed to fetch models: {e}[/bold red]")
                    continue
                elif user_input.strip() == "/commit":
                    import subprocess
                    console.print("[bold magenta]📝 Generating Commit Message...[/bold magenta]")
                    diff_staged = subprocess.run(["git", "diff", "--staged"], capture_output=True, text=True).stdout or ""
                    if not diff_staged.strip():
                        console.print("[yellow]No staged changes to commit. Use 'git add' first.[/yellow]")
                        continue
                    prompt = f"Write a structured conventional commit message for the following staged changes. Use bullet points for details if necessary. Only output the commit message.\n\nDiff:\n{diff_staged}"
                    self.messages.append({"role": "user", "content": prompt})
                    user_input = prompt
                elif user_input.strip().startswith("/delegate"):
                    parts = user_input.strip().split(" ", 2)
                    if len(parts) < 3:
                        console.print("[yellow]Usage: /delegate <role> <task>[/yellow]")
                        continue
                    role = parts[1]
                    task = parts[2]
                    console.print(f"[bold cyan]👨‍💻 Spawning sub-agent '{role}' for task: {task}[/bold cyan]")
                    
                    async def run_subagent():
                        from nimcode.agent import Agent
                        subagent = Agent()
                        subagent.settings = self.settings
                        subagent.messages.append({"role": "system", "content": f"You are a sub-agent with the role: {role}. You must complete the task assigned to you perfectly and report back the final result. Do not stream. Just execute and finish."})
                        res = await subagent.run_headless(task)
                        return res
                        
                    with console.status(f"[bold cyan]Sub-agent '{role}' is working...[/bold cyan]", spinner="dots"):
                        result = await run_subagent()
                        
                    console.print(f"\n[bold green]✅ Sub-agent '{role}' finished with result:[/bold green]\n{result}")
                    self.messages.append({"role": "system", "content": f"Sub-agent '{role}' completed the task '{task}' and returned:\n{result}"})
                    continue
                elif user_input.strip() == "/testgen":
                    if not os.path.exists(".git"):
                        console.print("[red]Not a git repository.[/red]")
                        continue
                    console.print("[bold yellow]Generating commit message...[/bold yellow]")
                    import subprocess
                    diff = subprocess.check_output(["git", "diff", "--cached"], text=True, encoding="utf-8", errors="replace")
                    if not diff:
                        diff = subprocess.check_output(["git", "diff"], text=True, encoding="utf-8", errors="replace")
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
                            await self.agent.run(prompt)
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
                            await self.agent.run(f"The command `{cmd}` failed with exit code {result.returncode}.\nStderr: {result.stderr[-2000:]}\nStdout: {result.stdout[-2000:]}\nFix the code so it passes.")
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
                elif user_input.strip().startswith("/learn"):
                    topic = user_input[len("/learn"):].strip()
                    if not topic:
                        console.print("[yellow]Usage: /learn <topic>[/yellow]")
                        continue
                    console.print(f"[bold cyan]🧠 Distilling recent context into a new skill: {topic}...[/bold cyan]")
                    prompt = f"Based on our recent conversation, write a concise instructional guide (a 'skill') on the topic: '{topic}'. Do not include conversational text, just the markdown instructions."
                    skill_content = await self.client.chat_one_shot(self.messages[-10:] + [{"role": "user", "content": prompt}])
                    skills_dir = os.path.join(os.getcwd(), ".nimcode", "skills")
                    os.makedirs(skills_dir, exist_ok=True)
                    safe_topic = "".join(c if c.isalnum() else "_" for c in topic)
                    skill_path = os.path.join(skills_dir, f"{safe_topic}.md")
                    with open(skill_path, "w", encoding="utf-8") as f:
                        f.write(skill_content)
                    console.print(f"[bold green]✓ Skill learned and saved to {skill_path}![/bold green]")
                    # Reload skills into prompt
                    self.messages[0]["content"] += f"\n\n--- SKILL: {safe_topic}.md ---\n{skill_content}\n"
                    continue


                elif user_input.strip() == "/thinking":
                    current = self.settings.get("show_thinking", True)
                    self.settings["show_thinking"] = not current
                    save_global_setting("show_thinking", not current)
                    status = "ON" if not current else "OFF"
                    console.print(f"[bold green]✓ Thinking block visibility toggled {status}[/bold green]")
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
                elif user_input.strip().startswith("/tasks"):
                    from .tools import ToolRegistry
                    parts = user_input.strip().split()
                    if len(parts) == 1 or parts[1] == "list":
                        tasks = ToolRegistry._BACKGROUND_TASKS
                        if not tasks:
                            console.print("[dim]No active background tasks.[/dim]")
                        else:
                            from rich.table import Table
                            table = Table(title="Background Tasks")
                            table.add_column("Task ID", style="cyan")
                            table.add_column("Command", style="green")
                            table.add_column("Status", style="yellow")
                            
                            for tid, info in tasks.items():
                                proc = info["process"]
                                status = "Running" if proc.poll() is None else f"Exited ({proc.returncode})"
                                table.add_row(tid, info["command"], status)
                            console.print(table)
                    elif len(parts) == 3 and parts[1] == "kill":
                        tid = parts[2]
                        tasks = ToolRegistry._BACKGROUND_TASKS
                        if tid in tasks:
                            proc = tasks[tid]["process"]
                            if proc.poll() is None:
                                proc.terminate()
                                console.print(f"[bold green]Task {tid} terminated.[/bold green]")
                            else:
                                console.print(f"[yellow]Task {tid} already exited.[/yellow]")
                        else:
                            console.print(f"[red]Task {tid} not found.[/red]")
                    elif len(parts) == 3 and parts[1] == "logs":
                        tid = parts[2]
                        tasks = ToolRegistry._BACKGROUND_TASKS
                        if tid in tasks:
                            log_file = tasks[tid]["log_file"]
                            if os.path.exists(log_file):
                                try:
                                    with open(log_file, "r", encoding="utf-8") as f:
                                        content = f.read()
                                        if len(content) > 2000:
                                            content = "...[TRUNCATED]...\n" + content[-2000:]
                                    console.print(f"[bold cyan]Logs for {tid}:[/bold cyan]\n{content}")
                                except Exception as e:
                                    console.print(f"[red]Error reading logs: {e}[/red]")
                            else:
                                console.print(f"[red]Log file not found.[/red]")
                        else:
                            console.print(f"[red]Task {tid} not found.[/red]")
                    else:
                        console.print("[yellow]Usage: /tasks [list | kill <id> | logs <id>][/yellow]")
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
                    try:
                        import pyautogui
                        import io
                        import base64
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
                    try:
                        import sounddevice as sd
                        import soundfile as sf
                        import os
                        import speech_recognition as sr
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
                            await self.agent.run(transcription)
                        except sr.UnknownValueError:
                            console.print("[bold red]Could not understand audio.[/bold red]")
                    except Exception as e:
                        console.print(f"[bold red]Voice failed: {e}[/bold red]")
                    continue
                elif user_input.strip() == "/index":
                    console.print("[bold cyan]🔍 Indexing project files with SQLite FTS5...[/bold cyan]")
                    import sqlite3
                    import glob
                    import os
                    from .tools import ToolRegistry
                    
                    db = sqlite3.connect(":memory:")
                    db.execute("CREATE VIRTUAL TABLE files USING fts5(path, content)")
                    count = 0
                    for ext in ["*.py", "*.js", "*.ts", "*.md", "*.json", "*.html", "*.css", "*.tsx", "*.jsx"]:
                        for file in glob.glob(f"**/{ext}", recursive=True):
                            if "node_modules" in file or "venv" in file or ".git" in file:
                                continue
                            try:
                                with open(file, "r", encoding="utf-8") as f:
                                    db.execute("INSERT INTO files (path, content) VALUES (?, ?)", (file, f.read()))
                                    count += 1
                            except:
                                pass
                    db.commit()
                    ToolRegistry._FTS_DB = db
                    console.print(f"[bold green]✓ Indexed {count} files for Semantic Search.[/bold green]")
                    self.messages.append({"role": "system", "content": f"Project is indexed. You can now use the SemanticSearch tool."})
                    continue
                elif user_input.strip().startswith("/research"):
                    query = user_input[len("/research"):].strip()
                    if not query:
                        console.print("[bold red]Please provide a research query. (e.g. /research how does auth work)[/bold red]")
                        continue
                        
                    async def bg_research(q):
                        subagent = NimAgent()
                        subagent.messages[0]["content"] += "\n\nYou are a background research subagent. Research the codebase and provide a summary."
                        result = await subagent.run_headless(q, max_turns=7)
                        console.print(f"\n\n[bold magenta]🔬 Subagent Research Complete for '{q}'![/bold magenta]\n{result}\n")
                        self.messages.append({"role": "system", "content": f"A background subagent completed research on '{q}'. Result:\n{result}"})
                    
                    asyncio.create_task(bg_research(query))
                    console.print("[dim italic]Subagent spawned in background. You can continue chatting![/dim italic]")
                    continue
                elif user_input.strip().startswith("/mcp install "):
                    package = user_input.split("/mcp install ")[1].strip()
                    console.print(f"[bold cyan]📦 Installing MCP Server: {package}...[/bold cyan]")
                    import json
                    settings_path = os.path.join(os.getcwd(), ".nimcode", "settings.json")
                    settings = {}
                    if os.path.exists(settings_path):
                        with open(settings_path, "r") as f:
                            settings = json.load(f)
                    
                    if "mcp_servers" not in settings:
                        settings["mcp_servers"] = {}
                        
                    server_name = package.split("@")[0].split("/")[-1]
                    settings["mcp_servers"][server_name] = {
                        "command": "npx",
                        "args": ["-y", package]
                    }
                    with open(settings_path, "w") as f:
                        json.dump(settings, f, indent=4)
                        
                    self.settings["mcp_servers"] = settings["mcp_servers"]
                    self.agent.mcp.servers = settings["mcp_servers"]
                    await self.agent.mcp.connect_all()
                    
                    console.print(f"[bold green]✓ MCP {server_name} installed and connected![/bold green]")
                    self.messages[0]["content"] += self.agent.mcp.get_system_prompt_additions()
                    continue
                elif user_input.strip().startswith("/swarm "):
                    task = user_input.split("/swarm ", 1)[1].strip()
                    console.print(f"[bold magenta]🐝 Spawning Swarm for task: {task}[/bold magenta]")
                    
                    async def run_swarm_coord(task_query):
                        try:
                            from .swarm import SwarmCoordinator
                            coordinator = SwarmCoordinator(
                                api_key=self.client.api_key, 
                                model=self.client.model,
                                base_url=getattr(self.client, 'base_url', None),
                                is_local=getattr(self.client, 'is_local', False)
                            )
                            result = await coordinator.run_swarm(task_query)
                            console.print(f"\n[bold magenta]🐝 Swarm Finished![/bold magenta]\n{result}")
                        except Exception as e:
                            console.print(f"[bold red]Swarm error: {e}[/bold red]")
                            
                    asyncio.create_task(run_swarm_coord(task))
                    continue
                elif user_input.strip().startswith("/tdd "):
                    feature = user_input.split("/tdd ", 1)[1].strip()
                    console.print(f"[bold green]🧪 Starting TDD loop for: {feature}[/bold green]")
                    
                    async def run_tdd(feat):
                        from .agent import NimAgent
                        tdd_agent = NimAgent(self.client.api_key, self.client.model)
                        tdd_agent.messages[0]["content"] = (
                            "You are a strict TDD bot. 1. Write a pytest file for the requested feature using Write tool. "
                            "2. Write the implementation. 3. Run 'pytest' via the Bash tool. "
                            "4. If it fails, read the error and fix the code. Repeat until tests pass."
                        )
                        result = await tdd_agent.run_headless(feat, max_turns=10)
                        console.print(f"\n[bold green]🧪 TDD Completed![/bold green]\n{result}")
                        
                    asyncio.create_task(run_tdd(feature))
                    continue
                elif user_input.strip().startswith("/grill-me "):
                    feature = user_input.split("/grill-me ", 1)[1].strip()
                    console.print(f"[bold yellow]🕵️  Grill-Me Mode Activated for: {feature}[/bold yellow]")
                    console.print("[dim]The agent will now ask you 3 clarifying questions before proceeding.[/dim]")
                    
                    async def run_grill_me(feat):
                        from .agent import NimAgent
                        grill_agent = NimAgent(self.client.api_key, self.client.model)
                        grill_agent.client.is_local = getattr(self.client, 'is_local', False)
                        grill_agent.client.base_url = getattr(self.client, 'base_url', None)
                        
                        prompt = f"The user wants to build: {feat}. Ask exactly 1 highly critical architectural/design question to clarify ambiguous requirements. Do NOT write any code yet. Just ask the question."
                        
                        for i in range(1, 4):
                            question = await grill_agent.run_headless(prompt, max_turns=1)
                            from rich.prompt import Prompt
                            console.print(f"\n[bold magenta]Question {i}/3:[/bold magenta] {question}")
                            answer = Prompt.ask("[bold cyan]Your answer[/bold cyan]")
                            prompt = f"The user answered: {answer}. If you have more questions up to a total of 3, ask the next one now. If this is question 3, summarize the final requirements."
                            
                        console.print("\n[bold green]✅ Grill-Me Complete! You can now use these requirements for /plan or normal chat.[/bold green]")
                        
                    asyncio.create_task(run_grill_me(feature))
                    continue
                elif user_input.strip() == "/update":
                    if not getattr(self, 'update_available', None):
                        console.print("[yellow]You are already on the latest version![/yellow]")
                    else:
                        console.print(f"[bold green]Upgrading nimcode to {self.update_available}...[/bold green]")
                        import subprocess
                        import sys
                        try:
                            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "nimcode"])
                            console.print("[bold green]Update successful! Please restart NimCode.[/bold green]")
                            return
                        except subprocess.CalledProcessError as e:
                            console.print(f"[bold red]Update failed: {e}[/bold red]")
                    continue
                elif user_input.strip().startswith("/"):
                    import difflib
                    valid_commands = ["/help", "/plan", "/code", "/trust", "/untrust", "/models", "/theme", "/clear", "/compact", "/commit", "/fix", "/exit", "/quit", "/config", "/alias", "/add", "/rewind", "/fork", "/testgen", "/vision", "/voice", "/index", "/research", "/mcp install", "/swarm", "/tdd", "/learn", "/cost", "/effort", "/thinking", "/grill-me", "/update", "/undo", "/teleport", "/buddy", "/ultraplan", "/bughunter", "/security-review", "/doctor", "/permissions", "/graph", "/guardian", "/thinkback", "/autofix-pr", "/terraform-god", "/sql-tune", "/decompile", "/sandbox"]
                    valid_commands.extend([f"/{cmd}" for cmd in self.plugin_manager.get_command_names()])
                    
                    cmd_parts = user_input.strip().split(" ", 1)
                    cmd_name = cmd_parts[0]
                    cmd_args = cmd_parts[1] if len(cmd_parts) > 1 else ""
                    
                    # Check if it's a plugin command
                    plugin_cmd_name = cmd_name.lstrip("/")
                    if plugin_cmd_name in self.plugin_manager.get_command_names():
                        result = self.plugin_manager.execute_command(plugin_cmd_name, cmd_args, self.agent)
                        if result:
                            console.print(result)
                        continue

                    matches = difflib.get_close_matches(cmd_name, valid_commands, n=1, cutoff=0.5)
                    if matches:
                        console.print(f"[yellow]Unknown command '{cmd_name}'. Did you mean [bold cyan]{matches[0]}[/bold cyan]?[/yellow]")
                    else:
                        console.print(f"[red]Unknown command '{cmd_name}'. Type /help for a list of commands.[/red]")
                    continue

                if not user_input.strip():
                    continue

                # ── Plan-mode file injection ──────────────────────────────────
                # When in /plan mode, detect any filenames in the user's message,
                # read them ourselves, and inject their content into the context
                # BEFORE the LLM sees the prompt. This guarantees the model
                # plans from real document content instead of generic templates.
                if getattr(self, "_in_plan_mode", False):
                    import re as _re
                    # Match bare filenames/paths with known doc extensions
                    _file_pattern = _re.compile(
                        r"[\w./\\-]+\.(?:md|txt|rst|pdf|json|yaml|yml|toml|csv|xml|sdd|prd|rfc|spec)",
                        _re.IGNORECASE,
                    )
                    _mentioned = _file_pattern.findall(user_input)
                    _injected: list[str] = []
                    for _fname in _mentioned:
                        _fpath = os.path.join(os.getcwd(), _fname)
                        if os.path.isfile(_fpath):
                            try:
                                with open(_fpath, "r", encoding="utf-8", errors="replace") as _fh:
                                    _content = _fh.read()
                                # Truncate very large files to ~40k chars to stay within context
                                _MAX = 40_000
                                _truncated = ""
                                if len(_content) > _MAX:
                                    _content = _content[:_MAX]
                                    _truncated = f"\n[... file truncated at {_MAX} chars. Pass offset/limit to the Read tool for more.]"
                                self.agent.messages.append({
                                    "role": "user",
                                    "content": (
                                        f"[AUTO-READ] Here is the full content of '{_fname}' "
                                        f"that the user mentioned:\n\n"
                                        f"```\n{_content}{_truncated}\n```\n\n"
                                        f"Use this content as the ground truth for your plan. "
                                        f"Do NOT invent requirements not present in this document."
                                    ),
                                })
                                _injected.append(_fname)
                                console.print(f"[dim]📎 Auto-injected: {_fname} ({len(_content):,} chars)[/dim]")
                            except Exception as _e:
                                console.print(f"[dim yellow]⚠ Could not auto-read {_fname}: {_e}[/dim yellow]")
                # ─────────────────────────────────────────────────────────────

                await self.agent.run(user_input)
                
                if getattr(self, 'is_autofix', False):
                    self.agent.permission_engine.mode = PermissionMode.DEFAULT
                    self.agent.max_turns = self.settings.get("max_turns", 30)
                    self.is_autofix = False
                    console.print("[green]Auto-fix complete. Restored standard permissions and turn limits.[/green]")
                    
                if self.settings.get("audio_cues", True):
                    import sys
                    sys.stdout.write("\a")
                    sys.stdout.flush()
                
            except KeyboardInterrupt:
                console.print("\n[bold yellow]⚠ Operation cancelled by user. (Press Ctrl+D to exit)[/bold yellow]")
                continue
            except asyncio.CancelledError:
                console.print("\n[bold yellow]⚠ Operation cancelled by user. (Press Ctrl+D to exit)[/bold yellow]")
                continue
            except EOFError:
                watcher.stop()
                break
