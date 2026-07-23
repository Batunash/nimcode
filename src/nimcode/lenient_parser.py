import re
import json
import logging
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)

class LenientParser:
    @staticmethod
    def extract_tool_calls(text: str) -> List[str]:
        """Extracts JSON strings from <tool_call> fenced blocks."""
        # The model might forget the closing tag, or put markdown fences around it.
        # We look for <tool_call> and extract everything until </tool_call> or EOF.
        pattern = re.compile(r"<tool_call>\s*(.*?)(?:</tool_call>|\Z)", re.DOTALL | re.IGNORECASE)
        matches = pattern.findall(text)
        
        # Clean up markdown code blocks if the model wrapped the JSON in them
        cleaned_matches = []
        for match in matches:
            match = match.strip()
            if match.startswith("```json"):
                match = match[7:]
            elif match.startswith("```"):
                match = match[3:]
            
            if match.endswith("```"):
                match = match[:-3]
                
            cleaned_matches.append(match.strip())
            
        return cleaned_matches

    @staticmethod
    def repair_json(json_str: str) -> str:
        """Attempts to fix common model JSON formatting errors."""
        repaired = json_str.strip()
        
        # 1. Remove trailing commas in objects and arrays
        repaired = re.sub(r",\s*}", "}", repaired)
        repaired = re.sub(r",\s*]", "]", repaired)
        
        # 2. Fix unescaped newlines within strings.
        # A simple approach: we find things that look like string literals and escape newlines.
        # We'll use a state machine or regex for simple cases. 
        # For a robust approach without a full parser, we replace literal newlines that are inside quotes.
        # Actually, python's json.loads is quite strict about unescaped newlines.
        def escape_newlines_in_strings(match):
            return match.group(0).replace("\n", "\\n")
            
        # Match string literals: " followed by anything except unescaped quote, followed by "
        # We need to be careful with escaped quotes inside the string.
        string_regex = re.compile(r'"(?:[^"\\]|\\.)*"', re.DOTALL)
        repaired = string_regex.sub(escape_newlines_in_strings, repaired)
        
        # 3. Very rudimentary single quote to double quote conversion for keys/values
        # (Only if it fails standard parsing, but we can do it proactively for top-level if needed).
        # We will try standard json.loads first, and if it fails, maybe do more aggressive repair.
        return repaired

    @classmethod
    def parse_tool_call(cls, tool_call_text: str) -> Dict[str, Any]:
        """Parses a tool call string into a dictionary."""
        try:
            return json.loads(tool_call_text)
        except json.JSONDecodeError:
            pass
            
        # Try repairing
        repaired = cls.repair_json(tool_call_text)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse tool call even after repair: {repaired}")
            raise ValueError(f"Malformed tool call JSON: {e}") from e

    @classmethod
    def process_model_response(cls, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Parses the raw text response from the model.
        Returns (plain_text_message, list_of_tool_calls).
        """
        # First, extract the tool calls
        tool_call_strings = cls.extract_tool_calls(text)
        
        tool_calls = []
        for tc_str in tool_call_strings:
            if not tc_str:
                continue
            try:
                tc = cls.parse_tool_call(tc_str)
                tool_calls.append(tc)
            except ValueError:
                # We could append an error message or raise. We'll raise to let the agent loop handle it and re-prompt.
                raise
                
        # The plain text is whatever is not in the tool_call blocks.
        # We remove the tool call blocks from the original text to get the assistant's prose.
        plain_text = re.sub(r"<tool_call>\s*(.*?)(?:</tool_call>|\Z)", "", text, flags=re.DOTALL | re.IGNORECASE)
        plain_text = plain_text.strip()
        
        return plain_text, tool_calls
