# Distributed Chat Application with Leader-Follower Replication

<p align="center">
  <img src="img/msg.png">
</p>

This project is a persistant, fault-tolerant chat system designed to operate in a distributed environment. It uses gRPC and Protocol Buffers for fast and structured communication between services, and supports both GUI-based (Tkinter) and terminal-based clients. Users can create accounts, log in, send/receive/delete messages, and interact with a searchable list of users.

The system follows a leader-follower replication model where one server starts as the leader, handling all write operations and syncing updates to followers. Followers register themselves with the leader and regularly ping it using heartbeat RPCs. If the leader fails, the follower with the lowest server ID is promoted to leader through an election mechanism, and all other followers reconfigure themselves accordingly. This ensures continuous availability and consistency even during sever or network failures.

## Components Overview

### Source Code Structure

```
src
├── base_client.py
├── gui_client.py
├── leader_server.py
├── models.py
├── server.py
├── follower_server.py 
├── spec_pb2_grpc.py
├── spec_pb2.py
├── spec_pb2.pyi
├── spec.proto
├── terminal_client.py
└── utils.py
```

### Clients

- `base_client.py` – Reconnect-capable gRPC client wrapper.
- `gui_client.py` – Rich Tkinter GUI with login, messaging, notifications, and deletion.
- `terminal_client.py` – Terminal-based chat interface. (Deprecated)

### Servers

- `leader_server.py` – Handles authentication, message logic, and syncs with followers.
- `follower_server.py` – Mirrors leader’s database and forwards client actions.
- `server.py` – Bootstraps either leader or follower and handles leader election.

### gRPC / Protocol Buffers

- `spec.proto` – Proto definition for all request/response messages and services.
- Generated Files – `spec_pb2.py`, `spec_pb2_grpc.py`, and `spec_pb2.pyi`.

### Database & Models

- `models.py` – SQLAlchemy models for users, messages, and deleted messages.
- `utils.py` – Contains status codes and human-readable error messages.


## Installation

1. Clone the repository and change the directory:

```bash
git clone https://github.com/your-username/distributed-chat-app.git
cd distributed-chat-app
```

2. Setup virual environment:

```bash
python -m venv venv
```

3. Activate the environment:

```bash
source venv/bin/activate         # On Linux/Mac
venv\Scripts\activate            # On Windows
```

4. Install the requirements:

```bash
pip install -r requirements.txt
```

## Usage

1. Start the Leader Server

```bash
python src/server.py [id] leader [client address] [internal address]
```

An example:
```bash
python src/server.py 1 leader localhost:5001 localhost:5002
```

2. Start a Follower Server (as many as needed) using leader's internal address

```bash
python src/server.py [id] follower [client address] [internal address] --leader_address=[leader internal address]
```

An example:
```bash
python src/server.py 2 follower localhost:5003 localhost:5004 --leader_address=localhost:5002
```

Replace ports and IDs as necessary. You can use remote IPs across machines too.

3. Start the GUI Client

```bash
python src/gui_client.py -a [client addresses 1] [client addresses 2]
```

An example:
```bash
python src/gui_client.py -a localhost:5001 localhost:5002
```

The client will try the first address; if the leader is down, it connects to the next available.


## Developer Notes

To test replication by crashing the servers:

- Linux: `Ctrl+C`
- Windows: `Fn+Ctrl+B`


## Test Coverage and Documentation
This project is thoroughly tested and documented. 

The code was tested using `pytest`. Run the tests from project root:

```
PYTHONPATH=src pytest tests/ --cov=src --cov-config=.coveragerc
```

Here's the latest code coverage summary for the core application:

| Name                      | Stmts | Miss | Cover |
|---------------------------|-------|------|-------|
| `src/__init__.py`         | 0     | 0    | 100%  |
| `src/base_client.py`      | 129   | 12   | 91%   |
| `src/follower_server.py`  | 116   | 8    | 93%   |
| `src/leader_server.py`    | 310   | 47   | 85%   |
| `src/message_frame.py`    | 19    | 0    | 100%  |
| `src/models.py`           | 42    | 1    | 98%   |
| `src/server.py`           | 105   | 9    | 91%   |
| `src/terminal_client.py`  | 95    | 13   | 86%   |
| `src/utils.py`            | 34    | 0    | 100%  |
| **TOTAL**                 | 850   | 90   | 89%   |


All classes and methods are documented with Google-style docstrings for consistency and clarity. The complete developer and API documentation is available via Sphinx and rendered using the Read the Docs theme. 

The HTML documentation can be rebuilt locally as:

```bash
cd docs
make html   # or on Windows: .\make.bat html
````

Open the generated docs using:
```bash
open _build/html/index.html       # macOS
start _build/html/index.html      # Windows
xdg-open _build/html/index.html   # Linux
```

