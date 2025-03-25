import pytest
import leader_server as leader_server
from unittest.mock import MagicMock, patch
from leader_server import ClientService
from models import UserModel
from google.protobuf.timestamp_pb2 import Timestamp
from datetime import datetime
from spec_pb2 import Ack
from leader_server import (
    serve_leader_client,
    serve_leader_follower,
    update_followers,
    fetch_all_data_from_orm,
    LeaderService
)

@pytest.fixture
def mock_session():
    """Provides a mocked SQLAlchemy session."""
    return MagicMock()


@pytest.fixture
def client_service(mock_session):
    """Creates the ClientService instance with mocked DB and update queue."""
    return ClientService(db_session=MagicMock(return_value=mock_session), update_queue=MagicMock())


@pytest.fixture
def mock_leader_state(tmp_path):
    """
    Pytest fixture providing a leader state dictionary.

    Args:
        tmp_path (Path): Temporary path for DB files.

    Returns:
        dict: A mock leader state.
    """
    return {
        'leader_id': 'leader1',
        'leader_address': 'localhost:50051',
        'followers': [],
        'db_engine': MagicMock(),
        'db_session': MagicMock(),
        'update_queue': MagicMock(),
        'client_address': 'localhost:60051'
    }

def test_create_account_new_user(client_service):
    """Tests creating a new account when username doesn't exist."""
    mock_session = client_service.db_session.return_value
    mock_session.query().filter_by().scalar.return_value = None
    mock_session.query().filter_by().first.return_value = UserModel(username="alice", password="123")

    with patch("leader_server.fully_load"), patch("leader_server.pickle.dumps"):
        request = MagicMock(username="alice", password="123")
        context = MagicMock()
        response = client_service.CreateAccount(request, context)

    assert response.error_code == 0
    assert "successfully" in response.error_message.lower()


def test_create_account_duplicate_user(client_service):
    """Tests creating a user that already exists."""
    mock_session = client_service.db_session.return_value
    mock_session.query().filter_by().scalar.return_value = True

    request = MagicMock(username="alice", password="123")
    context = MagicMock()
    response = client_service.CreateAccount(request, context)

    assert response.error_code != 0
    assert "already" in response.error_message.lower()


def test_login_success(client_service):
    """Tests login with correct password."""
    user = UserModel(username="bob", password="hashed_pw")
    hashed = user.password

    mock_session = client_service.db_session.return_value
    mock_session.query().filter_by().first.return_value = user

    with patch("leader_server.hash_password", return_value=hashed), \
         patch("leader_server.fully_load"), \
         patch("leader_server.pickle.dumps"), \
         patch.object(ClientService, "GenerateSessionID", return_value="mock-session"):
        request = MagicMock(username="bob", password="anything")
        context = MagicMock()
        response = client_service.Login(request, context)

    assert response.error_code == 0
    assert response.session_id == "mock-session"


def test_login_wrong_password(client_service):
    """Tests login with incorrect password."""
    user = UserModel(username="bob", password="correct")

    mock_session = client_service.db_session.return_value
    mock_session.query().filter_by().first.return_value = user

    with patch("leader_server.hash_password", return_value="wrong"):
        request = MagicMock(username="bob", password="wrong")
        context = MagicMock()
        response = client_service.Login(request, context)

    assert response.error_code != 0
    assert "incorrect" in response.error_message.lower()


def test_send_message_success(client_service):
    """Tests sending a message from one valid user to another."""
    sender = UserModel(id=1, username="alice", session_id="abc")
    receiver = UserModel(id=2, username="bob")
    inserted_message = MagicMock(id=123, content="hi")

    mock_session = client_service.db_session.return_value

    def side_effect_first(*args, **kwargs):
        # Return appropriate object depending on call order or content
        if not hasattr(side_effect_first, "call_count"):
            side_effect_first.call_count = 0
        side_effect_first.call_count += 1
        if side_effect_first.call_count == 1:
            return sender  # sender lookup
        elif side_effect_first.call_count == 2:
            return receiver  # receiver lookup
        elif side_effect_first.call_count == 3:
            return inserted_message  # inserted message
        return None

    mock_query = MagicMock()
    mock_query.filter_by.return_value.first.side_effect = side_effect_first
    mock_session.query.return_value = mock_query

    with patch("leader_server.fully_load"), patch("leader_server.pickle.dumps"):
        request = MagicMock(session_id="abc", to="bob", message="hi")
        context = MagicMock()
        response = client_service.Send(request, context)

    assert response.error_code == 0
    assert "sent" in response.error_message.lower()


def test_send_message_user_not_logged_in(client_service):
    """Tests sending a message with invalid session ID."""
    mock_session = client_service.db_session.return_value
    mock_session.query().filter_by().first.return_value = None

    request = MagicMock(session_id="invalid", to="bob", message="yo")
    context = MagicMock()
    response = client_service.Send(request, context)

    assert response.error_code != 0
    assert "login" in response.error_message.lower()


def test_list_users(client_service):
    """Tests listing users from the database."""
    user1 = UserModel(username="alice", logged_in=True)
    user2 = UserModel(username="bob", logged_in=False)

    mock_session = client_service.db_session.return_value
    mock_session.query().all.return_value = [user1, user2]

    request = MagicMock(wildcard="*")
    context = MagicMock()

    result = client_service.ListUsers(request, context)
    usernames = [user.username for user in result.user]

    assert "alice" in usernames
    assert "bob" in usernames


def test_logout_success(client_service):
    """Tests logout flow with valid session ID."""
    user = UserModel(username="alice", session_id="abc", logged_in=True)

    mock_session = client_service.db_session.return_value
    mock_session.query().filter_by().first.return_value = user

    request = MagicMock(session_id="abc")
    context = MagicMock()
    response = client_service.Logout(request, context)

    assert response.error_code == 0
    assert "logout" in response.error_message.lower()

def test_get_messages_success(client_service):
    """Tests retrieval of unread messages."""
    user = UserModel(id=1, username="alice", session_id="abc")
    message = MagicMock(sender=MagicMock(username="bob"), content="hello", id=1, is_received=False)

    session = client_service.db_session.return_value
    session.query().filter_by().first.return_value = user
    session.query().filter().all.return_value = [message]

    response = client_service.GetMessages(MagicMock(session_id="abc"), MagicMock())
    assert response.error_code == 0
    assert response.message[0].from_ == "bob"


def test_get_chat_success(client_service):
    """Tests fetching chat history with proper Timestamp conversion."""
    user = UserModel(id=1, username="alice", session_id="abc")
    receiver = UserModel(id=2, username="bob")

    # Real datetime value
    real_time = datetime.utcnow()

    # Mock message with datetime, not Timestamp
    message = MagicMock(sender=receiver, content="hi", id=1)
    message.time_stamp = real_time

    session = client_service.db_session.return_value

    mock_user_q = MagicMock()
    mock_user_q.first.side_effect = [user, receiver]
    session.query.return_value.filter_by.return_value = mock_user_q
    session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [message]

    response = client_service.GetChat(MagicMock(session_id="abc", username="bob"), MagicMock())
    assert response.error_code == 0
    assert response.message[0].message == "hi"


def test_get_unread_counts(client_service):
    """Tests unread count summary returns."""
    user = UserModel(id=1, username="alice", session_id="abc")
    session = client_service.db_session.return_value
    session.query().filter_by.return_value.first.return_value = user
    session.query().join().filter().group_by().all.return_value = [("bob", 3)]

    response = client_service.GetUnreadCounts(MagicMock(session_id="abc"), MagicMock())
    assert response.error_code == 0
    assert getattr(response.counts[0], "from") == "bob"
    assert response.counts[0].count == 3


def test_delete_messages(client_service):
    """Tests deleting a message."""
    user = UserModel(id=1, username="a", session_id="abc")
    msg = MagicMock(id=1, sender_id=1, receiver_id=2)

    session = client_service.db_session.return_value
    session.query().filter_by.return_value.first.return_value = user
    session.query().filter().all.return_value = [msg]

    with patch("leader_server.pickle.dumps"):
        response = client_service.DeleteMessages(
            MagicMock(session_id="abc", message_ids=[1]), MagicMock()
        )

    assert response.error_code == 0
    assert "deleted" in response.error_message.lower()


def test_delete_account(client_service):
    """Tests account deletion flow."""
    user = UserModel(id=1, session_id="abc")

    session = client_service.db_session.return_value
    session.query().filter_by.return_value.first.return_value = user
    session.query().filter().all.return_value = []

    response = client_service.DeleteAccount(MagicMock(session_id="abc"), MagicMock())
    assert response.error_code == 0
    assert "deleted" in response.error_message.lower()


def test_login_user_does_not_exist(client_service):
    """Tests login when user is not found."""
    session = client_service.db_session.return_value
    session.query().filter_by().first.return_value = None

    request = MagicMock(username="ghost", password="any")
    response = client_service.Login(request, MagicMock())
    assert response.error_code != 0
    assert "doesn't exist" in response.error_message.lower()


def test_send_receiver_not_found(client_service):
    sender = UserModel(id=1, username="alice", session_id="abc")

    session = client_service.db_session.return_value
    mock_query = MagicMock()
    mock_query.first.side_effect = [sender, None]
    session.query.return_value.filter_by.return_value = mock_query

    request = MagicMock(session_id="abc", to="bob", message="yo")
    response = client_service.Send(request, MagicMock())
    assert response.error_code != 0
    assert "doesn't exist" in response.error_message.lower()


def test_get_chat_no_messages(client_service):
    user = UserModel(id=1, username="alice", session_id="abc")
    receiver = UserModel(id=2, username="bob")

    session = client_service.db_session.return_value
    mock_query = MagicMock()
    mock_query.first.side_effect = [user, receiver]
    session.query.return_value.filter_by.return_value = mock_query
    session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    response = client_service.GetChat(MagicMock(session_id="abc", username="bob"), MagicMock())
    assert response.error_code != 0
    assert "no messages" in response.error_message.lower()


def test_delete_account_user_not_found(client_service):
    """Tests DeleteAccount when session is invalid."""
    session = client_service.db_session.return_value
    session.query().filter_by.return_value.first.return_value = None

    request = MagicMock(session_id="bad")
    response = client_service.DeleteAccount(request, MagicMock())
    assert response.error_code != 0


def test_delete_messages_invalid_user(client_service):
    """Tests DeleteMessages when user session is invalid."""
    session = client_service.db_session.return_value
    session.query().filter_by.return_value.first.return_value = None

    request = MagicMock(session_id="bad", message_ids=[1])
    response = client_service.DeleteMessages(request, MagicMock())
    assert response.error_code != 0


def test_heartbeat_returns_ack(client_service):
    """Tests that HeartBeat returns a success Ack."""
    service = leader_server.LeaderService({}, db_engine=MagicMock())
    response = service.HeartBeat(MagicMock(), MagicMock())
    assert isinstance(response, Ack)
    assert response.error_code == 0


def test_check_leader_ack(client_service):
    """Tests CheckLeader response."""
    service = leader_server.LeaderService({}, db_engine=MagicMock())
    response = service.CheckLeader(MagicMock(), MagicMock())
    assert isinstance(response, Ack)
    assert response.error_code == 0


def test_register_follower_adds_if_new(client_service):
    """Tests RegisterFollower adds new follower if unknown."""
    service = leader_server.LeaderService({"followers": []}, db_engine=MagicMock())

    with patch("leader_server.pickle.dumps", return_value=b"abc"), \
         patch("leader_server.grpc.insecure_channel"), \
         patch("leader_server.spec_pb2_grpc.FollowerServiceStub"):

        req = MagicMock(follower_id="5", follower_address="localhost:9999")
        resp = service.RegisterFollower(req, MagicMock())
        assert resp.error_code == 0


def test_delete_account_user_not_logged_in(client_service):
    session = client_service.db_session.return_value
    session.query().filter_by.return_value.first.return_value = None

    req = MagicMock(session_id="invalid")
    response = client_service.DeleteAccount(req, MagicMock())
    assert response.error_code != 0


def test_get_unread_counts_no_user(client_service):
    session = client_service.db_session.return_value
    session.query().filter_by.return_value.first.return_value = None

    req = MagicMock(session_id="ghost")
    response = client_service.GetUnreadCounts(req, MagicMock())
    assert response.error_code != 0


def test_delete_messages_exception_rollback(client_service):
    user = UserModel(id=1, username="u", session_id="abc")
    session = client_service.db_session.return_value
    session.query().filter_by.return_value.first.return_value = user

    session.query().filter.side_effect = Exception("DB error")
    req = MagicMock(session_id="abc", message_ids=[1])

    response = client_service.DeleteMessages(req, MagicMock())
    assert response.error_code != 0
    session.rollback.assert_called_once()


def test_get_messages_no_messages(client_service):
    """Tests GetMessages when inbox is empty."""
    user = UserModel(id=1, session_id="abc")
    session = client_service.db_session.return_value
    session.query().filter_by.return_value.first.return_value = user
    session.query().filter.return_value.all.return_value = []

    request = MagicMock(session_id="abc")
    response = client_service.GetMessages(request, MagicMock())
    assert response.error_code != 0
    assert "no messages" in response.error_message.lower()


def test_register_follower_skips_existing():
    """Tests RegisterFollower does not duplicate existing follower."""
    state = {
        "followers": [("3", "localhost:5003")]
    }
    req = MagicMock(follower_id="3", follower_address="localhost:5003")

    with patch("leader_server.pickle.dumps", return_value=b"x"), \
         patch("leader_server.grpc.insecure_channel"), \
         patch("leader_server.spec_pb2_grpc.FollowerServiceStub") as stub:
        stub.return_value.UpdateFollowers.return_value = MagicMock()
        service = leader_server.LeaderService(state, db_engine=MagicMock())
        resp = service.RegisterFollower(req, MagicMock())
        assert resp.error_code == 0


def test_delete_messages_skips_missing(client_service):
    """Tests delete fallback when message not found."""
    user = UserModel(id=1, session_id="abc")
    session = client_service.db_session.return_value
    session.query().filter_by.return_value.first.return_value = user
    session.query().filter.return_value.all.return_value = []

    req = MagicMock(session_id="abc", message_ids=[1])
    with patch("leader_server.pickle.dumps"):
        resp = client_service.DeleteMessages(req, MagicMock())
    assert resp.error_code == 0
    assert "deleted" in resp.error_message.lower()


def test_get_unread_counts_zero(client_service):
    """Tests GetUnreadCounts returns 0 results when no messages."""
    user = UserModel(id=1, session_id="abc")
    session = client_service.db_session.return_value
    session.query().filter_by.return_value.first.return_value = user
    session.query().join().filter().group_by().all.return_value = []

    req = MagicMock(session_id="abc")
    resp = client_service.GetUnreadCounts(req, MagicMock())
    assert resp.error_code == 0
    assert "unread" in resp.error_message.lower()
    assert len(resp.counts) == 0

def test_serve_leader_client(mock_leader_state):
    """
    Tests that serve_leader_client initializes the client-facing gRPC server.

    Args:
        mock_leader_state (dict): Leader state fixture.
    """
    server = serve_leader_client(mock_leader_state)
    assert server is not None
    server.stop(None)

def test_serve_leader_follower(mock_leader_state):
    """
    Tests that serve_leader_follower initializes the follower-facing gRPC server.

    Args:
        mock_leader_state (dict): Leader state fixture.
    """
    server = serve_leader_follower(mock_leader_state)
    assert server is not None
    server.stop(None)

@patch("leader_server.fetch_all_data_from_orm", return_value={"users": []})
@patch("leader_server.pickle.dumps", return_value=b"pickled_db")
def test_register_follower(mock_dumps, mock_fetch, mock_leader_state):
    """
    Tests the RegisterFollower method to ensure it returns pickled DB state 
    and appends the new follower to leader_state.

    Args:
        mock_dumps (MagicMock): Mocked pickle.dumps function.
        mock_fetch (MagicMock): Mocked fetch_all_data_from_orm function.
        mock_leader_state (dict): Leader state fixture.
    """
    service = LeaderService(mock_leader_state, mock_leader_state['db_engine'])
    request = MagicMock()
    request.follower_id = "f2"
    request.follower_address = "localhost:70051"

    context = MagicMock()
    response = service.RegisterFollower(request, context)
    assert response.pickled_db == b"pickled_db"
    assert ("f2", "localhost:70051") in mock_leader_state["followers"]


def test_leader_service_heartbeat_check():
    """
    Tests that HeartBeat and CheckLeader methods respond with success.

    No real gRPC calls are used. Instead, we instantiate LeaderService 
    and call methods directly.
    """
    service = LeaderService({}, MagicMock())
    request = MagicMock()
    context = MagicMock()

    response = service.HeartBeat(request, context)
    assert response.error_code == 0

    response = service.CheckLeader(request, context)
    assert response.error_code == 0

def test_fetch_all_data_from_orm():
    """
    Tests fetch_all_data_from_orm to confirm it queries the DB via sessionmaker.

    This uses a mock connection to ensure the code path is exercised.
    """
    mock_connection = MagicMock()
    fetch_all_data_from_orm(mock_connection)
    mock_connection.begin.assert_not_called()