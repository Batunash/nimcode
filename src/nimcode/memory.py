import os
import json
import time
import urllib.request
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class DynamicContextFetcher:
    CACHE_FILE = os.path.expanduser('~/.nimcode/context_map.json')
    CACHE_EXPIRY = 24 * 3600 # 24 hours
    URL = 'https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json'

    @classmethod
    def get_max_tokens(cls, model_name: str, default_limit: int = 8000) -> int:
        if not model_name:
            return default_limit
            
        data = cls._load_map()
        if not data:
            return default_limit
        
        # Exact match
        for k, v in data.items():
            if model_name.lower() == k.lower():
                return v.get('max_tokens', default_limit) or default_limit
                
        # Heuristic matching
        clean_model = model_name.split('/')[-1].lower()
        
        matches = []
        for k, v in data.items():
            if clean_model in k.lower():
                tokens = v.get('max_tokens')
                if tokens:
                    matches.append(tokens)
                    
        if matches:
            return max(matches)
            
        return default_limit

    @classmethod
    def _load_map(cls) -> Optional[dict]:
        if os.path.exists(cls.CACHE_FILE):
            if time.time() - os.path.getmtime(cls.CACHE_FILE) < cls.CACHE_EXPIRY:
                try:
                    with open(cls.CACHE_FILE, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except:
                    pass
                    
        # Fetch live
        try:
            req = urllib.request.Request(cls.URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5.0) as res:
                data = json.loads(res.read().decode('utf-8'))
                os.makedirs(os.path.dirname(cls.CACHE_FILE), exist_ok=True)
                with open(cls.CACHE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f)
                return data
        except Exception as e:
            logger.debug(f"Failed to fetch dynamic context map: {e}")
            return None

class MemoryManager:
    def __init__(self, model_name: str = None, fallback_max_tokens: int = 8000):
        # We assume 1 token ~= 4 chars roughly
        self.model_name = model_name
        self.fallback_max_tokens = fallback_max_tokens
        
    @property
    def max_tokens(self) -> int:
        if not self.model_name:
            return self.fallback_max_tokens
        return DynamicContextFetcher.get_max_tokens(self.model_name, self.fallback_max_tokens)

    @staticmethod
    def count_tokens(text: str) -> int:
        """Roughly count tokens in a string."""
        if not text:
            return 0
        return len(text) // 4 + 1

    @classmethod
    def count_messages_tokens(cls, messages: List[Dict[str, Any]]) -> int:
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            total += cls.count_tokens(content)
        return total

    def compact_context(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        If messages exceed max_tokens, drops the oldest messages.
        Always keeps the System prompt (first message).
        Always keeps the most recent user prompt.
        """
        total_tokens = self.count_messages_tokens(messages)
        if total_tokens <= self.max_tokens:
            return messages

        # We need to compact
        if not messages:
            return messages

        compacted = [messages[0]] # System prompt
        remaining_messages = messages[1:]
        
        # We start from the end and add backwards until we hit the limit
        # Reserved tokens for system prompt
        current_tokens = self.count_tokens(messages[0].get("content", ""))
        
        kept_messages = []
        for msg in reversed(remaining_messages):
            msg_tokens = self.count_tokens(msg.get("content", ""))
            if current_tokens + msg_tokens > self.max_tokens:
                # If we haven't even kept the most recent message, we MUST keep it and just truncate its content
                if not kept_messages:
                    truncated_content = msg.get("content", "")[:(self.max_tokens - current_tokens) * 4]
                    kept_messages.insert(0, {"role": msg["role"], "content": truncated_content + "...[TRUNCATED]"})
                break
            
            kept_messages.insert(0, msg)
            current_tokens += msg_tokens

        compacted.extend(kept_messages)
        return compacted

    @staticmethod
    def log_to_nimcode_md(turn: int, prompt: str, response: str, cwd: str = ".") -> None:
        """Appends the interaction to NIMCODE.md for persistent session history."""
        file_path = os.path.join(cwd, "NIMCODE.md")
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"## Turn {turn}\n\n")
            f.write(f"**User**: {prompt}\n\n")
            f.write(f"**Agent**: {response}\n\n")
            f.write("---\n\n")
