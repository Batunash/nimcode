import re
import json
import logging
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)

class LenientParser:
    @staticmethod
    def extract_tool_calls(text: str) -> List[Tuple[str, str]]:
        """Extracts tool names and JSON strings from <tool_call> fenced blocks."""
        # We look for <tool_call> or <tool_call name="..."> and extract everything until </tool_call> or EOF.
        pattern = re.compile(r"<tool_call([^>]*)>\s*(.*?)(?:</tool_call>|\Z)", re.DOTALL | re.IGNORECASE)
        matches = pattern.findall(text)
        
        # Clean up markdown code blocks if the model wrapped the JSON in them
        cleaned_matches = []
        for attr_str, inner_text in matches:
            # Parse name from attributes if it exists (e.g., name="Read")
            name = ""
            name_match = re.search(r'name=["\'](.*?)["\']', attr_str, re.IGNORECASE)
            if name_match:
                name = name_match.group(1).strip()

            match = inner_text.strip()
            if match.startswith("```json"):
                match = match[7:]
            elif match.startswith("```"):
                match = match[3:]
            
            if match.endswith("```"):
                match = match[:-3]
                
            cleaned_matches.append((name, match.strip()))
            
        return cleaned_matches

    @staticmethod
    def repair_json(json_str: str) -> str:
        """Attempts to fix common model JSON formatting errors."""
        repaired = json_str.strip()
        
        # 1. Remove trailing commas in objects and arrays
        repaired = re.sub(r",\s*}", "}", repaired)
        repaired = re.sub(r",\s*]", "]", repaired)
        
        # 2. Fix unescaped newlines within strings.
        def escape_newlines_in_strings(match):
            return match.group(0).replace("\n", "\\n")
            
        string_regex = re.compile(r'"(?:[^"\\]|\\.)*"', re.DOTALL)
        repaired = string_regex.sub(escape_newlines_in_strings, repaired)
        
        # 3. Handle truncated JSON outputs (e.g. model stream cut off)
        # If it seems like an unclosed string, close it.
        open_quotes = len(re.findall(r'(?<!\\)"', repaired))
        if open_quotes % 2 != 0:
            repaired += '"'
            
        # Count open brackets and braces to auto-close them, ignoring those inside strings
        # We can remove all properly closed strings before counting
        no_strings = re.sub(r'"(?:[^"\\]|\\.)*"', '""', repaired)
        open_braces = no_strings.count("{") - no_strings.count("}")
        open_brackets = no_strings.count("[") - no_strings.count("]")
        
        if open_brackets > 0:
            repaired += "]" * open_brackets
        if open_braces > 0:
            repaired += "}" * open_braces
            
        return repaired

    @staticmethod
    def _extract_content_fallback(repaired: str) -> Optional[Dict[str, Any]]:
        """Fallback regex extractor for Append, Write, and ReplaceBlock tools when JSON parser fails due to unescaped quotes."""
        try:
            tool_match = re.search(r'"tool"\s*:\s*"([^"]+)"', repaired)
            if not tool_match:
                return None
            
            tool_name = tool_match.group(1)
            if tool_name not in ["Append", "Write", "ReplaceBlock"]:
                return None
                
            fp_match = re.search(r'"file_path"\s*:\s*"([^"]+)"', repaired)
            if not fp_match:
                return None
                
            fp = fp_match.group(1)
            content_key = "replacement_content" if tool_name == "ReplaceBlock" else "content"
            content_start_idx = repaired.find(f'"{content_key}"')
            if content_start_idx == -1:
                return None
            
            # Find the colon after the key
            colon_idx = repaired.find(':', content_start_idx + len(content_key) + 2)
            if colon_idx == -1:
                return None
                
            # Find the opening quote of the value
            quote_idx = repaired.find('"', colon_idx)
            if quote_idx == -1:
                return None
                
            rest = repaired[quote_idx + 1:]
            
            # Strip trailing braces, brackets, whitespace, and the final quote
            rest = rest.rstrip(' \t\n\r}]+')
            if rest.endswith('"'):
                rest = rest[:-1]
            raw_content = rest
            raw_content = raw_content.replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')
            
            if tool_name == "ReplaceBlock":
                sl_match = re.search(r'"start_line"\s*:\s*(\d+)', repaired)
                el_match = re.search(r'"end_line"\s*:\s*(\d+)', repaired)
                if sl_match and el_match:
                    return {
                        "tool": tool_name, 
                        "args": {
                            "file_path": fp, 
                            "start_line": int(sl_match.group(1)), 
                            "end_line": int(el_match.group(1)), 
                            "replacement_content": raw_content
                        }
                    }
                return None
            else:
                return {
                    "tool": tool_name, 
                    "args": {
                        "file_path": fp, 
                        "content": raw_content
                    }
                }
        except Exception as e:
            logger.debug(f"Fallback extraction failed: {e}")
            return None

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
            # Fallback for unescaped quotes in Append/Write/ReplaceBlock
            fallback_result = cls._extract_content_fallback(repaired)
            if fallback_result:
                return fallback_result
                
            
            logger.error(f"Failed to parse tool call even after repair: {repaired}")
            raise ValueError(f"Malformed tool call JSON: {e}") from e

    @classmethod
    def process_model_response(cls, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Parses the raw text response from the model.
        Returns (plain_text_message, list_of_tool_calls).
        """
        # First, extract the tool calls
        tool_call_tuples = cls.extract_tool_calls(text)
        
        tool_calls = []
        for name, tc_str in tool_call_tuples:
            if not tc_str:
                continue
            try:
                tc_json = cls.parse_tool_call(tc_str)
                # If model used <tool_call name="..."> and provided raw arguments in JSON
                if isinstance(tc_json, dict) and "tool" not in tc_json and name:
                    tc = {"tool": name, "args": tc_json}
                else:
                    tc = tc_json
                tool_calls.append(tc)
            except ValueError:
                # We could append an error message or raise. We'll raise to let the agent loop handle it and re-prompt.
                raise
                
        # The plain text is whatever is not in the tool_call blocks.
        # We remove the tool call blocks from the original text to get the assistant's prose.
        plain_text = re.sub(r"<tool_call[^>]*>\s*(.*?)(?:</tool_call>|\Z)", "", text, flags=re.DOTALL | re.IGNORECASE)
        plain_text = plain_text.strip()
        
        return plain_text, tool_calls
