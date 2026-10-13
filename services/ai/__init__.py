"""AI provider selection and shared interface."""

import os

class AIServiceError(Exception):
    """An error that can be shown safely in the web interface."""


from .ollama_provider import generate_with_ollama


def generate_text(system_prompt, user_prompt, temperature=0.7):
    provider = os.getenv("AI_PROVIDER", "ollama").strip().lower()
    if provider == "ollama":
        return generate_with_ollama(system_prompt, user_prompt, temperature=temperature)
    if provider == "gemini":
        raise AIServiceError("Gemini接続はまだ設定されていません。AI_PROVIDERをollamaに戻してください。")
    raise AIServiceError(f"未対応のAI_PROVIDERです: {provider}")
