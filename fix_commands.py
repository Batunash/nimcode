import re

with open('tests/test_repl.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_commands = False
for line in lines:
    if line.strip().startswith('commands = ['):
        in_commands = True
        new_lines.append(line)
        new_lines.append('''        "/help",
        "/models",
        "/compact",
        "/clear",
        "/history",
        "/save",
        "/load",
        "/tokens",
        "/config",
        "/theme monokai",
        "/theme",
        "/code",
        "/grill-me",
        "/decompile target",
        "/sql-tune",
        "/terraform-god",
        "/autofix-pr",
        "/thinkback",
        "/guardian",
        "/graph",
        "/review",
        "/commit",
        "/undo",
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
        "/exit"
    ]
''')
    elif in_commands:
        if line.strip() == ']' or line.strip() == '],':
            in_commands = False
    else:
        new_lines.append(line)

with open('tests/test_repl.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
