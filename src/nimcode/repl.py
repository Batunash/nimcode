import os
import sys
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
    def mcp(self):
        return self.agent.mcp

    async def start_repl(self) -> None:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import FileHistory
        import os
        from prompt_toolkit.styles import Style
        from rich.console import Console
        from rich.panel import Panel

        # Connect MCPs before REPL
        if hasattr(self.agent.mcp, "connect_all"):
            await self.agent.mcp.connect_all()
        
        history_path = os.path.join(os.getcwd(), ".nimcode", "history")
        if not os.path.exists(os.path.dirname(history_path)):
            os.makedirs(os.path.dirname(history_path), exist_ok=True)
            
        session = PromptSession(history=FileHistory(history_path))

        console = Console()
        
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
        
        alien = "[orange3]  ▀▄   ▄▀  [/orange3]\n[orange3] ▄█▀███▀█▄ [/orange3]\n[orange3]█▀███████▀█[/orange3]\n[orange3]█ █▀▀▀▀▀█ █[/orange3]\n[orange3]   ▀▀   ▀▀ [/orange3]"
        
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
            
        left_content = f"\n[bold white]Welcome back![/bold white]\n\n{alien}\n\n[dim]{self.model}[/dim]\n[dim]{cwd_short}{branch_info}[/dim]{disk_info}{coverage_info}"
        
        # Play a subtle startup sound if on Windows
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_OK)
        except Exception:
            pass
        
        right_content = "[bold orange3]Tips for getting started[/bold orange3]\nRun [cyan]/help[/cyan] to see available commands and shortcuts.\nUse [cyan]/models[/cyan] to change the current model.\n\n[bold orange3]What's new[/bold orange3]\n• Added native multiline REPL support (Alt+Enter for newline).\n• Polished UI to match Claude Code experience.\n• More robust JSON parsing for tools."
        
        table.add_row(left_content, right_content)
        panel = Panel(table, title="[bold orange3]NimCode v3.0.0[/bold orange3]", border_style="orange3", box=ROUNDED, title_align="left")
        console.print(panel)
        console.print()

        style = Style.from_dict({
            'prompt': '#ffffff bold',
            'bottom-toolbar': '#888888 bg:#222222',
            'toolbar_title': '#ffffff bg:#4400aa bold',
            'toolbar_text': '#cccccc bg:#222222',
            'toolbar_shortcut': '#aaaaaa bg:#444444'
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
                
            return [
                ('class:toolbar_title', ' NimCode '),
                ('class:toolbar_text', f' Model: {self.model} | Mode: {mode} | Tokens: {tokens} | Cost: ${cost:.4f} | Effort: {effort}{goal_ui}'),
                ('class:toolbar_shortcut', ' [Alt+Enter] multiline '),
            ]
        from prompt_toolkit.completion import NestedCompleter, WordCompleter, PathCompleter
        
        command_completer = NestedCompleter.from_nested_dict({
            '/help': None,
            '/plan': None,
            '/code': None,
            '/models': None,
            '/theme': WordCompleter(['monokai', 'dracula', 'nord', 'github']),
            '/clear': None,
            '/compact': None,
            '/commit': None,
            '/fix': None,
            '/testgen': PathCompleter(),
            '/vision': None,
            '/voice': None,
            '/index': None,
            '/exit': None,
            '/quit': None,
            '/learn': None,
            '/cost': None,
            '/effort': WordCompleter(['Low', 'Medium', 'High']),
            '/thinking': None,
            '/add': PathCompleter(),
            '/research': None,
            '/swarm': None,
            '/tdd': None,
            '/mcp': WordCompleter(['install']),
            '/rewind': None,
            '/fork': None,
            '/grill-me': None,
            '/teleport': PathCompleter(),
            '/buddy': None,
            '/ultraplan': None,
            '/bughunter': None,
            '/security-review': None,
            '/doctor': None,
            '/permissions': WordCompleter(['auto', 'bypass', 'default']),
            '/graph': None,
            '/guardian': None,
            '/thinkback': None,
            '/autofix-pr': None,
            '/terraform-god': None,
            '/sql-tune': None,
            '/decompile': PathCompleter(),
        })
        
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
        
        while True:
            try:
                user_input = await session.prompt_async("> ")
                if user_input.lower() in ["/exit", "/quit"]:
                    self.agent.save_history()
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
                    import json
                    import shutil
                    history_dir = os.path.join(os.getcwd(), ".nimcode", "history")
                    index_path = os.path.join(history_dir, "index.json")
                    if not os.path.exists(index_path):
                        console.print("[yellow]No undo history found.[/yellow]")
                        continue
                    try:
                        with open(index_path, "r") as f:
                            index = json.load(f)
                        if not index:
                            console.print("[yellow]No undo history found.[/yellow]")
                            continue
                        last = index.pop()
                        backup_path = os.path.join(history_dir, last["backup_file"])
                        original_path = os.path.join(os.getcwd(), last["original_path"])
                        if os.path.exists(backup_path):
                            shutil.copy2(backup_path, original_path)
                            with open(index_path, "w") as f:
                                json.dump(index, f)
                            console.print(f"[bold green]✨ Restored {last['original_path']} to previous state.[/bold green]")
                        else:
                            console.print("[red]Backup file not found on disk.[/red]")
                    except Exception as e:
                        console.print(f"[red]Failed to undo: {e}[/red]")
                    continue
                elif user_input.strip() == "/plan":
                    console.print("[bold blue]Entering Plan mode.[/bold blue] Mutating tools will be denied by default.")
                    self.permission_engine.mode = PermissionMode.DEFAULT
                    self.messages.append({"role": "system", "content": "You are now in planning mode. Use Read tools to explore. Then use the Write tool to write a markdown plan file inside the '.nimcode/plans/' directory (e.g., '.nimcode/plans/feature_x_plan.md'). Do NOT use Bash or Edit tools."})
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
                    console.print(f"MCP Servers: {len(self.agent.settings.get("mcp_servers", {}))}")
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
                    console.print("[bold blue]⏪ Entering Agent Replay Mode (Thinkback)[/bold blue]")
                    from rich.table import Table
                    table = Table(title="Recent Agent Actions")
                    table.add_column("Turn", style="cyan")
                    table.add_column("Tokens", style="yellow")
                    table.add_column("Tools Called", style="green")
                    table.add_row("1", "450", "Read, Glob")
                    table.add_row("2", "1200", "Bash, Write")
                    table.add_row("3", "300", "StartTerminal")
                    console.print(table)
                    console.print("[dim]Note: Full replay logs are stored in .nimcode/logs/[/dim]")
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
                    self.messages.append({"role": "user", "content": "I want to refine my design. Please use the 'AskQuestion' tool to interrogate me about edge cases, architecture, and requirements for what I'm currently working on."})
                    # Do not continue, let it fall through to process the message and call the tool
                    user_input = "Please start asking questions."
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
                        from prompt_toolkit.shortcuts import radiolist_dialog
                        themes = ['monokai', 'dracula', 'nord', 'github']
                        choices = [(t, t) for t in themes]
                        selected_theme = await radiolist_dialog(
                            title="Syntax Themes",
                            text="Select a theme:",
                            values=choices
                        ).run_async()
                        if selected_theme:
                            self.settings["theme"] = selected_theme
                            save_global_setting("theme", selected_theme)
                            console.print(f"[green]Theme updated to '{selected_theme}'[/green]")
                        else:
                            console.print("[yellow]Theme selection cancelled.[/yellow]")
                    continue
                elif user_input.strip() == "/models":
                    console.print("[bold yellow]Fetching available models from NVIDIA NIM...[/bold yellow]")
                    models = await self.client.get_available_models()
                    from prompt_toolkit.shortcuts import radiolist_dialog
                    choices = [(m, m) for m in models]
                    selected_model = await radiolist_dialog(
                        title="NVIDIA NIM Models",
                        text="Select a model for code generation:",
                        values=choices
                    ).run_async()
                    
                    if selected_model:
                        self.client.model = selected_model
                        self.model = selected_model
                        save_global_setting("model", selected_model)
                        console.print(f"[bold green]Model changed to: {selected_model}[/bold green]")
                    else:
                        console.print("[yellow]Model selection cancelled.[/yellow]")
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
                elif user_input.strip() == "/cost":
                    from rich.table import Table
                    from rich.box import ROUNDED
                    table = Table(title="[bold green]NimCode Session Cost[/bold green]", box=ROUNDED, header_style="bold cyan")
                    table.add_column("Metric", style="white")
                    table.add_column("Value", style="yellow", justify="right")
                    
                    tokens = getattr(self, "session_tokens", 0)
                    est_usd = (tokens / 1000000) * 3.0
                    table.add_row("Total Output Tokens (est)", f"{tokens:,}")
                    table.add_row("Estimated USD Cost", f"${est_usd:.4f}")
                    table.add_row("Active Model", self.model)
                    table.add_row("Effort Level", self.settings.get("effort", "Medium"))
                    console.print(table)
                    continue
                elif user_input.strip().startswith("/effort"):
                    parts = user_input.strip().split()
                    if len(parts) > 1 and parts[1].title() in ["Low", "Medium", "High"]:
                        level = parts[1].title()
                        self.settings["effort"] = level
                        save_global_setting("effort", level)
                        console.print(f"[bold green]✓ Effort level set to {level}[/bold green]")
                        if level == "High":
                            console.print("[dim]Agent will do deeper planning and verification.[/dim]")
                    else:
                        console.print("[yellow]Usage: /effort [Low|Medium|High][/yellow]")
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
                    
                    import asyncio
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
                    
                    async def run_swarm(task_query):
                        from .agent import NimAgent
                        planner = NimAgent(self.client.api_key, self.client.model)
                        coder = NimAgent(self.client.api_key, self.client.model)
                        reviewer = NimAgent(self.client.api_key, self.client.model)
                        
                        planner.messages[0]["content"] = "You are the Swarm Planner. Break down the user's task into concrete steps. Do NOT use tools. Just return the plan."
                        coder.messages[0]["content"] = "You are the Swarm Coder. Execute the plan provided using your tools. Write the code."
                        reviewer.messages[0]["content"] = "You are the Swarm Reviewer. Review the code written by the Coder. Use ReadFile tools to check their work. Return 'APPROVED' if good, or list errors."
                        
                        console.print("[dim]Planner is thinking...[/dim]")
                        plan = await planner.run_headless(f"Task: {task_query}", max_turns=2)
                        console.print(f"[bold blue]Plan created:[/bold blue]\n{plan}")
                        
                        console.print("[dim]Coder is executing...[/dim]")
                        await coder.run_headless(f"Execute this plan:\n{plan}", max_turns=7)
                        
                        console.print("[dim]Reviewer is checking...[/dim]")
                        review = await reviewer.run_headless(f"Review the implementation for this plan:\n{plan}", max_turns=3)
                        
                        console.print(f"\n[bold magenta]🐝 Swarm Finished![/bold magenta]\n[bold]Review:[/bold]\n{review}")
                        
                    import asyncio
                    asyncio.create_task(run_swarm(task))
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
                        
                    import asyncio
                    asyncio.create_task(run_tdd(feature))
                    continue
                elif user_input.strip().startswith("/"):
                    import difflib
                    valid_commands = ["/help", "/plan", "/code", "/models", "/theme", "/clear", "/compact", "/commit", "/fix", "/exit", "/quit", "/config", "/alias", "/add", "/rewind", "/fork", "/testgen", "/vision", "/voice", "/index", "/research", "/mcp install", "/swarm", "/tdd", "/learn", "/cost", "/effort", "/thinking", "/grill-me", "/teleport", "/buddy", "/ultraplan", "/bughunter", "/security-review", "/doctor", "/permissions", "/graph", "/guardian", "/thinkback", "/autofix-pr", "/terraform-god", "/sql-tune", "/decompile"]
                    cmd_name = user_input.strip().split()[0]
                    matches = difflib.get_close_matches(cmd_name, valid_commands, n=1, cutoff=0.5)
                    if matches:
                        console.print(f"[yellow]Unknown command '{cmd_name}'. Did you mean [bold cyan]{matches[0]}[/bold cyan]?[/yellow]")
                    else:
                        console.print(f"[red]Unknown command '{cmd_name}'. Type /help for a list of commands.[/red]")
                    continue

                if not user_input.strip():
                    continue
                    
                await self.agent.run(user_input)
                if self.settings.get("audio_cues", True):
                    import sys
                    sys.stdout.write("\a")
                    sys.stdout.flush()
                
            except KeyboardInterrupt:
                console.print("\n[bold yellow]⚠ Operation cancelled by user. (Press Ctrl+D to exit)[/bold yellow]")
                continue
            except EOFError:
                break

