import re

with open('tests/test_repl.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('"/undo",\n            "/exit",\n            "/exit",\n            "/plan",', '"/undo",\n            "/plan",')

with open('tests/test_repl.py', 'w', encoding='utf-8') as f:
    f.write(content)
