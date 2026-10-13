import os

from flask import Flask, render_template, request

from services.ai import AIServiceError, generate_text

app = Flask(__name__)

SYSTEM_PROMPT = """あなたは日本全国の旅行計画を手伝うアシスタントです。
ユーザーが指定した地域・日程・予算・人数・希望を優先し、日本語でわかりやすく答えてください。
営業時間、運賃、施設の営業状況など確認できない情報は断定せず、事前確認が必要だと伝えてください。"""


def get_trip_values(source):
    return {
        "destination": source.get("destination", "").strip(),
        "days": source.get("days", "1").strip(),
        "budget": source.get("budget", "").strip(),
        "people": source.get("people", "2").strip(),
        "theme": source.get("theme", "").strip(),
        "preferences": source.get("preferences", "").strip(),
    }


def render_page(values=None, plan="", error="", active_tab="create"):
    return render_template(
        "index.html",
        values=values or {"destination": "", "days": "1", "budget": "", "people": "2", "theme": "", "preferences": ""},
        plan=plan,
        error=error,
        active_tab=active_tab,
        provider=os.getenv("AI_PROVIDER", "ollama").lower(),
        model=os.getenv("OLLAMA_MODEL", "llava:7b"),
    )


@app.get("/")
def index():
    return render_page()


@app.post("/generate")
def generate():
    values = get_trip_values(request.form)
    if not values["destination"]:
        return render_page(values, error="行き先を入力してください。", active_tab="create"), 400

    prompt = f"""次の条件で、日本国内の旅行プランを作成してください。
行き先・地域: {values['destination']}
日数: {values['days']}日
予算（1人あたり）: {values['budget'] or '指定なし'}
人数: {values['people']}人
テーマ: {values['theme'] or '指定なし'}
好み・希望: {values['preferences'] or '指定なし'}

日ごとに、時間帯、訪問先、楽しみ方、移動の目安を整理してください。
最後に予算の目安と持ち物のヒントをまとめてください。"""

    try:
        plan = generate_text(SYSTEM_PROMPT, prompt)
        return render_page(values, plan=plan, active_tab="result")
    except AIServiceError as exc:
        return render_page(values, error=str(exc), active_tab="create"), 502


@app.post("/revise")
def revise():
    values = get_trip_values(request.form)
    current_plan = request.form.get("current_plan", "").strip()
    changes = request.form.get("changes", "").strip()
    if not current_plan or not changes:
        return render_page(values, plan=current_plan, error="変更したい内容を入力してください。", active_tab="result"), 400

    prompt = f"""次の旅行プランを、ユーザーの追加希望に合わせて変更してください。
行き先: {values['destination']}
日数: {values['days']}日 / 人数: {values['people']}人
予算: {values['budget'] or '指定なし'}
テーマ: {values['theme'] or '指定なし'}
追加の好み: {values['preferences'] or '指定なし'}

現在の旅行プラン:
{current_plan}

変更してほしいこと:
{changes}

希望に合わせたプラン全体を、最初から最後まで読みやすく書き直してください。"""

    try:
        plan = generate_text(SYSTEM_PROMPT, prompt)
        return render_page(values, plan=plan, active_tab="result")
    except AIServiceError as exc:
        return render_page(values, plan=current_plan, error=str(exc), active_tab="result"), 502


if __name__ == "__main__":
    app.run(debug=True)
