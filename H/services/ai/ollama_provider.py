"""Ollama adapter. Other providers can implement the same generate function."""

import os

import requests

from . import AIServiceError


def generate_with_ollama(system_prompt, user_prompt, temperature=0.7):
    base_url = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "llava:7b")
    try:
        response = requests.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=600,
        )
        response.raise_for_status()
        result = response.json().get("message", {}).get("content", "").strip()
        if not result:
            raise AIServiceError("Ollamaから空の回答が返りました。もう一度お試しください。")
        return result
    except requests.ConnectionError as exc:
        raise AIServiceError("Ollamaに接続できません。Ollamaアプリが起動しているか確認してください。") from exc
    except requests.Timeout as exc:
        raise AIServiceError("Ollamaから10分以内に応答がありませんでした。モデルの状態を確認してください。") from exc
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            raise AIServiceError(f"モデル「{model}」が見つかりません。ollama listでモデル名を確認してください。") from exc
        raise AIServiceError("Ollamaがエラーを返しました。Ollamaアプリとモデルの状態を確認してください。") from exc
    except (requests.RequestException, ValueError) as exc:
        raise AIServiceError("Ollamaへの通信に失敗しました。起動状態を確認してください。") from exc
