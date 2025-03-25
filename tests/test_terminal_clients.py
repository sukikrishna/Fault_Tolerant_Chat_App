import pytest
from unittest.mock import MagicMock, patch
from terminal_client import ChatClientTerminal


@pytest.fixture
def client():
    """Creates a ChatClientTerminal instance with a mocked stub.

    Returns:
        ChatClientTerminal: The terminal client with mocked gRPC stub.
    """
    with patch("terminal_client.grpc.insecure_channel"):
        client = ChatClientTerminal(port=2625)
        client.stub = MagicMock()
        return client


def test_do_create_success(client, capsys):
    """Tests account creation with valid arguments."""
    client.stub.CreateAccount.return_value.error_message = "Success"
    client.do_create("alice pass123")
    captured = capsys.readouterr()
    assert "Success" in captured.out


def test_do_create_invalid_args(client, capsys):
    """Tests account creation with missing arguments."""
    client.do_create("alice")
    captured = capsys.readouterr()
    assert "Invalid Arguments" in captured.out


def test_do_login_success(client, capsys):
    """Tests login with valid credentials."""
    client.stub.Login.return_value = MagicMock(
        error_code=0, session_id="abc", error_message="Logged in"
    )
    with patch("threading.Thread.start"):  # avoid launching thread
        client.do_login("alice pass123")
    assert client.user_session_id == "abc"
    captured = capsys.readouterr()
    assert "Logged in" in captured.out


def test_do_login_invalid_args(client, capsys):
    """Tests login with missing arguments."""
    client.do_login("alice")
    captured = capsys.readouterr()
    assert "Invalid Arguments" in captured.out


def test_do_send_success(client, capsys):
    """Tests sending a message."""
    client.user_session_id = "abc"
    client.stub.Send.return_value.error_message = "Message sent"
    client.do_send("bob hey there")
    captured = capsys.readouterr()
    assert "Message sent" in captured.out


def test_do_send_invalid_args(client, capsys):
    """Tests sending with missing message."""
    client.do_send("bob")
    captured = capsys.readouterr()
    assert "Invalid Arguments" in captured.out


def test_do_list(client, capsys):
    """Tests listing users."""
    user = MagicMock(username="alice", status="online")
    client.stub.ListUsers.return_value.user = [user]
    client.do_list("")
    captured = capsys.readouterr()
    assert "alice" in captured.out
    assert "[ online ]" in captured.out


def test_do_delete(client, capsys):
    """Tests deleting account."""
    client.user_session_id = "abc"
    client.stub.DeleteAccount.return_value.error_message = "Deleted"
    client.do_delete("")
    captured = capsys.readouterr()
    assert "Deleted" in captured.out


def test_do_help(client, capsys):
    """Tests help command for all supported commands."""
    commands = ["list", "create", "login", "send", "logout", "exit", "delete", "help", ""]
    for cmd in commands:
        client.do_help(cmd)
    captured = capsys.readouterr()
    assert "Displays this help message" in captured.out


def test_emptyline(client):
    """Tests that empty input doesn't crash the CLI."""
    assert client.emptyline() is None


def test_do_exit(client, monkeypatch):
    """Tests do_exit shuts down channel and exits."""
    client.channel = MagicMock()
    with patch("builtins.quit") as mock_quit:
        client.do_exit("")
        client.channel.close.assert_called_once()
        mock_quit.assert_called_once()

def test_do_help_all_commands(client, capsys):
    """Tests help messages for all known commands."""
    for cmd in ["list", "create", "login", "send", "logout", "exit", "delete", "help", ""]:
        client.do_help(cmd)
    captured = capsys.readouterr()
    assert "help message" in captured.out.lower()


def test_do_help_all_variants(client, capsys):
    """Tests help for each command explicitly."""
    for command in ["list", "create", "login", "send", "logout", "exit", "delete", "help", "unknown"]:
        client.do_help(command)
    captured = capsys.readouterr()
    assert "help message" in captured.out.lower()


def test_do_exit_calls_quit(client):
    """Tests do_exit calls channel.close and quit."""
    client.channel = MagicMock()
    with patch("builtins.quit") as mock_quit:
        client.do_exit("")
        client.channel.close.assert_called_once()
        mock_quit.assert_called_once()


def test_do_help_default(client, capsys):
    """Tests default help message when no command is provided."""
    client.do_help("")  # fallback case
    captured = capsys.readouterr()
    assert "help message" in captured.out.lower()