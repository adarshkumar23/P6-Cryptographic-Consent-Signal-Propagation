import os

from cryptography.fernet import Fernet

os.environ.setdefault("SATELLITE_KEK", Fernet.generate_key().decode())
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest

from app.config import get_settings

get_settings.cache_clear()

from app.db import Base, make_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def db_session():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
