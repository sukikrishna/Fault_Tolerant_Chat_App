# tests/test_message_frame.py

import tkinter as tk
import time
import pytest

from message_frame import MessageFrame

@pytest.fixture
def root():
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    yield root
    root.destroy()


def test_message_frame_creation(root):
    """Tests if the message frame is created correctly."""
    # Sample message data
    message_data = {
        "id": 1,
        "from": "alice",
        "content": "Hello, Bob!",
        "timestamp": int(time.time())
    }

    frame = MessageFrame(root, message_data)

    # Check message ID
    assert frame.message_id == 1

    # Check if BooleanVar is set to False initially
    assert not frame.select_var.get()

    # Simulate checkbox toggle
    frame.select_var.set(True)
    assert frame.select_var.get()
