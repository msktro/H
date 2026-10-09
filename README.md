# TabiNote | Flask + Ollama

旅行条件を入力し、ローカルのOllamaで旅行プランを生成する検証用Web画面です。ログイン、データベース保存、地図APIは含みません。

## 起動方法

1. Ollamaをインストールして起動します。
2. ターミナルでモデルを取得します（例）。

   ```powershell
   ollama pull llama3.1
   ```

3. このフォルダで仮想環境を作成し、依存関係を入れます。

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

4. Flaskを起動します。

   ```powershell
   python app.py
   ```

5. ブラウザで http://127.0.0.1:5000 を開きます。

既定では `http://localhost:11434` のOllamaと `llama3.1` を使用します。変更する場合は、環境変数 `OLLAMA_URL` と `OLLAMA_MODEL` を設定してください。

## 注意

Ollamaが返すプランは提案文です。実際の営業時間、交通、料金、予約可否は確認していません。旅程の確定前に各施設・交通機関の公式情報を確認してください。
