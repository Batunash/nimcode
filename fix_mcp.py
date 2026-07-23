import re

with open('src/nimcode/repl.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('self.mcp.', 'self.agent.mcp.')
content = content.replace('self.mcp,', 'self.agent.mcp,')
content = content.replace('self.mcp_servers', 'self.agent.settings.get("mcp_servers", {})')

with open('src/nimcode/repl.py', 'w', encoding='utf-8') as f:
    f.write(content)
