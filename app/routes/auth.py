from flask import Blueprint, render_template, request, redirect, url_for, session, g

from app.extensions import db
from app.models import User

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if not username:
            return render_template("auth/login.html", error="Username is required.")

        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username)
            db.session.add(user)
            db.session.commit()

        session.clear()
        session["user_id"] = user.id
        return redirect(url_for("recipes.list_recipes"))

    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
