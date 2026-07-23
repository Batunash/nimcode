import pytest
import httpx
import respx
import asyncio
import json
from unittest.mock import patch
from nimcode.nim_client import NimClient

@pytest.fixture
def client():
    return NimClient(api_key="test_key")

def test_count_tokens_approx(client):
    messages = [
        {"role": "system", "content": "Hello"},
        {"role": "user", "content": "World!"}
    ]
    # system(6) + Hello(5) = 11
    # user(4) + World!(6) = 10
    # Total chars = 21. 21 // 4 = 5. Plus 2 messages * 4 = 8. Total = 13
    assert client.count_tokens_approx(messages) == 13

@pytest.mark.asyncio
@respx.mock
async def test_chat_success(client):
    messages = [{"role": "user", "content": "Hi"}]
    
    mock_route = respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, 
            content=b'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\ndata: [DONE]\n'
        )
    )

    chunks = []
    async for chunk in client.chat(messages):
        chunks.append(chunk)

    assert chunks == ["Hello"]
    assert mock_route.called

@pytest.mark.asyncio
@respx.mock
async def test_chat_malformed_json_skipped(client):
    messages = [{"role": "user", "content": "Hi"}]
    
    mock_route = respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, 
            content=b'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\ndata: {bad json\n\ndata: [DONE]\n'
        )
    )

    chunks = []
    async for chunk in client.chat(messages):
        chunks.append(chunk)

    assert chunks == ["Hello"]

@pytest.mark.asyncio
@respx.mock
async def test_chat_400_bad_request(client):
    messages = [{"role": "user", "content": "Hi"}]
    
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=httpx.Response(400, content=b"Bad Request Error")
    )

    chunks = []
    async for chunk in client.chat(messages):
        chunks.append(chunk)
        
    assert "Error: Model API returned 400" in chunks[0]

@pytest.mark.asyncio
@respx.mock
async def test_chat_unexpected_error(client):
    messages = [{"role": "user", "content": "Hi"}]
    
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        side_effect=httpx.ConnectError("Network Error")
    )

    chunks = []
    async for chunk in client.chat(messages):
        chunks.append(chunk)

    assert "Error communicating with NVIDIA API" in chunks[0]

@pytest.mark.asyncio
@respx.mock
async def test_chat_vision(client):
    # Test chat_vision to get coverage
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "vision success"}}]})
    )
    result = await client.chat_vision("base64_fake_data", "What is this?")
    assert result == "vision success"

@pytest.mark.asyncio
@respx.mock
async def test_chat_vision_error(client):
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=httpx.Response(400, content=b"Bad vision")
    )
    result = await client.chat_vision("base64_fake_data", "What is this?")
    assert "Vision processing failed" in result

@pytest.mark.asyncio
@respx.mock
async def test_chat_vision_unexpected_error(client):
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        side_effect=Exception("Fatal Error")
    )
    result = await client.chat_vision("base64", "prompt")
    assert "Vision error: Fatal Error" in result

@pytest.mark.asyncio
@respx.mock
async def test_chat_one_shot(client):
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "one shot success"}}]})
    )
    result = await client.chat_one_shot("prompt")
    assert result == "one shot success"
    
@pytest.mark.asyncio
async def test_get_available_models(client):
    models = await client.get_available_models()
    assert len(models) > 0

@pytest.mark.asyncio
@respx.mock
async def test_chat_tools_passed(client):
    messages = [{"role": "user", "content": "Hi"}]
    tools = [{"type": "function", "function": {"name": "test_tool"}}]
    
    def check_request(request):
        payload = json.loads(request.content)
        assert "tools" in payload
        assert payload["tools"] == tools
        return httpx.Response(200, content=b'data: [DONE]\n')

    mock_route = respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(side_effect=check_request)

    async for _ in client.chat(messages, tools=tools):
        pass

    assert mock_route.called
