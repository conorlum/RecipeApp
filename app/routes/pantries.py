from flask import Blueprint, render_template, request, redirect, url_for, g

from app.extensions import db
from app.auth_utils import login_required
from app.models import Pantry, PantryItem
from app.services.normalize import normalize_name

bp = Blueprint("pantries", __name__, url_prefix="/pantries")


def _ensure_pantry(pantry_id):
    return Pantry.query.filter_by(id=pantry_id, owner_id=g.user.id).first_or_404()


def _ensure_home_pantry():
    """Core flow #9: auto-create a 'Home' pantry the first time a user
    touches this feature so they're never starting from zero."""
    if not g.user.pantries:
        home = Pantry(owner_id=g.user.id, name="Home")
        db.session.add(home)
        db.session.flush()
        g.user.active_pantry_id = home.id
        db.session.commit()


@bp.route("")
@login_required
def list_pantries():
    _ensure_home_pantry()
    pantries = Pantry.query.filter_by(owner_id=g.user.id).order_by(Pantry.created_at).all()
    return render_template("pantries/list.html", pantries=pantries, active_pantry_id=g.user.active_pantry_id)


@bp.route("/new", methods=["POST"])
@login_required
def new_pantry():
    name = request.form.get("name", "").strip()
    if name:
        pantry = Pantry(owner_id=g.user.id, name=name)
        db.session.add(pantry)
        db.session.flush()
        if g.user.active_pantry_id is None:
            g.user.active_pantry_id = pantry.id
        db.session.commit()
    return redirect(url_for("pantries.list_pantries"))


@bp.route("/<int:pantry_id>/rename", methods=["POST"])
@login_required
def rename_pantry(pantry_id):
    pantry = _ensure_pantry(pantry_id)
    name = request.form.get("name", "").strip()
    if name:
        pantry.name = name
        db.session.commit()
    return redirect(url_for("pantries.list_pantries"))


@bp.route("/<int:pantry_id>/delete", methods=["POST"])
@login_required
def delete_pantry(pantry_id):
    pantry = _ensure_pantry(pantry_id)
    if g.user.active_pantry_id == pantry.id:
        g.user.active_pantry_id = None
    db.session.delete(pantry)
    db.session.commit()
    return redirect(url_for("pantries.list_pantries"))


@bp.route("/<int:pantry_id>/items", methods=["POST"])
@login_required
def add_item(pantry_id):
    pantry = _ensure_pantry(pantry_id)
    name = normalize_name(request.form.get("name", ""))
    if name:
        db.session.add(PantryItem(pantry_id=pantry.id, name=name))
        db.session.commit()
    return redirect(url_for("pantries.list_pantries"))


@bp.route("/<int:pantry_id>/items/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_item(pantry_id, item_id):
    pantry = _ensure_pantry(pantry_id)
    item = PantryItem.query.filter_by(id=item_id, pantry_id=pantry.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("pantries.list_pantries"))


@bp.route("/switch", methods=["POST"])
@login_required
def switch_active():
    pantry_id = request.form.get("pantry_id", "").strip()
    if pantry_id.isdigit():
        pantry = _ensure_pantry(int(pantry_id))
        g.user.active_pantry_id = pantry.id
        db.session.commit()
    return redirect(url_for("pantries.list_pantries"))
