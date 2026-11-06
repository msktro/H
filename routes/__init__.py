"""Tabidea ルーティングパッケージ。各機能のBlueprintを一括登録します。"""

from flask import Blueprint

from .auth import auth_bp
from .business import business_bp
from .geoapify import geoapify_bp
from .groups import groups_bp
from .journeys import journeys_bp
from .main import main_bp
from .plans import plans_bp
from .reviews import reviews_bp
from .support import support_bp

ALL_BLUEPRINTS = [
    main_bp,
    auth_bp,
    plans_bp,
    groups_bp,
    journeys_bp,
    business_bp,
    reviews_bp,
    support_bp,
    geoapify_bp,
]


def register_blueprints(app):
    """すべての機能別BlueprintをFlaskアプリケーションへ登録します。"""
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)
