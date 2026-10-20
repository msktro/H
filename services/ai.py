import os
import requests
from flask import current_app

class AIError(Exception):
    pass

def generate_text(system, prompt):
    provider = current_app.config.get("AI_PROVIDER", "ollama").lower()
    if provider == "ollama":
        return _ollama(system, prompt)
    if provider == "gemini":
        return _gemini(system, prompt)
    raise AIError(f"AI_PROVIDER「{provider}」には対応していません。")

def _ollama(system, prompt):
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "llava:7b")
    try:
        r = requests.post(f"{base}/api/chat", json={
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "stream": False,
        }, timeout=(10, 300))
        r.raise_for_status()
        answer = r.json()["message"]["content"].strip()
        if not answer:
            raise AIError("AIから空の応答が返りました。")
        return answer
    except requests.ConnectionError as exc:
        raise AIError("Ollamaに接続できません。Ollamaアプリとモデルを確認してください。") from exc
    except requests.Timeout as exc:
        raise AIError("AIの応答に時間がかかっています。") from exc
    except (requests.RequestException, KeyError, ValueError) as exc:
        raise AIError(f"Ollamaの応答を読み取れません。モデル名「{model}」を確認してください。") from exc

def _gemini(system, prompt):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
    if not key:
        raise AIError("Geminiを使うにはGEMINI_API_KEYを設定してください。")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    try:
        r = requests.post(url, headers={"x-goog-api-key": key}, json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        }, timeout=(10, 180))
        r.raise_for_status()
        answer = "".join(x.get("text", "") for x in r.json()["candidates"][0]["content"]["parts"]).strip()
        if not answer:
            raise AIError("Geminiから空の応答が返りました。")
        return answer
    except requests.Timeout as exc:
        raise AIError("Geminiの応答に時間がかかっています。") from exc
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        raise AIError("Gemini APIを利用できません。APIキー、モデル名、通信状態を確認してください。") from exc
