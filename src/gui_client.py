import tkinter as tk
import threading
import time
from tkinter import ttk, scrolledtext, simpledialog
from base_client import ChatClientBase
import tkinter.messagebox as messagebox
from ttkthemes import ThemedStyle
import signal

import spec_pb2

from message_frame import MessageFrame


class ChatClientGUI(tk.Tk, ChatClientBase):
    def __init__(self, addresses):
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

        # chat_update_thread = threading.Thread(
        #     target=self.update_chat)
        # chat_update_thread.daemon = True
        # chat_update_thread.start()

        notification_update_thread = threading.Thread(
            target=self.update_notification)
        notification_update_thread.daemon = True
        notification_update_thread.start()

        self.protocol("WM_DELETE_WINDOW", self.exit_)

        signal.signal(signal.SIGINT, self.exit_)

    def exit_(self, *args, **kwargs):
        try:
            self.logout()
        except Exception as e:
            print("Error logging out:", e)
        self.destroy()

    def search_users(self):
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
        try:
            selection = self.user_listbox.get(self.user_listbox.curselection())
            username = selection.split(' [')[0]
            self.recipient_var.set(username)
            self.clear_chat()
            self.load_chat_history(username)
        except Exception:
            pass  # ignore if no selection

    def delete_selected_messages(self):
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
                self.load_chat_history(self.recipient_var.get())
            else:
                error_message = response.error_message if response else "Failed to delete messages. Server error."
                messagebox.showerror("Error", error_message)
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")


    def create_widgets(self):

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
        self.notification_text.configure(state='normal')
        self.notification_text.insert(tk.END, notification_text + "\n")
        self.notification_text.configure(state='disabled')
        self.notification_text.see(tk.END)

    def signup(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        response = ChatClientBase.create_account(self, username, password)
        if response.error_code != 0:
            messagebox.showerror("Error", response.error_message)
            return
        self.login()

    def login(self):
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
        messagebox.showerror(
            "Error", "Server failed, connected to backup server. Please relogin")
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
        response = ChatClientBase.list_users(self)

        if response:
            users = [user for user in response]

            # self.recipient_combobox["values"] = tuple(
            #     [user.username for user in users])

            self.notification_text.config(state='normal')
            self.notification_text.insert(tk.END, "List of users:\n")
            for user in users:
                self.notification_text.insert(
                    tk.END, f"{user.username} [{user.status}]\n")
            self.notification_text.config(state='disabled')

    def send_message(self):
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
        self.connect()
        if self.stub:
            messagebox.showinfo("Success", "Connection re-established.")
            self.retry_button.pack_forget()
        else:
            messagebox.showerror(
                "Error", "Failed to establish connection. Try again.")

    def clear_chat(self):
        # self.chat_text.config(state='normal')
        # self.chat_text.delete(1.0, tk.END)
        # self.chat_text.config(state='disabled')
        for widget in self.chat_frame_inner.winfo_children():
            widget.destroy()

    def change_recipient(self, event):
        self.clear_chat()
        self.load_chat_history(event.widget.get())

    def load_chat_history(self, recipient):
        if not self.user_session_id or not recipient:
            return

        response = ChatClientBase.get_chat(self, recipient)
        if not response or response.error_code != 0:
            return

        self.clear_chat()
        current_user = self.logged_in_label.cget("text").replace("Logged in as: ", "")

        for message in response.message:
            is_self = message.from_ == current_user
            message_data = {
                "id": message.message_id,
                "from": message.from_,
                "content": message.message,
                "timestamp": message.time_stamp.seconds  # or convert properly if needed
            }

            msg_frame = MessageFrame(self.chat_frame_inner, message_data)
            msg_frame.pack(fill='x', pady=2, padx=5, anchor='e' if is_self else 'w')

            self.chat_canvas.update_idletasks()
            self.chat_canvas.yview_moveto(1.0)  # scroll to bottom



    def update_notification(self):
        """
        Periodically checks for unread messages and updates the notification area
        and popup once after login.
        """
        seen_senders = {}  # Tracks unread count per sender
        popup_shown = False  # Local to this thread

        while True:
            msgs = ChatClientBase.receive_messages(self)

            if msgs and msgs.error_code in [0, 17]:  # 0 = messages; 17 = no messages
                # Reset sender counts
                seen_senders.clear()

                if msgs.error_code == 0:
                    for message in msgs.message:
                        seen_senders[message.from_] = seen_senders.get(message.from_, 0) + 1

                # Show popup (once per login, even if 0 messages)
                if not self.unread_popup_shown and not popup_shown:
                    total_unread = sum(seen_senders.values())
                    self.after(0, lambda: messagebox.showinfo(
                        "Unread Messages", f"You have {total_unread} unread messages."))
                    self.unread_popup_shown = True
                    popup_shown = True

                # Update notification display
                self.notification_text.config(state='normal')
                self.notification_text.delete(1.0, tk.END)
                self.notification_text.insert(tk.END, "Unread messages:\n")
                if seen_senders:
                    for sender, count in seen_senders.items():
                        self.notification_text.insert(tk.END, f"- {sender} ({count})\n")
                else:
                    self.notification_text.insert(tk.END, "No unread messages\n")
                self.notification_text.config(state='disabled')
                self.notification_text.see(tk.END)

            time.sleep(3)



    def update_chat(self):
        while True:
            # here it might be a good idea
            # to only load a certain amount of messages
            # and have that built in capability on the server side as well
            self.load_chat_history(self.recipient_var.get())
            time.sleep(1)

    def update_user_list(self, interval=0):
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
        app = cls(addresses)
        app.mainloop()


if __name__ == "__main__":
    import argparse

    # take in a list of available address with the first one being
    # the master
    parser = argparse.ArgumentParser(
        description="Start a chat client.")
    parser.add_argument('-a', '--addresses', nargs='+',
                        help='<Required> give list of available servers', required=True)

    args = parser.parse_args()
    addresses = args.addresses
    # print(addresses)

    ChatClientGUI.run(addresses)
