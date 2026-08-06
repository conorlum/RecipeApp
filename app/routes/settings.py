import secrets

from flask import Blueprint, render_template, redirect, url_for, g

from app.extensions import db
from app.auth_utils import login_required

bp = Blueprint("settings", __name__, url_prefix="/settings")


def _generate_token():
    return secrets.token_urlsafe(32)


@bp.route("/token")
@login_required
def token():
    if not g.user.api_token:
        g.user.api_token = _generate_token()
        db.session.commit()
    return render_template("settings/token.html", token=g.user.api_token)


@bp.route("/token/regenerate", methods=["POST"])
@login_required
def regenerate_token():
    g.user.api_token = _generate_token()
    db.session.commit()
    return redirect(url_for("settings.token"))
