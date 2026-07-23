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

    with pytest.raises(ValueError, match="HTTP 400 Bad Request: Bad Request Error"):
        async for _ in client.chat(messages):
            pass

@pytest.mark.asyncio
@respx.mock
async def test_chat_unexpected_error(client):
    messages = [{"role": "user", "content": "Hi"}]
    
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=httpx.Response(403, content=b"Forbidden")
    )

    with pytest.raises(RuntimeError, match="Unexpected API error 403: Forbidden"):
        async for _ in client.chat(messages):
            pass

@pytest.mark.asyncio
@respx.mock
async def test_chat_retries_on_500(client):
    messages = [{"role": "user", "content": "Hi"}]
    
    # First 4 times return 500, 5th time return 200
    mock_route = respx.post("https://integrate.api.nvidia.com/v1/chat/completions")
    mock_route.side_effect = [
        httpx.Response(500),
        httpx.Response(502),
        httpx.Response(503),
        httpx.Response(429),
        httpx.Response(200, content=b'data: {"choices": [{"delta": {"content": "Success"}}]}\n\ndata: [DONE]\n')
    ]

    with patch("asyncio.sleep") as mock_sleep:
        chunks = []
        async for chunk in client.chat(messages):
            chunks.append(chunk)
            
        assert chunks == ["Success"]
        assert mock_sleep.call_count == 4

@pytest.mark.asyncio
@respx.mock
async def test_chat_max_retries_exceeded(client):
    messages = [{"role": "user", "content": "Hi"}]
    
    mock_route = respx.post("https://integrate.api.nvidia.com/v1/chat/completions")
    mock_route.side_effect = [httpx.Response(500)] * 5

    with patch("asyncio.sleep") as mock_sleep:
        with pytest.raises(httpx.HTTPStatusError):
            async for _ in client.chat(messages):
                pass
        
        assert mock_sleep.call_count == 4

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
