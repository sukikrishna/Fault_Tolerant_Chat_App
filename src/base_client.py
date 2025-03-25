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

    # def __call__(self, instance, *args, **kwargs):
    #     """Handles retry logic when a gRPC error occurs."""

    #     try:
    #         return self.method(instance, *args, **kwargs)
    #     except grpc.RpcError as e:
    #         if e.code() == grpc.StatusCode.UNAVAILABLE:
    #             print("Server is unavailable. Trying to reconnect...")
    #             instance.connect()
    #             return self.method(instance, *args, **kwargs)
    #         else:
    #             print("Error:", e)

    def __call__(self, instance, *args, **kwargs):
        """Handles retry logic when a gRPC error occurs."""

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                return self.method(instance, *args, **kwargs)
            except grpc.RpcError as e:
                if e.code() == grpc.StatusCode.UNAVAILABLE:
                    print(f"Server is unavailable (attempt {attempt+1}/{max_attempts}). Trying to reconnect...")
                    instance.connect()
                    if attempt == max_attempts - 1:
                        raise  # Re-raise on the last attempt
                else:
                    print(f"Error: {e}")
                    raise


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

    # def relogin(self):
    #     pass


    def relogin(self):
        """Attempts to maintain the user session when reconnecting to a new server."""
        if self.user_session_id and self.reconnect_with_session():
            print("Successfully reconnected with existing session")
            return True
        else:
            print("Session expired, please log in again")
            self.user_session_id = ""
            return False


    # def connect(self):
    #     """Tries to connect to the leader server and establish a gRPC stub. Falls back to other addresses if needed."""

    #     # breakpoint()
    #     with self.lock:
    #         # Check the connection using a simple request like ListUsers
    #         try:
    #             # Update this line to use ListUsersRequest instead of Empty
    #             response = self.stub.ListUsers(spec_pb2.ListUsersRequest(wildcard="*"))
    #             if response:
    #                 print("Connection is active")
    #                 return
    #         except (Exception, grpc.RpcError) as e:
    #             pass

    #         if len(self.addresses) == 0:
    #             print("No server is available.")
    #             return

    #         tried = set()
    #         retries = 0
    #         success = False
    #         while retries < self.max_retries:
    #             try:
    #                 print("Trying to connect to ", self.addresses[0])
    #                 self.channel = grpc.insecure_channel(self.addresses[0])
    #                 self.stub = spec_pb2_grpc.ClientAccountStub(self.channel)
    #                 response = self.stub.ListUsers(spec_pb2.ListUsersRequest(wildcard="*"))
    #                 if response:
    #                     success = True
    #                     print("Connected to the server")
    #                     break
    #             except grpc.RpcError as e:
    #                 if (e.code() == grpc.StatusCode.UNIMPLEMENTED):
    #                     # we are probably talking to a follower so move the address to the end
    #                     if (self.addresses[0] in tried):
    #                         # we have visted all the addresses and nodes are not responding
    #                         # so we can exit
    #                         self.exit_()
    #                         return

    #                     tried.add(self.addresses[0])
    #                     self.addresses.append(self.addresses.pop(0))
    #                     print("talking to a follower, moving to next address",
    #                         self.addresses)
    #                 else:
    #                     print(
    #                         f"Connection failed. Retrying in {self.retry_interval} seconds... Error: {e.code()}")
    #                     retries += 1
    #                 time.sleep(self.retry_interval)

    #         if not success:
    #             print("Failed to establish connection after maximum retries.")
    #             # if reachingout to the server multiple times doesn't get response
    #             # delete this address as it is usless
    #             # you want to relogin here, because session data isn't
    #             # replicated accross databases
    #             self.addresses.pop(0)
    #             # print(self.addresses)
    #             self.relogin()
    #             return
    #             # return self.connect()
    #         else:
    #             print(f"Connected to {self.addresses[0]}")
                
    #             # If we have a session ID, try to verify it's still valid
    #             if self.user_session_id:
    #                 try:
    #                     response = self.stub.GetUnreadCounts(
    #                         spec_pb2.SessionRequest(session_id=self.user_session_id)
    #                     )
    #                     # If we get an error about not being logged in, clear the session ID
    #                     if response.error_code == StatusCode.USER_NOT_LOGGED_IN:
    #                         print("Session expired on the new server")
    #                         self.user_session_id = ""
    #                     else:
    #                         print("Session successfully maintained after reconnection")
    #                 except Exception as e:
    #                     print(f"Error verifying session: {e}")
    #                     # If there's any error, we'll just leave the session ID as is
    #                     # and let subsequent calls determine if it's valid
    #                     pass


    def connect(self):
        """Tries to connect to the leader server and establish a gRPC stub. Falls back to other addresses if needed."""

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
            
            # Try all available addresses
            while len(tried) < len(self.addresses) and retries < self.max_retries:
                current_address = self.addresses[0]
                
                try:
                    print(f"Trying to connect to {current_address}")
                    self.channel = grpc.insecure_channel(current_address)
                    self.stub = spec_pb2_grpc.ClientAccountStub(self.channel)
                    response = self.stub.ListUsers(spec_pb2.ListUsersRequest(wildcard="*"))
                    
                    if response:
                        print(f"Connected to the server at {current_address}")
                        # Successfully connected, keep this address as the first one
                        return
                        
                except grpc.RpcError as e:
                    if e.code() == grpc.StatusCode.UNIMPLEMENTED:
                        # We're talking to a follower, move this address to the end
                        print(f"Address {current_address} is a follower, moving to next address")
                    else:
                        print(f"Connection to {current_address} failed: {e.code()}")
                        
                    # Mark this address as tried
                    tried.add(current_address)
                    
                    # Move this address to the end and try the next one
                    self.addresses.append(self.addresses.pop(0))
                    time.sleep(self.retry_interval)
                    
                except Exception as e:
                    print(f"Unexpected error connecting to {current_address}: {e}")
                    tried.add(current_address)
                    self.addresses.append(self.addresses.pop(0))
                    time.sleep(self.retry_interval)
                    
                retries += 1
                
                # If we've tried all addresses, reset and try again (up to max_retries)
                if len(tried) >= len(self.addresses):
                    if retries < self.max_retries:
                        print(f"Tried all addresses, retrying (attempt {retries}/{self.max_retries})")
                        tried = set()  # Reset tried set
                        time.sleep(self.retry_interval)
            
            # If we reach here, we couldn't connect to any server
            print("Failed to establish connection after trying all available servers.")
            
            if self.user_session_id:
                print("Attempting to relogin with existing session")
                self.relogin()


    def reconnect_with_session(self):
        """Attempts to reconnect while maintaining the same session."""
        if not self.user_session_id:
            return False
        
        # Try to connect to any available server
        self.connect()
        
        if not self.stub:
            return False
        
        # Verify if the session is still valid
        try:
            # Use a lightweight call to verify the session
            response = self.stub.GetUnreadCounts(
                spec_pb2.SessionRequest(session_id=self.user_session_id)
            )
            # If we don't get an error code for not logged in, session is valid
            return response.error_code != StatusCode.USER_NOT_LOGGED_IN
        except grpc.RpcError:
            return False


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
