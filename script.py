import socket
import re
import threading
import json
import os
import subprocess
import tkinter as tk
from tkinter import messagebox
from obswebsocket import obsws, requests

CONFIG_FILE = "config.json"

class TwitchOBSController:
    def __init__(self, root):
        self.root = root
        self.root.title("Twitch OBS Remote")
        self.root.geometry("400x380")
        
        self.config = self.load_config()
        self.running = False
        self.obs = None
        self.sock = None
        self.obs_connected = False

        # --- MENU BAR ---
        self.menu_bar = tk.Menu(root)
        root.config(menu=self.menu_bar)
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Config", command=self.open_config_file)
        file_menu.add_command(label="Reload Config", command=self.reload_config)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=root.quit)

        # --- UI ELEMENTS ---
        tk.Label(root, text="Twitch OBS Controller", font=("Arial", 16, "bold")).pack(pady=10)

        status_frame = tk.LabelFrame(root, text="Connection Status", padx=10, pady=10)
        status_frame.pack(padx=20, pady=10, fill="x")

        self.obs_label = tk.Label(status_frame, text="OBS: Disconnected", fg="red")
        self.obs_label.pack(anchor="w")

        self.twitch_label = tk.Label(status_frame, text="Twitch: Disconnected", fg="red")
        self.twitch_label.pack(anchor="w")

        self.user_frame = tk.LabelFrame(root, text="Allowed Users", padx=10, pady=10)
        self.user_frame.pack(padx=20, pady=10, fill="x")
        self.user_list_label = tk.Label(self.user_frame, text="", wraplength=300)
        self.user_list_label.pack()
        self.update_user_display()

        self.btn_toggle = tk.Button(root, text="START TOOL", bg="green", fg="white", 
                                   font=("Arial", 12, "bold"), command=self.toggle_tool)
        self.btn_toggle.pack(pady=20)

        self.monitor_connections()

    def load_config(self):
        """Creates a blank placeholder config if none exists."""
        placeholder = {
            "TWITCH_CHANNEL": "YOUR_CHANNEL_HERE",
            "ALLOWED_USERS": ["USER1", "USER2"],
            "OBS_HOST": "localhost",
            "OBS_PORT": 4455,
            "OBS_PW": "PASSWORD_HERE"
        }
        if not os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "w") as f:
                json.dump(placeholder, f, indent=4)
            return placeholder
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)

    def is_config_valid(self):
        """Checks if the user has replaced placeholder values."""
        invalid_triggers = ["YOUR_CHANNEL_HERE", "PASSWORD_HERE", ""]
        channel = self.config.get("TWITCH_CHANNEL", "")
        password = self.config.get("OBS_PW", "")
        
        if channel in invalid_triggers or password in invalid_triggers:
            return False
        return True

    def open_config_file(self):
        if os.name == 'nt':
            os.startfile(CONFIG_FILE)
        else:
            subprocess.call(('open', CONFIG_FILE))

    def reload_config(self):
        if self.running:
            messagebox.showwarning("Warning", "Stop the tool before reloading.")
            return
        self.config = self.load_config()
        self.update_user_display()
        messagebox.showinfo("Success", "Config reloaded.")

    def update_user_display(self):
        users = self.config.get('ALLOWED_USERS', [])
        self.user_list_label.config(text=", ".join(users) if users else "None")

    def update_status(self, label, text, color):
        label.config(text=text, fg=color)

    def monitor_connections(self):
        if self.running:
            # Twitch Check
            twitch_alive = False
            if self.sock:
                try:
                    if self.sock.fileno() != -1: twitch_alive = True
                except: pass
            
            if twitch_alive:
                chan = self.config.get('TWITCH_CHANNEL', '').lstrip('#')
                self.update_status(self.twitch_label, f"Twitch: #{chan} ✅", "green")
            else:
                self.update_status(self.twitch_label, "Twitch: Connection Lost ❌", "red")

            # OBS Check
            if self.obs_connected:
                try:
                    self.obs.call(requests.GetVersion())
                    self.update_status(self.obs_label, "OBS: Connected ✅", "green")
                except:
                    self.obs_connected = False
                    self.update_status(self.obs_label, "OBS: Connection Lost (Searching...) ❌", "orange")
            else:
                threading.Thread(target=self.attempt_obs_connection, daemon=True).start()

        self.root.after(3000, self.monitor_connections)

    def attempt_obs_connection(self):
        try:
            temp_obs = obsws(self.config['OBS_HOST'], self.config['OBS_PORT'], self.config['OBS_PW'])
            temp_obs.connect()
            self.obs = temp_obs
            self.obs_connected = True
        except:
            self.obs_connected = False

    def toggle_tool(self):
        if not self.running:
            # Check if config is still placeholders
            if not self.is_config_valid():
                messagebox.showerror("Config Error", "Please edit config.json and replace placeholder values before starting.")
                return

            self.running = True
            self.btn_toggle.config(text="STOP TOOL", bg="red")
            self.update_status(self.obs_label, "OBS: Searching...", "orange")
            threading.Thread(target=self.run_twitch_backend, daemon=True).start()
        else:
            self.running = False
            self.btn_toggle.config(text="START TOOL", bg="green")
            self.cleanup()

    def cleanup(self):
        self.obs_connected = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
            except: pass
            self.sock = None
        if self.obs:
            try: self.obs.disconnect()
            except: pass
            self.obs = None
        self.root.after(0, lambda: self.update_status(self.obs_label, "OBS: Disconnected", "red"))
        self.root.after(0, lambda: self.update_status(self.twitch_label, "Twitch: Disconnected", "red"))

    def run_twitch_backend(self):
        try:
            raw_channel = self.config.get('TWITCH_CHANNEL', '').lstrip('#')
            clean_channel = f"#{raw_channel}"

            self.sock = socket.socket()
            self.sock.settimeout(1.0)
            self.sock.connect(("irc.chat.twitch.tv", 6667))
            self.sock.send(f"PASS blah\r\n".encode('utf-8'))
            self.sock.send(f"NICK justinfan12345\r\n".encode('utf-8'))
            self.sock.send(f"JOIN {clean_channel}\r\n".encode('utf-8'))

            buffer = ""
            while self.running:
                try:
                    data = self.sock.recv(2048).decode('utf-8', errors='ignore')
                    if not data: break
                    buffer += data
                    lines = buffer.split("\r\n")
                    buffer = lines.pop()

                    for line in lines:
                        if line.startswith('PING'):
                            self.sock.send("PONG\r\n".encode('utf-8'))
                            continue
                        match = re.search(r':(\w+)!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #\w+ :(.+)', line)
                        if match:
                            user, msg = match.group(1).lower(), match.group(2).strip().lower()
                            if user in [u.lower() for u in self.config.get('ALLOWED_USERS', [])]:
                                if self.obs_connected:
                                    try:
                                        if msg.startswith("!start"):
                                            self.obs.call(requests.StartStream())
                                        elif msg.startswith("!stop"):
                                            self.obs.call(requests.StopStream())
                                    except: pass
                except socket.timeout: continue 
                except OSError: break 
        except Exception as e:
            if self.running: 
                self.root.after(0, lambda: messagebox.showerror("Twitch Error", f"Twitch failed: {e}"))
        
        self.cleanup()
        self.running = False
        self.root.after(0, lambda: self.btn_toggle.config(text="START TOOL", bg="green"))

if __name__ == "__main__":
    root = tk.Tk()
    app = TwitchOBSController(root)
    root.mainloop()