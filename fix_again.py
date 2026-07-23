import re

with open('tests/test_repl.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: _stream_response mock in test_run_complete
content = re.sub(
    r'async def stream_mock\(\*args, \*\*kwargs\):\n\s+yield "TASK_COMPLETE"\n\s+agent._stream_response = stream_mock',
    r'agent._stream_response = AsyncMock(return_value="TASK_COMPLETE")',
    content
)

# Fix 2: _stream_response mock in test_stream_response_success
content = re.sub(
    r'async def mock_chat_generator\(msgs\):\n\s+yield "Hello"\n\s+yield " World"\n\s+a.client.chat.return_value = mock_chat_generator\(\[\]\)',
    r'''async def mock_chat_generator(*args, **kwargs):
            yield "Hello"
            yield " World"
        a.client.chat = mock_chat_generator''',
    content
)

# Also fix the assert in test_stream_response_success which we accidentally changed to agent.messages[-1]
content = content.replace(
    'res = await agent._stream_response()\n        assert agent.messages[-1]["content"] == "TASK_COMPLETE"',
    'res = await agent._stream_response()\n        assert res == "Hello World"'
)

with open('tests/test_repl.py', 'w', encoding='utf-8') as f:
    f.write(content)
