import tkinter as tk
import threading
import time
from tkinter import ttk, scrolledtext, simpledialog
from base_client import ChatClientBase
import tkinter.messagebox as messagebox
from ttkthemes import ThemedStyle
import signal
import argparse
import spec_pb2

from message_frame import MessageFrame


class ChatClientGUI(tk.Tk, ChatClientBase):
    """
    A Tkinter-based graphical chat client that communicates with a distributed gRPC server.

    This class extends both the Tkinter main window (`tk.Tk`) and the gRPC base client (`ChatClientBase`).
    It provides a full GUI interface for user login, account creation, message sending,
    unread message notifications, message deletion, and session handling across multiple servers.

    Attributes:
        addresses (List[str]): List of gRPC server addresses for leader-follower failover support.
        user_session_id (str): Session token assigned by the server upon login.
        is_search_active (bool): Tracks whether the user search box is actively being used.
    """
    def __init__(self, addresses):
        """
        Initializes the GUI chat client and sets up the interface and background threads.

        This constructor initializes both the Tkinter GUI and the base gRPC chat client.
        It establishes a connection to one of the provided server addresses, sets up the
        main window layout, and starts background threads for periodically updating the
        user list, chat window, and unread message notifications.

        Args:
            addresses (List[str]): List of gRPC server addresses, with the leader expected
                                   to be the first address in the list.
        """
        tk.Tk.__init__(self)
        ChatClientBase.__init__(self, addresses)

        self.is_search_active = False

        self.title("Chat App")
        self.geometry("1000x800")

        self.create_widgets()
        self.unread_popup_shown = False  # Flag to show unread popup once per login

        user_list_update_thread = threading.Thread(
            target=self.update_user_list)
        user_list_update_thread.daemon = True
        user_list_update_thread.start()

        chat_update_thread = threading.Thread(
            target=self.update_chat)
        chat_update_thread.daemon = True
        chat_update_thread.start()

        notification_update_thread = threading.Thread(
            target=self.update_notification)
        notification_update_thread.daemon = True
        notification_update_thread.start()

        self.protocol("WM_DELETE_WINDOW", self.exit_)

        signal.signal(signal.SIGINT, self.exit_)

    def exit_(self, *args, **kwargs):
        """Logs out the user and closes the application window."""
        try:
            self.logout()
        except Exception as e:
            print("Error logging out:", e)
        self.destroy()

    def search_users(self):
        """Searches for users based on the text in the recipient entry field."""
        pattern = self.recipient_var.get().strip()
        if not pattern:
            self.is_search_active = False
            pattern = "*"
        else:
            self.is_search_active = True
            if not pattern.endswith("*"):
                pattern += "*"

        try:
            request = spec_pb2.ListUsersRequest(wildcard=pattern)
            response = self.stub.ListUsers(request)

            self.user_listbox.delete(0, tk.END)
            total = 0
            online = 0

            for user in response.user:
                total += 1
                if user.status.lower() == "online":
                    online += 1
                self.user_listbox.insert(tk.END, f"{user.username} [{user.status}]")

            self.user_stats_label.config(text=f"Users found: {total} | Online Users: {online}")

        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {e}")

    def select_user_from_list(self, event):
        """Callback when a user is selected from the listbox. Loads chat history.

        Args:
            event (tk.Event): The selection event from Listbox.
        """
        try:
            selection = self.user_listbox.get(self.user_listbox.curselection())
            username = selection.split(' [')[0]
            self.recipient_var.set(username)
            self.clear_chat()
            self.load_chat_history(username)
        except Exception:
            pass  # ignore if no selection

    def delete_selected_messages(self):
        """Deletes messages selected via checkboxes in the chat frame."""
        message_ids = []
        for widget in self.chat_frame_inner.winfo_children():
            if isinstance(widget, MessageFrame) and widget.select_var.get():
                message_ids.append(widget.message_id)

        if not message_ids:
            messagebox.showinfo("Info", "No messages selected for deletion.")
            return

        try:
            response = self.delete_messages(message_ids)
            if response and response.error_code == 0:
                messagebox.showinfo("Deleted", response.error_message)
                self.clear_chat()
                self.load_chat_history(self.recipient_var.get())
            else:
                error_message = response.error_message if response else "Failed to delete messages. Server error."
                messagebox.showerror("Error", error_message)
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")


    def create_widgets(self):
        """Creates and lays out all GUI components."""
        style = ThemedStyle(self)
        style.set_theme("adapta")

        scrolledtext.ScrolledText.style = "TScrolledText"

        # Create frames
        top_frame = ttk.Frame(self)
        top_frame.pack(side=tk.TOP, fill=tk.X)

        # print("stub:", self.stub)
        if not self.stub:
            self.retry_button = ttk.Button(
                top_frame, text="Retry Connection", command=self.retry_connection)
            self.retry_button.pack(side=tk.LEFT, padx=5)
            messagebox.showerror(
                "Error", "Failed to establish connection. Click the Retry Connection button to try again.")

        chat_frame = ttk.Frame(self)
        chat_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        recipient_frame = ttk.Frame(self)
        recipient_frame.pack(side=tk.TOP, fill=tk.X)

        message_frame = ttk.Frame(self)
        message_frame.pack(side=tk.TOP, fill=tk.X)

        self.results_frame = ttk.LabelFrame(self, text="List of Users", padding=5)
        self.results_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        self.user_stats_label = ttk.Label(self.results_frame, text="Users found: 0 | Online Users: 0")
        self.user_stats_label.pack(anchor='w', padx=5, pady=(0, 5))

        user_list_container = ttk.Frame(self.results_frame)
        user_list_container.pack(fill=tk.X)

        scrollbar = ttk.Scrollbar(user_list_container, orient="vertical")
        self.user_listbox = tk.Listbox(user_list_container, height=4, yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.user_listbox.yview)

        self.user_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.user_listbox.delete(0, tk.END)

        self.user_listbox.bind('<<ListboxSelect>>', self.select_user_from_list)

        # Create input fields and labels
        self.logged_in_label = ttk.Label(top_frame, text="Logged in as:")
        self.logged_in_label.pack(side=tk.LEFT, padx=5)
        self.logged_in_label.pack_forget()

        self.username_label = ttk.Label(top_frame, text="Username:")
        self.username_label.pack(side=tk.LEFT, padx=5)

        self.username_entry = ttk.Entry(top_frame)
        self.username_entry.pack(side=tk.LEFT, padx=5)

        self.password_label = ttk.Label(top_frame, text="Password:")
        self.password_label.pack(side=tk.LEFT, padx=5)

        self.password_entry = ttk.Entry(top_frame, show="*")
        self.password_entry.pack(side=tk.LEFT, padx=5)

        # Create buttons
        self.signup_button = ttk.Button(
            top_frame, text="Sign up", command=self.signup)
        self.signup_button.pack(side=tk.LEFT, padx=5)

        # Create buttons
        self.login_button = ttk.Button(
            top_frame, text="Login", command=self.login)
        self.login_button.pack(side=tk.LEFT, padx=5)

        # logout button
        self.logout_button = ttk.Button(
            top_frame, text="Logout", command=self.logout)
        self.logout_button.pack(side=tk.LEFT, padx=5)
        self.logout_button.pack_forget()
        
        # Add this after the logout button
        self.delete_button = ttk.Button(
            top_frame, text="Delete Account", command=self.delete_account)
        self.delete_button.pack(side=tk.LEFT, padx=5)
        self.delete_button.pack_forget()  # Initially hidden

        # Create notification area inside chat_frame
        self.notification_text = scrolledtext.ScrolledText(
            chat_frame, wrap=tk.WORD, state='disabled', height=4)
        self.notification_text.pack(
            side=tk.TOP, padx=5, pady=(0, 2), fill=tk.X, expand=False)

        # Add a separator line between notification_text and chat_text
        separator = ttk.Separator(chat_frame, orient="horizontal")
        separator.pack(side=tk.TOP, padx=5, pady=5, fill=tk.X)

        self.chat_canvas = tk.Canvas(chat_frame)
        self.chat_scrollbar = ttk.Scrollbar(chat_frame, orient="vertical", command=self.chat_canvas.yview)
        self.chat_frame_inner = ttk.Frame(self.chat_canvas)

        # Add content window to canvas
        self.chat_window = self.chat_canvas.create_window((0, 0), window=self.chat_frame_inner, anchor="nw", tags="inner")

        # Resize inner frame when canvas resizes
        def resize_inner(event):
            self.chat_canvas.itemconfig("inner", width=event.width)

        self.chat_canvas.bind("<Configure>", resize_inner)

        # Update scrollregion when content changes
        self.chat_frame_inner.bind(
            "<Configure>",
            lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        )

        self.chat_canvas.configure(yscrollcommand=self.chat_scrollbar.set, takefocus=0)
        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.chat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create message input field and send button
        self.message_entry = ttk.Entry(message_frame)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        send_button = ttk.Button(
            message_frame, text="Send", command=self.send_message)
        send_button.pack(side=tk.RIGHT, padx=5)

        recipient_label = ttk.Label(recipient_frame, text="")
        recipient_label.pack(side=tk.LEFT, padx=5)


        delete_button = ttk.Button(chat_frame, text="Delete Selected", command=self.delete_selected_messages)
        delete_button.pack(side=tk.BOTTOM, pady=5)


        ttk.Label(recipient_frame, text="To:").pack(side=tk.LEFT, padx=(5, 2))

        self.recipient_var = tk.StringVar()
        self.recipient_entry = ttk.Entry(
            recipient_frame, textvariable=self.recipient_var)
        self.recipient_entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        self.search_button = ttk.Button(
            recipient_frame, text="Search", command=self.search_users)
        self.search_button.pack(side=tk.LEFT, padx=5)


    def display_notification(self, notification_text):
        """Displays a notification in the notification panel.

        Args:
            notification_text (str): The text to display.
        """
        self.notification_text.configure(state='normal')
        self.notification_text.insert(tk.END, notification_text + "\n")
        self.notification_text.configure(state='disabled')
        self.notification_text.see(tk.END)

    def signup(self):
        """Handles account signup and auto-login if successful."""
        username = self.username_entry.get()
        password = self.password_entry.get()
        response = ChatClientBase.create_account(self, username, password)
        if response.error_code != 0:
            messagebox.showerror("Error", response.error_message)
            return
        self.login()

    def login(self):
        """Handles user login and updates the GUI state."""
        username = self.username_entry.get()
        password = self.password_entry.get()
        response = ChatClientBase.login(self, username, password)

        if response.error_code == 0:
            self.unread_popup_shown = False  # Reset flag on login

            self.user_session_id = response.session_id
            # threading.Thread(target=self.receive_thread).start()
            self.username_label.pack_forget()
            self.username_entry.pack_forget()
            self.password_label.pack_forget()
            self.password_entry.pack_forget()
            self.login_button.pack_forget()
            self.signup_button.pack_forget()

            self.logout_button.pack(side="left", padx=(10, 0))

            self.logged_in_label.config(text=f"Logged in as: {username}")
            self.logged_in_label.pack(side="left")
            self.delete_button.pack(side="right", padx=5)
            self.user_listbox.config(state='normal')
            self.is_search_active = False

            self.notification_thread = threading.Thread(target=self.update_notification, daemon=True)
            self.notification_thread.start()        
        else:
            messagebox.showerror("Error", response.error_message)

    def relogin(self):
        """Prompts the user to log in again after reconnecting to a backup server."""
        if ChatClientBase.relogin(self):
            # Successfully maintained session
            self.display_notification("Server connection restored. Your session continues.")
            return
        # print("Reconnected to a backup server. Login required.")
    
        try:
            self.unread_popup_shown = False
            
            self.logged_in_label.pack_forget()
            self.logout_button.pack_forget()
            self.delete_button.pack_forget()
            
            self.username_label.pack(side="left")
            self.username_entry.pack(side="left")
            self.password_label.pack(side="left")
            self.password_entry.pack(side="left")
            self.login_button.pack(side="left")
            self.signup_button.pack(side="left")
            self.user_listbox.config(state='normal')
            self.is_search_active = False

            self.notification_thread = threading.Thread(target=self.update_notification, daemon=True)
            self.notification_thread.start()
        except Exception as e:
            print(e)

    def logout(self):
        """Logs the user out and resets GUI to login view."""
        response = ChatClientBase.logout(self)

        if response.error_code == 0:
            self.logged_in_label.pack_forget()
            self.logout_button.pack_forget()
            self.delete_button.pack_forget()
            self.user_listbox.delete(0, tk.END)  # Hide user list
            self.user_listbox.config(state='disabled')
            self.is_search_active = False
            self.username_label.pack(side="left")
            self.username_entry.pack(side="left")
            self.password_label.pack(side="left")
            self.password_entry.pack(side="left")
            self.login_button.pack(side="left")
            self.signup_button.pack(side="left")

    def reset_to_login_view(self):
        """Resets the GUI state to the pre-login screen."""
        self.logged_in_label.pack_forget()
        self.logout_button.pack_forget()
        self.delete_button.pack_forget()
        self.user_listbox.delete(0, tk.END)  # Hide user list
        self.user_listbox.config(state='disabled')
        self.is_search_active = False
        self.username_label.pack(side="left")
        self.username_entry.pack(side="left")
        self.password_label.pack(side="left")
        self.password_entry.pack(side="left")
        self.login_button.pack(side="left")
        self.signup_button.pack(side="left")

    def display_users(self):
        """Displays the list of users in the notification panel."""
        response = ChatClientBase.list_users(self)

        if response:
            users = [user for user in response]

            self.notification_text.config(state='normal')
            self.notification_text.insert(tk.END, "List of users:\n")
            for user in users:
                self.notification_text.insert(
                    tk.END, f"{user.username} [{user.status}]\n")
            self.notification_text.config(state='disabled')

    def send_message(self):
        """Sends the message typed in the input field to the selected user."""
        to = self.recipient_var.get()
        message = self.message_entry.get()

        if to and message:
            response = ChatClientBase.send_message(self, to, message)
            if response.error_code == 0:
                self.message_entry.delete(0, tk.END)

                # Create and display only the new message frame
                current_user = self.logged_in_label.cget("text").replace("Logged in as: ", "")
                message_data = {
                    "id": -1,  # dummy ID since server doesn't send it back
                    "from": "You",
                    "content": message,
                    "timestamp": int(time.time())
                }
                msg_frame = MessageFrame(self.chat_frame_inner, message_data)
                msg_frame.pack(fill='x', pady=2, padx=5, anchor='e')
                self.chat_canvas.update_idletasks()
                self.chat_canvas.yview_moveto(1.0)

            else:
                messagebox.showerror("Error", response.error_message)
        else:
            messagebox.showerror(
                "Error", "Please select a recipient and enter a message.")


    def retry_connection(self):
        """Attempts to reconnect to a server and restore GUI functionality."""
        self.connect()
        if self.stub:
            messagebox.showinfo("Success", "Connection re-established.")
            self.retry_button.pack_forget()
        else:
            messagebox.showerror(
                "Error", "Failed to establish connection. Try again.")

    def clear_chat(self):
        """Clears the chat message display area."""
        for widget in self.chat_frame_inner.winfo_children():
            widget.destroy()

    def change_recipient(self, event):
        """Handles recipient switching via event.

        Args:
            event (tk.Event): Triggered from a recipient input widget.
        """
        self.clear_chat()
        self.load_chat_history(event.widget.get())


    def load_chat_history(self, recipient):
        """Loads and displays chat history with the specified recipient."""
        if not self.user_session_id or not recipient:
            return

        response = ChatClientBase.get_chat(self, recipient)
        if not response or response.error_code != 0:
            return

        self.clear_chat()
        current_user = self.logged_in_label.cget("text").replace("Logged in as: ", "")

        self.chat_canvas.configure(state='disabled')
        self.chat_canvas.update_idletasks()

        # Temporarily suppress scrolling
        frames = []

        for message in response.message:
            is_self = message.from_ == current_user
            message_data = {
                "id": message.message_id,
                "from": message.from_,
                "content": message.message,
                "timestamp": message.time_stamp.seconds
            }

            msg_frame = MessageFrame(self.chat_frame_inner, message_data)
            frames.append((msg_frame, is_self))

        for msg_frame, is_self in frames:
            msg_frame.pack(fill='x', pady=2, padx=5, anchor='e' if is_self else 'w')

        self.chat_canvas.configure(state='normal')
        self.chat_canvas.update_idletasks()

        # Smart scroll if overflow, otherwise scroll to top
        chat_bbox = self.chat_canvas.bbox("all")
        view_height = self.chat_canvas.winfo_height()
        if chat_bbox and chat_bbox[3] > view_height:
            self.chat_canvas.yview_moveto(1.0)
        else:
            self.chat_canvas.yview_moveto(0.0)

    def update_notification(self):
        """Periodically fetches and updates unread message counts."""
        popup_shown = False

        while True:
            try:
                response = ChatClientBase.get_unread_counts(self)
                if not response or response.error_code != 0:
                    time.sleep(3)
                    continue

                total_unread = sum(count.count for count in response.counts)

                if not self.unread_popup_shown and not popup_shown:
                    self.after(0, lambda: messagebox.showinfo(
                        "Unread Messages", f"You have {total_unread} unread messages."))
                    self.unread_popup_shown = True
                    popup_shown = True

                self.notification_text.config(state='normal')
                self.notification_text.delete(1.0, tk.END)
                self.notification_text.insert(tk.END, "Unread messages:\n")
                if response.counts:
                    current_chat_user = self.recipient_var.get().strip()
                    for item in response.counts:
                        sender = getattr(item, "from")
                        if sender == current_chat_user:
                            continue  # Skip notifications from the current open chat
                        self.notification_text.insert(tk.END, f"- {sender} ({item.count})\n")

                    # for item in response.counts:
                    #     self.notification_text.insert(
                    #         tk.END, f"- {getattr(item, 'from')} ({item.count})\n")
                else:
                    self.notification_text.insert(tk.END, "No unread messages\n")
                self.notification_text.config(state='disabled')
                self.notification_text.see(tk.END)

            except Exception as e:
                print("Notification error:", e)

            time.sleep(3)

    def refresh_chat(self, response):
        """Updates the chat display with new messages from server response."""
        self.clear_chat()
        current_user = self.logged_in_label.cget("text").replace("Logged in as: ", "")
        for message in response.message:
            is_self = message.from_ == current_user
            message_data = {
                "id": message.message_id,
                "from": message.from_,
                "content": message.message,
                "timestamp": message.time_stamp.seconds
            }

            msg_frame = MessageFrame(self.chat_frame_inner, message_data)
            msg_frame.pack(fill='x', pady=2, padx=5, anchor='e' if is_self else 'w')

        self.chat_canvas.update_idletasks()
        chat_bbox = self.chat_canvas.bbox("all")
        view_height = self.chat_canvas.winfo_height()
        if chat_bbox and chat_bbox[3] > view_height:
            self.chat_canvas.yview_moveto(1.0)
        else:
            self.chat_canvas.yview_moveto(0.0)


    def update_chat(self):
        """Continuously checks and updates current chat window if new messages arrive."""
        last_seen_message_ids = set()

        while True:
            recipient = self.recipient_var.get()
            if self.user_session_id and recipient:
                try:
                    response = ChatClientBase.get_chat(self, recipient)

                    if response and response.error_code == 0:
                        current_ids = {msg.message_id for msg in response.message}
                        if current_ids != last_seen_message_ids:
                            self.after(0, lambda: self.refresh_chat(response))
                            last_seen_message_ids = current_ids

                except Exception as e:
                    print("Chat update error:", e)

            time.sleep(1)


    def update_user_list(self, interval=0):
        """Background thread that periodically updates the user list.

        Args:
            interval (int): Sleep interval between updates (default: 0).
        """
        while True:
            if self.user_session_id and not self.is_search_active:
                try:
                    users = self.list_users("*")
                    total = len(users)
                    online = sum(1 for user in users if user.status == "online")
                    self.user_stats_label.config(text=f"Users found: {total} | Online Users: {online}")

                    current_items = self.user_listbox.get(0, tk.END)
                    user_index_map = {item.split(' [')[0]: idx for idx, item in enumerate(current_items)}

                    for user in users:
                        name = user.username
                        status = "online" if user.status == "online" else "offline"
                        new_entry = f"{name} [{status}]"

                        if name in user_index_map:
                            idx = user_index_map[name]
                            if current_items[idx] != new_entry:
                                self.user_listbox.delete(idx)
                                self.user_listbox.insert(idx, new_entry)
                        else:
                            self.user_listbox.insert(tk.END, new_entry)

                except Exception:
                    pass
            time.sleep(interval)

    def delete_account(self):
        """Handles secure deletion of a user account after confirming password."""
        confirm = messagebox.askyesno(
            "Confirm Deletion", "Are you sure you want to delete your account? This action cannot be undone."
        )

        if not confirm:
            return

        # Ask for password again before deleting
        password = simpledialog.askstring(
            "Password Confirmation",
            "Please enter your password to delete your account:",
            show="*"
        )

        if not password:
            messagebox.showwarning("Cancelled", "Account deletion cancelled.")
            return

        # Try logging in again to verify password
        username = self.username_entry.get()
        login_response = ChatClientBase.login(self, username, password)

        if login_response.error_code != 0:
            messagebox.showerror("Error", "Password incorrect. Cannot delete account.")
            return

        self.user_session_id = login_response.session_id
        response = ChatClientBase.delete_account(self)

        if not response:
            messagebox.showerror("Error", "No response from server.")
            return

        if response.error_code == 0:
            messagebox.showinfo("Deleted", "Account deleted successfully.")
            self.user_session_id = ""
            self.reset_to_login_view()

            # Clear chat and notification areas
            self.clear_chat()
            self.notification_text.config(state='normal')
            self.notification_text.delete(1.0, tk.END)
            self.notification_text.config(state='disabled')

        else:
            messagebox.showerror("Error", response.error_message)

    @classmethod
    def run(cls, addresses):
        """Runs the GUI client.

        Args:
            addresses (List[str]): List of server addresses to try.
        """
        app = cls(addresses)
        app.mainloop()


if __name__ == "__main__":
    # list of available address with the first one being the leader
    parser = argparse.ArgumentParser(
        description="Start a chat client.")
    # parser.add_argument('-a', '--addresses', nargs='+',
    #                     help='<Required> give list of available servers', required=True)
    # args = parser.parse_args()
    # addresses = args.addresses
    


    parser.add_argument('--host', required=True, help='Hostname of the servers, e.g., localhost')
    parser.add_argument('--port', type=int, required=True, help='Port of the current leader')

    args = parser.parse_args()

    # replica_ports = list(range(5001, 5011, 2))
    # 2625
    replica_ports = list(range(args.port, args.port + 15, 2))

    addresses = [f"{args.host}:{port}" for port in replica_ports]
    # print(addresses)

    ChatClientGUI.run(addresses)
