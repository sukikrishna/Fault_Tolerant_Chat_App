import pytest
from utils import StatusCode, StatusMessages, HelpMessages


def test_status_messages_mapping():
    """Tests the mapping of the status messages."""
    for code in StatusMessages.error_dict:
        msg = StatusMessages.get_error_message(code)
        assert isinstance(msg, str)
        assert msg == StatusMessages.error_dict[code]


def test_help_messages():
    """Tests all the help messages."""
    assert isinstance(HelpMessages.HELP_MSG, str)
    assert "create" in HelpMessages.HELP_MSG

    assert "Creates a new account" in HelpMessages.HELP_CREATE
    assert "Lists all users" in HelpMessages.HELP_LIST
    assert "Logs in" in HelpMessages.HELP_LOGIN
    assert "Sends a message" in HelpMessages.HELP_SEND
    assert "Receives all messages" in HelpMessages.HELP_RECEIVE
    assert "Deletes your account" in HelpMessages.HELP_DELETE
    assert "Exits the program" in HelpMessages.HELP_EXIT
    assert "Displays this help message" in HelpMessages.HELP_HELP
    assert "Logs out of your account" in HelpMessages.HELP_LOGOUT
