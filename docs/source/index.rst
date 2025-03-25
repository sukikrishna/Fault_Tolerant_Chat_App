.. Distributed Chat App with Replication and Persistance documentation master file, created by
   sphinx-quickstart on Tue Mar 25 17:28:54 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Distributed Chat App with Replication and Persistance documentation
===================================================================

This project is a persistant, fault-tolerant chat system designed to operate in a distributed environment. It uses gRPC and Protocol Buffers for fast and structured communication between services, and supports both GUI-based (Tkinter) and terminal-based clients. Users can create accounts, log in, send/receive/delete messages, and interact with a searchable list of users.

The system follows a leader-follower replication model where one server starts as the leader, handling all write operations and syncing updates to followers. Followers register themselves with the leader and regularly ping it using heartbeat RPCs. If the leader fails, the follower with the lowest server ID is promoted to leader through an election mechanism, and all other followers reconfigure themselves accordingly. This ensures continuous availability and consistency even during sever or network failures.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   modules