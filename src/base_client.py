import grpc
import threading
import time
import spec_pb2_grpc
import spec_pb2
import functools


class reconnect_on_error:
    """Decorator to automatically reconnect and retry gRPC calls if the server is unavailable."""

    def __init__(self, method):
        self.method = method

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return functools.partial(self.__call__, instance)

    def __call__(self, instance, *args, **kwargs):
        """Handles retry logic when a gRPC error occurs."""

        try:
            return self.method(instance, *args, **kwargs)
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                print("Server is unavailable. Trying to reconnect...")
                instance.connect()
                return self.method(instance, *args, **kwargs)
            else:
                print("Error:", e)


class ChatClientBase:
    def __init__(self, addresses, max_retries=2, retry_interval=1):
        self.user_session_id = ""
        self.addresses = addresses
        self.max_retries = max_retries
        self.retry_interval = retry_interval
        self.channel = None
        self.stub = None
        self.lock = threading.Lock()
        self.connect()

    def exit_(self):
        pass

    def relogin(self):
        pass

    def connect(self):
        """Tries to connect to the leader server and establish a gRPC stub. Falls back to other addresses if needed."""

        # breakpoint()
        with self.lock:
            # Check the connection using a simple request like ListUsers
            try:
                # Update this line to use ListUsersRequest instead of Empty
                response = self.stub.ListUsers(spec_pb2.ListUsersRequest(wildcard="*"))
                if response:
                    print("Connection is active")
                    return
            except (Exception, grpc.RpcError) as e:
                pass

            if len(self.addresses) == 0:
                print("No server is available.")
                return

            tried = set()
            retries = 0
            success = False
            while retries < self.max_retries:
                try:
                    print("Trying to connect to ", self.addresses[0])
                    self.channel = grpc.insecure_channel(self.addresses[0])
                    self.stub = spec_pb2_grpc.ClientAccountStub(self.channel)
                    response = self.stub.ListUsers(spec_pb2.Empty())
                    if response:
                        success = True
                        print("Connected to the server")
                        break
                except grpc.RpcError as e:
                    if (e.code() == grpc.StatusCode.UNIMPLEMENTED):
                        # we are probably talking to a follower so move the address to the end
                        if (self.addresses[0] in tried):
                            # we have visted all the addresses and nodes are not responding
                            # so we can exit
                            self.exit_()
                            return

                        tried.add(self.addresses[0])
                        self.addresses.append(self.addresses.pop(0))
                        print("talking to a follower, moving to next address",
                              self.addresses)
                    else:
                        print(
                            f"Connection failed. Retrying in {self.retry_interval} seconds... Error: {e.code()}")
                        retries += 1
                    time.sleep(self.retry_interval)

        if not success:
            print("Failed to establish connection after maximum retries.")
            # if reachingout to the server multiple times doesn't get response
            # delete this address as it is usless
            # you want to relogin here, because session data isn't
            # replicated accross databases
            self.addresses.pop(0)
            # print(self.addresses)
            self.relogin()
            return
            # return self.connect()
        else:
            print(f"Connected to {self.addresses[0]}")

    # @reconnect_on_error
    # def list_users(self):
    #     response = self.stub.ListUsers(spec_pb2.Empty())
    #     return response.user

    @reconnect_on_error
    def list_users(self, wildcard="*"):
        """Fetches a list of users matching the given wildcard.

        Args:
            wildcard (str): Username pattern. Defaults to "*".

        Returns:
            List[User]: A list of user objects.
        """

        request = spec_pb2.ListUsersRequest(wildcard=wildcard)
        response = self.stub.ListUsers(request)
        return response.user


    @reconnect_on_error
    def create_account(self, username, password):
        """Creates a new user account.

        Args:
            username (str): Desired username.
            password (str): Desired password.

        Returns:
            ServerResponse: gRPC server response.
        """

        response = self.stub.CreateAccount(
            spec_pb2.CreateAccountRequest(username=username, password=password))
        return response

    @reconnect_on_error
    def login(self, username, password):
        """Logs the user in and retrieves a session ID.

        Args:
            username (str): Account username.
            password (str): Account password.

        Returns:
            ServerResponse: gRPC server response.
        """

        response = self.stub.Login(
            spec_pb2.LoginRequest(username=username, password=password))
        return response

    @reconnect_on_error
    def send_message(self, to, message):
        """Sends a message to another user.

        Args:
            to (str): Recipient username.
            message (str): Message content.

        Returns:
            ServerResponse: gRPC server response.
        """

        response = self.stub.Send(
            spec_pb2.SendRequest(session_id=self.user_session_id, message=message, to=to))
        return response

    @reconnect_on_error
    def logout(self):
        """Logs out the current user session.

        Returns:
            ServerResponse: gRPC server response.
        """

        response = self.stub.Logout(
            spec_pb2.DeleteAccountRequest(session_id=self.user_session_id))
        return response

    @reconnect_on_error
    def delete_account(self):
        """Deletes the currently logged-in user's account.

        Returns:
            ServerResponse: gRPC server response.
        """

        response = self.stub.DeleteAccount(
            spec_pb2.DeleteAccountRequest(session_id=self.user_session_id))
        return response

    @reconnect_on_error
    def receive_messages(self):
        """Retrieves unread messages for the logged-in user.

        Returns:
            Messages: A message list from the server.
        """

        msgs = self.stub.GetMessages(
            spec_pb2.ReceiveRequest(session_id=self.user_session_id))
        return msgs

    @reconnect_on_error
    def acknowledge_received_messages(self, message_ids):
        """Acknowledges messages as received so they won't be returned again.

        Args:
            message_ids (List[int]): List of message IDs.

        Returns:
            ServerResponse: gRPC server response.
        """

        ack_response = self.stub.AcknowledgeReceivedMessages(
            spec_pb2.AcknowledgeRequest(session_id=self.user_session_id, message_ids=message_ids))
        return ack_response

    @reconnect_on_error
    def get_chat(self, recipient):
        """Retrieves full chat history with a specific user.

        Args:
            recipient (str): Username of the chat partner.

        Returns:
            Messages: A list of all messages between the two users.
        """

        msgs = self.stub.GetChat(
            spec_pb2.ChatRequest(session_id=self.user_session_id, username=recipient))
        return msgs
    
    @reconnect_on_error
    def delete_messages(self, message_ids):
        """Deletes specific messages by ID.

        Args:
            message_ids (List[int]): List of message IDs to delete.

        Returns:
            ServerResponse: gRPC server response.
        """

        request = spec_pb2.DeleteMessagesRequest(
            session_id=self.user_session_id,
            message_ids=message_ids
        )
        response = self.stub.DeleteMessages(request)
        return response
    
    @reconnect_on_error
    def get_unread_counts(self):
        """Fetches count of unread messages grouped by sender."""
        response = self.stub.GetUnreadCounts(
            spec_pb2.SessionRequest(session_id=self.user_session_id)
        )
        return response
