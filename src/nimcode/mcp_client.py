import logging
from typing import Dict, Any, List
from contextlib import AsyncExitStack

logger = logging.getLogger(__name__)

class MCPManager:
    """Manages connections to MCP servers."""
    
    def __init__(self, mcp_config: Dict[str, Any]):
        self.config = mcp_config
        self.servers = mcp_config.get("mcp_servers", {})
        self.exit_stack = AsyncExitStack()
        self.sessions = {}  # name -> ClientSession
        self.server_tools = {} # name -> list of tools
        
    async def connect_all(self):
        """Initialize all MCP servers."""
        if not self.servers:
            return
            
        try:
            from mcp.client.stdio import stdio_client, StdioServerParameters
            from mcp.client.session import ClientSession
        except ImportError:
            logger.warning("MCP SDK not installed. Skipping MCP initialization.")
            return

        for name, details in self.servers.items():
            cmd = details.get("command")
            args = details.get("args", [])
            env = details.get("env", None)
            
            logger.info(f"Connecting to MCP server '{name}'...")
            try:
                params = StdioServerParameters(command=cmd, args=args, env=env)
                read, write = await self.exit_stack.enter_async_context(stdio_client(params))
                session = await self.exit_stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                self.sessions[name] = session
                
                # Fetch tools
                tools_response = await session.list_tools()
                self.server_tools[name] = tools_response.tools if hasattr(tools_response, "tools") else []
                logger.info(f"MCP Server '{name}' initialized with {len(self.server_tools[name])} tools.")
            except Exception as e:
                logger.error(f"Failed to connect to MCP server '{name}': {e}")

    async def close(self):
        await self.exit_stack.aclose()
        
    def get_system_prompt_additions(self) -> str:
        """Returns extra text to add to the system prompt about MCPs."""
        if not self.sessions:
            return ""
            
        lines = ["\n\nAvailable MCP Servers & Tools:"]
        for name, tools in self.server_tools.items():
            lines.append(f"- Server '{name}':")
            for t in tools:
                lines.append(f"  * {t.name}: {t.description}")
        return "\n".join(lines)
        
        
    async def call_tool_by_name(self, tool_name: str, arguments: dict) -> Any:
        for server_name, tools in self.server_tools.items():
            for t in tools:
                if t.name == tool_name:
                    return await self.sessions[server_name].call_tool(tool_name, arguments)
        raise ValueError(f"MCP Tool {tool_name} not found.")

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> Any:
        if server_name not in self.sessions:
            raise ValueError(f"Server {server_name} not found or not connected.")
        session = self.sessions[server_name]
        result = await session.call_tool(tool_name, arguments)
        return result
