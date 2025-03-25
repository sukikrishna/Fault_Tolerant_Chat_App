import pytest
from sqlalchemy.orm import scoped_session
from models import (
    UserModel,
    MessageModel,
    DeletedMessageModel,
    init_db,
    get_session_factory,
)


@pytest.fixture
def db_session():
    """Creates an in-memory SQLite database session for testing.

    Returns:
        scoped_session: A scoped SQLAlchemy session for the test.
    """
    engine = init_db("sqlite:///:memory:", drop_tables=False)
    session_factory = get_session_factory(engine)
    session = scoped_session(session_factory)
    yield session
    session.remove()


def test_user_model_creation(db_session):
    """Tests that a user can be created and queried from the database."""
    user = UserModel(username="alice", password="secret", logged_in=True, session_id="abc123")
    db_session.add(user)
    db_session.commit()

    result = db_session.query(UserModel).filter_by(username="alice").first()
    assert result is not None
    assert result.username == "alice"
    assert result.logged_in is True
    assert result.session_id == "abc123"


def test_message_model_creation(db_session):
    """Tests creating a message between two users."""
    sender = UserModel(username="bob", password="x")
    receiver = UserModel(username="carol", password="y")
    db_session.add_all([sender, receiver])
    db_session.commit()

    message = MessageModel(
        sender_id=sender.id,
        receiver_id=receiver.id,
        content="Hello Carol!",
        is_received=False,
        sender_deleted=False,
        receiver_deleted=False,
    )
    db_session.add(message)
    db_session.commit()

    result = db_session.query(MessageModel).first()
    assert result is not None
    assert result.content == "Hello Carol!"
    assert result.sender_id == sender.id
    assert result.receiver_id == receiver.id


def test_deleted_message_model(db_session):
    """Tests inserting a deleted message record."""
    sender = UserModel(username="dave", password="z")
    receiver = UserModel(username="eve", password="q")
    db_session.add_all([sender, receiver])
    db_session.commit()

    deleted = DeletedMessageModel(
        sender_id=sender.id,
        receiver_id=receiver.id,
        content="Old message",
        is_received=True,
        original_message_id=42,
    )
    db_session.add(deleted)
    db_session.commit()

    result = db_session.query(DeletedMessageModel).first()
    assert result is not None
    assert result.original_message_id == 42
    assert result.content == "Old message"
    assert result.is_received is True
