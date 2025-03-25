# import sys
# import os
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from concurrent import futures
import grpc
import spec_pb2
import spec_pb2_grpc

# from src.message_frame import StatusCode, StatusMessages

from models import UserModel, MessageModel, DeletedMessageModel, init_db, get_session_factory
from sqlalchemy.orm import scoped_session
from sqlalchemy import inspect

import pickle
import queue

table_class_mapping = {
    'users': UserModel,
    'messages': MessageModel,
    'deleted_messages': DeletedMessageModel
}


class FollowerService(spec_pb2_grpc.FollowerServiceServicer):
    def __init__(self, db_session, leader_address, state):
        """Initializes the follower's internal service.

        Args:
            db_session (SessionFactory): SQLAlchemy session factory.
            leader_address (str): Address of the current leader.
            state (dict): Shared follower state.
        """

        self.db_session = db_session
        self.leader_address = leader_address
        self.state = state
        # print("Follower service initialized")

    def AcceptUpdates(self, request, context):
        """Applies state updates from the leader.

        Args:
            request (AcceptUpdatesRequest): Pickled update data.
            context (grpc.ServicerContext): gRPC context.

        Returns:
            ServerResponse: Acknowledgment response.
        """

        update_data = request.update_data
        self.process_update_data(update_data)

        response = spec_pb2.ServerResponse(
            error_code=0,
            error_message=""
        )
        return response

    def process_update_data(self, update_data):
        """Deserializes and applies an update to the local database.

        Args:
            update_data (bytes): Pickled (table, action, object) tuple.
        """
        # Add your implementation for processing the update_data
        session = scoped_session(self.db_session)

        try:
            data = pickle.loads(update_data)
            # update the followers list
            table, action, obj = data

            # Copy attributes without accessing them through SQLAlchemy's descriptors
            # This avoids the detached instance error
            obj_dict = {}
            for c in inspect(obj.__class__).mapper.column_attrs:
                # Access the raw dictionary underlying the object to avoid triggering lazy loading
                if c.key in obj.__dict__:
                    obj_dict[c.key] = obj.__dict__[c.key]
                else:
                    # For any attributes not in __dict__, use a safer approach
                    try:
                        obj_dict[c.key] = getattr(obj, c.key)
                    except Exception:
                        # If attribute access fails, use a default value or skip
                        obj_dict[c.key] = None

            # Recreate the object from the data
            new_obj = table_class_mapping[table]()
            for key, value in obj_dict.items():
                setattr(new_obj, key, value)

            if action == 'add':
                session.add(new_obj)
            elif action == 'delete':
                existing = session.query(table_class_mapping[table]).get(new_obj.id)
                if existing:
                    session.delete(existing)
            elif action == 'update':
                # For updates, use merge which handles detached instances better
                session.merge(new_obj)

            session.commit()

            # If this was a user update with session information, ensure we keep it
            if action == 'update' and table == 'users':
                existing = session.query(table_class_mapping[table]).get(new_obj.id)
                if existing and hasattr(new_obj, 'session_id') and new_obj.session_id:
                    existing.session_id = new_obj.session_id
                    existing.logged_in = True
                    session.commit()
        
        except Exception as e:
            print(f"Error processing update: {e}")
            session.rollback()
        finally:
            session.remove()

    def UpdateLeader(self, request, context):
        """Updates the leader address and re-syncs the database.

        Args:
            request (NewLeaderRequest): Contains new leader info.
            context (grpc.ServicerContext): gRPC context.

        Returns:
            Ack: Acknowledgment response.
        """

        # print("UPDATING leader", flush=True)
        leader_address, leader_id = request.new_leader_address, request.new_leader_id
        # print('new leader', leader_address, leader_id, flush=True)
        assign_new_leader(self.state, leader_address, leader_id)
        return spec_pb2.Ack(error_code=0, error_message="")

    def UpdateFollowers(self, request, context):
        """Adds a new follower to the internal list.

        Args:
            request (UpdateFollowersRequest): Pickled follower info.
            context (grpc.ServicerContext): gRPC context.

        Returns:
            Ack: Acknowledgment response.
        """

        # print("Updating followers for follower")
        new_follower = pickle.loads(request.update_data)
        # remove the current follower from the list
        self.state['followers'].append(new_follower)
        # print(new_follower, self.state['followers'])
        return spec_pb2.Ack(error_code=0, error_message="")


def request_update(follower_state):
    """Registers this follower with the leader and syncs local DB.

    Args:
        follower_state (dict): Shared follower state dictionary.
    """

    leader_address, server_id, internal_address, db_session = follower_state[
        'leader_address'], follower_state['follower_id'], follower_state['follower_address'], follower_state['db_session']

    with grpc.insecure_channel(leader_address) as channel:
        stub = spec_pb2_grpc.LeaderServiceStub(channel)
        register_follower_request = spec_pb2.RegisterFollowerRequest(
            follower_id=server_id, follower_address=internal_address)
        response = stub.RegisterFollower(register_follower_request)
        leader_db = pickle.loads(response.pickled_db)

        # update database with the leader data
        session = scoped_session(db_session)
        try:
            for table_name, records in leader_db.items():
                for record in records:
                    # print("record", record, type(record), record.username)

                    from sqlalchemy import inspect

                    def object_as_dict(obj_):
                        """Converts a SQLAlchemy model instance to a dictionary.

                        Args:
                            obj_ (Base): SQLAlchemy model instance.

                        Returns:
                            dict: Dictionary of column names and values.
                        """
                        return {c.key: obj_.__dict__.get(c.key) for c in inspect(obj_).mapper.column_attrs}

                    new_record = table_class_mapping[table_name](
                        **object_as_dict(record)
                    )
                    session.add(new_record)

            # Commit the transaction
            session.commit()
        except Exception as e:
            print("Error occurred:", e)
            session.rollback()
        finally:
            session.remove()  # Replace session.close() with session.remove()
        follower_state['followers'] = list(
            set([tuple(follower.split('-')) for follower in response.other_followers]))


def assign_new_leader(state, leader_address, leader_id):
    """Accepts a new leader and resets local state.

    Args:
        state (dict): Shared follower state.
        leader_address (str): New leader's address.
        leader_id (str): New leader's ID.
    """

    print("Accepting new leader")
    state['leader_address'] = leader_address
    # this is only required for windows that has file lockers
    # print('db_eninge in ', 'db_engine' in state)
    if 'db_engine' in state:
        try:
            state['db_engine'].dispose()
        except Exception as e:
            print('deleting engine', e)
    database_engine = init_db(state['database_url'], drop_tables=True)
    SessionFactory = get_session_factory(database_engine)
    state['database_engine'] = database_engine
    state['db_session'] = SessionFactory

    follower_server = server_follower_leader(state)

    state['follower_leader_server'] = follower_server
    # send message to the leaders registe method
    request_update(state)

    # remove leader from the list of followers
    try:
        state['followers'].remove((leader_address, leader_id))
    except:
        pass

    print('Assigning new leader complete')


# class ClientServiceFollower(spec_pb2_grpc.ClientAccountServicer):
#     pass

class ClientServiceFollower(spec_pb2_grpc.ClientAccountServicer):
    def __init__(self, leader_address):
        """Initializes the follower-side client service stub that forwards to leader.

        Args:
            leader_address (str): Address of the current leader server.
        """
        self.leader_address = leader_address

    def __getattr__(self, name):
        """Overrides attribute access to raise unimplemented error for all RPC methods.

        Args:
            name (str): Method name being accessed.

        Returns:
            Callable: A dummy method that raises UNIMPLEMENTED error.
        """
        # Forward all method calls to the leader
        def method(*args, **kwargs):
            raise grpc.RpcError(grpc.StatusCode.UNIMPLEMENTED, "This method is not available on follower.")
        return method


def serve_follower_client(follower_state):
    """Starts the follower’s gRPC server for clients.

    Args:
        follower_state (dict): Shared follower state.

    Returns:
        grpc.Server: The gRPC server object.
    """

    db_session, address, leader_address, client_address = follower_state['db_session'], follower_state[
        'follower_address'], follower_state['leader_address'], follower_state['client_address']

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    spec_pb2_grpc.add_ClientAccountServicer_to_server(
        ClientServiceFollower(leader_address=leader_address), server)
    server.add_insecure_port(client_address)
    server.start()
    print("Client server started, listening on ", client_address)
    return server


def server_follower_leader(follower_state):
    """Starts the internal gRPC server for leader-follower updates.

    Args:
        follower_state (dict): Shared follower state.

    Returns:
        grpc.Server: The gRPC server object.
    """

    db_session, leader_address, address, followers = follower_state['db_session'], follower_state[
        'leader_address'], follower_state['follower_address'], follower_state['followers']

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    spec_pb2_grpc.add_FollowerServiceServicer_to_server(
        FollowerService(db_session=db_session, leader_address=leader_address, state=follower_state), server)

    server.add_insecure_port(address)
    server.start()
    print("Follower server started, listening on " + address)
    return server
