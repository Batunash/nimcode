import httpx
import asyncio
import logging
import json
import random
from typing import List, Dict, Any, Optional, AsyncGenerator

logger = logging.getLogger(__name__)

class NimClient:
    def __init__(self, api_key: str, base_url: str = "https://integrate.api.nvidia.com/v1", model: str = "deepseek-ai/deepseek-v4-pro", timeout: float = 120.0, max_retries: int = 15, retry_base_delay: float = 2.0, retry_max_delay: float = 60.0):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = None if timeout == 0 else timeout
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.retry_max_delay = retry_max_delay
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        
    async def get_available_models(self) -> List[str]:
        """Fetches available models from the NIM API. Falls back to known models on error."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=self.headers,
                    timeout=10.0
                )
                if response.status_code == 200:
                    data = response.json()
                    models = [m["id"] for m in data.get("data", []) if m.get("id")]
                    if models:
                        return sorted(models)
        except Exception as e:
            logger.debug(f"Failed to fetch models from API: {e}")
        
        # Fallback to known model list
        from .model_registry import FALLBACK_MODELS
        return FALLBACK_MODELS

    async def chat_one_shot(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.2
        }
        delay = self.retry_base_delay
        for attempt in range(self.max_retries):
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self.headers,
                        json=payload,
                        timeout=self.timeout
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429 and attempt < self.max_retries - 1:
                        logger.warning(f"Rate limited (429) in chat_one_shot. Retrying in {delay}s...")
                        await asyncio.sleep(delay)
                        delay *= 2
                    else:
                        raise
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        logger.warning(f"Error in chat_one_shot: {e}. Retrying in {delay}s...")
                        await asyncio.sleep(delay)
                        delay *= 2
                    else:
                        raise

    async def chat_vision(self, base64_image: str, prompt: str) -> str:
        # For vision, we might need a specific vision model, but we'll try with the default if it supports multimodal
        # Or switch to a known vision model like nv-llama-3.2-90b-vision-instruct
        vision_model = "meta/llama-3.2-90b-vision-instruct"
        payload = {
            "model": vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.2
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                logger.error(f"Vision API error: {e.response.text}")
                return f"Vision processing failed: {e.response.text}"
            except Exception as e:
                return f"Vision error: {str(e)}"

    async def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None, stream: bool = True) -> AsyncGenerator[str, None]:
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.2,
            "stream": stream
        }
        
        max_retries = self.max_retries
        base_delay = self.retry_base_delay
        max_delay = self.retry_max_delay
        
        for attempt in range(max_retries):
            chunk_yielded = False
            try:
                async with httpx.AsyncClient() as client:
                    async with client.stream("POST", f"{self.base_url}/chat/completions", headers=self.headers, json=payload, timeout=self.timeout) as response:
                        if response.status_code in [408, 429, 500, 502, 503, 504, 529]:
                            raise httpx.HTTPStatusError(f"Temporary server error {response.status_code}", request=response.request, response=response)
                        
                        response.raise_for_status()
                        
                        async for line in response.aiter_lines():
                            if line.startswith("data: ") and line != "data: [DONE]":
                                data_str = line[6:]
                                try:
                                    data_json = json.loads(data_str)
                                    chunk = data_json["choices"][0]["delta"].get("content", "")
                                    if chunk:
                                        chunk_yielded = True
                                        yield chunk
                                except json.JSONDecodeError:
                                    pass
                        return  # Success
            except httpx.HTTPStatusError as e:
                transient_codes = [408, 429, 500, 502, 503, 504, 529]
                if e.response.status_code not in transient_codes or chunk_yielded or attempt == max_retries - 1:
                    try:
                        await e.response.aread()
                        text = e.response.text
                    except Exception:
                        text = "<unread stream>"
                    logger.error(f"API HTTP error: {e.response.status_code} - {text}")
                    if e.response.status_code == 429:
                        yield f"\n\n[Error: Rate Limit Exceeded (429). The API rejected the request because of too many requests or exceeded quota. Please try again later, check your NIM credits, or switch to a different model.]"
                    else:
                        yield f"\n\n[Error: Model API returned {e.response.status_code}. Please check your API key if 401.]"
                    return
                    
                delay = min(max_delay, base_delay * (2 ** attempt))
                logger.warning(f"API HTTP error {e.response.status_code}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
                
            except Exception as e:
                if chunk_yielded or attempt == max_retries - 1:
                    logger.error(f"API connection error: {type(e).__name__} - {e}")
                    yield f"\n\n[Error communicating with NVIDIA API: {type(e).__name__} - {e}]"
                    return
                    
                delay = min(max_delay, base_delay * (2 ** attempt))
                logger.warning(f"API connection error: {type(e).__name__} - {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)

    def count_tokens_approx(self, messages: List[Dict[str, Any]]) -> int:
        total_chars = 0
        for msg in messages:
            total_chars += len(msg.get("role", ""))
            total_chars += len(str(msg.get("content", "")))
        return total_chars // 4 + (len(messages) * 4)
