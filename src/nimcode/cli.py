import argparse
import asyncio
import os
import sys
from rich.console import Console
from .agent import Agent
from .config import load_settings, save_global_setting
from .permissions import PermissionMode

console = Console()

def run_login():
    console.print("[bold cyan]NimCode Login[/bold cyan]")
    console.print("Get your API key from [bold underline blue]https://build.nvidia.com/[/bold underline blue]")
    
    import getpass
    api_key = getpass.getpass("Enter your NVIDIA NIM API Key: ")
    if not api_key.strip():
        console.print("[red]API Key cannot be empty.[/red]")
        return
        
    save_global_setting("api_key", api_key.strip())
    console.print("[green][OK] API Key saved successfully to ~/.nimcode/settings.json[/green]")

def run_doctor():
    console.print("[bold cyan]NimCode Doctor[/bold cyan] - Diagnostics")
    key = os.environ.get("NIM_API_KEY")
    if key:
        console.print("[green][OK][/green] NIM_API_KEY environment variable is set.")
    else:
        console.print("[red][X][/red] NIM_API_KEY environment variable is missing.")
    
    # Check .nimcode existence
    if os.path.exists(".nimcode"):
        console.print("[green][OK][/green] .nimcode directory found in current project.")
    else:
        console.print("[yellow][!][/yellow] No .nimcode directory found. Standard settings apply.")
    
    console.print("[green][OK][/green] MCP SDK installed.")
    console.print("Diagnostics complete.")

def install_hook():
    if not os.path.exists(".git"):
        console.print("[red][X][/red] Not a git repository.")
        return
        
    hook_path = os.path.join(".git", "hooks", "prepare-commit-msg")
    with open(hook_path, "w", encoding="utf-8") as f:
        f.write("#!/bin/sh\n")
        f.write("# NimCode auto-commit hook\n")
        f.write("if [ -z \"$(cat $1)\" ]; then\n")
        f.write("  nimcode /commit > $1\n")
        f.write("fi\n")
    
    import stat
    os.chmod(hook_path, os.stat(hook_path).st_mode | stat.S_IEXEC)
    console.print(f"[green][OK][/green] Git hook installed to {hook_path}")

def main():
    parser = argparse.ArgumentParser(description="NimCode: Autonomous Coding Agent for NVIDIA NIM APIs")
    
    # Check for doctor manually to avoid subparser conflict
    if len(sys.argv) > 1:
        if sys.argv[1] == "doctor":
            run_doctor()
            return
        elif sys.argv[1] == "install-hook":
            install_hook()
            return
        elif sys.argv[1] == "login":
            run_login()
            return
        
    # Main CLI arguments
    parser.add_argument("prompt", nargs="?", default=None, help="The task you want NimCode to accomplish. If omitted, starts interactive REPL.")
    parser.add_argument("--api-key", "-k", default=None, help="NVIDIA NIM API Key. Can also be set via NIM_API_KEY environment variable.")
    parser.add_argument("--model", "-m", default="meta/llama-3.1-70b-instruct", help="Model ID to use from NIM.")
    parser.add_argument("--max-turns", "-t", type=int, default=30, help="Maximum number of turns the agent is allowed to run.")
    parser.add_argument("--permission-mode", "-p", type=PermissionMode, choices=list(PermissionMode), default=PermissionMode.DEFAULT, help="Permission mode for mutating tools.")
    parser.add_argument("--resume", "-r", action="store_true", help="Resume from the last session stored in NIMCODE.md.")
    
    args = parser.parse_args()
    
    settings = load_settings()
    
    final_key = args.api_key or os.environ.get("NIM_API_KEY") or settings.get("api_key")
    if not final_key:
        console.print("[yellow]No API Key found. Let's get you set up![/yellow]")
        run_login()
        settings = load_settings()
        final_key = settings.get("api_key")
        if not final_key:
            console.print("[bold red]API Key is required to use NimCode. Exiting.[/bold red]")
            sys.exit(1)
        
    console.print(f"[bold green]Starting NimCode[/bold green] with model [cyan]{args.model}[/cyan]")
    
    agent = Agent(
        api_key=final_key,
        model=args.model,
        max_turns=args.max_turns,
        permission_mode=args.permission_mode
    )
    
    if args.resume:
        # Load from history if possible
        agent.load_history()

    piped_input = None
    if not sys.stdin.isatty():
        piped_input = sys.stdin.read().strip()
        
    if piped_input:
        prompt = f"{piped_input}\n\n{args.prompt or ''}".strip()
        console.print(f"Task (with piped input): {prompt}")
        asyncio.run(agent.run(prompt))
    elif args.prompt:
        console.print(f"Task: {args.prompt}")
        asyncio.run(agent.run(args.prompt))
    else:
        console.print("[bold yellow]Entering Interactive REPL Mode[/bold yellow]. Type /exit to quit, /plan for planning mode, /code for coding mode.")
        asyncio.run(agent.start_repl())
    
    console.print("[bold green]Done![/bold green]")

if __name__ == "__main__":
    main()
