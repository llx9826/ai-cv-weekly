"""LunaClaw Brief — LLM 客户端"""

import os
import requests


class LLMClient:
    """通用 LLM 客户端（OpenAI 兼容接口）"""

    def __init__(self, llm_config: dict):
        self.api_key = llm_config.get("api_key") or os.getenv("BAILIAN_API_KEY", "")
        self.base_url = (
            llm_config.get("base_url")
            or os.getenv("BAILIAN_BASE_URL", "https://coding.dashscope.aliyuncs.com/v1")
        )
        self.model = llm_config.get("model") or os.getenv("BAILIAN_MODEL", "kimi-k2.5")
        self.timeout = llm_config.get("timeout", 180)

        if not self.api_key:
            raise ValueError(
                "LLM API Key 未设置。请设置 BAILIAN_API_KEY 环境变量或在 config.local.yaml 中指定。"
            )

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 8000,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            print(f"[LLM] API 错误：{resp.status_code} - {resp.text[:200]}")
            return ""
        except Exception as e:
            print(f"[LLM] 请求失败：{type(e).__name__}: {e}")
            return ""
