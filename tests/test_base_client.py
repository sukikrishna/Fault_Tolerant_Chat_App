import pytest
import grpc
from unittest.mock import patch, MagicMock
from base_client import ChatClientBase
from grpc import RpcError

class FakeRpcError(RpcError):
    def code(self):
        return None

@pytest.fixture
def mock_stub():
    """Creates a mock gRPC stub for simulating server responses.

    Returns:
        MagicMock: A mocked gRPC stub with preconfigured return values.
    """
    stub = MagicMock()
    stub.ListUsers.return_value.user = []
    stub.CreateAccount.return_value.error_code = 0
    stub.Login.return_value.error_code = 0
    stub.Send.return_value.error_code = 0
    stub.Logout.return_value.error_code = 0
    stub.DeleteAccount.return_value.error_code = 0
    stub.GetMessages.return_value.message = []
    stub.AcknowledgeReceivedMessages.return_value.error_code = 0
    stub.GetChat.return_value.message = []
    stub.DeleteMessages.return_value.error_code = 0
    stub.GetUnreadCounts.return_value.counts = []
    return stub


@pytest.fixture
def client(mock_stub):
    """Initializes a ChatClientBase with a mocked gRPC stub.

    Args:
        mock_stub (MagicMock): Mocked stub to inject into the client.

    Returns:
        ChatClientBase: The initialized chat client instance.
    """
    addresses = ["localhost:50051"]
    with patch("base_client.grpc.insecure_channel"):
        client = ChatClientBase(addresses)
        client.stub = mock_stub
        return client


def test_list_users(client):
    """Tests that list_users returns an empty user list."""
    users = client.list_users()
    assert users == []


def test_create_account(client):
    """Tests account creation returns success status."""
    resp = client.create_account("user", "pass")
    assert resp.error_code == 0


def test_login(client):
    """Tests login returns success status."""
    resp = client.login("user", "pass")
    assert resp.error_code == 0


def test_send_message(client):
    """Tests sending a message succeeds."""
    client.user_session_id = "abc"
    resp = client.send_message("bob", "hi")
    assert resp.error_code == 0


def test_logout(client):
    """Tests logging out succeeds."""
    client.user_session_id = "abc"
    resp = client.logout()
    assert resp.error_code == 0


def test_delete_account(client):
    """Tests deleting an account succeeds."""
    client.user_session_id = "abc"
    resp = client.delete_account()
    assert resp.error_code == 0


def test_receive_messages(client):
    """Tests receiving messages returns an empty list."""
    client.user_session_id = "abc"
    msgs = client.receive_messages()
    assert msgs.message == []


def test_get_chat(client):
    """Tests getting chat history returns empty list."""
    client.user_session_id = "abc"
    resp = client.get_chat("bob")
    assert resp.message == []


def test_delete_messages(client):
    """Tests deleting specific messages by ID."""
    client.user_session_id = "abc"
    resp = client.delete_messages([1])
    assert resp.error_code == 0


def test_get_unread_counts(client):
    """Tests getting unread message counts returns empty counts."""
    client.user_session_id = "abc"
    resp = client.get_unread_counts()
    assert resp.counts == []

@pytest.fixture
def reconnect_client():
    with patch("base_client.grpc.insecure_channel"):
        client = ChatClientBase(["localhost:50051"])
        client.stub = MagicMock()
        return client

def test_connect_all_addresses_fail():
    """Tests connect retries all servers and fails."""
    addresses = ["addr1", "addr2"]

    with patch("base_client.grpc.insecure_channel"), \
         patch("base_client.spec_pb2_grpc.ClientAccountStub") as stub_class:

        stub = stub_class.return_value
        stub.ListUsers.side_effect = MagicMock(side_effect=Exception("fail"))

        client = ChatClientBase(addresses, max_retries=1)
        client.stub = stub

        # Should complete without crashing
        client.connect()


def test_exit_is_callable(reconnect_client):
    """Tests exit_ method exists and is callable."""
    reconnect_client.exit_()  # just runs without error

def test_delete_messages_calls_stub():
    """Covers delete_messages() happy path."""
    client = ChatClientBase(["localhost:5000"])
    client.user_session_id = "abc"
    mock_response = MagicMock()

    with patch.object(client, "stub") as stub:
        stub.DeleteMessages.return_value = mock_response
        resp = client.delete_messages([1, 2])
        assert resp == mock_response


def test_get_unread_counts_success():
    """Covers get_unread_counts() call."""
    client = ChatClientBase(["localhost:5000"])
    client.user_session_id = "abc"
    mock_response = MagicMock()

    with patch.object(client, "stub") as stub:
        stub.GetUnreadCounts.return_value = mock_response
        resp = client.get_unread_counts()
        assert resp == mock_response

def test_create_account_retry_on_error():
    client = ChatClientBase(["localhost:5000"])
    client.user_session_id = "abc"

    class FakeUnavailable(grpc.RpcError):
        def code(self): return grpc.StatusCode.UNAVAILABLE

    with patch.object(client, "stub") as stub:
        stub.CreateAccount.side_effect = [
            FakeUnavailable(),
            MagicMock()
        ]
        client.create_account("test", "pass")
        assert stub.CreateAccount.call_count == 2


def test_logout_retry_on_unavailable():
    client = ChatClientBase(["localhost:5000"])
    client.user_session_id = "abc"

    class FakeUnavailable(grpc.RpcError):
        def code(self): return grpc.StatusCode.UNAVAILABLE

    with patch.object(client, "stub") as stub:
        stub.Logout.side_effect = [
            FakeUnavailable(),
            MagicMock()
        ]
        client.logout()
        assert stub.Logout.call_count == 2


def test_exit_method_runs():
    """Covers the exit_() placeholder method."""
    client = ChatClientBase(["localhost:5000"])
    client.exit_()  # Just confirm it runs
