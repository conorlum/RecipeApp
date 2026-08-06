from flask import Blueprint, render_template, request, redirect, url_for

from app.extensions import db
from app.auth_utils import login_required
from app.models import QuantityEquivalency
from app.services.normalize import normalize_name

bp = Blueprint("equivalencies", __name__, url_prefix="/equivalencies")


@bp.route("")
@login_required
def list_equivalencies():
    equivalencies = QuantityEquivalency.query.order_by(QuantityEquivalency.phrase).all()
    return render_template("equivalencies/list.html", equivalencies=equivalencies)


@bp.route("/new", methods=["POST"])
@login_required
def new_equivalency():
    phrase = normalize_name(request.form.get("phrase", ""))
    quantity = request.form.get("quantity", "").strip()
    unit = request.form.get("unit", "").strip()

    equivalencies = QuantityEquivalency.query.order_by(QuantityEquivalency.phrase).all()

    if not phrase or not quantity or not unit:
        return render_template(
            "equivalencies/list.html", equivalencies=equivalencies, error="Phrase, quantity, and unit are all required."
        )

    if QuantityEquivalency.query.filter_by(phrase=phrase).first():
        return render_template(
            "equivalencies/list.html",
            equivalencies=equivalencies,
            error=f'"{phrase}" already exists — edit that row instead.',
        )

    try:
        quantity_value = float(quantity)
    except ValueError:
        return render_template(
            "equivalencies/list.html", equivalencies=equivalencies, error="Quantity must be a number."
        )

    db.session.add(QuantityEquivalency(phrase=phrase, quantity=quantity_value, unit=unit))
    db.session.commit()
    return redirect(url_for("equivalencies.list_equivalencies"))


@bp.route("/<int:equivalency_id>/edit", methods=["POST"])
@login_required
def edit_equivalency(equivalency_id):
    equivalency = QuantityEquivalency.query.get_or_404(equivalency_id)
    phrase = normalize_name(request.form.get("phrase", ""))
    quantity = request.form.get("quantity", "").strip()
    unit = request.form.get("unit", "").strip()

    if not (phrase and quantity and unit):
        return redirect(url_for("equivalencies.list_equivalencies"))

    equivalencies = QuantityEquivalency.query.order_by(QuantityEquivalency.phrase).all()

    other = QuantityEquivalency.query.filter(
        QuantityEquivalency.phrase == phrase, QuantityEquivalency.id != equivalency.id
    ).first()
    if other:
        return render_template(
            "equivalencies/list.html",
            equivalencies=equivalencies,
            error=f'"{phrase}" already exists on another row.',
        )

    try:
        quantity_value = float(quantity)
    except ValueError:
        return render_template(
            "equivalencies/list.html", equivalencies=equivalencies, error="Quantity must be a number."
        )

    equivalency.phrase = phrase
    equivalency.quantity = quantity_value
    equivalency.unit = unit
    db.session.commit()

    return redirect(url_for("equivalencies.list_equivalencies"))


@bp.route("/<int:equivalency_id>/delete", methods=["POST"])
@login_required
def delete_equivalency(equivalency_id):
    equivalency = QuantityEquivalency.query.get_or_404(equivalency_id)
    db.session.delete(equivalency)
    db.session.commit()
    return redirect(url_for("equivalencies.list_equivalencies"))
