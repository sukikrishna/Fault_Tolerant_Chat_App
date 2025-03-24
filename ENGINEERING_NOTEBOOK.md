# Engineering Notebook

# Leader Follower Architecture Summary

We built this distributed chat application using a leader-follower model. In our system, the clients interact with a leader server that handles all writes, logins, and reads. Every write operation (e.g., user creation, message send, account deletion) is recorded in a persistent SQLite database, and the same update is serialized and sent to all followers using gRPC.

Followers start by requesting a full snapshot of the database via RegisterFollower, and then stay in sync by receiving updates through AcceptUpdates. These updates are distributed using a dedicated background thread on the leader.

Each follower runs a heartbeat checker to monitor the leader’s availability. If the leader fails, a new leader is elected among the followers based on a deterministic lowest-ID rule. The newly promoted leader picks up replication duties and continues accepting client requests. Clients are built in a way that they reconnect to the next available leader server.

## Design Decisions

### 1. Separation of Leader and Follower Roles (Leader-Follower Replication)

We have a leader server that handles all of the client requests and database writes. The followers passively replicate the leader’s data via `AcceptUpdates`. When the leader experience crash/failstop failures, a follower with the lowest ID is elected as the new leader.

### 2. Persistence via SQLite & SQLAlchemy ORM

We assign each server (leader or follower) its own persistent SQLite database (e.g., chat_1.db, chat_2.db ...). There is no shared store which avoids a single point of failure. We have thre models: `UserModel`, `MessageModel`, and `DeletedMessageModel`. All models are managed using SQLAlchemy ORM. ORM objects are serialized and sent to followers.

### 3. Follower Initialization & Data Sync
When a new follower server starts, it must first synchronize its local state with the current leader to become a fully consistent replica of the leader. On receiving the request, the leader responds with a full database dump to sync state (initial replication). Followers deserialize the chat data in into own local SQL database. It also stores the current list of active followers for participation in future leader elections and replication.

### 4. Replication: Push-based Update Propagation
We use a push-based replication model to maintain consistency across all replicas.  Any state-changing operation (e.g. user creation, message sending, or account deletion) is placed into an update queue. A dedicated background thread monitors this queue and ensures that changes are immediately propagated to all followers. The leader then distributes these serialized updates to each follower via gRPC calls. Our design ensures that all followers are consistently updated in near real-time without data loss.

### 5. Session-Scoped Connections for Thread-Safety
We use `scoped_session` to ensure thread-safe database interactions for multi-threaded gRPC servers. Without proper session isolation, concurrent threads could interfere with each other’s database operations, leading to data corruption, stale reads, or transaction conflicts. By wrapping the session factory in `scoped_session`, each thread automatically gets its own dedicated database session, avoiding cross-thread interference.

### 6. Client Awareness & Failover Handling
We have designed the client so that it mains maintain a list of known server addresses so that they have awareness of multiple server addresses. This list is used to ensure continued service availability in the event of a leader crash. When a client initiates a connection, it attempts to communicate with the first server in its list (assumed to be the leader). If the leader is unreachable, the client rotates to the next server in its list and attempts reconnection. The client continues rotating until it reaches either a new leader that has been elected among the followers, or a previously unreachable but now-available original leader.