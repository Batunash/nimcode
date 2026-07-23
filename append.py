with open('tests/test_agent.py', 'a', encoding='utf-8') as f:
    f.write('''
@pytest.mark.asyncio
async def test_run_subagent_max_turns(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    
    agent._stream_response = AsyncMock(return_value="Something")
    agent.parser.parse = MagicMock(return_value=[])
    
    await agent.run("Hi")
    assert agent.messages[-1]["role"] == "user"
    assert "Please continue" in agent.messages[-1]["content"]

@pytest.mark.asyncio
async def test_run_subagent_tool_denied(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    agent._stream_response = AsyncMock(return_value="<tool_call>{\\\"tool\\\": \\\"Read\\\", \\\"args\\\": {}}</tool_call>")
    
    with patch("nimcode.lenient_parser.LenientParser.process_model_response") as mock_parse:
        mock_parse.return_value = ("prose", [{"tool": "Read", "args": {}}])
        with patch("nimcode.permissions.PermissionEngine.check_permission", return_value=False):
            await agent.run("Hi")
            assert "User explicitly denied" in agent.messages[-1]["content"]

@pytest.mark.asyncio
async def test_run_subagent_tool_success(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    agent.max_turns = 2
    agent._stream_response = AsyncMock(side_effect=["<tool_call>{\\\"tool\\\": \\\"Read\\\", \\\"args\\\": {}}</tool_call>", "TASK_COMPLETE"])
    
    with patch("nimcode.lenient_parser.LenientParser.process_model_response") as mock_parse:
        mock_parse.side_effect = [
            ("prose", [{"tool": "Read", "args": {}}]),
            ("prose", [])
        ]
        with patch("nimcode.permissions.PermissionEngine.check_permission", return_value=True):
            with patch("nimcode.tools.ToolRegistry.get_tool_schema", return_value={"name": "Read"}):
                with patch("nimcode.tools.ToolRegistry.execute", return_value="Output"):
                    await agent.run("Hi")
                    # Should reach TASK_COMPLETE

@pytest.mark.asyncio
async def test_run_subagent_tool_error(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    agent.max_turns = 2
    agent._stream_response = AsyncMock(side_effect=["<tool_call>{\\\"tool\\\": \\\"Read\\\", \\\"args\\\": {}}</tool_call>", "TASK_COMPLETE"])
    
    with patch("nimcode.lenient_parser.LenientParser.process_model_response") as mock_parse:
        mock_parse.side_effect = [
            ("prose", [{"tool": "Read", "args": {}}]),
            ("prose", [])
        ]
        with patch("nimcode.permissions.PermissionEngine.check_permission", return_value=True):
            with patch("nimcode.tools.ToolRegistry.get_tool_schema", return_value={"name": "Read"}):
                with patch("nimcode.tools.ToolRegistry.execute", side_effect=Exception("Read Error")):
                    await agent.run("Hi")
                    assert "Tool Read returned:\\nRead Error" in agent.messages[-2]["content"]

@pytest.mark.asyncio
async def test_run_subagent_mcp_tool(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    agent.max_turns = 2
    agent._stream_response = AsyncMock(side_effect=["<tool_call>{\\\"tool\\\": \\\"Read\\\", \\\"args\\\": {}}</tool_call>", "TASK_COMPLETE"])
    
    with patch("nimcode.lenient_parser.LenientParser.process_model_response") as mock_parse:
        mock_parse.side_effect = [
            ("prose", [{"tool": "Read", "args": {}}]),
            ("prose", [])
        ]
        with patch("nimcode.permissions.PermissionEngine.check_permission", return_value=True):
            with patch("nimcode.tools.ToolRegistry.get_tool_schema", return_value=None):
                
                class MockCallToolResult:
                    def __init__(self, text):
                        self.text = text
                class MockMCPResult:
                    def __init__(self):
                        self.content = [MockCallToolResult("MCP Output")]
                        
                agent.mcp.call_tool_by_name = AsyncMock(return_value=MockMCPResult())
                await agent.run("Hi")
                assert "Tool Read returned:\\nMCP Output" in agent.messages[-2]["content"]

@pytest.mark.asyncio
async def test_run_subagent_mcp_tool_error(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    agent.max_turns = 2
    agent._stream_response = AsyncMock(side_effect=["<tool_call>{\\\"tool\\\": \\\"Read\\\", \\\"args\\\": {}}</tool_call>", "TASK_COMPLETE"])
    
    with patch("nimcode.lenient_parser.LenientParser.process_model_response") as mock_parse:
        mock_parse.side_effect = [
            ("prose", [{"tool": "Read", "args": {}}]),
            ("prose", [])
        ]
        with patch("nimcode.permissions.PermissionEngine.check_permission", return_value=True):
            with patch("nimcode.tools.ToolRegistry.get_tool_schema", return_value=None):
                agent.mcp.call_tool_by_name = AsyncMock(side_effect=Exception("MCP Down"))
                await agent.run("Hi")
                assert "Error executing MCP tool Read: MCP Down" in agent.messages[-2]["content"]

def test_agent_git_context_error():
    with patch("os.path.exists", return_value=True):
        with patch("subprocess.check_output", side_effect=Exception("Git error")):
            agent = Agent(api_key="key")
            assert "GIT CONTEXT" not in agent.messages[0]["content"]
            
def test_agent_load_skills(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "skill1.md").write_text("Do good stuff")
    
    with patch("nimcode.agent.Path.home", return_value=tmp_path):
        agent = Agent(api_key="key")
        assert "CRITICAL USER SKILLS" in agent.messages[0]["content"]
        assert "Do good stuff" in agent.messages[0]["content"]
''')
