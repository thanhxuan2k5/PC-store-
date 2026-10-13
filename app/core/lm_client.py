
import json
import httpx
from typing import Optional, List, Dict, Any
from openai import OpenAI, APIConnectionError, APITimeoutError

from app.config import settings


class LMStudioClient:
    """Singleton client quản lý kết nối tới LM Studio."""

    _instance: Optional["LMStudioClient"] = None
    _client: Optional[OpenAI] = None
    _available: Optional[bool] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None and settings.LM_STUDIO_ENABLED:
            api_key = getattr(settings, "LM_STUDIO_API_KEY", "") or "lm-studio"
            self._client = OpenAI(
                base_url=settings.LM_STUDIO_URL,
                api_key=api_key,
                timeout=settings.LM_STUDIO_TIMEOUT,
            )

    def is_available(self) -> bool:
        """Ping LM Studio kiểm tra kết nối."""
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
        temperature: float = 0.8,
        max_tokens: int = 800,
        top_p: float = 0.95,
        json_mode: bool = False,
    ) -> Optional[str]:
        """Gọi chat completion đồng bộ thông thường."""
        if not self._client or not settings.LM_STUDIO_ENABLED:
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
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = self._client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            self._available = True
            return content

        except (APIConnectionError, APITimeoutError):
            print(f"[LMStudio] ⚠️ Không kết nối được tới {settings.LM_STUDIO_URL} — fallback về logic mặc định")
            self._available = False
            return None
        except Exception as e:
            print(f"[LMStudio] ⚠️ Lỗi: {e} — fallback về logic mặc định")
            return None

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.65,
        max_tokens: int = 900,
        top_p: float = 0.92,
    ):
        """Gọi chat completion dạng Streaming qua OpenAI-compatible API."""
        if not self._client or not settings.LM_STUDIO_ENABLED:
            return

        try:
            response = self._client.chat.completions.create(
                model=settings.LM_STUDIO_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=True,
            )
            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content
            self._available = True
        except Exception as e:
            print(f"[LMStudio Stream Error] {e}")
            self._available = False

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 150,
    ) -> Optional[Dict[str, Any]]:
        """Gọi chat và parse kết quả JSON tự động cho Sentiment Analysis."""
        raw = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        if not raw:
            return None

        try:
            return json.loads(raw.strip())
        except json.JSONDecodeError:
            import re
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
            return None

    def get_embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Gọi endpoint /v1/embeddings từ LM Studio nếu có load embedding model."""
        if not self._client or not settings.LM_STUDIO_ENABLED:
            return None
        try:
            resp = self._client.embeddings.create(
                model=getattr(settings, "LM_STUDIO_EMBED_MODEL", "text-embedding-nomic-embed-text-v1.5"),
                input=texts
            )
            return [d.embedding for d in resp.data]
        except Exception:
            return None


lm_client = LMStudioClient()
