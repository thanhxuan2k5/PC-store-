
import json
import httpx
from typing import Optional, List, Dict, Any
from openai import OpenAI, APIConnectionError, APITimeoutError

from app.config import settings


class LMStudioClient:
    _instance: Optional["LMStudioClient"] = None
    _client: Optional[OpenAI] = None
    _available: Optional[bool] = None  # Cache trạng thái availability

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Chỉ khởi tạo OpenAI client 1 lần
        if self._client is None and settings.LM_STUDIO_ENABLED:
            api_key = getattr(settings, "LM_STUDIO_API_KEY", "")
            if not api_key:
                api_key = "lm-studio" # Default token placeholder
            self._client = OpenAI(
                base_url=settings.LM_STUDIO_URL,
                api_key=api_key,
                timeout=settings.LM_STUDIO_TIMEOUT,
            )


    def is_available(self) -> bool:
        if not settings.LM_STUDIO_ENABLED:
            return False
        if self._available is not None:
            return self._available
        try:
            api_key = getattr(settings, "LM_STUDIO_API_KEY", "") or "lm-studio"
            resp = httpx.get(
                f"{settings.LM_STUDIO_URL}/models",
                timeout=3.0,
                headers={"Authorization": f"Bearer {api_key}"}
            )
            self._available = (resp.status_code == 200)
        except Exception:
            self._available = False
        return self._available

    def reset_availability(self):
        self._available = None

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 800,
        top_p: float = 0.95,
        json_mode: bool = False,
    ) -> Optional[str]:
        if not self._client or not settings.LM_STUDIO_ENABLED:
            return None

        if not self.is_available():
            return None

        try:
            kwargs: Dict[str, Any] = dict(
                model=settings.LM_STUDIO_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=False,
            )
            # JSON mode: một số model hỗ trợ structured output
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = self._client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            # Reset cache khi thành công
            self._available = True
            return content

        except (APIConnectionError, APITimeoutError):
            print(f"[LMStudio] [WARN] Khong the ket noi toi {settings.LM_STUDIO_URL} - fallback ve rule-based")
            self._available = False
            return None
        except Exception as e:
            print(f"[LMStudio] [WARN] Loi: {e} - fallback ve rule-based")
            return None

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 150,
    ) -> Optional[Dict[str, Any]]:
        raw = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Thử tìm JSON trong response nếu model thêm text ngoài
            import re
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
    def get_embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        if not self._client or not settings.LM_STUDIO_ENABLED:
            return None
        try:
            response = self._client.embeddings.create(
                model="text-embedding-bge-small-en-v1.5",
                input=texts
            )
            return [data.embedding for data in response.data]
        except Exception:
            return None


# Singleton instance — import ở mọi service
lm_client = LMStudioClient()

