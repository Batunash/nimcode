import httpx
import asyncio
import logging
import json
import random
from typing import List, Dict, Any, Optional, AsyncGenerator

logger = logging.getLogger(__name__)

class NimClient:
    def __init__(self, api_key: str, base_url: str = "https://integrate.api.nvidia.com/v1", model: str = "meta/llama-3.1-70b-instruct"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        
    async def get_available_models(self) -> List[str]:
        return [
            "meta/llama-3.1-70b-instruct",
            "meta/llama-3.1-8b-instruct",
            "meta/llama-3.1-405b-instruct",
            "nvidia/nemotron-4-340b-instruct",
            "mistralai/mixtral-8x22b-instruct-v0.1"
        ]

    async def chat_one_shot(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.2
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

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
                    timeout=60.0
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
        
        max_retries = 6
        base_delay = 2.0
        
        for attempt in range(max_retries):
            chunk_yielded = False
            try:
                async with httpx.AsyncClient() as client:
                    async with client.stream("POST", f"{self.base_url}/chat/completions", headers=self.headers, json=payload, timeout=60.0) as response:
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
                    yield f"\n\n[Error: Model API returned {e.response.status_code}. Please check your API key if 401.]"
                    return
                    
                delay = base_delay * (2 ** attempt)
                logger.warning(f"API HTTP error {e.response.status_code}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
                
            except Exception as e:
                if chunk_yielded or attempt == max_retries - 1:
                    logger.error(f"API connection error: {type(e).__name__} - {e}")
                    yield f"\n\n[Error communicating with NVIDIA API: {type(e).__name__} - {e}]"
                    return
                    
                delay = base_delay * (2 ** attempt)
                logger.warning(f"API connection error: {type(e).__name__} - {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)

    def count_tokens_approx(self, messages: List[Dict[str, Any]]) -> int:
        total_chars = 0
        for msg in messages:
            total_chars += len(msg.get("role", ""))
            total_chars += len(str(msg.get("content", "")))
        return total_chars // 4 + (len(messages) * 4)
