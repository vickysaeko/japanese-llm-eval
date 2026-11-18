"""Model providers with a pluggable interface.

- MockProvider: deterministic fake outputs, no API key. For testing/demo only.
  Outputs are clearly labeled [MOCK].
- ClaudeProvider / OpenAIProvider / GeminiProvider: API keys are read
  only from environment variables. If a key is missing, get_provider()
  raises and the run command skips that model. Never hardcode keys.
"""
from __future__ import annotations

import hashlib
import os


class ProviderError(RuntimeError):
    pass


class BaseProvider:
    name = "base"

    def generate(self, prompt, prompt_id="", category=""):
        raise NotImplementedError


_MOCK_TEMPLATES = {
    "translation_en_ja": "[MOCK] 日本での新サービスの開始をお知らせできることを嬉しく思います。当社のチームは製品を現地のニーズに合わせて適応させるために懸命に取り組んでまいりました。皆さまからのご感想を心よりお待ちしております。",
    "summarization": "[MOCK] リモートワークの普及で働き方の見直しが進み、ハイブリッド型が増えた一方、コミュニケーションの質やチームの一体感の維持が課題となっている。",
    "dialogue": "[MOCK] お問い合わせありがとうございます。注文番号12345の配送状況を確認いたします。現在、配送センターで出荷準備中となっております。お届けまで今しばらくお待ちくださいませ。",
    "grammar_correction": "[MOCK] 私は昨日、友達と一緒に映画を見に行きました。映画はとても面白くて、時間が経つのを忘れてしまいました。",
    "cultural_nuance_keigo": "[MOCK] お世話になっております。来週火曜14時に予定しておりました打ち合わせにつきまして、誠に恐縮ではございますが、水曜10時に変更をお願いできますでしょうか。ご都合をお知らせいただけますと幸いです。",
    "business_summarization": "[MOCK] ・売上は前年比8%増の12億円、新規顧客・法人向けプランが好調\n・営業利益は前年比2%減の1億8千万円、広告費が想定を上回った\n・来期は広告費の見直しと既存顧客向けアップセルを強化する方針",
}


class MockProvider(BaseProvider):
    """Deterministic fake outputs. No API key needed. Testing/demo only."""

    name = "mock"

    def generate(self, prompt, prompt_id="", category=""):
        base = _MOCK_TEMPLATES.get(category, "[MOCK] これはモック出力です。プロンプトに対する日本語の回答例です。")
        seed = hashlib.sha256(f"{prompt_id}:{category}".encode()).hexdigest()
        suffix = " なお、内容は要点を押さえ、丁寧な表現を心がけています。" if int(seed[:2], 16) % 2 == 0 else ""
        return base + suffix


def _require_requests():
    try:
        import requests
    except ImportError as exc:
        raise ProviderError("requests が必要です。pip install -r requirements.txt を実行してください。") from exc
    return requests


def _post_json(url, headers, payload, timeout=60):
    requests = _require_requests()
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    except Exception as exc:
        raise ProviderError(f"API呼び出しに失敗しました: {exc}") from exc
    if resp.status_code >= 400:
        raise ProviderError(f"APIエラー {resp.status_code}: {resp.text[:500]}")
    try:
        return resp.json()
    except Exception as exc:
        raise ProviderError(f"API応答の解析に失敗しました: {exc}") from exc


class ClaudeProvider(BaseProvider):
    name = "claude"

    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise ProviderError("ANTHROPIC_API_KEY が設定されていません。")
        self.model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    def generate(self, prompt, prompt_id="", category=""):
        data = _post_json(
            "https://api.anthropic.com/v1/messages",
            {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            {
                "model": self.model,
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        parts = data.get("content", [])
        texts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("type") == "text"]
        return "".join(texts).strip()


class OpenAIProvider(BaseProvider):
    name = "openai"

    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key:
            raise ProviderError("OPENAI_API_KEY が設定されていません。")
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def generate(self, prompt, prompt_id="", category=""):
        data = _post_json(
            "https://api.openai.com/v1/chat/completions",
            {"Authorization": f"Bearer {self.api_key}", "content-type": "application/json"},
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
        )
        choices = data.get("choices", [])
        if not choices:
            return ""
        return (choices[0].get("message", {}) or {}).get("content", "").strip()


class GeminiProvider(BaseProvider):
    name = "gemini"

    def __init__(self):
        self.api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not self.api_key:
            raise ProviderError("GOOGLE_API_KEY が設定されていません。")
        self.model = os.environ.get("GOOGLE_MODEL", os.environ.get("GEMINI_MODEL", "gemini-1.5-flash"))

    def generate(self, prompt, prompt_id="", category=""):
        data = _post_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            {"x-goog-api-key": self.api_key, "content-type": "application/json"},
            {"contents": [{"parts": [{"text": prompt}]}]},
        )
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = (candidates[0].get("content", {}) or {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()


PROVIDER_CLASSES = {
    "mock": MockProvider,
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
}


def get_provider(name):
    """Build a provider by name. Raises ProviderError if the key is missing."""
    cls = PROVIDER_CLASSES.get(name.strip().lower())
    if cls is None:
        raise ProviderError(f"不明なモデル名です: {name}（使えるのは {', '.join(PROVIDER_CLASSES)}）")
    return cls()
