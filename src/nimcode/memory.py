import os
from typing import List, Dict, Any

class MemoryManager:
    def __init__(self, max_tokens: int = 4000):
        # We assume 1 token ~= 4 chars roughly
        self.max_tokens = max_tokens

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
