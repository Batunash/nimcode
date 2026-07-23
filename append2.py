with open('tests/test_agent.py', 'a', encoding='utf-8') as f:
    f.write('''
@pytest.mark.asyncio
async def test_agent_auto_linting_py(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    agent.max_turns = 2
    agent._stream_response = AsyncMock(side_effect=["<tool_call>{\\\"tool\\\": \\\"Write\\\", \\\"args\\\": {\\\"file_path\\\": \\\"test.py\\\"}}</tool_call>", "TASK_COMPLETE"])
    
    with patch("nimcode.lenient_parser.LenientParser.process_model_response") as mock_parse:
        mock_parse.side_effect = [
            ("prose", [{"tool": "Write", "args": {"file_path": "test.py"}}]),
            ("prose", [])
        ]
        with patch("nimcode.permissions.PermissionEngine.check_permission", return_value=True):
            with patch("nimcode.tools.ToolRegistry.get_tool_schema", return_value={"name": "Write"}):
                with patch("nimcode.tools.ToolRegistry.execute", return_value="Diff:\\n+ print('hello')"):
                    with patch("subprocess.run") as mock_run:
                        # Mock flake8 error
                        mock_run.return_value = MagicMock(returncode=1, stdout="Syntax error")
                        await agent.run("Hi")
                        assert "Auto-Linter found errors:" in agent.messages[-2]["content"]

@pytest.mark.asyncio
async def test_agent_auto_linting_js(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    agent.max_turns = 2
    agent._stream_response = AsyncMock(side_effect=["<tool_call>{\\\"tool\\\": \\\"Write\\\", \\\"args\\\": {\\\"file_path\\\": \\\"test.js\\\"}}</tool_call>", "TASK_COMPLETE"])
    
    with patch("nimcode.lenient_parser.LenientParser.process_model_response") as mock_parse:
        mock_parse.side_effect = [
            ("prose", [{"tool": "Write", "args": {"file_path": "test.js"}}]),
            ("prose", [])
        ]
        with patch("nimcode.permissions.PermissionEngine.check_permission", return_value=True):
            with patch("nimcode.tools.ToolRegistry.get_tool_schema", return_value={"name": "Write"}):
                with patch("nimcode.tools.ToolRegistry.execute", return_value="Output"):
                    with patch("subprocess.run") as mock_run:
                        await agent.run("Hi")
                        assert mock_run.call_count == 1
                        assert "prettier" in mock_run.call_args[0][0]

@pytest.mark.asyncio
async def test_distill_memory_context_full(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    agent._stream_response = AsyncMock(return_value="TASK_COMPLETE")
    
    # Fake large token count
    agent.memory.count_messages_tokens = MagicMock(return_value=5000)
    agent.memory.max_tokens = 4000
    agent._distill_memory = AsyncMock(return_value=[{"role": "system", "content": "Distilled"}])
    
    await agent.run("Hi")
    assert agent.messages[0]["content"] == "Distilled"
''')
