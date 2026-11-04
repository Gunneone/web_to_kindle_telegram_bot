"""
SQLite storage for users and the articles they sent. Missing columns are added on startup,
so existing databases keep working; rows created before a column existed hold NULL there.
"""

import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint, create_engine, event, inspect, or_, text
from sqlalchemy.orm import declarative_base, sessionmaker

def utcnow() -> datetime:
    """Naive UTC, like the timestamps already stored."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


Base = declarative_base()
engine = create_engine(os.getenv('DATABASE_URL', 'sqlite:///users.db'))


if engine.dialect.name == 'sqlite':
    @event.listens_for(engine, 'connect')
    def _sqlite_pragmas(dbapi_connection, _record):
        # The bot and the web app are separate processes sharing one file: let readers and a
        # writer overlap, and wait for a busy lock instead of failing at once
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA busy_timeout=5000')
        cursor.close()


Session = sessionmaker(bind=engine, expire_on_commit=False)

# Where books go. TELEGRAM is the EPUB file handed over by the front end itself: a file in the
# Telegram chat (a web app would offer a download); the stored value stays 'telegram'.
KINDLE = 'kindle'
TELEGRAM = 'telegram'
BOTH = 'both'
DELIVERY_MODES = (KINDLE, TELEGRAM, BOTH)

# Article.status
PROCESSING = 'processing'
SENT = 'sent'
PREVIEW = 'preview'  # sent, but the post is paywalled and only the free part was included
FAILED = 'failed'
DELIVERED = (SENT, PREVIEW)  # rows from before the status column (NULL) were successful sends too


class Article(Base):
    __tablename__ = 'articles'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    article_url = Column(String)
    timestamp = Column(DateTime, default=utcnow)
    epub_path = Column(String)
    title = Column(String)
    status = Column(String)
    error = Column(String)


class User(Base):
    __tablename__ = 'users'
    # Telegram users keep their Telegram id (always positive). Accounts created on the web through
    # Google or an email address get negative ids, so the two can never collide (see core.accounts)
    user_id = Column(Integer, primary_key=True)
    kindle_email = Column(String)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    last_book_received_date = Column(String)
    preserve_image_links = Column(Integer, default=0)  # SQLite uses INTEGER for boolean
    delivery_mode = Column(String)  # NULL: not chosen yet (Kindle once an address is set, chat until then)
    language = Column(String)  # NULL: follow the Telegram app language
    setup_verified = Column(Integer, default=0)  # the test book arrived

    @property
    def image_links(self) -> bool:
        return bool(self.preserve_image_links)

    @property
    def targets(self) -> set[str]:
        """Where a new book is delivered: {'kindle'}, {'telegram'} or both."""
        mode = self.delivery_mode
        if not self.kindle_email or mode == TELEGRAM:
            return {TELEGRAM}
        if mode == BOTH:
            return {KINDLE, TELEGRAM}
        return {KINDLE}

    @property
    def chose_chat_only(self) -> bool:
        """The user asked for EPUB files in the chat, so don't nudge them towards Kindle setup."""
        return self.delivery_mode == TELEGRAM


class Identity(Base):
    """A way to sign in (Telegram, Google, email) and the account it belongs to."""
    __tablename__ = 'identities'
    __table_args__ = (UniqueConstraint('provider', 'subject'),)
    id = Column(Integer, primary_key=True)
    provider = Column(String, nullable=False)  # 'telegram' | 'google' | 'email'
    subject = Column(String, nullable=False)  # the provider's stable id; the lowercased address for email
    user_id = Column(Integer, nullable=False, index=True)
    email = Column(String)  # a verified address, when the provider gave one
    created_at = Column(DateTime, default=utcnow)


def init_db():
    Base.metadata.create_all(engine)
    check_and_create_columns()


def check_and_create_columns():
    """Check if all columns exist and create missing ones."""
    inspector = inspect(engine)
    for table in Base.metadata.tables.values():
        existing_columns = {col['name'] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in existing_columns:
                with engine.begin() as connection:
                    connection.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type}'))


def upsert_user(user_id: int, *, username: str | None = None, first_name: str | None = None,
                last_name: str | None = None) -> User:
    """Create the user on first contact and keep their name current."""
    with Session() as session:
        user = session.get(User, user_id)
        if not user:
            user = User(user_id=user_id, preserve_image_links=0, setup_verified=0)
            session.add(user)
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        session.commit()
        return user


def get_user(user_id: int) -> User | None:
    with Session() as session:
        return session.get(User, user_id)


def update_user(user_id: int, **fields) -> User | None:
    with Session() as session:
        user = session.get(User, user_id)
        if not user:
            return None
        for name, value in fields.items():
            setattr(user, name, value)
        session.commit()
        return user


def delete_user_data(user_id: int) -> None:
    """
    Remove the user, their history and the EPUB files nobody else's history points to.

    Every conversion gets its own directory, so a path is shared only by rows written before that
    (the path used to be derived from the title alone).
    """
    with Session() as session:
        articles = session.query(Article).filter_by(user_id=user_id).all()
        paths = {a.epub_path for a in articles if a.epub_path}
        for article in articles:
            session.delete(article)
        session.query(Identity).filter_by(user_id=user_id).delete()
        user = session.get(User, user_id)
        if user:
            session.delete(user)
        session.commit()
        shared = {path for (path,) in session.query(Article.epub_path).filter(Article.epub_path.in_(paths))}
    for path in paths - shared:
        try:
            os.remove(path)
            os.rmdir(os.path.dirname(path))  # the book's own directory; left alone unless empty
        except OSError:
            pass


def create_article(user_id: int, url: str) -> Article:
    with Session() as session:
        article = Article(user_id=user_id, article_url=url, status=PROCESSING, timestamp=utcnow())
        session.add(article)
        session.commit()
        return article


def update_article(article_id: int, **fields) -> Article | None:
    with Session() as session:
        article = session.get(Article, article_id)
        if not article:
            return None
        for name, value in fields.items():
            setattr(article, name, value)
        session.commit()
        return article


def get_article(article_id: int) -> Article | None:
    with Session() as session:
        return session.get(Article, article_id)


def recent_delivery(user_id: int, url: str, days: int = 30) -> Article | None:
    """The user's latest successful delivery of this URL within the last `days` days."""
    since = utcnow() - timedelta(days=days)
    with Session() as session:
        return (session.query(Article)
                .filter(Article.user_id == user_id, Article.article_url == url,
                        or_(Article.status.in_(DELIVERED), Article.status.is_(None)),
                        Article.timestamp >= since)
                .order_by(Article.timestamp.desc())
                .first())


def history(user_id: int, offset: int = 0, limit: int = 5) -> tuple[list[Article], int]:
    """A page of the user's articles, newest first, plus the total count."""
    with Session() as session:
        query = session.query(Article).filter(Article.user_id == user_id)
        total = query.count()
        articles = query.order_by(Article.timestamp.desc(), Article.id.desc()).offset(offset).limit(limit).all()
        return articles, total
