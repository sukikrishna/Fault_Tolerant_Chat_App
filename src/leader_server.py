from concurrent import futures
import logging
import uuid
import queue

import grpc
import spec_pb2
import spec_pb2_grpc
from utils import StatusCode, StatusMessages

from models import UserModel, MessageModel, DeletedMessageModel, init_db, get_session_factory
from sqlalchemy.orm import scoped_session
from sqlalchemy import or_, and_
from google.protobuf.timestamp_pb2 import Timestamp

import pickle
from sqlalchemy.orm import sessionmaker
from sqlalchemy import inspect
import threading
import time
import queue
from follower_server import *
import fnmatch


import hashlib

def hash_password(password):
    """Hashes the given password using SHA-256.

    Args:
        password (str): The plain text password.

    Returns:
        str: The hashed password.
    """
    return hashlib.sha256(password.encode()).hexdigest()


class ClientService(spec_pb2_grpc.ClientAccountServicer):

    def __init__(self, db_session, update_queue):
        """Initializes the ClientService.

        Args:
            db_session (SessionFactory): SQLAlchemy session factory.
            update_queue (Queue): Queue to send update events to followers.
        """

        super().__init__()
        self.db_session = db_session
        self.update_queue = update_queue

    def CreateAccount(self, request, context):
        """Handles user account creation.

        Args:
            request (CreateAccountRequest): gRPC request with username and password.
            context (grpc.ServicerContext): gRPC context object.

        Returns:
            ServerResponse: Response indicating success or failure.
        """

        session = scoped_session(self.db_session)
        context.set_code(grpc.StatusCode.OK)

        user_exists = session.query(UserModel).filter_by(
            username=request.username).scalar()
        if user_exists:
            status_code = StatusCode.USER_NAME_EXISTS
            status_message = StatusMessages.get_error_message(status_code)
        else:
            # create a new user
            hashed_password = hash_password(request.password)
            new_user = UserModel(username=request.username, password=hashed_password)
            # new_user = UserModel(username=request.username,
            #                      password=request.password)
            session.add(new_user)
            session.commit()
            status_code = StatusCode.SUCCESS
            status_message = "Account created successfully!!"

            # get added user
            added_user = session.query(UserModel).filter_by(
                username=request.username).first()

            update_info = pickle.dumps(('users', 'add', added_user))
            # create_update_info("add", added_user, 'users')

            self.update_queue.put(update_info)

        session.remove()
        return spec_pb2.ServerResponse(error_code=status_code, error_message=status_message)

    def Login(self, request, context):
        """Handles user login and session ID generation.

        Args:
            request (LoginRequest): gRPC request with username and password.
            context (grpc.ServicerContext): gRPC context object.

        Returns:
            ServerResponse: Includes session ID if login is successful.
        """

        context.set_code(grpc.StatusCode.OK)
        session = scoped_session(self.db_session)
        user = session.query(UserModel).filter_by(
            username=request.username).first()

        session_id = None
        if user is None:
            status_code = StatusCode.USER_DOESNT_EXIST
            status_message = StatusMessages.get_error_message(status_code)
        else:
            if user.password != hash_password(request.password):
                status_code = StatusCode.INCORRECT_PASSWORD
                status_message = StatusMessages.get_error_message(status_code)
            else:
                session_id = self.GenerateSessionID()
                user.logged_in = True
                user.session_id = session_id
                session.commit()

                status_code = StatusCode.SUCCESS
                status_message = "Login successful!!"
                session_id = session_id

        return spec_pb2.ServerResponse(error_code=status_code, error_message=status_message, session_id=session_id)

    def Send(self, request, context):
        """Handles sending a message from one user to another.

        Args:
            request (SendRequest): gRPC request with message details.
            context (grpc.ServicerContext): gRPC context object.

        Returns:
            ServerResponse: Indicates whether the message was sent successfully.
        """

        context.set_code(grpc.StatusCode.OK)

        session_id = request.session_id
        session = scoped_session(self.db_session)
        user = session.query(UserModel).filter_by(
            session_id=session_id).first()

        if user is None:
            status_code = StatusCode.USER_NOT_LOGGED_IN
            status_message = StatusMessages.get_error_message(status_code)
        else:
            receiver = session.query(UserModel).filter_by(
                username=request.to).first()

            if receiver is None:
                status_code = StatusCode.RECEIVER_DOESNT_EXIST
                status_message = StatusMessages.get_error_message(status_code)
            else:
                msg = MessageModel(
                    sender_id=user.id,
                    receiver_id=receiver.id,
                    content=request.message
                )
                session.add(msg)
                session.commit()

                status_code = StatusCode.SUCCESS
                status_message = "Message sent successfully!!"
                # breakpoint()
                # get added message
                msg2 = session.query(MessageModel).filter_by(
                    id=msg.id).first()

                # print("before updating followers")
                update_info = pickle.dumps(('messages', "add", msg2))
                # print(update_info)
                try:
                    self.update_queue.put(update_info)
                except Exception as e:
                    print(e)
        # Remove any remaining session
        session.remove()
        # print("responding with server response")
        return spec_pb2.ServerResponse(error_code=status_code, error_message=status_message)

    # def ListUsers(self, request, context):
    #     context.set_code(grpc.StatusCode.OK)
    #     users = spec_pb2.Users()

    #     session = scoped_session(self.db_session)
    #     all_users = session.query(UserModel).all()

    #     for user in all_users:
    #         user_ = users.user.add()
    #         user_.username = user.username
    #         user_.status = "online" if user.logged_in else "offline"

    #     # Remove any remaining session
    #     session.remove()

    #     return users

    def ListUsers(self, request, context):
        """Returns a list of users matching the optional wildcard.

        Args:
            request (ListUsersRequest): Request with optional wildcard filter.
            context (grpc.ServicerContext): gRPC context object.

        Returns:
            Users: A list of users and their online statuses.
        """

        context.set_code(grpc.StatusCode.OK)
        users = spec_pb2.Users()
        pattern = request.wildcard if request.wildcard else "*"

        session = scoped_session(self.db_session)
        all_users = session.query(UserModel).all()

        for user in all_users:
            if fnmatch.fnmatch(user.username.lower(), pattern.lower()):
                user_ = users.user.add()
                user_.username = user.username
                user_.status = "online" if user.logged_in else "offline"

        session.remove()
        return users
    
    
    def DeleteMessages(self, request, context):
        """Deletes specific messages and moves them to the deleted table.

        Args:
            request (DeleteMessagesRequest): Request with message IDs and session ID.
            context (grpc.ServicerContext): gRPC context object.

        Returns:
            ServerResponse: Indicates success or failure.
        """

        session = scoped_session(self.db_session)
        user = session.query(UserModel).filter_by(session_id=request.session_id).first()

        if not user:
            status_code = StatusCode.USER_NOT_LOGGED_IN
            status_message = StatusMessages.get_error_message(status_code)
        else:
            try:
                messages_to_delete = session.query(MessageModel).filter(
                    MessageModel.id.in_(request.message_ids),
                    or_(
                        MessageModel.sender_id == user.id,
                        MessageModel.receiver_id == user.id
                    )
                ).all()

                for message in messages_to_delete:
                    # move to deleted messages table
                    deleted = DeletedMessageModel(
                        sender_id=message.sender_id,
                        receiver_id=message.receiver_id,
                        content=message.content,
                        is_received=message.is_received,
                        original_message_id=message.id
                    )
                    session.add(deleted)
                    session.delete(message)

                    # propagate deletion to followers
                    update_info = pickle.dumps(('messages', 'delete', message))
                    self.update_queue.put(update_info)

                session.commit()
                status_code = StatusCode.SUCCESS
                status_message = f"{len(messages_to_delete)} message(s) deleted successfully."

            except Exception as e:
                session.rollback()
                status_code = StatusCode.INVALID_ARGUMENTS
                status_message = str(e)

        session.remove()
        return spec_pb2.ServerResponse(error_code=status_code, error_message=status_message)


    def GetMessages(self, request, context):
        """Fetches unread messages for the logged-in user.

        Args:
            request (ReceiveRequest): Request with session ID.
            context (grpc.ServicerContext): gRPC context object.

        Returns:
            Messages: List of unread messages.
        """

        context.set_code(grpc.StatusCode.OK)

        msgs = spec_pb2.Messages()

        session = scoped_session(self.db_session)
        user = session.query(UserModel).filter_by(
            session_id=request.session_id).first()

        if not user:
            msgs.error_code = StatusCode.USER_NOT_LOGGED_IN
            msgs.error_message = StatusMessages.get_error_message(
                msgs.error_code)
        else:

            messages = session.query(MessageModel).filter(
                and_(MessageModel.receiver_id == user.id, MessageModel.is_received == False)).all()

            if len(messages) == 0:
                msgs.error_code = StatusCode.NO_MESSAGES
                msgs.error_message = StatusMessages.get_error_message(
                    msgs.error_code)
            else:
                for message in messages:
                    # print(message.is_received)
                    msg = msgs.message.add()
                    msg.from_ = message.sender.username
                    msg.message = message.content
                    msg.message_id = message.id
                    message.is_received = True

                session.commit()
                msgs.error_code = StatusCode.SUCCESS
                msgs.error_message = "Messages received successfully!!"

        session.remove()

        return msgs

    def AcknowledgeReceivedMessages(self, request, context):
        """Marks messages as received by their IDs.

        Args:
            request (AcknowledgeReceivedMessagesRequest): Message IDs to mark.
            context (grpc.ServicerContext): gRPC context object.

        Returns:
            ServerResponse: Acknowledgement result.
        """

        session = scoped_session(self.db_session)
        user = session.query(UserModel).filter_by(
            session_id=request.session_id).first()

        if user is None:
            status_code = StatusCode.USER_NOT_LOGGED_IN
            status_message = StatusMessages.get_error_message(status_code)
        else:
            messages = session.query(MessageModel).filter(
                MessageModel.id.in_(request.message_ids),
                MessageModel.receiver_id == user.id
            ).all()

            for message in messages:
                message.is_received = True

                # stop deleting messages
                # Move the message to the deleted_messages table
                # deleted_message = DeletedMessageModel(
                #     sender_id=message.sender_id,
                #     receiver_id=message.receiver_id,
                #     content=message.content,
                #     is_received=message.is_received,
                #     original_message_id=message.id,
                # )
                # session.add(deleted_message)
                # session.delete(message)

            session.commit()
            status_code = StatusCode.SUCCESS
            status_message = "Messages acknowledged successfully!!"

        session.remove()

        return spec_pb2.ServerResponse(error_code=status_code, error_message=status_message)

    def Logout(self, request, context):
        """Logs out the current user.

        Args:
            request (DeleteAccountRequest): Request with session ID.
            context (grpc.ServicerContext): gRPC context object.

        Returns:
            ServerResponse: Logout result.
        """

        session = scoped_session(self.db_session)
        user = session.query(UserModel).filter_by(
            session_id=request.session_id).first()

        if user is None:
            status = StatusCode.USER_NOT_LOGGED_IN
            status_message = StatusMessages.get_error_message(status)
        else:
            user.session_id = None
            user.logged_in = False
            session.commit()
            status = StatusCode.SUCCESS
            status_message = "Logout successful!!"

        session.remove()

        return spec_pb2.ServerResponse(error_code=status, error_message=status_message)

    def GetChat(self, request, context):
        """Returns full chat history between current user and another user.

        Args:
            request (ChatRequest): Includes session ID and target username.
            context (grpc.ServicerContext): gRPC context object.

        Returns:
            Messages: List of messages with timestamps.
        """

        context.set_code(grpc.StatusCode.OK)

        msgs = spec_pb2.Messages()

        session = scoped_session(self.db_session)
        user = session.query(UserModel).filter_by(
            session_id=request.session_id).first()

        if user is None:
            msgs.error_code = StatusCode.USER_NOT_LOGGED_IN
            msgs.error_message = StatusMessages.get_error_message(
                msgs.error_code)
        else:
            receiver = session.query(UserModel).filter_by(
                username=request.username).first()

            messages = session.query(MessageModel).filter(
                or_(
                    and_(MessageModel.sender_id == user.id,
                         MessageModel.receiver_id == receiver.id),
                    and_(MessageModel.sender_id == receiver.id,
                         MessageModel.receiver_id == user.id)
                )
            ).order_by(MessageModel.time_stamp).all()

            if len(messages) == 0:
                msgs.error_code = StatusCode.NO_MESSAGES
                msgs.error_message = StatusMessages.get_error_message(
                    msgs.error_code)
            else:
                for message in messages:
                    msg = msgs.message.add()
                    msg.from_ = message.sender.username
                    msg.message = message.content
                    msg.message_id = message.id
                    # print(message.time_stamp)
                    timestamp_proto = Timestamp()
                    # print(timestamp_proto)
                    timestamp_proto.FromDatetime(message.time_stamp)
                    msg.time_stamp.CopyFrom(timestamp_proto)
                    if (message.receiver_id == user.id):
                        message.is_received = True

                session.commit()
                msgs.error_code = StatusCode.SUCCESS
                msgs.error_message = "Messages received successfully!!"

        session.remove()

        return msgs
    

    def GetUnreadCounts(self, request, context):
        """Returns unread message count per sender without marking them as read."""
        from spec_pb2 import UnreadSummary, UnreadCount

        summary = UnreadSummary()
        session = scoped_session(self.db_session)

        user = session.query(UserModel).filter_by(session_id=request.session_id).first()
        if not user:
            summary.error_code = StatusCode.USER_NOT_LOGGED_IN
            summary.error_message = StatusMessages.get_error_message(summary.error_code)
            session.remove()
            return summary

        from sqlalchemy import func
        results = session.query(
            UserModel.username,
            func.count(MessageModel.id)
        ).join(UserModel, UserModel.id == MessageModel.sender_id
        ).filter(
            MessageModel.receiver_id == user.id,
            MessageModel.sender_id != user.id,  # exclude self-messages
            MessageModel.is_received == False
        ).group_by(UserModel.username).all()


        for sender, count in results:
            summary.counts.append(UnreadCount(**{"from": sender, "count": count}))

        summary.error_code = StatusCode.SUCCESS
        summary.error_message = "Unread counts fetched."
        session.remove()
        return summary


    def DeleteAccount(self, request, context):
        """Deletes the current user's account and related messages.

        Args:
            request (DeleteAccountRequest): Request with session ID.
            context (grpc.ServicerContext): gRPC context object.

        Returns:
            ServerResponse: Result of the deletion.
        """

        session = scoped_session(self.db_session)
        user = session.query(UserModel).filter_by(
            session_id=request.session_id).first()

        if user is None:
            status_code = StatusCode.USER_NOT_LOGGED_IN
            status_message = StatusMessages.get_error_message(status_code)
        else:
            # Move user's messages to deleted_messages table
            messages_to_delete = session.query(MessageModel).filter(
                MessageModel.receiver_id == user.id
            ).all()

            for message in messages_to_delete:
                deleted_message = DeletedMessageModel(
                    sender_id=message.sender_id,
                    receiver_id=message.receiver_id,
                    content=message.content,
                    is_received=message.is_received,
                    original_message_id=message.id,
                )
                session.add(deleted_message)
                session.delete(message)

            # Delete user
            session.delete(user)
            session.commit()

            status_code = StatusCode.SUCCESS
            status_message = "Account deleted successfully!!"

        session.remove()

        return spec_pb2.ServerResponse(error_code=status_code, error_message=status_message)

    @staticmethod
    def GenerateSessionID():
        """Generates a new unique session ID.

        Returns:
            str: A UUID-based session string.
        """

        return str(uuid.uuid4())


def fetch_all_data_from_orm(connection):
    """Fetches all ORM table data into a dictionary.

    Args:
        connection (sqlalchemy.engine.Connection): Database connection.

    Returns:
        dict: A mapping of table names to ORM objects.
    """
    data = {}
    Session = sessionmaker(bind=connection)
    session = Session()

    # Get the list of classes defined in your ORM
    # Replace with your actual ORM classes
    orm_classes = [UserModel, MessageModel, DeletedMessageModel]

    for orm_class in orm_classes:
        table_name = orm_class.__tablename__
        table_data = session.query(orm_class).all()
        data[table_name] = table_data

    session.close()
    return data


class LeaderService(spec_pb2_grpc.LeaderServiceServicer):
    def __init__(self, states, db_engine):
        """Initializes the leader service with server state and DB engine.

        Args:
            states (dict): Shared leader state dictionary.
            db_engine (Engine): SQLAlchemy database engine.
        """

        super().__init__()
        self.states = states
        self.db_engine = db_engine

    def RegisterFollower(self, request, context):
        """Registers a follower and returns the current database snapshot.

        Args:
            request (RegisterFollowerRequest): Follower ID and address.
            context (grpc.ServicerContext): gRPC context.

        Returns:
            RegisterFollowerResponse: Serialized DB and known followers.
        """

        follower_id = request.follower_id
        follower_address = request.follower_address
        if (follower_id, follower_address) not in self.states['followers']:
            self.states['followers'].append((follower_id, follower_address))
        # print(self.states)

        # Fetch and pickle the data from ORM objects
        with self.db_engine.begin() as connection:
            # Implement this function to fetch data from ORM objects
            data = fetch_all_data_from_orm(connection)
            pickled_data = pickle.dumps(data)

        other_followers = [
            f"{follower[0]}-{follower[1]}" for follower in self.states['followers'] if follower[0] != follower_id]
        # print(other_followers)
        # inform other followers about this new follower
        for follower in other_followers:
            saddress = follower.split("-")[1]
            # print(follower, saddress)
            with grpc.insecure_channel(saddress) as channel:
                stub = spec_pb2_grpc.FollowerServiceStub(channel)
                # print(channel, stub)
                stub.UpdateFollowers(spec_pb2.UpdateFollowersRequest(
                    update_data=pickle.dumps((follower_id, follower_address))
                ))

        response = spec_pb2.RegisterFollowerResponse(
            error_code=0,
            error_message="",
            pickled_db=pickled_data,
            other_followers=other_followers
        )
        # print("Follower {} registered {} resp {}".format(follower_id, request.follower_address, response))

        return response

    def HeartBeat(self, request, context):
        """Responds to heartbeat checks from followers.

        Args:
            request (Empty): Empty message.
            context (grpc.ServicerContext): gRPC context.

        Returns:
            Ack: Acknowledgment response.
        """

        return spec_pb2.Ack(error_code=0, error_message="")

    def CheckLeader(self, request, context):
        """Confirms that this node is the current leader.

        Args:
            request (Empty): Empty message.
            context (grpc.ServicerContext): gRPC context.

        Returns:
            Ack: Acknowledgment response.
        """

        return spec_pb2.Ack(error_code=0, error_message="")


table_class_mapping = {
    'users': UserModel,
    'messages': MessageModel,
    'deleted_messages': DeletedMessageModel
}


def serve_leader_client(leader_state):
    """Starts the gRPC server for handling client requests.

    Args:
        leader_state (dict): Dictionary containing leader server state.

    Returns:
        grpc.Server: The gRPC server object.
    """
    db_session, address, update_queue, client_address = leader_state['db_session'], leader_state[
        'leader_address'], leader_state['update_queue'], leader_state['client_address']
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    spec_pb2_grpc.add_ClientAccountServicer_to_server(
        ClientService(db_session=db_session, update_queue=update_queue), server)
    server.add_insecure_port(client_address)
    server.start()
    print("Client server started, listening on " + client_address)
    return server

# internal channel for leader to communicate with follower


def serve_leader_follower(leader_state):
    """Starts the gRPC server for inter-leader/follower communication.

    Args:
        leader_state (dict): Dictionary containing leader server state.

    Returns:
        grpc.Server: The gRPC server object.
    """
    address, db_engine = leader_state['leader_address'], leader_state['db_engine']

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=20))
    spec_pb2_grpc.add_LeaderServiceServicer_to_server(
        LeaderService(leader_state, db_engine=db_engine), server)
    server.add_insecure_port(address)
    server.start()
    print("Leader server started, listening on " + address)
    return server


def get_update_data(update_queue):
    """Fetches the next item from the update queue, if available.

    Args:
        update_queue (queue.Queue): The update queue.

    Returns:
        Any: The next update item or None if the queue is empty.
    """
    try:
        data = update_queue.get(block=False)
        return data
    except queue.Empty:
        return None


def update_followers(leader_state):
    """Continuously sends updates from the queue to all followers.

    Args:
        leader_state (dict): Dictionary containing leader server state.
    """

    time.sleep(5)

    while True:
        follower_addresses = leader_state['followers']
        update_queue = leader_state['update_queue']

        # Fetch the update data here
        update_data = get_update_data(update_queue)

        if update_data is not None:
            # Iterate through each follower and send updates
            for _, follower_address in follower_addresses:
                try:
                    # print(follower_address)
                    with grpc.insecure_channel(follower_address) as channel:
                        stub = spec_pb2_grpc.FollowerServiceStub(channel)
                        accept_updates_request = spec_pb2.AcceptUpdatesRequest(
                            update_data=update_data)
                        response = stub.AcceptUpdates(accept_updates_request)
                except Exception as e:
                    print("Error while sending updates to follower: " + str(e))
        time.sleep(2)
