# webtactix/llm/openai_compat
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Union
import tiktoken
from openai import AsyncOpenAI


@dataclass(frozen=True)
class OpenAICompatConfig:
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.0
    timeout_s: float = 180.0


class OpenAICompatClient:
    """
    Standard OpenAI Python SDK client with custom base_url.
    Works for OpenAI, Qwen, DeepSeek, and other OpenAI-compatible services.
    """

    def __init__(self, cfg: OpenAICompatConfig) -> None:
        self.cfg = cfg

        self._client = AsyncOpenAI(
            base_url=self.cfg.base_url,
            api_key=self.cfg.api_key,
            timeout=self.cfg.timeout_s,
        )

    async def chat_text(self, *, system: str, user: str, temperature: Optional[float] = None) -> Tuple[str, Dict[str, Any]]:
        temp = self.cfg.temperature if temperature is None else float(temperature)
        model = self.cfg.model

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        attempt = 0
        while attempt < 3:
            try:
                print(f'[DBG] Creating completions request... (Attempt {attempt+1})')
                resp = await self._client.chat.completions.create(
                    model=model,
                    temperature=temp,
                    messages=messages,
                )
                print(f'[DBG] Completions request returned successfully.')
                break
            except Exception as e:
                import asyncio
                if "429" in str(e) or "rate limit" in str(e).lower():
                    print(f"[LLM] Rate limit hit, waiting 30s...")
                    await asyncio.sleep(30)
                    continue  # Do not increment attempt for rate limits
                else:
                    attempt += 1
                    print(f'[LLM ERR] Attempt {attempt}:', type(e).__name__, str(e))
                    await asyncio.sleep(20)
        else:
            print('[DBG] Failed to get LLM response after retries')
            raise Exception("Failed to get LLM response after retries")

        content = resp.choices[0].message.content or ""
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    parts.append(item["text"])
                elif isinstance(item, str):
                    parts.append(item)
            output_text = "".join(parts).strip()
        else:
            output_text = str(content).strip()

        usage: Dict[str, Any] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "estimated": False,
            "model": model,
        }

        if hasattr(resp, "usage") and resp.usage is not None:
            usage["prompt_tokens"] = int(getattr(resp.usage, "prompt_tokens", 0) or 0)
            usage["completion_tokens"] = int(getattr(resp.usage, "completion_tokens", 0) or 0)
            usage["total_tokens"] = int(getattr(resp.usage, "total_tokens", 0) or 0)
            usage["estimated"] = False
            return output_text, usage

        try:
            try:
                enc = tiktoken.encoding_for_model(model)
            except Exception:
                enc = tiktoken.get_encoding("cl100k_base")

            prompt_tokens = sum(len(enc.encode(m["content"])) for m in messages)
            completion_tokens = len(enc.encode(output_text))
            total_tokens = prompt_tokens + completion_tokens

            usage["prompt_tokens"] = int(prompt_tokens)
            usage["completion_tokens"] = int(completion_tokens)
            usage["total_tokens"] = int(total_tokens)
            usage["estimated"] = True
        except Exception:
            usage["estimated"] = True

        return output_text, usage

    async def chat_json(self, *, system: str, user: str, temperature: Optional[float] = None) -> Tuple[
        Union[Dict[str, Any], list], Dict[str, Any]]:
        
        for attempt in range(3):
            text, usage = await self.chat_text(system=system, user=user, temperature=temperature)
    
            s = text.strip()
            
            # Extract JSON block if it's wrapped in markdown
            import re
            m = re.search(r'```(?:json)?\s*(.*?)\s*```', s, re.DOTALL)
            if m:
                s = m.group(1).strip()
            else:
                # Fallback: try to find the outermost {} or []
                start = s.find('{')
                end = s.rfind('}')
                start_arr = s.find('[')
                end_arr = s.rfind(']')
                
                # Use the one that comes first (or is valid)
                if start != -1 and end != -1 and (start_arr == -1 or start < start_arr):
                    s = s[start:end+1]
                elif start_arr != -1 and end_arr != -1:
                    s = s[start_arr:end_arr+1]

            try:
                import json
                obj = json.loads(s, strict=False)
                if not isinstance(obj, (dict, list)):
                    raise ValueError(f"JSON root must be dict or list, got {type(obj)}")
                return obj, usage
            except (json.JSONDecodeError, ValueError) as e:
                print(f"[LLM JSON ERR] Attempt {attempt + 1}: {e}\nTrying to decode:\n{s}\n")
                if attempt == 2:
                    raise ValueError(f"Failed to decode JSON after 3 attempts. Last error: {e}\nResponse:\n{text}")
                
                user += f"\n\nSystem Error on previous output: {e}. Please ensure you return ONLY valid JSON without preamble."
                import asyncio
                await asyncio.sleep(2)
