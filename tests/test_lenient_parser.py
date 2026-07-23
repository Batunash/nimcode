import pytest
from nimcode.lenient_parser import LenientParser

def test_extract_tool_calls_clean():
    text = "Here is my tool call:\n<tool_call>\n{\"tool\": \"Read\", \"args\": {}}\n</tool_call>\nAnd some prose."
    calls = LenientParser.extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0] == "{\"tool\": \"Read\", \"args\": {}}"

def test_extract_tool_calls_unclosed():
    text = "Here is my tool call:\n<tool_call>\n{\"tool\": \"Read\"}"
    calls = LenientParser.extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0] == "{\"tool\": \"Read\"}"

def test_extract_tool_calls_markdown_wrapped():
    text = "<tool_call>\n```json\n{\"tool\": \"Read\"}\n```\n</tool_call>"
    calls = LenientParser.extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0] == "{\"tool\": \"Read\"}"

def test_extract_tool_calls_markdown_wrapped_no_lang():
    text = "<tool_call>\n```\n{\"tool\": \"Read\"}\n```\n</tool_call>"
    calls = LenientParser.extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0] == "{\"tool\": \"Read\"}"

def test_repair_trailing_comma():
    bad_json = '{"tool": "Read", "args": {"file": "a.txt",},}'
    parsed = LenientParser.parse_tool_call(bad_json)
    assert parsed["tool"] == "Read"
    assert parsed["args"]["file"] == "a.txt"

def test_repair_unescaped_newlines():
    bad_json = '{"tool": "Write", "args": {"content": "Line1\nLine2"}}'
    parsed = LenientParser.parse_tool_call(bad_json)
    assert parsed["args"]["content"] == "Line1\nLine2"

def test_parse_invalid_raises():
    bad_json = '{"tool": "Read", "args": {broken}}'
    with pytest.raises(ValueError, match="Malformed tool call JSON"):
        LenientParser.parse_tool_call(bad_json)

def test_process_model_response():
    text = "Sure, I will read the file.\n<tool_call>\n{\"tool\": \"Read\", \"args\": {\"file\": \"a.txt\"}}\n</tool_call>\nDone."
    prose, calls = LenientParser.process_model_response(text)
    assert prose == "Sure, I will read the file.\n\nDone."
    assert len(calls) == 1
    assert calls[0]["tool"] == "Read"

def test_process_model_response_empty_call():
    text = "<tool_call>\n\n</tool_call>"
    prose, calls = LenientParser.process_model_response(text)
    assert len(calls) == 0

def test_process_model_response_raises_on_invalid():
    text = "<tool_call>\n{invalid}\n</tool_call>"
    with pytest.raises(ValueError, match="Malformed tool call JSON"):
        LenientParser.process_model_response(text)
