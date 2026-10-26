"""Gemini REST API adapter."""

import os

import requests

from . import AIServiceError


def generate_with_gemini(system_prompt, user_prompt, temperature=0.7):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    if not api_key:
        raise AIServiceError("Geminiを使うにはGEMINI_API_KEYを設定してください。")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    try:
        response = requests.post(
            url,
            headers={"x-goog-api-key": api_key},
            json={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {"temperature": temperature},
            },
            timeout=(10, 180),
        )
        response.raise_for_status()
        payload = response.json()
        candidates = payload.get("candidates", [])
        if not candidates:
            reason = payload.get("promptFeedback", {}).get("blockReason")
            suffix = f"（理由: {reason}）" if reason else ""
            raise AIServiceError(f"Geminiから回答がありませんでした{suffix}")
        parts = candidates[0].get("content", {}).get("parts", [])
        answer = "".join(part.get("text", "") for part in parts).strip()
        if not answer:
            raise AIServiceError("Geminiから空の応答が返りました。")
        return answer
    except requests.Timeout as exc:
        raise AIServiceError("Geminiの応答に時間がかかっています。") from exc
    except requests.HTTPError as exc:
        response = exc.response
        status = response.status_code if response is not None else "不明"
        detail = ""
        if response is not None:
            try:
                detail = response.json().get("error", {}).get("message", "")
            except (ValueError, AttributeError):
                pass
        if status == 403:
            hint = "APIキーの権限や利用可能なAPI設定を確認してください。"
        elif status == 404:
            hint = f"モデル名「{model}」が利用可能か確認してください。"
        elif status == 429:
            hint = "Gemini APIの利用上限または課金設定を確認してください。"
        elif status == 400:
            hint = "APIキー、モデル名、送信内容を確認してください。"
        else:
            hint = "APIキーと通信状態を確認してください。"
        message = f"Gemini APIエラー（HTTP {status}）。{hint}"
        if detail:
            message += f" 詳細: {detail}"
        raise AIServiceError(message) from exc
    except requests.ConnectionError as exc:
        error_type = type(exc).__name__
        raise AIServiceError(
            f"Geminiサーバーに接続できません（{error_type}）。"
            "インターネット接続やプロキシ設定を確認してください。"
        ) from exc
    except requests.RequestException as exc:
        error_type = type(exc).__name__
        raise AIServiceError(f"Geminiへの通信中にエラーが発生しました（{error_type}）。") from exc
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        error_type = type(exc).__name__
        raise AIServiceError(f"Geminiの応答を読み取れませんでした（{error_type}）。") from exc
