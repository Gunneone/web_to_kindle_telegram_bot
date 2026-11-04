"""
Who is signing in. An account is a `users` row; an identity (Telegram, Google, an email address)
is one way to reach it, so the pipeline, history and settings never care how someone signed in.

- A Telegram identity always belongs to the account whose id is the Telegram id: the same row the
  bot uses, so a person's Kindle address and history are shared between the bot and the web app.
- Google and email identities belong to web accounts with negative ids. Telegram ids are positive,
  so the two never collide.
- Signing in with an address that another identity of a *verified* address already uses reaches
  the same account.
- Connecting Telegram to a web account merges the web account into the Telegram one.
"""

from . import db

TELEGRAM = 'telegram'
GOOGLE = 'google'
EMAIL = 'email'
PROVIDERS = (TELEGRAM, GOOGLE, EMAIL)


class LinkConflict(Exception):
    """The identity belongs to another Telegram account, so the two can't be joined."""


def normalize_subject(provider: str, subject: str) -> str:
    subject = str(subject).strip()
    return subject.lower() if provider == EMAIL else subject


def identities(user_id: int) -> list[db.Identity]:
    with db.Session() as session:
        return (session.query(db.Identity).filter_by(user_id=user_id)
                .order_by(db.Identity.created_at, db.Identity.id).all())


def email_of(user_id: int) -> str | None:
    """A verified address of the account, if any identity brought one."""
    return next((i.email for i in identities(user_id) if i.email), None)


def sign_in(provider: str, subject: str, *, email: str | None = None, username: str | None = None,
            first_name: str | None = None, last_name: str | None = None,
            current_user_id: int | None = None) -> db.User:
    """
    The account for a verified identity, created on first use.

    current_user_id: the account that is already signed in, when the person is connecting another
    way to sign in. Raises LinkConflict when the identity belongs to a different Telegram account.
    """
    if provider not in PROVIDERS:
        raise ValueError(f'unknown provider {provider!r}')
    subject = normalize_subject(provider, subject)
    email = email.strip().lower() if email else None

    with db.Session() as session:
        identity = session.query(db.Identity).filter_by(provider=provider, subject=subject).first()
        owner = identity.user_id if identity else None
        if owner is None and provider == TELEGRAM:
            owner = int(subject)
        if owner is None and email:
            match = session.query(db.Identity).filter(db.Identity.email == email).first()
            owner = match.user_id if match else None

    if current_user_id is not None and owner is not None and owner != current_user_id:
        account = _reconcile(current_user_id, owner)
    elif current_user_id is not None:
        account = current_user_id
    elif owner is not None:
        account = owner
    else:
        account = _new_web_id()

    user = _ensure_user(account, username=username, first_name=first_name, last_name=last_name,
                        telegram=provider == TELEGRAM)
    _ensure_identity(provider, subject, account, email)
    return user


def _reconcile(current: int, owner: int) -> int:
    """Join two accounts that turned out to be the same person; returns the one that remains."""
    if current > 0 and owner > 0:
        raise LinkConflict('both are Telegram accounts')
    if current > 0 > owner:
        keep, drop = current, owner
    elif owner > 0 > current:
        keep, drop = owner, current
    else:
        keep, drop = current, owner  # two web accounts: the signed-in one stays
    merge(drop, keep)
    return keep


def merge(src_id: int, dst_id: int) -> None:
    """
    Move everything of `src_id` to `dst_id` and remove `src_id`. The destination's own settings win;
    only what it hasn't set yet is taken over.
    """
    if src_id == dst_id:
        return
    with db.Session() as session:
        src = session.get(db.User, src_id)
        dst = session.get(db.User, dst_id)
        if dst is None:
            dst = db.User(user_id=dst_id, preserve_image_links=0, setup_verified=0)
            session.add(dst)
        if src is not None:
            if not dst.kindle_email and src.kindle_email:
                dst.kindle_email = src.kindle_email
                dst.setup_verified = src.setup_verified
                dst.delivery_mode = dst.delivery_mode or src.delivery_mode
            for name in ('language', 'amazon_store', 'username', 'first_name', 'last_name',
                         'last_book_received_date'):
                if not getattr(dst, name) and getattr(src, name):
                    setattr(dst, name, getattr(src, name))
            dst.preserve_image_links = dst.preserve_image_links or src.preserve_image_links
            session.delete(src)
        session.query(db.Article).filter_by(user_id=src_id).update({'user_id': dst_id})
        session.query(db.Identity).filter_by(user_id=src_id).update({'user_id': dst_id})
        session.commit()


def _new_web_id() -> int:
    with db.Session() as session:
        lowest = session.query(db.User.user_id).order_by(db.User.user_id).first()
    return min(0, lowest[0] if lowest else 0) - 1


def _ensure_user(user_id: int, *, username, first_name, last_name, telegram: bool) -> db.User:
    if telegram:
        return db.upsert_user(user_id, username=username, first_name=first_name, last_name=last_name)
    with db.Session() as session:
        user = session.get(db.User, user_id)
        if user is None:
            user = db.User(user_id=user_id, preserve_image_links=0, setup_verified=0)
            session.add(user)
        if first_name and not user.first_name:
            user.first_name = first_name
        if last_name and not user.last_name:
            user.last_name = last_name
        session.commit()
        return user


def _ensure_identity(provider: str, subject: str, user_id: int, email: str | None) -> None:
    with db.Session() as session:
        identity = session.query(db.Identity).filter_by(provider=provider, subject=subject).first()
        if identity is None:
            session.add(db.Identity(provider=provider, subject=subject, user_id=user_id, email=email))
        else:
            identity.user_id = user_id
            identity.email = email or identity.email
        session.commit()
