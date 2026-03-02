import tkinter as tk
from tkinter import ttk, messagebox
import asyncio
import threading
from main import BotManager, load_config
import sys
import requests
import os
import json


class BotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ChatBot Controller")
        self.root.geometry("400x500")
        self.root.configure(bg="#f0f0f0")

        self.config = load_config()
        self.manager = BotManager(self.config)
        self.loop = None
        self.thread = None
        
        # GitHub Remote Settings
        self.github_token = tk.StringVar(value=os.getenv("GITHUB_TOKEN", ""))
        self.github_repo = tk.StringVar(value=os.getenv("GITHUB_REPO", "")) # format: owner/repo


        self.setup_ui()

    def setup_ui(self):
        # Professional styling
        style = ttk.Style()
        style.configure("TButton", font=("Helvetica", 12), padding=10)
        style.configure("Start.TButton", foreground="white", background="#4CAF50")
        style.configure("Stop.TButton", foreground="white", background="#f44336")
        
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(expand=True, fill="both")

        ttk.Label(main_frame, text="Bot Control Panel", font=("Helvetica", 16, "bold")).pack(pady=10)

        self.status_label = ttk.Label(main_frame, text="Status: Stopped", font=("Helvetica", 10), foreground="gray")
        self.status_label.pack(pady=5)

        self.start_btn = ttk.Button(main_frame, text="Start Bot", command=self.start_bot, style="TButton")
        self.start_btn.pack(fill="x", pady=5)

        self.stop_btn = ttk.Button(main_frame, text="Stop Bot (Local)", command=self.stop_bot, state="disabled", style="TButton")
        self.stop_btn.pack(fill="x", pady=5)

        ttk.Separator(main_frame, orient="horizontal").pack(fill="x", pady=15)

        ttk.Label(main_frame, text="Remote Control (GitHub)", font=("Helvetica", 12, "bold")).pack(pady=5)
        
        ttk.Label(main_frame, text="GitHub PAT Token:").pack(anchor="w")
        ttk.Entry(main_frame, textvariable=self.github_token, show="*").pack(fill="x", pady=2)
        
        ttk.Label(main_frame, text="Repo (owner/repo):").pack(anchor="w")
        ttk.Entry(main_frame, textvariable=self.github_repo).pack(fill="x", pady=2)

        self.remote_btn = ttk.Button(main_frame, text="Run on GitHub", command=self.trigger_github_action, style="TButton")
        self.remote_btn.pack(fill="x", pady=10)

        self.remote_status = ttk.Label(main_frame, text="", font=("Helvetica", 9), foreground="blue")
        self.remote_status.pack()

        ttk.Label(main_frame, text="Logging output in terminal window", font=("Helvetica", 8), foreground="gray").pack(side="bottom", pady=10)

    def trigger_github_action(self):
        token = self.github_token.get()
        repo = self.github_repo.get()
        
        if not token or not repo:
            messagebox.showerror("Error", "GitHub Token and Repo (owner/repo) are required.")
            return
            
        if "/" not in repo:
            messagebox.showerror("Error", "Repo must be in 'owner/repo' format.")
            return

        self.remote_btn.config(state="disabled")
        self.remote_status.config(text="Sending trigger...")
        
        threading.Thread(target=self._dispatch_request, args=(token, repo), daemon=True).start()

    def _dispatch_request(self, token, repo):
        url = f"https://api.github.com/repos/{repo}/actions/workflows/run_bot.yml/dispatches"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {"ref": "main"}
        
        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 204:
                self.root.after(0, lambda: self.remote_status.config(text="Successfully triggered GitHub Action!", foreground="green"))
            else:
                error_msg = response.json().get('message', response.text)
                self.root.after(0, lambda: self.on_remote_error(f"Failed: {response.status_code} - {error_msg}"))
        except Exception as e:
            self.root.after(0, lambda: self.on_remote_error(str(e)))
        finally:
            self.root.after(3000, lambda: self.remote_btn.config(state="normal"))

    def on_remote_error(self, error):
        self.remote_status.config(text=f"Error: {error}", foreground="red")
        messagebox.showerror("Remote Error", f"Failed to trigger GitHub Actions: {error}")


    def start_bot(self):
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_label.config(text="Status: Starting...", foreground="#4CAF50")

        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.run_async_loop, daemon=True)
        self.thread.start()

    def run_async_loop(self):
        asyncio.set_event_loop(self.loop)
        try:
            # Initialize all bots by default for now
            self.loop.run_until_complete(self.manager.initialize_bots())
            self.loop.run_until_complete(self.manager.start())
        except Exception as e:
            print(f"Error in async loop: {e}")
            self.root.after(0, lambda: self.on_bot_error(str(e)))
        finally:
            self.root.after(0, self.on_bot_stopped)

    def stop_bot(self):
        self.status_label.config(text="Status: Stopping...", foreground="#f44336")
        self.stop_btn.config(state="disabled")
        if self.loop:
            self.loop.call_soon_threadsafe(lambda: asyncio.create_task(self.manager.stop()))

    def on_bot_stopped(self):
        self.status_label.config(text="Status: Stopped", foreground="gray")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def on_bot_error(self, error):
        messagebox.showerror("Error", f"Bot encountered an error: {error}")
        self.on_bot_stopped()

if __name__ == "__main__":
    root = tk.Tk()
    app = BotGUI(root)
    
    def on_closing():
        if app.manager.bots:
            if messagebox.askokcancel("Quit", "Bot is running. Do you want to stop it and quit?"):
                app.stop_bot()
                # Wait a bit for bots to stop
                root.after(1000, root.destroy)
        else:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
