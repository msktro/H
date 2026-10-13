import os

#112

import requests
from flask import Flask, render_template, request

app = Flask(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")


@app.get("/")
def index():
    return render_template("index.html", model=OLLAMA_MODEL)


@app.post("/generate")
def generate():
    values = {
        "destination": request.form.get("destination", "関東").strip(),
        "days": request.form.get("days", "1").strip(),
        "budget": request.form.get("budget", "").strip(),
        "people": request.form.get("people", "2").strip(),
        "theme": request.form.get("theme", "").strip(),
        "preferences": request.form.get("preferences", "").strip(),
    }
    if not values["destination"]:
        values["destination"] = "関東"

    prompt = f"""日本語で、旅行者向けの現実的で読みやすい旅行プランを作ってください。
指定条件:
- 行き先: {values['destination']}
- 日数: {values['days']}日
- 予算: {values['budget'] or '指定なし'}
- 人数: {values['people']}人
- 旅行のテーマ: {values['theme'] or '指定なし'}
- 好み・希望: {values['preferences'] or '指定なし'}

日ごとに時間帯、行き先、そこで楽しめること、移動の目安を示してください。最後に概算予算と持ち物のヒントをまとめてください。
営業時間・運賃・施設の営業状況を確認できない場合は断定せず、事前確認が必要だと明記してください。"""

    try:
        response = requests.post(
            f"{OLLAMA_URL.rstrip('/')}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": "あなたは関東旅行の計画を手伝うアシスタントです。条件を優先し、確認できない事実を作らないでください。"},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            },
            timeout=180,
        )
        response.raise_for_status()
        result = response.json()["message"]["content"]
        return render_template("index.html", model=OLLAMA_MODEL, values=values, result=result)
    except requests.ConnectionError:
        error = "Ollamaに接続できません。Ollamaを起動し、モデルを取得してからもう一度お試しください。"
    except requests.Timeout:
        error = "AIの応答に時間がかかっています。少し待ってからもう一度お試しください。"
    except (requests.RequestException, KeyError, ValueError):
        error = "プランを生成できませんでした。Ollamaのモデル名と起動状態を確認してください。"
    return render_template("index.html", model=OLLAMA_MODEL, values=values, error=error), 502


if __name__ == "__main__":
    app.run(debug=True)
