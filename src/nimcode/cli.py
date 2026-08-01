import argparse
import asyncio
import logging
import os
import sys
from rich.console import Console
from .agent import Agent
from .config import load_settings, save_global_setting
from .permissions import PermissionMode

logger = logging.getLogger(__name__)
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
    env_key = os.environ.get("NIM_API_KEY")
    settings = load_settings()
    settings_key = settings.get("api_key")
    if env_key or settings_key:
        source = "environment variable" if env_key else "settings.json (`nimcode login`)"
        console.print(f"[green][OK][/green] NIM API key found via {source}.")
    else:
        console.print("[red][X][/red] No NIM API key found. Set NIM_API_KEY or run `nimcode login`.")
    
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
        f.write("# Only generate a message if the user hasn't supplied one.\n")
        f.write("if [ -z \"$(cat $1)\" ]; then\n")
        f.write("  nimcode \"Generate a conventional commit message for the currently staged changes. Use the Bash tool to run 'git diff --staged', then write ONLY the commit message (no preamble, no explanation) to stdout.\" > \"$1\"\n")
        f.write("fi\n")

    # Make it executable. On Windows the stat bit is a no-op, but Git for Windows
    # runs hooks regardless; guard against platforms where chmod is unsupported.
    try:
        import stat
        os.chmod(hook_path, os.stat(hook_path).st_mode | stat.S_IEXEC)
    except Exception as e:
        logger.debug("Could not set executable bit on hook (non-fatal): %s", e)
    console.print(f"[green][OK][/green] Git hook installed to {hook_path}")

def _silence_anyio_errors():
    import sys
    original_hook = sys.unraisablehook
    def custom_unraisablehook(unraisable):
        # These are known teardown-noise patterns from anyio/MCP that surface on Ctrl+C.
        # Log at debug (traceable) instead of silently swallowing, so genuine errors still surface.
        if unraisable.exc_type == RuntimeError and "exit cancel scope in a different task" in str(unraisable.exc_value):
            logger.debug("anyio cancel-scope teardown noise (suppressed): %s", unraisable.exc_value)
            return
        if unraisable.exc_type == BaseExceptionGroup and "unhandled errors in a TaskGroup" in str(unraisable.exc_value):
            logger.debug("anyio TaskGroup teardown noise (suppressed): %s", unraisable.exc_value)
            return
        original_hook(unraisable)
    sys.unraisablehook = custom_unraisablehook

def main():
    _silence_anyio_errors()
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
    parser.add_argument("--model", "-m", default="deepseek-ai/deepseek-v4-pro", help="Model ID to use from NIM.")
    parser.add_argument("--max-turns", "-t", type=int, default=None, help="Maximum number of turns the agent is allowed to run. If omitted, uses settings.json max_turns (default 200; 0 = unlimited).")
    parser.add_argument("--permission-mode", "-p", type=PermissionMode, choices=list(PermissionMode), default=PermissionMode.DEFAULT, help="Permission mode for mutating tools.")
    parser.add_argument("--resume", "-r", action="store_true", help="Resume from the last session stored in .nimcode/sessions/session.json.")
    
    args = parser.parse_args()
    
    settings = load_settings()
    api_base_url = settings.get("api_base_url", "https://integrate.api.nvidia.com/v1")
    
    final_key = args.api_key or os.environ.get("NIM_API_KEY") or settings.get("api_key")
    is_local = "localhost" in api_base_url or "127.0.0.1" in api_base_url
    
    if not final_key and not is_local:
        console.print("[yellow]No API Key found. Let's get you set up![/yellow]")
        run_login()
        settings = load_settings()
        final_key = settings.get("api_key")
        if not final_key:
            console.print("[bold red]API Key is required to use NimCode. Exiting.[/bold red]")
            sys.exit(1)
            
    final_key = final_key or "local-dummy-key"
        
    agent = Agent(
        api_key=final_key,
        model=args.model,
        max_turns=args.max_turns,
        permission_mode=args.permission_mode
    )
    
    if args.resume:
        # Load from history if possible
        agent.load_history()

    async def safe_start_repl(repl):
        loop = asyncio.get_running_loop()
        def custom_exception_handler(loop, context):
            msg = context.get("message", "")
            exception = context.get("exception", None)
            if "unhandled errors in a TaskGroup" in str(msg) or "unhandled errors in a TaskGroup" in str(exception):
                logger.debug("TaskGroup teardown noise (suppressed): %s", exception or msg)
                return
            if exception and isinstance(exception, RuntimeError) and "exit cancel scope in a different task" in str(exception):
                logger.debug("anyio cancel-scope teardown noise (suppressed): %s", exception)
                return
            # Only swallow the specific shutdown-warning shapes, not all async generator messages.
            if "asynchronous generator" in str(msg) and ("never awaited" in str(msg) or "GeneratorExit" in str(msg)):
                logger.debug("async generator teardown noise (suppressed): %s", msg)
                return
            loop.default_exception_handler(context)
        loop.set_exception_handler(custom_exception_handler)
        
        try:
            await repl.start_repl()
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Goodbye![/bold yellow]")

    piped_input = None
    if not sys.stdin.isatty():
        piped_input = sys.stdin.read().strip()

    try:
        if piped_input:
            console.print(f"[bold green]Starting NimCode[/bold green] with model [cyan]{args.model}[/cyan]")
            prompt = f"{piped_input}\n\n{args.prompt or ''}".strip()
            console.print(f"Task (with piped input): {prompt}")
            asyncio.run(agent.run(prompt))
        elif args.prompt:
            console.print(f"[bold green]Starting NimCode[/bold green] with model [cyan]{args.model}[/cyan]")
            console.print(f"Task: {args.prompt}")
            asyncio.run(agent.run(args.prompt))
        else:
            from .repl import NimcodeREPL
            repl = NimcodeREPL(agent)
            asyncio.run(safe_start_repl(repl))
    except KeyboardInterrupt:
        # Ctrl+C during an active async stream/await — graceful exit, no traceback.
        console.print("\n[bold yellow]Interrupted. Exiting NimCode.[/bold yellow]")
        return

    # We don't print "Done!" for REPL to keep it clean on exit
    if args.prompt or piped_input:
        console.print("[bold green]Done![/bold green]")

if __name__ == "__main__":
    main()
