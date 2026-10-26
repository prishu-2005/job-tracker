import os
import tempfile

import pytest

from app import app, init_db


@pytest.fixture
def client():
    """A test client with a fresh temporary database for every test."""
    fd, path = tempfile.mkstemp()
    app.config["DATABASE"] = path
    app.config["TESTING"] = True

    with app.app_context():
        init_db()

    with app.test_client() as client:
        yield client

    os.close(fd)
    os.unlink(path)