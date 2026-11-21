import os
import tempfile

import pytest

# use a throwaway database for tests, set before the app is imported
_tmp = tempfile.mkdtemp()
os.environ["TALLY_DB"] = os.path.join(_tmp, "test.db")


@pytest.fixture(autouse=True)
def empty_db():
    from app import db
    db.delete_all()
    yield
    db.delete_all()
