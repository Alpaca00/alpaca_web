import re

from flask_security import RoleMixin, SQLAlchemyUserDatastore, UserMixin
from flask_validator import ValidateEmail, ValidateInteger, ValidateString, Validator
from loguru import logger
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text

from opponent_app.models import db


class ValidatePhone(Validator):
    """Validate phone number.

    Examples:
        >> ValidatePhone.check_value("+380501234567")
        True
    """
    REGEX = r"^(?:\+38)?(?:\([0-9]{3}\D)[ .-]?[0-9]{3}[ .-]?[0-9]{2}[ .-]?[0-9]{2}|[0-9]{3}[ .-]?[0-9]{3}[ .-]?[0-9]{2}[ .-]?[0-9]{2}|[0-9]{3}[0-9]{7}$gm"

    def check_value(self, value) -> bool:
        """Check value.

        :param value: phone number to validate, e.g. +380501234567
        """
        if re.findall(self.REGEX, value):
            logger.info(value)
            return True
        else:
            raise AssertionError("Invalid phone number.")


class ValidatePassword(Validator):
    """Validate password."""
    def check_value(self, value) -> bool:
        """Check value.

        :param value: password to validate, e.g. Password1
        """
        if (
            not re.findall("\d", value)
            and not re.findall("[A-Z]", value)
            and not len(value) >= 8
        ):
            raise AssertionError(
                """The password must contain at least 1 digit, 0-9 and 1 uppercase letter,
                 A-Z and characters long must have more than 7."""
            )
        else:
            return True


class User(db.Model):
    """User model for storing users."""

    __tablename__ = "users"  # noqa
    id = Column(Integer, primary_key=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(33), nullable=False)
    phone = Column(String, nullable=False)
    address = Column(String(255), nullable=False)
    address2 = Column(String(255), nullable=False)
    city = Column(String(255), nullable=False)
    state = Column(String(255), nullable=False)
    zip_code = Column(Integer, nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"))
    order = db.relationship("Order", overlaps="orders,users")

    @classmethod
    def __declare_last__(cls):
        """Validate user fields."""
        ValidateString(User.full_name)
        ValidateEmail(User.email)
        ValidatePhone(User.phone)
        ValidateString(User.address)
        ValidateString(User.address2)
        ValidateString(User.city)
        ValidateString(User.state)
        ValidateInteger(User.zip_code)


roles_users = db.Table(
    "roles_users",
    Column("user_account_id", Integer, ForeignKey("users_accounts.id")),
    Column("role_id", Integer, ForeignKey("role.id")),
)


class UserAccount(db.Model, UserMixin):
    """UserAccount model for storing users."""

    __tablename__ = "users_accounts"  # noqa
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(33), nullable=False, unique=True)
    password = Column(String, nullable=False)
    active = Column(Boolean)
    remember = Column(Boolean, default=False)
    registered_on = db.Column(db.DateTime, nullable=False)
    admin = db.Column(db.Boolean, nullable=False, default=False)
    confirmed = db.Column(db.Boolean, nullable=False, default=False)
    confirmed_on = db.Column(db.DateTime, nullable=True)
    count = db.Column(Integer, nullable=True)

    users_opponent = db.relationship(
        "UserOpponent", backref="users_accounts", lazy=True
    )
    users_members = db.relationship(
        "UserMember",
        backref="users_accounts",
        overlaps="users_accounts,members,users_members",
    )

    roles = db.relationship(
        "Role",
        secondary=roles_users,
        backref=db.backref("users_accounts", lazy="dynamic"),
    )

    @classmethod
    def __declare_last__(cls):
        """Validate user fields."""
        ValidateString(UserAccount.name)
        ValidateEmail(UserAccount.email)
        ValidatePassword(UserAccount.password)


class Role(db.Model, RoleMixin):
    """Role model for storing roles."""

    id = Column(Integer, primary_key=True)
    name = Column(String(40))
    description = Column(String(255))


user_datastore = SQLAlchemyUserDatastore(db, UserAccount, Role)


class UserOpponent(db.Model):
    """UserOpponent model for storing users."""

    __tablename__ = "users_opponents"  # noqa
    id = Column(Integer, primary_key=True)
    opponent_category = Column(String(50), nullable=True, default="Amateur")
    opponent_city = Column(String(50))
    opponent_district = Column(String(50))
    opponent_date = Column(String(50))
    opponent_phone = Column(String(50))
    user_account_id = Column(Integer, ForeignKey("users_accounts.id"))
    user_account = db.relationship(
        "UserAccount",
        overlaps="users_accounts, users_opponent,OfferOpponent.user_opponent, queues_opponents",
    )
    offers_opponent = db.relationship(
        "OfferOpponent", backref="users_opponents", lazy="dynamic"
    )


class OfferOpponent(db.Model):
    """OfferOpponent model for storing offers."""
    __tablename__ = "offers_opponents"  # noqa
    id = Column(Integer, primary_key=True)
    offer_name = Column(String(50))
    offer_email = Column(String(50))
    offer_phone = Column(String(50))
    offer_category = Column(String(50), nullable=True, default="Amateur")
    offer_city = Column(String(50), default="Lviv")
    offer_district = Column(String(50))
    offer_date = Column(String(50))
    offer_accept = Column(Boolean, unique=False, default=False)
    offer_message = Column(Text(), nullable=True)
    user_opponent_id = Column(Integer, ForeignKey("users_opponents.id"))
    user_opponent = db.relationship(
        "UserOpponent",
        overlaps="offers_opponent, users_opponents, offers_opponents",
    )


class QueueOpponent(db.Model):
    """QueueOpponent model for storing queues."""

    __tablename__ = "queues_opponents"  # noqa
    id = Column(Integer, primary_key=True)
    queue_name = Column(String(50))
    queue_email = Column(String(50))
    queue_phone = Column(String(50))
    queue_category = Column(String(50), nullable=True, default="Amateur")
    queue_city = Column(String(50), default="Lviv")
    queue_district = Column(String(50))
    queue_date = Column(String(50))
    queue_accept = Column(Boolean, unique=False, default=False)
    queue_message = Column(Text(), nullable=True)
    queue_offer_opponent_id = Column(Integer, ForeignKey("offers_opponents.id"))
    queue_offer_opponent = db.relationship(
        "OfferOpponent",
        overlaps="queue_opponent, users_opponents, queues_opponents",
    )


class UserMember(db.Model):
    """UserMember model for storing users."""

    __tablename__ = "users_members"  # noqa
    id = Column(Integer, primary_key=True)
    member_title = Column(String(50))
    member_category = Column(String(50), nullable=True, default="Amateur")
    member_city = Column(String(50), default="Lviv")
    member_district = Column(String(50))
    member_date = Column(String(50))
    member_phone = Column(String(50))
    member_quantity = Column(String(50))
    user_id = Column(Integer, ForeignKey("users_accounts.id"), nullable=False)
    user_account = db.relationship(
        "UserAccount", overlaps="users_accounts,users_members"
    )
    members = db.relationship("Member", overlaps="members,users_members")


class Member(db.Model):
    """Member model for storing members."""

    __tablename__ = "members"  # noqa
    id = Column(Integer, primary_key=True)
    tour_member_name = Column(String(50))
    tour_member_phone = Column(String(50))
    tour_member_email = Column(String(50))
    tour_member_accept = Column(Boolean, unique=False, default=False)
    user_member_id = Column(Integer, ForeignKey("users_members.id"))
    user_member = db.relationship("UserMember", overlaps="members,users_members")
