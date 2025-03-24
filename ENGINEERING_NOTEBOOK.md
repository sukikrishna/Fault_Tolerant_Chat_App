# Engineering Notebook





# Leader Server Architecture
We built this distributed chat application using a leader-follower model. In our system, the clients interact with a leader server that handles all writes, logins, and reads. Every write operation (e.g., user creation, message send, account deletion) is recorded in a persistent SQLite database, and the same update is serialized and sent to all followers using gRPC.

Followers start by requesting a full snapshot of the database via RegisterFollower, and then stay in sync by receiving updates through AcceptUpdates. These updates are distributed using a dedicated background thread on the leader.

Each follower runs a heartbeat checker to monitor the leader’s availability. If the leader fails, a new leader is elected among the followers based on a deterministic lowest-ID rule. The newly promoted leader picks up replication duties and continues accepting client requests. Clients are built in a way that they reconnect to the next available leader server.

## Design Decisions

### 1. Separation of Leader and Follower Roles (Leader-Follower Replication)

We have a leader server that handles all of the client requests and database writes. The followers passively replicate the leader’s data via `AcceptUpdates`. When the leader experience crash/failstop failures, a follower with the lowest ID is elected as the new leader.

### 2. Persistence via SQLite & SQLAlchemy ORM

We assign each server (leader or follower) its own persistent SQLite database (e.g., chat_1.db, chat_2.db ...). There is no shared store which avoids a single point of failure. We have thre models: `UserModel`, `MessageModel`, and `DeletedMessageModel`. All models are managed using SQLAlchemy ORM. ORM objects are serialized and sent to followers.

### 3. Follower Initialization & Data Sync
When a new follower server starts, it must first synchronize its local state with the current leader to become a fully consistent replica of the leader.

 On receiving the request, the leader responds with a full database dump to sync state (initial replication). Followers deserialize the chat data in into own local SQL database. It also stores the current list of active followers for participation in future leader elections and replication.

### 4. Replication: Push-based Update Propagation
We use a push-based replication model to maintain consistency across all replicas.  Any state-changing operation (e.g. user creation, message sending, or account deletion) is placed into an update queue. A dedicated background thread monitors this queue and ensures that changes are immediately propagated to all followers. The leader then distributes these serialized updates to each follower via gRPC calls. Our design ensures that all followers are consistently updated in near real-time without data loss.


6. Session-Scoped Connections for Thread-Safety
scoped_session ensures thread-safe database interactions for multi-threaded gRPC servers (leader_server.py, follower_server.py).

### 5. Client Awareness & Failover Handling
The clients maintain a list of known server addresses. When the current leader is unavailable, the client tries the next address (rotating followers) until connection is successful.