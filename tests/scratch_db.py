"""
Test files run in one process (unittest discover) and share the `core.db` module, whose engine is
created once at import. Tests that empty the tables use their own scratch database instead, so
they can't wipe the users other test files created.
"""

import os
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core import db


def use_scratch_database(cls):
    """Class decorator: give the TestCase an empty database for its tests, restored afterwards."""
    original_set_up = cls.__dict__.get('setUpClass')
    original_tear_down = cls.__dict__.get('tearDownClass')

    @classmethod
    def setUpClass(klass):
        klass._real_db = (db.engine, db.Session)
        db.engine = create_engine(f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'scratch.db')}")
        db.Session = sessionmaker(bind=db.engine, expire_on_commit=False)
        db.init_db()
        if original_set_up:
            original_set_up.__func__(klass)

    @classmethod
    def tearDownClass(klass):
        if original_tear_down:
            original_tear_down.__func__(klass)
        db.engine, db.Session = klass._real_db

    cls.setUpClass = setUpClass
    cls.tearDownClass = tearDownClass
    return cls
