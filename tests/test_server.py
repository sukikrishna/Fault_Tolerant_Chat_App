import pytest
from unittest.mock import patch, MagicMock
import server


@pytest.fixture
def follower_state():
    """Mock follower state for testing promotion logic."""
    return {
        'follower_id': '1',
        'follower_address': 'localhost:6001',
        'leader_address': 'localhost:5000',
        'client_address': 'localhost:7000',
        'followers': [('2', 'localhost:6002')],
        'db_session': MagicMock(),
        'db_engine': MagicMock(),
        'database_url': 'sqlite:///chat_test.db',
        'promotion_in_progress': False
    }


def test_upgrade_follower_promotes_to_leader(follower_state):
    """Tests upgrade from follower to leader starts correct services."""
    with patch("server.serve_leader_follower") as mock_serve_follower, \
         patch("server.serve_leader_client") as mock_serve_client, \
         patch("server.update_followers"), \
         patch("server.claim_leadery"), \
         patch("server.gc.collect"), \
         patch("server.time.sleep"), \
         patch("server.threading.Thread.start"):

        mock_serve_follower.return_value.wait_for_termination = MagicMock()
        mock_serve_client.return_value.wait_for_termination = MagicMock()

        server.upgrade_follower(follower_state)

        assert "leader_id" in follower_state
        assert "update_queue" in follower_state


def test_check_new_leader_valid_response(follower_state):
    """Tests check_new_leader accepts live leader."""
    min_follower = ("2", "localhost:6002")

    with patch("server.grpc.insecure_channel"), \
         patch("server.spec_pb2_grpc.LeaderServiceStub") as stub_class:
        stub = stub_class.return_value
        stub.CheckLeader.return_value = MagicMock(error_code=0)

        server.check_new_leader(min_follower, follower_state)

        assert follower_state['leader_address'] == "localhost:6002"


def test_check_new_leader_removes_dead(follower_state):
    """Tests removal of dead follower if CheckLeader fails."""
    min_follower = ("2", "localhost:6002")

    with patch("server.grpc.insecure_channel"), \
         patch("server.spec_pb2_grpc.LeaderServiceStub") as stub_class:
        stub = stub_class.return_value
        stub.CheckLeader.side_effect = Exception("no response")

        server.check_new_leader(min_follower, follower_state)

        assert ("2", "localhost:6002") not in follower_state['followers']


def test_leader_routine_starts_servers():
    """Tests leader_routine starts and blocks on gRPC servers."""
    with patch("server.init_db"), \
         patch("server.get_session_factory"), \
         patch("server.serve_leader_follower") as f_stub, \
         patch("server.serve_leader_client") as c_stub, \
         patch("server.update_followers"), \
         patch("server.threading.Thread.start"):

        f_stub.return_value.wait_for_termination = MagicMock()
        c_stub.return_value.wait_for_termination = MagicMock()

        server.leader_routine("1", "localhost:5001", "localhost:6001")


def test_follower_routine_starts_servers():
    """Tests follower_routine starts heartbeat and registers with leader."""
    with patch("server.init_db"), \
         patch("server.get_session_factory"), \
         patch("server.server_follower_leader") as leader_stub, \
         patch("server.request_update"), \
         patch("server.serve_follower_client") as client_stub, \
         patch("server.threading.Thread.start"):

        leader_stub.return_value.wait_for_termination = MagicMock()
        client_stub.return_value.wait_for_termination = MagicMock()

        server.follower_routine("2", "localhost:5002", "localhost:6002", "localhost:5000")

@pytest.fixture
def follower_state():
    """Mocked follower state dictionary."""
    return {
        "follower_id": "2",
        "follower_address": "localhost:5002",
        "client_address": "localhost:6002",
        "leader_address": "localhost:5000",
        "followers": [("3", "localhost:5003")],
        "db_engine": MagicMock(),
        "db_session": MagicMock(),
        "database_url": "sqlite:///chat.db",
        "promotion_in_progress": False
    }

def test_leader_routine_starts_servers_and_threads():
    """Covers leader_routine threading and server waiting paths."""
    with patch("server.init_db"), \
         patch("server.get_session_factory"), \
         patch("server.serve_leader_follower") as mock_follower, \
         patch("server.serve_leader_client") as mock_client, \
         patch("server.update_followers"), \
         patch("server.threading.Thread") as mock_thread:

        mock_thread.return_value.start = MagicMock()
        mock_follower.return_value.wait_for_termination = MagicMock()
        mock_client.return_value.wait_for_termination = MagicMock()

        server.leader_routine("5", "localhost:9999", "localhost:8888")
        mock_thread.return_value.start.assert_called_once()
        mock_follower.return_value.wait_for_termination.assert_called_once()
        mock_client.return_value.wait_for_termination.assert_called_once()


def test_follower_routine_thread_and_servers():
    """Covers follower_routine including registration and heartbeat."""
    with patch("server.init_db"), \
         patch("server.get_session_factory"), \
         patch("server.server_follower_leader") as mock_internal, \
         patch("server.request_update"), \
         patch("server.serve_follower_client") as mock_client, \
         patch("server.threading.Thread") as mock_thread:

        mock_internal.return_value.wait_for_termination = MagicMock()
        mock_client.return_value.wait_for_termination = MagicMock()

        mock_thread.return_value.start = MagicMock()

        server.follower_routine("3", "localhost:5555", "localhost:6666", "localhost:5000")
        mock_thread.return_value.start.assert_called_once()
        mock_client.return_value.wait_for_termination.assert_called_once()


def test_follower_promotes_itself(follower_state):
    """Tests upgrade_follower is called when self has lowest ID."""
    with (
        patch("server.grpc.insecure_channel"),
        patch("server.spec_pb2_grpc.LeaderServiceStub") as stub_class,
        patch("server.upgrade_follower") as upgrade_mock
    ):
        stub = stub_class.return_value
        stub.HeartBeat.side_effect = Exception("down")

        follower_state["follower_id"] = "1"
        follower_state["followers"] = []

        server.follower_heart_beat_checker(follower_state)
        upgrade_mock.assert_called_once()


def test_claim_leadery_sends_update():
    """Tests claim_leadery notifies all followers."""
    state = {
        "leader_id": "1",
        "leader_address": "localhost:5000",
        "followers": [("2", "localhost:5002")]
    }

    with patch("server.grpc.insecure_channel"), \
         patch("server.spec_pb2_grpc.FollowerServiceStub") as stub_class:
        stub = stub_class.return_value
        stub.UpdateLeader.return_value = MagicMock()
        server.claim_leadery(state)
        stub.UpdateLeader.assert_called_once()


def test_upgrade_follower_full_path(follower_state):
    """Tests upgrade_follower updates state and calls claim_leadery."""
    with (
        patch("server.serve_leader_follower") as serve_f,
        patch("server.serve_leader_client") as serve_c,
        patch("server.gc.collect"),
        patch("server.claim_leadery"),
        patch("server.update_followers"),
        patch("server.threading.Thread.start")
    ):
        serve_f.return_value.wait_for_termination = MagicMock()
        serve_c.return_value.wait_for_termination = MagicMock()
        server.upgrade_follower(follower_state)

        assert "leader_id" in follower_state
        assert follower_state["leader_id"] == "2"


def test_check_new_leader_handles_exceptions(follower_state):
    """Tests check_new_leader removes dead follower if CheckLeader fails."""
    min_follower = ("3", "localhost:5003")

    with patch("server.grpc.insecure_channel"), \
         patch("server.spec_pb2_grpc.LeaderServiceStub") as stub_class:
        stub = stub_class.return_value
        stub.CheckLeader.side_effect = Exception("timeout")

        server.check_new_leader(min_follower, follower_state)
        assert min_follower not in follower_state["followers"]
    
    with patch("builtins.print") as mock_print:
        server.check_new_leader(min_follower, follower_state)
        mock_print.assert_any_call("New leader is dead")
