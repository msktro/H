# Tabidea

企画書・画面設計書・テーブル設計書を参考に新規作成したFlask旅行プランアプリです。

## 初期版の機能
旅行者／事業者の登録、ログイン、メニュー、旅行者プロフィール、全国向けAIプラン生成・保存・変更、旅行中AIサポート、グループチャット（3秒ごとの自動更新）、グループアルバム（JPG・PNG・GIF・WebP、1枚5MBまで）、事業者情報の登録と公開状態管理、公開施設・店舗のお気に入り保存を含みます。

旅行中AIサポートは、選択した自分の旅行プランまたはグループ共有プランを会話の参考情報として使います。プラン詳細の「AIに相談」またはメニューから開けます。AI機能はGeminiを使います。会話は画面を閉じると消えます。AIは現在地やリアルタイムの運行・営業時間を取得しないため、現地情報は公式情報で確認してください。

## Windowsで起動
PowerShellで実行します。

    cd C:\Users\2538002\H
    py -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    Copy-Item .env.example .env

.envの `GEMINI_API_KEY` にGoogle AI Studioで取得したAPIキーを設定してください。`GEMINI_MODEL` は利用可能なGeminiモデル名にします。

## 地図・場所検索・ルート
GeoapifyのプロジェクトでAPIキーを作成し、`.env` の `GEOAPIFY_API_KEY=` の右側に設定してください。場所の入力候補にはAddress Autocomplete API、周辺スポットにはPlaces API、経路にはRouting APIを使用します。キーはFlaskサーバーからのみ利用します。プラン詳細画面の地図はMapLibre GL JSで表示します。

場所を2か所以上検索して追加すると、徒歩・車・自転車・公共交通のルートを計算できます。追加済みの地点から周辺スポットも検索できます。地図・ルートの地点は現在の画面内だけで保持し、プランにはまだ保存しません。

その後、アプリを起動し、ブラウザで http://127.0.0.1:5000 を開きます。

    python app.py

初回起動時にinstance/tabidea.dbを作成します。ログイン画面から新規登録してください。

## パスワードを忘れた場合
ログイン画面の「パスワードを忘れた場合」から再設定リンクを発行できます。開発中はリンクがFlask起動中のターミナルに表示されます。リンクの有効期限は30分で、パスワード変更後は再利用できません。

メールで送る場合は`.env`に`MAIL_SERVER`、`MAIL_PORT`、`MAIL_USERNAME`、`MAIL_PASSWORD`、`MAIL_DEFAULT_SENDER`を設定し、`PASSWORD_RESET_DEV_MODE=0`にしてください。メール設定とSMTP認証情報はGitHubにアップロードしないでください。

## AI接続
Google AI StudioでAPIキーを取得し、`.env` の `GEMINI_API_KEY` に設定します。`GEMINI_MODEL` には利用可能なGeminiモデル名を指定してください。AI接続は `services/ai/` にまとめています。

## 注意
.envはGitHubにアップロードしないでください。共有前にSECRET_KEYを変更してください。AI案は最新情報を保証しません。地図のタイル表示にはインターネット接続が必要です。SQLiteはこのPC内の単一ファイルに保存され、複数PC共有の設定はまだありません。


## 初期版の機能
旅行者／事業者の登録、ログイン、メニュー、旅行者プロフィール、全国向けAIプラン生成・保存・変更、旅行中AIサポート、グループチャット（3秒ごとの自動更新）、グループアルバム（JPG・PNG・GIF・WebP、1枚5MBまで）、事業者情報の登録と公開状態管理、公開施設・店舗のお気に入り保存を含みます。

旅行中AIサポートは、選択した自分の旅行プランまたはグループ共有プランを会話の参考情報として使います。プラン詳細の「AIに相談」またはメニューから開けます。AI機能はGeminiを使います。会話は画面を閉じると消えます。AIは現在地やリアルタイムの運行・営業時間を取得しないため、現地情報は公式情報で確認してください。

## Windowsで起動
PowerShellで実行します。

    cd C:\Users\2538002\H
    py -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    Copy-Item .env.example .env

.envの `GEMINI_API_KEY` にGoogle AI Studioで取得したAPIキーを設定してください。`GEMINI_MODEL` は利用可能なGeminiモデル名にします。

## 地図・場所検索・ルート
GeoapifyのプロジェクトでAPIキーを作成し、`.env` の `GEOAPIFY_API_KEY=` の右側に設定してください。場所の入力候補にはAddress Autocomplete API、周辺スポットにはPlaces API、経路にはRouting APIを使用します。キーはFlaskサーバーからのみ利用します。プラン詳細画面の地図はMapLibre GL JSで表示します。

場所を2か所以上検索して追加すると、徒歩・車・自転車・公共交通のルートを計算できます。追加済みの地点から周辺スポットも検索できます。地図・ルートの地点は現在の画面内だけで保持し、プランにはまだ保存しません。

その後、アプリを起動し、ブラウザで http://127.0.0.1:5000 を開きます。

    python app.py

初回起動時にinstance/tabidea.dbを作成します。ログイン画面から新規登録してください。

## パスワードを忘れた場合
ログイン画面の「パスワードを忘れた場合」から再設定リンクを発行できます。開発中はリンクがFlask起動中のターミナルに表示されます。リンクの有効期限は30分で、パスワード変更後は再利用できません。

メールで送る場合は`.env`に`MAIL_SERVER`、`MAIL_PORT`、`MAIL_USERNAME`、`MAIL_PASSWORD`、`MAIL_DEFAULT_SENDER`を設定し、`PASSWORD_RESET_DEV_MODE=0`にしてください。メール設定とSMTP認証情報はGitHubにアップロードしないでください。

## AI接続
Google AI StudioでAPIキーを取得し、`.env` の `GEMINI_API_KEY` に設定します。`GEMINI_MODEL` には利用可能なGeminiモデル名を指定してください。AI接続は `services/ai/` にまとめています。

## 注意
.envはGitHubにアップロードしないでください。共有前にSECRET_KEYを変更してください。AI案は最新情報を保証しません。地図のタイル表示にはインターネット接続が必要です。SQLiteはこのPC内の単一ファイルに保存され、複数PC共有の設定はまだありません。


## 事業者の電話番号認証
事業者は代表者名、電話番号、アクセス、営業時間を登録できます。デモではSMSを送らず、認証ボタンを押した後に画面上へ表示される6桁コードを使います。認証後に掲載を公開できます。実際の本人確認機能ではありません。
