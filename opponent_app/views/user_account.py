import calendar
from datetime import datetime

import humanize
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from flask_babel import gettext
from flask_login import current_user, login_required, logout_user
from loguru import logger

from opponent_app.decorators import check_confirmed
from opponent_app.helpers import Message, mail, mail_settings
from opponent_app.models import (
    Member,
    OfferOpponent,
    QueueOpponent,
    UserAccount,
    UserMember,
    UserOpponent,
    db,
)
from opponent_app.views.common import render_content_tournaments

user_account_app = Blueprint("user_account_app", __name__)


@user_account_app.url_defaults
def add_language_code(endpoint, values) -> None:  # noqa
    """Add language code to url.

    :param endpoint: endpoint name
    :param values: url values
    """
    values.setdefault("lang_code", g.lang_code)


@user_account_app.url_value_preprocessor
def pull_lang_code(endpoint, values) -> None:  # noqa
    """Pull language code from url.

    :param endpoint: endpoint name
    :param values: url values
    """
    g.lang_code = values.pop("lang_code")


def format_opponent_datetime(opponent_date) -> tuple:
    """Format opponent date and time."""
    convert_dt = datetime.strptime(opponent_date, "%Y-%m-%dT%H:%M")
    abbr_month = calendar.month_abbr[int(convert_dt.date().month)]
    day_ = humanize.naturaldate(convert_dt.day)
    time_ = humanize.naturaltime(convert_dt.time())
    return abbr_month, day_, time_


def get_user_opponent_history(user_id):
    """Get user's opponent history."""
    user_history = (
        UserAccount.query.filter_by(id=user_id)
        .join(UserOpponent)
        .all()
    )
    lst_history = []
    for x in user_history:
        for i in x.users_opponent:
            abr_month, day_, time_ = format_opponent_datetime(i.opponent_date)
            lst_history.append([
                abr_month,
                day_,
                time_,
                i.opponent_city,
                i.opponent_district,
                i.opponent_category,
                i.opponent_phone,
                i.id,
                x.name,
                x.email,
                x.count,
            ])
    return lst_history


def get_queue_size(user_opponent_id):
    """Get queue size."""
    queue_opponent = (
        UserOpponent.query.join(OfferOpponent)
        .filter_by(user_opponent_id=user_opponent_id)
        .join(QueueOpponent)
        .all()
    )
    size = len(queue_opponent)
    return size


def get_offer_data():
    """Get offer data."""
    offer_data = []
    offer_id = []
    offer_opponent = OfferOpponent.query.join(UserOpponent).all()
    if offer_opponent is not None:
        for i in offer_opponent:
            abr_month, day_, time_ = format_opponent_datetime(i.offer_date)
            offer_id.append(i.offer_accept)
            offer_data.append([
                abr_month,
                day_,
                time_,
                i.offer_phone,
                i.offer_name,
                i.offer_email,
                i.offer_city,
                i.offer_district,
                i.offer_category,
                i.offer_phone,
                i.user_opponent_id,
                i.id,
                i.offer_accept,
                i.offer_message,
            ])
    return offer_data, offer_id, offer_opponent


@user_account_app.route("/", methods=["GET", "POST"])
@check_confirmed
def user_account():
    """User account page."""
    if request.method == "GET":
        user_history = get_user_opponent_history(current_user.id)
        for item in user_history:
            size = get_queue_size(int(item[7]))
            item.append(size)
        offer_data, offer_id, offer_opponent = get_offer_data()
        return render_template(
            "user.html",
            cur=current_user,
            opponents=user_history,
            dates=user_history,
            offer_data=offer_data,
            offer_id=offer_id,
            offer_opponent=offer_opponent,
        )

    if request.method == "POST":
        date_time = request.form.get("partydate")  # noqa
        category = request.form.get("category")
        district = request.form.get("district")
        phone = request.form.get("phone")

        opponent = UserOpponent(
            opponent_category=category,
            opponent_city="Lviv",
            opponent_district=district,
            opponent_phone=phone,
            opponent_date=date_time,
            user_account_id=current_user.id,
        )
        db.session.add(opponent)
        db.session.commit()

        size = UserOpponent.query.join(UserAccount).filter_by(email=current_user.email).all()
        user_rating = UserAccount.query.filter_by(email=current_user.email).one_or_none()
        user_rating.count = len(size)
        db.session.commit()

        flash(gettext("Successfully. Your post has been added."))
        return redirect(url_for("user_account_app.user_account"))

    return render_template("user.html", cur=current_user)


@user_account_app.route("/update/<post_id>", methods=["GET", "POST", "DELETE"])
def update_post_request(post_id: int):
    """Update post request."""
    if request.method == "POST":
        card_opponent = (
            UserOpponent.query.filter_by(id=post_id)
            .join(UserAccount)
            .one_or_none()
        )
        if card_opponent is None:
            abort(404)
        else:
            card_opponent.opponent_phone = request.form.get("phone")
            card_opponent.opponent_category = request.form.get("category")
            card_opponent.opponent_district = request.form.get("district")
            card_opponent.opponent_date = request.form.get("partydate")
            db.session.commit()
            return redirect(url_for("user_account_app.user_account"))
    if request.method == "GET":
        card_opponent = (
            UserOpponent.query.filter_by(id=post_id)
            .join(UserAccount)
            .one_or_none()
        )
        if card_opponent is None:
            abort(404)
        else:
            return render_template(
                "user_update.html",
                cur=current_user,
                post_id=post_id,
                phone=card_opponent.opponent_phone,
                category=card_opponent.opponent_category,
                district=card_opponent.opponent_district,
                date=card_opponent.opponent_date,
            )
        # send_list_to_mail
    return render_template("user_update.html", cur=current_user, post_id=post_id)


@user_account_app.route("/delete/<post_id>", methods=["GET", "POST", "DELETE"])
def delete_post_request(post_id: int):
    """Delete post request."""
    if request.method == "GET":
        card_opponent = (
            UserOpponent.query.filter_by(id=post_id)
            .join(UserAccount)
            .one_or_none()
        )
        card_offer = OfferOpponent.query.filter_by(
            user_opponent_id=post_id
        ).one_or_none()

        queue_opponent = (
            UserOpponent.query.join(OfferOpponent)
            .filter_by(user_opponent_id=post_id)
            .join(QueueOpponent)
            .one_or_none()
        )
        if card_opponent is None and card_offer is None:
            abort(404)
        else:
            body = f"Sorry, {card_opponent.user_account.name} deleted this post\nGame time: {card_opponent.opponent_date},\nOpponent info:\n{card_opponent.user_account.name}\n{card_opponent.user_account.email}\n{card_opponent.opponent_phone}\n{card_opponent.opponent_district}\n{card_opponent.opponent_category}"
            if queue_opponent is not None:
                flash(gettext("You need cancel all offers for this post."))

            elif card_offer is not None:
                send_info_by_user(
                    subject="Opponent's post deleted.",
                    recipient=card_offer.offer_email,
                    body=body,
                )

                db.session.delete(card_offer)
                db.session.delete(card_opponent)
                db.session.commit()
                flash(gettext("Successfully. Your post has been deleted."))
            card = (
                UserOpponent.query.filter_by(id=post_id)
                .join(UserAccount)
                .one_or_none()
            )
            if card is not None:
                db.session.delete(card)
                db.session.commit()
                flash(gettext("Successfully. Your post has been deleted."))
        return redirect(url_for("user_account_app.user_account"))
    return render_template("user.html", cur=current_user)


@user_account_app.route("/cancel/<post_id>", methods=["GET", "POST", "DELETE"])
def cancel_post_offer(post_id: int):
    """Cancel post offer."""
    if request.method == "GET":
        offer_opponent = OfferOpponent.query.filter_by(id=post_id).one_or_none()
        user_opponent_id = offer_opponent.user_opponent_id
        queue_opponent = (
            QueueOpponent.query.join(OfferOpponent)
            .filter_by(id=post_id)
            .one_or_none()
        )

        if offer_opponent is None:
            abort(404)
        else:
            body = f"Sorry, {offer_opponent.user_opponent.user_account.name} canceled your offer\nGame time: {offer_opponent.user_opponent.opponent_date},\nOpponent info:\n{offer_opponent.user_opponent.user_account.name}\n{offer_opponent.user_opponent.user_account.email}\n{offer_opponent.user_opponent.opponent_phone}\n{offer_opponent.user_opponent.opponent_district}\n{offer_opponent.user_opponent.opponent_category}"
            send_info_by_user(
                subject="Your offer canceled.",
                recipient=offer_opponent.offer_email,
                body=body,
            )

            flash(gettext("Successfully. The offer has been deleted."))

            if queue_opponent is not None:
                phone = queue_opponent.queue_phone
                name = queue_opponent.queue_name
                email = queue_opponent.queue_email
                category = queue_opponent.queue_category
                city = queue_opponent.queue_city
                district = queue_opponent.queue_district
                date = queue_opponent.queue_date
                message = queue_opponent.queue_message
                db.session.delete(queue_opponent)
                db.session.delete(offer_opponent)
                db.session.commit()
                offer_opponent = OfferOpponent(
                    offer_phone=phone,
                    offer_name=name,
                    offer_email=email,
                    offer_category=category,
                    offer_city=city,
                    offer_district=district,
                    offer_date=date,
                    user_opponent_id=int(user_opponent_id),
                    offer_message=message,
                )
                db.session.add(offer_opponent)
                db.session.commit()
            else:
                db.session.delete(offer_opponent)
                db.session.commit()
        return redirect(url_for("user_account_app.user_account"))
    return render_template("user.html", cur=current_user)


@user_account_app.route("/accept/<post_id>", methods=["GET", "POST", "DELETE"])
def accept_post_offer(post_id: int):
    """Accept post offer."""
    if request.method == "GET":
        offer_opponent = OfferOpponent.query.filter_by(id=post_id).one_or_none()
        if offer_opponent is None:
            abort(404)
        else:
            if not offer_opponent.offer_accept:
                body = f"Wow! {offer_opponent.user_opponent.user_account.name} accepted your offer\nGame time: {offer_opponent.user_opponent.opponent_date},\nOpponent info:\n{offer_opponent.user_opponent.user_account.name}\n{offer_opponent.user_opponent.user_account.email}\n{offer_opponent.user_opponent.opponent_phone}\n{offer_opponent.user_opponent.opponent_district}\n{offer_opponent.user_opponent.opponent_category}"
                send_info_by_user(
                    subject="Your offer accepted.",
                    recipient=offer_opponent.offer_email,
                    body=body,
                )
                offer_opponent.offer_accept = True
                db.session.commit()
                flash(gettext("Successfully. The offer has been accepted."))
                return redirect(url_for("user_account_app.user_account"))
    return render_template("user.html", cur=current_user)


def send_info_by_user(subject, recipient, body):
    """Send info by user."""
    msg = Message(
        subject=subject,
        sender=mail_settings.get("MAIL_USERNAME"),
        recipients=[recipient],
        body=body,
    )
    return mail.send(msg)


@user_account_app.route("/login", methods=["GET", "POST"])
@login_required
def logout():
    """Logout."""
    if request.method == "GET":
        logout_user()
        return redirect(url_for("login_app.login"))


@user_account_app.route("/tournaments", methods=["GET", "POST"])
@check_confirmed
def user_account_tournaments():
    """User account tournaments."""
    if request.method == "GET":
        tournaments_history = (
            UserMember.query.filter_by(user_id=current_user.id).join(Member).all()
        )
        query = db.session.query(Member.user_member_id).all()
        return render_content_tournaments(
            tournaments_history, "user_tournaments.html", query
        )
    if request.method == "POST":
        title = request.form.get("title")
        date_time = request.form.get("partydate")
        category = request.form.get("category")
        district = request.form.get("district")
        phone = request.form.get("phone")
        quantity = request.form.get("quantity")
        if title and date_time and category and district and phone and quantity:
            user_member = UserMember(
                member_title=title,
                member_category=category,
                member_district=district,
                member_date=date_time,
                member_phone=phone,
                member_quantity=quantity,
                user_id=current_user.id,
            )
            db.session.add(user_member)
            db.session.commit()
            id_tour = UserMember.query.order_by(UserMember.id.desc()).first()  # noqa
            if id_tour:
                member = Member(
                    user_member_id=id_tour.id,
                    tour_member_name=current_user.name,
                    tour_member_phone=phone,
                    tour_member_email=current_user.email,
                    tour_member_accept=True,
                )
                db.session.add(member)
                db.session.commit()
                flash(gettext("Successfully. The tournament has been created."))
                return render_template("user_tournaments.html", cur=current_user)
            else:
                abort(404)
        else:
            abort(404)


@user_account_app.route("/tournaments/confirm_members", methods=["GET", "POST"])
@check_confirmed
def confirm_members():
    """Confirm members."""
    if request.method == "GET":
        members = (
            Member.query.join(UserMember).filter_by(user_id=current_user.id).all()
        )
        return render_template(
            "user_tournaments_confirm_members.html", members=members
        )
    return redirect(url_for("user_account_app.user_account_tournaments"))


@user_account_app.route(
    "/tournaments/confirm_members/confirm/<confirm_id>/<confirm>",
    methods=["GET", "POST"],
)
@check_confirmed
def actions_tournament(confirm_id: id, confirm: str):
    """Actions tournament."""
    if request.method == "GET":
        member = Member.query.filter_by(id=confirm_id).one_or_none()
        if not member:
            abort(404)
        else:
            if member.tour_member_accept is False and confirm == "accept":
                body = (
                    "Wow! Your request to participate in the tournament has been confirmed."
                    "\n https://alpaca00.website/finder/tournaments/"
                )
                send_info_by_user(
                    subject="Your offer accepted.",
                    recipient=member.tour_member_email,
                    body=body,
                )
                member.tour_member_accept = True
                db.session.commit()
                flash(gettext("Successfully. The member has been accepted."))
                return redirect(url_for("user_account_app.confirm_members"))
            elif member.tour_member_accept is False and confirm == "delete":
                body = (
                    "Sorry! Your request to participate in the tournament has been denied."
                    "\n https://alpaca00.website/finder/tournaments/"
                )
                send_info_by_user(
                    subject="Your offer denied.",
                    recipient=member.tour_member_email,
                    body=body,
                )
                db.session.delete(member)
                db.session.commit()
                flash(gettext("Successfully. The member has been deleted."))
                return redirect(url_for("user_account_app.confirm_members"))
            else:
                abort(404)
    return redirect(url_for("user_account_app.confirm_members"))


@user_account_app.errorhandler(404)
def handle_not_found_error(exception):
    """Handle not found error."""
    logger.info(exception)
    return render_template("404.html"), 404
