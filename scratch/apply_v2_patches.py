import os

# 1. Patch tools.py
tools_path = r"C:\Users\batu.DESKTOP-IQT2FP8\Desktop\Dev\Projects\nimcode\src\nimcode\tools.py"
with open(tools_path, "r", encoding="utf-8") as f:
    tools_code = f.read()

if "DelegateTask" not in tools_code:
    target = '            "TestRunner": {'
    replacement = '''            "DelegateTask": {
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
            "TestRunner": {'''
    tools_code = tools_code.replace(target, replacement)
    with open(tools_path, "w", encoding="utf-8") as f:
        f.write(tools_code)
    print("Patched tools.py schemas")

# 2. Patch mcp_client.py
mcp_path = r"C:\Users\batu.DESKTOP-IQT2FP8\Desktop\Dev\Projects\nimcode\src\nimcode\mcp_client.py"
with open(mcp_path, "r", encoding="utf-8") as f:
    mcp_code = f.read()

if "def add_server(" not in mcp_code:
    target_close = "    async def close(self):"
    methods = '''
    async def add_server(self, name: str, command: str, args: list = None, env: dict = None):
        """Dynamically add and connect a new MCP server."""
        if name in self.sessions:
            logger.warning(f"MCP server '{name}' already exists.")
            return

        try:
            from mcp.client.stdio import stdio_client, StdioServerParameters
            from mcp.client.session import ClientSession
        except ImportError:
            logger.error("MCP SDK not installed. Cannot add server.")
            return

        logger.info(f"Dynamically connecting to MCP server '{name}'...")
        try:
            params = StdioServerParameters(command=command, args=args or [], env=env)
            read, write = await self.exit_stack.enter_async_context(stdio_client(params))
            session = await self.exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self.sessions[name] = session
            
            tools_response = await session.list_tools()
            self.server_tools[name] = tools_response.tools if hasattr(tools_response, "tools") else []
            self.servers[name] = {"command": command, "args": args or [], "env": env}
            logger.info(f"MCP Server '{name}' dynamically initialized with {len(self.server_tools[name])} tools.")
        except Exception as e:
            logger.error(f"Failed to dynamically connect to MCP server '{name}': {e}")

    async def remove_server(self, name: str):
        """Dynamically remove an MCP server."""
        if name not in self.sessions:
            logger.warning(f"MCP server '{name}' not found.")
            return
        
        logger.info(f"Removing MCP server '{name}'...")
        try:
            del self.sessions[name]
            del self.server_tools[name]
            if name in self.servers:
                del self.servers[name]
            logger.info(f"MCP Server '{name}' removed.")
        except Exception as e:
            logger.error(f"Error removing MCP server '{name}': {e}")

    async def close(self):'''
    mcp_code = mcp_code.replace(target_close, methods)
    with open(mcp_path, "w", encoding="utf-8") as f:
        f.write(mcp_code)
    print("Patched mcp_client.py")
