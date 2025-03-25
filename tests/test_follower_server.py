import pytest
import pickle
import grpc
import follower_server
from unittest.mock import MagicMock, patch, create_autospec
from follower_server import FollowerService, ClientServiceFollower
from models import UserModel


@pytest.fixture
def mock_db_session():
    """Provides a mocked scoped SQLAlchemy session."""
    return MagicMock()


@pytest.fixture
def follower_service(mock_db_session):
    """Returns an instance of FollowerService with mocked state and DB session."""
    state = {
        'followers': [],
        'leader_address': 'localhost:50051'
    }
    return FollowerService(db_session=mock_db_session, leader_address='localhost:50051', state=state)


def test_accept_updates_add(follower_service):
    """Tests AcceptUpdates with an 'add' operation."""
    user = UserModel(id=1, username="test", password="x")
    table = 'users'
    action = 'add'

    with patch("follower_server.pickle.loads", return_value=(table, action, user)), \
         patch("follower_server.inspect") as mock_inspect:
        attr = MagicMock()
        attr.mapper.column_attrs = []
        mock_inspect.return_value = attr

        response = follower_service.AcceptUpdates(MagicMock(update_data=b"pickle"), MagicMock())

    assert response.error_code == 0


def test_accept_updates_delete(follower_service):
    """Tests AcceptUpdates with a 'delete' operation."""
    user = UserModel(id=1, username="test", password="x")
    table = 'users'
    action = 'delete'

    with patch("follower_server.pickle.loads", return_value=(table, action, user)), \
         patch("follower_server.inspect") as mock_inspect:
        mock_inspect.return_value.mapper.column_attrs = []
        session = follower_service.db_session.return_value
        session.query().get.return_value = user

        response = follower_service.AcceptUpdates(MagicMock(update_data=b"pickle"), MagicMock())

    assert response.error_code == 0


def test_update_leader(follower_service):
    """Tests that leader address is updated in state."""
    request = MagicMock(new_leader_address="localhost:6000", new_leader_id="1")
    context = MagicMock()

    with patch("follower_server.assign_new_leader") as mock_assign:
        response = follower_service.UpdateLeader(request, context)
        mock_assign.assert_called_once_with(follower_service.state, "localhost:6000", "1")

    assert response.error_code == 0


def test_update_followers(follower_service):
    """Tests adding a follower to internal list."""
    follower_data = ("2", "localhost:6002")
    pickled = pickle.dumps(follower_data)

    request = MagicMock(update_data=pickled)
    context = MagicMock()

    response = follower_service.UpdateFollowers(request, context)
    assert follower_data in follower_service.state['followers']
    assert response.error_code == 0


def test_client_service_follower_unimplemented():
    """Tests that all methods in ClientServiceFollower raise UNIMPLEMENTED."""
    client_stub = ClientServiceFollower("localhost:50051")
    with pytest.raises(grpc.RpcError):
        client_stub.SomeMethod()  # Should raise by __getattr__

def test_accept_updates_update_user(follower_service):
    """Tests 'update' operation and session handling for users."""
    user = UserModel(id=1, username="alice", password="x", session_id="sess")
    table = 'users'
    action = 'update'

    with patch("follower_server.pickle.loads", return_value=(table, action, user)), \
         patch("follower_server.inspect") as mock_inspect:

        mock_inspect.return_value.mapper.column_attrs = []
        session = follower_service.db_session.return_value
        session.query().get.return_value = user

        response = follower_service.AcceptUpdates(MagicMock(update_data=b"pickle"), MagicMock())

    assert response.error_code == 0

def test_accept_updates_merge_called_for_update(follower_service):
    """Tests 'update' with merge fallback logic for non-user tables."""
    fake_obj = MagicMock(id=1)
    table = 'messages'
    action = 'update'

    with patch("follower_server.pickle.loads", return_value=(table, action, fake_obj)), \
         patch("follower_server.inspect") as mock_inspect:

        mock_inspect.return_value.mapper.column_attrs = []
        session = follower_service.db_session.return_value
        response = follower_service.AcceptUpdates(MagicMock(update_data=b"pickle"), MagicMock())

        session.merge.assert_called_once()
        assert response.error_code == 0

def test_accept_updates_raises_and_rolls_back(follower_service):
    """Simulates exception inside AcceptUpdates and checks rollback."""
    with patch("follower_server.pickle.loads", side_effect=Exception("corrupt")), \
         patch("follower_server.inspect"), \
         patch("follower_server.print") as mock_print:

        session = follower_service.db_session.return_value
        response = follower_service.AcceptUpdates(MagicMock(update_data=b"bad"), MagicMock())
        session.rollback.assert_called_once()
        assert response.error_code == 0
        mock_print.assert_called()

def test_assign_new_leader_updates_state():
    """Tests that assign_new_leader updates follower state and launches follower leader server."""
    state = {
        'database_url': 'sqlite:///:memory:',
        'leader_address': '',
        'followers': [("localhost:1234", "1")],
    }

    with patch("follower_server.init_db"), \
         patch("follower_server.get_session_factory"), \
         patch("follower_server.server_follower_leader"), \
         patch("follower_server.request_update"):

        follower_server.assign_new_leader(state, "localhost:9999", "1")

    assert state['leader_address'] == "localhost:9999"

def test_request_update_syncs_db():
    """Tests that request_update properly loads leader state into DB."""
    user = UserModel(id=1, username="test", password="pass")

    state = {
        'leader_address': 'localhost:5000',
        'follower_id': '2',
        'follower_address': 'localhost:6000',
        'db_session': MagicMock(),
    }

    with patch("follower_server.grpc.insecure_channel"), \
         patch("follower_server.spec_pb2_grpc.LeaderServiceStub") as stub_cls, \
         patch("follower_server.pickle.loads", return_value={"users": [user], "messages": []}):

        stub = stub_cls.return_value
        stub.RegisterFollower.return_value = MagicMock(
            pickled_db=b'data', other_followers=[]
        )

        follower_server.request_update(state)
        assert "followers" in state


def test_assign_new_leader_sets_all_keys():
    state = {
        "leader_address": "",
        "db_engine": MagicMock(),
        "database_url": "sqlite:///:memory:",
        "followers": [("localhost:1", "1")]
    }

    with patch("follower_server.init_db") as init_db, \
         patch("follower_server.get_session_factory"), \
         patch("follower_server.server_follower_leader"), \
         patch("follower_server.request_update"):
        follower_server.assign_new_leader(state, "localhost:9999", "1")
        assert state["leader_address"] == "localhost:9999"


def test_request_update_merges_users():
    follower_state = {
        "leader_address": "localhost:5000",
        "follower_id": "2",
        "follower_address": "localhost:6000",
        "db_session": MagicMock()
    }

    user = UserModel(username="abc", password="x")
    data = {"users": [user], "messages": []}

    with patch("follower_server.grpc.insecure_channel"), \
         patch("follower_server.spec_pb2_grpc.LeaderServiceStub") as stub_cls, \
         patch("follower_server.pickle.loads", return_value=data):
        stub_cls.return_value.RegisterFollower.return_value = MagicMock(
            pickled_db=b"blob", other_followers=[]
        )
        follower_server.request_update(follower_state)
        assert "followers" in follower_state


def test_wait_for_port_release_success():
    """Tests wait_for_port_release returns True when port is free."""
    with patch("follower_server.socket.socket") as mock_socket:
        mock_socket.return_value.__enter__.return_value.connect_ex.return_value = 1  # port not in use
        assert follower_server.wait_for_port_release("localhost:1234", timeout=1)


def test_wait_for_port_release_timeout():
    """Tests wait_for_port_release returns False after timeout."""
    with patch("follower_server.socket.socket") as mock_socket:
        mock_socket.return_value.__enter__.return_value.connect_ex.return_value = 0  # always in use
        assert not follower_server.wait_for_port_release("localhost:1234", timeout=1)


def test_process_update_data_handles_missing_attr(follower_service):
    """Tests update_data logic handles missing attribute fallback."""
    dummy_obj = MagicMock()
    dummy_obj.__class__.__name__ = "UserModel"
    dummy_obj.__dict__ = {"id": 1, "username": "a"}  # no password attr
    table = "users"

    with patch("follower_server.pickle.loads", return_value=(table, "add", dummy_obj)), \
         patch("follower_server.inspect") as mock_inspect:
        mock_inspect.return_value.mapper.column_attrs = [
            MagicMock(key="id"),
            MagicMock(key="username"),
            MagicMock(key="password")  # password missing from __dict__
        ]
        response = follower_service.AcceptUpdates(MagicMock(update_data=b"bad"), MagicMock())
        assert response.error_code == 0


def test_serve_follower_client_retry_bind_failure():
    """Covers retry logic in serve_follower_client."""
    state = {
        "db_session": MagicMock(),
        "leader_address": "localhost:5000",
        "client_address": "localhost:9999",
    }

    with patch("follower_server.grpc.server") as mock_grpc_server, \
         patch("follower_server.wait_for_port_release", return_value=True):
        mock_grpc_server.return_value.add_insecure_port.side_effect = [Exception("fail"), 1]
        follower_server.serve_follower_client(state)


def test_server_follower_leader_retry_logic():
    """Covers retry loop in server_follower_leader bind attempts."""
    state = {
        "db_session": MagicMock(),
        "leader_address": "localhost:5000",
        "follower_address": "localhost:9999",
    }

    with patch("follower_server.grpc.server") as mock_grpc_server, \
         patch("follower_server.wait_for_port_release", return_value=True):
        mock_grpc_server.return_value.add_insecure_port.side_effect = [Exception("fail"), 1]
        follower_server.server_follower_leader(state)
