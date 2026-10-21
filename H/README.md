# Tabidea

企画書・画面設計書・テーブル設計書を参考に新規作成したFlask旅行プランアプリです。

## 初期版の機能
旅行者／事業者の登録、ログイン、メニュー、旅行者プロフィール、全国向けAIプラン生成・保存・変更、旅行中AIサポート、グループチャット（3秒ごとの自動更新）、グループアルバム（JPG・PNG・GIF・WebP、1枚5MBまで）、事業者情報の登録と公開状態管理、公開施設・店舗のお気に入り保存を含みます。

旅行中AIサポートは、選択した自分の旅行プランまたはグループ共有プランを会話の参考情報として使います。プラン詳細の「AIに相談」またはメニューから開けます。Ollama／Geminiは `.env` の `AI_PROVIDER` で設定した既存の接続先を使います。会話は画面を閉じると消えます。AIは現在地やリアルタイムの運行・営業時間を取得しないため、現地情報は公式情報で確認してください。

## Windowsで起動
PowerShellで実行します。

    cd C:\Users\2538002\Tabidea1
    py -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    Copy-Item .env.example .env

.envのOLLAMA_MODELをollama listに表示されるモデル名に合わせてください。モデルがない場合はOllamaを起動して取得します。

## 地図・場所検索・ルート
GeoapifyのプロジェクトでAPIキーを作成し、`.env` の `GEOAPIFY_API_KEY=` の右側に設定してください。場所の入力候補にはAddress Autocomplete API、周辺スポットにはPlaces API、経路にはRouting APIを使用します。キーはFlaskサーバーからのみ利用します。プラン詳細画面の地図はMapLibre GL JSで表示します。

場所を2か所以上検索して追加すると、徒歩・車・自転車・公共交通のルートを計算できます。追加済みの地点から周辺スポットも検索できます。地図・ルートの地点は現在の画面内だけで保持し、プランにはまだ保存しません。

    ollama list
    ollama pull llava:7b

その後、アプリを起動し、ブラウザで http://127.0.0.1:5000 を開きます。

    python app.py

初回起動時にinstance/tabidea.dbを作成します。ログイン画面から新規登録してください。

## Geminiに切り替える
Google AI StudioでAPIキーを取得し、.envのAI_PROVIDERをgeminiに変更してGEMINI_API_KEYを設定します。AI接続はservices/ai.pyにまとめています。GeminiはGoogle公式GenerateContent REST APIを使用します。

## 注意
.envはGitHubにアップロードしないでください。共有前にSECRET_KEYを変更してください。AI案は最新情報を保証しません。地図のタイル表示にはインターネット接続が必要です。SQLiteはこのPC内の単一ファイルに保存され、複数PC共有の設定はまだありません。
