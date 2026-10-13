# TabiNote — 全国対応の旅行プランナー

FlaskとOllamaを使った旅行計画の試作アプリです。全国の行き先を自由入力してAIプランを作成し、追加の希望を伝えてプラン全体を変更できます。ログイン、保存、地図・予約連携はまだありません。

## 起動方法

1. Ollamaアプリを起動し、使用するモデルを確認します。

   ```powershell
   ollama list
   ```

2. このプロジェクトの仮想環境を有効にします。

   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

3. 必要なライブラリを入れます（初回、または依存関係を変更したとき）。

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Flaskを起動します。

   ```powershell
   python app.py
   ```

5. ブラウザで http://127.0.0.1:5000 を開きます。

既定ではOllamaの `http://localhost:11434` と `llava:7b` を使います。別のモデルを使う場合は、起動前にPowerShellで ` $env:OLLAMA_MODEL="モデル名" ` を設定します。

## 構成

- `app.py`: ページ表示、プラン生成、変更のルート
- `services/ai/`: AI接続の共通窓口とOllama用アダプター
- `templates/index.html`: メニュー、入力フォーム、結果・変更画面
- `static/style.css`: 画面デザイン

AI接続を `services/ai/` に分けています。将来Geminiを使う場合は、Gemini用アダプターを追加して共通窓口から選択する構成です。

## 注意

AIの回答は旅行案です。営業時間、運賃、施設の営業状況、予約可否を取得・確認していません。実際の旅行前に公式情報を確認してください。プランは画面上の変更に利用できますが、データベースには保存されません。
