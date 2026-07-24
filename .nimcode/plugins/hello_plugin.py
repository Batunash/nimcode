def handle_hello(args, agent):
    return f"[bold green]Hello from plugin! You said: {args}[/bold green]"

def register_commands():
    return {
        "hello": handle_hello
    }
