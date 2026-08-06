from functools import wraps

from flask import session, redirect, url_for, g, request, jsonify

from app.models import User


def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = User.query.get(user_id) if user_id else None


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        return view(**kwargs)

    return wrapped_view


def token_required(view):
    """Bearer-token auth for POST /api/ingest (the Instagram Shortcut
    endpoint) — the one route with no browser session to read a cookie
    from. Every other route stays session-based via login_required."""

    @wraps(view)
    def wrapped_view(**kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header[len("Bearer "):].strip() if auth_header.startswith("Bearer ") else ""
        user = User.query.filter_by(api_token=token).first() if token else None
        if user is None:
            return jsonify({"error": "Invalid or missing API token."}), 401
        g.user = user
        return view(**kwargs)

    return wrapped_view
