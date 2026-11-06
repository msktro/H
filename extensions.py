"""複数のファイルから共有するFlask拡張機能を用意します。"""

from flask_sqlalchemy import SQLAlchemy
# アプリ本体の設定後に初期化するため、ここでは共有インスタンスだけ作ります。
db = SQLAlchemy()
