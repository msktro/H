"""Gemini-only AI provider interface."""

class AIServiceError(Exception):
    """An error that can be shown safely in the web interface."""


from .gemini_provider import generate_with_gemini


def generate_text(system_prompt, user_prompt, temperature=0.7):
    return generate_with_gemini(system_prompt, user_prompt, temperature=temperature)
