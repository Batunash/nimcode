import re

with open('tests/test_repl.py', 'r', encoding='utf-8') as f:
    content = f.read()

replacement = '''"/exit",
            "/plan",
            "/teleport target",
            "/teleport",
            "/buddy",
            "/ultraplan",
            "/bughunter",
            "/security-review",
            "/doctor",
            "/swarm",
            "/tdd",
            "/research",
            "/mcp install xxx",
            "/cost",
            "/effort High",
            "/thinking",
            "/testgen",
            "/vision",
            "/voice",
            "/index",
            "/fix",
            "/rewind",
            "/fork",
            "/permissions bypass",
            "/permissions auto",
            "/permissions default",
            "/permissions",
            "dummy_command",
            "/exit" # Extra for safety'''

content = content.replace('"/exit" # Extra for safety', replacement)

with open('tests/test_repl.py', 'w', encoding='utf-8') as f:
    f.write(content)
