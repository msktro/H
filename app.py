import hmac
import os
import secrets

from flask import Flask, abort, render_template, request, session

from auth import auth_bp, init_db, login_required
from services.ai import AIServiceError, generate_text

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "local-development-key-change-before-deploy"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
app.register_blueprint(auth_bp)
init_db(app.instance_path)

SYSTEM_PROMPT = """あなたは日本全国の旅行計画を手伝うアシスタントです。
ユーザーが指定した地域・日程・予算・人数・希望を優先し、日本語でわかりやすく答えてください。
営業時間、運賃、施設の営業状況など確認できない情報は断定せず、事前確認が必要だと伝えてください。"""


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


@app.before_request
def protect_post_requests():
    if request.method == "POST":
        expected = session.get("_csrf_token", "")
        provided = request.form.get("_csrf_token", "")
        if not expected or not hmac.compare_digest(expected, provided):
            abort(400, description="フォームの有効期限が切れました。ページを更新して再度お試しください。")


@app.context_processor
def inject_template_context():
    return {"csrf_token": csrf_token, "logged_in_user": session.get("user_name")}


def get_trip_values(source):
    return {
        "destination": source.get("destination", "").strip(),
        "days": source.get("days", "1").strip(),
        "budget": source.get("budget", "").strip(),
        "people": source.get("people", "2").strip(),
        "theme": source.get("theme", "").strip(),
        "preferences": source.get("preferences", "").strip(),
    }


def render_page(values=None, plan="", error="", active_tab="create", revision_note=""):
    return render_template(
        "index.html",
        values=values or {"destination": "", "days": "1", "budget": "", "people": "2", "theme": "", "preferences": ""},
        plan=plan,
        error=error,
        revision_note=revision_note,
        active_tab=active_tab,
        provider=os.getenv("AI_PROVIDER", "ollama").lower(),
        model=os.getenv("OLLAMA_MODEL", "llava:7b"),
    )


@app.get("/")
@login_required
def index():
    return render_page()


@app.post("/generate")
@login_required
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
@login_required
def revise():
    values = get_trip_values(request.form)
    current_plan = request.form.get("current_plan", "").strip()
    changes = request.form.get("changes", "").strip()
    if not current_plan or not changes:
        return render_page(values, plan=current_plan, error="変更したい内容を入力してください。", active_tab="result"), 400

    prompt = f"""旅行プランの変更依頼です。元のプランをそのまま繰り返さず、変更希望を最優先して具体的に作り直してください。
行き先: {values['destination']}
日数: {values['days']}日 / 人数: {values['people']}人
予算: {values['budget'] or '指定なし'}
テーマ: {values['theme'] or '指定なし'}
追加の好み: {values['preferences'] or '指定なし'}

【変更前のプラン】
{current_plan}

【必ず反映する変更希望】
{changes}

【変更ルール】
1. 変更希望に書かれた内容をすべて実際の行程に反映する。
2. 希望と矛盾する変更前の予定は削除または置き換える。
3. 変更希望に触れていない条件や予定は、矛盾しない範囲で維持する。
4. 返答は「変更した点」と「変更後の旅行プラン」の2つの見出しに分ける。
5. 「変更した点」では、何をどのように変えたかを具体的に列挙する。
6. 「変更後の旅行プラン」には、変更を反映した全日程を省略せず書く。
変更希望を反映できない場合は、できない理由を明記し、代わりの案を出す。"""

    try:
        plan = generate_text(SYSTEM_PROMPT, prompt, temperature=0.2)
        return render_page(values, plan=plan, active_tab="result", revision_note=changes)
    except AIServiceError as exc:
        return render_page(values, plan=current_plan, error=str(exc), active_tab="result"), 502


if __name__ == "__main__":
    app.run(debug=True)
