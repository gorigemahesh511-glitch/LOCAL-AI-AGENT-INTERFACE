
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from datetime import datetime
import urllib.request
import urllib.error
import json
import threading
import shutil
import os
import subprocess
import sys
import time
import re


# =========================================================
# CONFIGURATION
# =========================================================

APP_NAME = "AI LOCAL AGENT"
MODEL_NAME = "qwen3.5:4b"
OLLAMA_URL = "http://localhost:11434/api/chat"

GENERATED_DIR = (
    Path.home() / "Documents" / "AI_LOCAL_AGENT" / "generated_files"
)
REGISTRY_FILE = GENERATED_DIR / ".agent_created_files.json"

ALLOWED_ROOTS = [
    Path.home(),
    Path.cwd(),
    Path("D:/Coding"),
]

ctk.set_default_color_theme("blue")
ctk.set_appearance_mode("Dark")


# =========================================================
# BACKEND: FILE MANAGEMENT
# =========================================================

def inside(path, root):
    try:
        path.resolve().relative_to(root.expanduser().resolve())
        return True
    except (ValueError, OSError):
        return False


def safe_path(value, default=None):
    if not value or not str(value).strip():
        raise ValueError("A path is required.")

    value = str(value).strip()
    aliases = {
        "desktop": Path.home() / "Desktop",
        "documents": Path.home() / "Documents",
        "downloads": Path.home() / "Downloads",
        "workspace": Path.cwd(),
        "generated": GENERATED_DIR,
    }

    normalized = value.replace("\\", "/")
    first, separator, rest = normalized.partition("/")

    if first.lower() in aliases:
        path = aliases[first.lower()]
        if separator and rest:
            path = path / rest
    else:
        path = Path(value).expanduser()
        if not path.is_absolute() and default:
            path = default / path

    path = path.resolve()

    if not any(
        inside(path, root)
        for root in ALLOWED_ROOTS + [GENERATED_DIR]
    ):
        raise PermissionError("That path is outside the allowed folders.")

    return path


def registered_files():
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        return {
            str(Path(item).resolve())
            for item in data
            if isinstance(item, str)
        }
    except (OSError, ValueError, TypeError):
        return set()


def save_registry(paths):
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_FILE.write_text(
        json.dumps(sorted(paths), indent=2),
        encoding="utf-8",
    )


def create_file(filename, content):
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    # Relative names are saved in the agent's dedicated folder.
    supplied = Path(filename).expanduser()
    if supplied.is_absolute():
        path = safe_path(str(supplied))
    else:
        name = supplied.name
        if name in {"", ".", ".."}:
            raise ValueError("Please provide a valid filename.")
        path = (GENERATED_DIR / name).resolve()

    if not path.suffix:
        path = path.with_suffix(".txt")

    if not any(
        inside(path, root)
        for root in ALLOWED_ROOTS + [GENERATED_DIR]
    ):
        raise PermissionError("The file path is not allowed.")

    if path.exists():
        raise FileExistsError(
            f"{path.name} already exists. Choose a different filename."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    paths = registered_files()
    paths.add(str(path.resolve()))
    save_registry(paths)

    return f"Created {path.name}\nFull path: {path}"


def read_file(filename):
    path = safe_path(filename)

    if not path.exists() and not path.suffix:
        path = path.with_suffix(".txt")

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    # Prevent accidentally displaying enormous files in chat.
    content = path.read_text(encoding="utf-8")
    if len(content) > 12000:
        content = content[:12000] + "\n... (content shortened)"

    return f"Contents of {path.name}:\n{content}"


def list_folder(folder_path="downloads"):
    folder = safe_path(folder_path)

    if not folder.is_dir():
        raise NotADirectoryError(f"Folder not found: {folder}")

    items = list(folder.iterdir())[:50]
    if not items:
        return f"The folder {folder} is empty."

    lines = [
        f"{'[FOLDER]' if item.is_dir() else '[FILE]'} {item.name}"
        for item in items
    ]
    return f"Contents of {folder}:\n" + "\n".join(lines)


def create_folder(folder_name, parent="workspace"):
    name = Path(folder_name).name

    if name in {"", ".", ".."} or name != folder_name:
        raise ValueError("Provide a folder name, not a full path.")

    parent_path = safe_path(parent)
    new_path = (parent_path / name).resolve()

    if not any(
        inside(new_path, root)
        for root in ALLOWED_ROOTS + [GENERATED_DIR]
    ):
        raise PermissionError("The folder path is not allowed.")

    new_path.mkdir(parents=True, exist_ok=True)
    return f"Folder created or already exists:\n{new_path}"


def move_file(source, destination_folder):
    source_path = safe_path(source)
    destination = safe_path(destination_folder)

    if not source_path.is_file():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    destination.mkdir(parents=True, exist_ok=True)
    target = destination / source_path.name

    if target.exists():
        raise FileExistsError(
            f"{target.name} already exists in the destination. "
            "Nothing was overwritten."
        )

    shutil.move(str(source_path), str(target))

    paths = registered_files()
    old_path = str(source_path.resolve())

    if old_path in paths:
        paths.remove(old_path)
        paths.add(str(target.resolve()))
        save_registry(paths)

    return f"Moved {source_path.name} to:\n{target}"


def get_agent_files():
    results = []

    for item in registered_files():
        path = Path(item)

        try:
            if path.is_file():
                results.append({
                    "name": path.name,
                    "path": str(path.resolve()),
                    "size": path.stat().st_size,
                })
        except OSError:
            pass

    return sorted(results, key=lambda item: item["name"].lower())


def open_file_location(file_path):
    path = Path(file_path).resolve()

    if not path.is_file():
        raise FileNotFoundError("The file no longer exists.")

    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])


# =========================================================
# BACKEND: OPTIONAL OLLAMA MODEL
# =========================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": (
                "Create a new text file. Relative filenames go into "
                "the generated files folder. Never overwrite files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file from an allowed location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"},
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_folder",
            "description": "List files and folders in an allowed folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_path": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Create a folder in an allowed location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_name": {"type": "string"},
                    "parent": {"type": "string"},
                },
                "required": ["folder_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": (
                "Move a file to another folder without overwriting."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "destination_folder": {"type": "string"},
                },
                "required": ["source", "destination_folder"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "create_file": create_file,
    "read_file": read_file,
    "list_folder": list_folder,
    "create_folder": create_folder,
    "move_file": move_file,
}

SYSTEM_PROMPT = """
You are AI LOCAL AGENT, a helpful desktop assistant.
Answer clearly and naturally.
Use your file tools when the user requests file operations.
Relative filenames created by create_file go into the agent's generated
files folder. Never claim a file operation succeeded unless its tool
succeeded. Never overwrite an existing file.
Only work within allowed user folders.
"""


def ask_ollama(prompt, history, model_name, log_callback=None):
    """Send a message to an already-running local Ollama model."""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    for _ in range(5):
        payload = {
            "model": model_name,
            "messages": messages,
            "tools": TOOLS,
            "stream": False,
        }

        request = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8"))

        message = data.get("message", {})
        messages.append(message)

        tool_calls = message.get("tool_calls", [])
        if not tool_calls:
            return message.get("content", "").strip(), messages[1:-1]

        for call in tool_calls:
            function = call.get("function", {})
            name = function.get("name", "")
            arguments = function.get("arguments", {})

            if isinstance(arguments, str):
                arguments = json.loads(arguments)

            if log_callback:
                log_callback(f"Using tool: {name}")

            try:
                if name not in TOOL_FUNCTIONS:
                    raise ValueError("Unknown tool.")

                result = TOOL_FUNCTIONS[name](**arguments)
            except Exception as exc:
                result = f"Tool error: {exc}"

            messages.append({
                "role": "tool",
                "tool_name": name,
                "content": str(result),
            })

    return "I reached the tool-call limit. Please try again.", messages[1:]


def demo_response(prompt):
    """Offline fallback: no model is downloaded or simulated as real AI."""

    text = prompt.lower().strip()

    if any(word in text for word in ("hello", "hi", "hey")):
        return (
            "Hello! Welcome to AI LOCAL AGENT.\n\n"
            "I'm currently in demo mode because no local model is "
            "connected. You can still explore the interface and Files panel."
        )

    if "create file" in text or "make a file" in text:
        match = re.search(
            r"(?:create file|make a file)\s+(?:named\s+)?([^\s]+)",
            prompt,
            re.IGNORECASE,
        )
        if match:
            name = Path(match.group(1)).name
            if name in {"", ".", ".."}:
                return "Please provide a valid filename."

            try:
                result = create_file(
                    name,
                    "This file was created by AI LOCAL AGENT in demo mode.\n"
                    f"Created: {datetime.now():%Y-%m-%d %H:%M:%S}\n",
                )
                return result
            except Exception as exc:
                return f"I couldn't create that file: {exc}"

    if "list" in text and ("file" in text or "folder" in text):
        try:
            return list_folder("generated")
        except Exception as exc:
            return f"Couldn't list files: {exc}"

    return (
        "I'm running in demo mode, so I can't generate a real AI answer "
        "without an available model.\n\n"
        "You can still test the interface and file creation. For real "
        "AI responses, connect an already-running Ollama model; this app "
        "will not download one automatically."
    )


# =========================================================
# USER INTERFACE
# =========================================================

class AILocalAgent(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(APP_NAME)
        self.geometry("1200x780")
        self.minsize(850, 580)

        self.theme = "Dark"
        self.busy = False
        self.model_name = MODEL_NAME
        self.history = []
        self.messages = []
        self.files_visible = False
        self.thinking_job = None
        self.thinking_index = 0
        self.placeholder = "Ask anything"

        self.apply_theme()
        self.build_layout()
        self.refresh_files()
        self.show_welcome()

    # ---------------- Theme ----------------

    def apply_theme(self):
        ctk.set_appearance_mode(self.theme)

        if self.theme == "Light":
            self.colors = {
                "bg": "#F5F6F8",
                "sidebar": "#E9ECF1",
                "card": "#FFFFFF",
                "text": "#20242B",
                "muted": "#697586",
                "border": "#D8DDE5",
                "blue": "#2563EB",
                "green": "#0F9D76",
                "input": "#FFFFFF",
            }
        else:
            self.colors = {
                "bg": "#17191F",
                "sidebar": "#111319",
                "card": "#222630",
                "text": "#ECEEF3",
                "muted": "#9BA4B4",
                "border": "#303541",
                "blue": "#3268D5",
                "green": "#45C7A0",
                "input": "#222630",
            }

    def change_theme(self, value):
        self.theme = value
        self.apply_theme()
        self.rebuild()

    # ---------------- Layout ----------------

    def build_layout(self):
        self.configure(fg_color=self.colors["bg"])

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(
            self,
            width=210,
            corner_radius=0,
            fg_color=self.colors["sidebar"],
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(6, weight=1)

        ctk.CTkLabel(
            self.sidebar,
            text="✦  AI LOCAL AGENT",
            font=("Segoe UI", 17, "bold"),
            text_color=self.colors["text"],
        ).grid(row=0, column=0, padx=15, pady=(24, 25), sticky="w")

        self.side_button("＋  New Chat", self.new_chat, 1)
        self.side_button("▤  Files", self.toggle_files, 2)
        self.side_button("⇩  Export Chat", self.export_chat, 3)
        self.side_button("＋  Attach File", self.attach_file, 4)

        theme_frame = ctk.CTkFrame(
            self.sidebar,
            fg_color="transparent",
        )
        theme_frame.grid(row=7, column=0, sticky="ew", padx=14, pady=14)

        ctk.CTkLabel(
            theme_frame,
            text="Appearance",
            text_color=self.colors["muted"],
        ).pack(anchor="w", pady=(0, 5))

        self.theme_menu = ctk.CTkOptionMenu(
            theme_frame,
            values=["Dark", "Light", "System"],
            command=self.change_theme,
            fg_color=self.colors["card"],
            button_color=self.colors["blue"],
        )
        self.theme_menu.set(self.theme)
        self.theme_menu.pack(fill="x")

        self.main = ctk.CTkFrame(self, fg_color=self.colors["bg"])
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        self.header = ctk.CTkFrame(
            self.main,
            fg_color=self.colors["bg"],
            height=65,
        )
        self.header.grid(row=0, column=0, sticky="ew", padx=22, pady=10)
        self.header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.header,
            text="AI LOCAL AGENT",
            font=("Segoe UI", 18, "bold"),
            text_color=self.colors["text"],
        ).grid(row=0, column=0, sticky="w")

        self.status_label = ctk.CTkLabel(
            self.header,
            text="● Demo mode until a local model is available",
            font=("Segoe UI", 11),
            text_color=self.colors["muted"],
        )
        self.status_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

        self.model_menu = ctk.CTkOptionMenu(
            self.header,
            values=[MODEL_NAME, "llama3.2", "qwen2.5:3b"],
            command=self.change_model,
            width=145,
        )
        self.model_menu.set(self.model_name)
        self.model_menu.grid(row=0, column=1, rowspan=2, padx=8)

        if self.files_visible:
            self.files_panel = ctk.CTkFrame(
                self,
                width=300,
                fg_color=self.colors["sidebar"],
                corner_radius=0,
            )
            self.files_panel.grid(row=0, column=2, sticky="nsew")
            self.files_panel.grid_propagate(False)
            self.build_files_panel()

        self.chat_frame = ctk.CTkScrollableFrame(
            self.main,
            fg_color=self.colors["bg"],
        )
        self.chat_frame.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=22,
            pady=(0, 10),
        )

        self.composer = ctk.CTkFrame(
            self.main,
            fg_color=self.colors["card"],
            corner_radius=20,
            border_width=1,
            border_color=self.colors["border"],
        )
        self.composer.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=22,
            pady=(0, 18),
        )
        self.composer.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            self.composer,
            text="+",
            width=38,
            height=38,
            fg_color="transparent",
            text_color=self.colors["text"],
            hover_color=self.colors["border"],
            command=self.attach_file,
        ).grid(row=0, column=0, padx=(8, 2), pady=8)

        self.message_input = ctk.CTkTextbox(
            self.composer,
            height=48,
            wrap="word",
            fg_color="transparent",
            border_width=0,
            text_color=self.colors["text"],
            font=("Segoe UI", 14),
        )
        self.message_input.grid(
            row=0, column=1, sticky="ew", padx=4, pady=4
        )
        self.message_input.insert("1.0", self.placeholder)
        self.message_input.bind("<FocusIn>", self.clear_placeholder)
        self.message_input.bind("<FocusOut>", self.restore_placeholder)
        self.message_input.bind("<Control-Return>", self.send_message)

        ctk.CTkButton(
            self.composer,
            text="🎙",
            width=38,
            height=38,
            fg_color="transparent",
            text_color=self.colors["text"],
            hover_color=self.colors["border"],
            command=self.voice_placeholder,
        ).grid(row=0, column=2, padx=2, pady=8)

        self.send_button = ctk.CTkButton(
            self.composer,
            text="↑",
            width=40,
            height=40,
            corner_radius=14,
            font=("Segoe UI", 22, "bold"),
            command=self.send_message,
        )
        self.send_button.grid(row=0, column=3, padx=(2, 8), pady=8)

        self.messages_area = self.chat_frame

        # Re-render previous messages after theme/layout changes.
        for item in self.messages:
            self.render_message(item["role"], item["content"])

    def side_button(self, text, command, row):
        ctk.CTkButton(
            self.sidebar,
            text=text,
            command=command,
            anchor="w",
            height=40,
            corner_radius=10,
            fg_color="transparent",
            text_color=self.colors["text"],
            hover_color=self.colors["border"],
        ).grid(row=row, column=0, sticky="ew", padx=12, pady=3)

    # ---------------- Chat display ----------------

    def show_welcome(self):
        if self.messages:
            return

        ctk.CTkLabel(
            self.chat_frame,
            text="How can I help you today?",
            font=("Segoe UI", 26, "bold"),
            text_color=self.colors["text"],
        ).pack(pady=(110, 8))

        ctk.CTkLabel(
            self.chat_frame,
            text=(
                "Ask a question, explore the interface, or try creating "
                "a file. Real AI responses need an available model."
            ),
            font=("Segoe UI", 13),
            text_color=self.colors["muted"],
            wraplength=550,
        ).pack(pady=4)

    def clear_chat_widgets(self):
        for widget in self.chat_frame.winfo_children():
            widget.destroy()

    def render_message(self, role, content):
        row = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        row.pack(fill="x", pady=8, padx=4)

        is_user = role == "user"
        name = "You" if is_user else "AI LOCAL AGENT"

        bubble = ctk.CTkFrame(
            row,
            fg_color=self.colors["blue"] if is_user else self.colors["card"],
            corner_radius=14,
        )
        bubble.pack(
            anchor="e" if is_user else "w",
            padx=(55, 0) if is_user else (0, 55),
        )

        ctk.CTkLabel(
            bubble,
            text=name,
            font=("Segoe UI", 11, "bold"),
            text_color="#FFFFFF" if is_user else self.colors["green"],
        ).pack(anchor="w", padx=14, pady=(9, 2))

        ctk.CTkLabel(
            bubble,
            text=content,
            font=("Segoe UI", 14),
            text_color="#FFFFFF" if is_user else self.colors["text"],
            justify="left",
            anchor="w",
            wraplength=620,
        ).pack(anchor="w", padx=14, pady=(2, 12))

        self.after(50, self.scroll_to_bottom)

    def add_message(self, role, content):
        self.messages.append({"role": role, "content": content})
        self.render_message(role, content)

    def scroll_to_bottom(self):
        try:
            self.chat_frame._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    # ---------------- Placeholder ----------------

    def clear_placeholder(self, event=None):
        if self.message_input.get("1.0", "end").strip() == self.placeholder:
            self.message_input.delete("1.0", "end")
            self.message_input.configure(text_color=self.colors["text"])

    def restore_placeholder(self, event=None):
        if not self.message_input.get("1.0", "end").strip():
            self.message_input.insert("1.0", self.placeholder)

    # ---------------- Thinking animation ----------------

    def show_thinking(self):
        self.thinking_index = 0
        self.thinking_label = ctk.CTkLabel(
            self.chat_frame,
            text="Thinking",
            font=("Segoe UI", 13),
            text_color=self.colors["muted"],
        )
        self.thinking_label.pack(anchor="w", pady=8, padx=14)
        self.animate_thinking()

    def animate_thinking(self):
        if not self.busy or not self.thinking_label.winfo_exists():
            return

        self.thinking_index = (self.thinking_index + 1) % 4
        self.thinking_label.configure(
            text="Thinking" + "." * self.thinking_index
        )
        self.thinking_job = self.after(350, self.animate_thinking)

    def hide_thinking(self):
        if self.thinking_job:
            self.after_cancel(self.thinking_job)
            self.thinking_job = None

        if (
            hasattr(self, "thinking_label")
            and self.thinking_label.winfo_exists()
        ):
            self.thinking_label.destroy()

    # ---------------- Sending and receiving ----------------

    def send_message(self, event=None):
        prompt = self.message_input.get("1.0", "end").strip()

        if not prompt or prompt == self.placeholder or self.busy:
            return "break"

        self.busy = True
        self.message_input.delete("1.0", "end")
        self.add_message("user", prompt)
        self.show_thinking()
        self.send_button.configure(state="disabled")
        self.status_label.configure(text="● Working...")

        threading.Thread(
            target=self.inference_worker,
            args=(prompt, list(self.history), self.model_name),
            daemon=True,
        ).start()

        return "break"

    def inference_worker(self, prompt, history, model_name):
        try:
            # Do not download a model. Try only the configured local service.
            response = None
            new_history = history

            try:
                response, new_history = ask_ollama(
                    prompt,
                    history,
                    model_name,
                )
                status = f"● Connected to local model: {model_name}"
            except (urllib.error.URLError, TimeoutError, OSError,
                    json.JSONDecodeError, KeyError, ValueError) as exc:
                response = demo_response(prompt)
                status = "● Demo mode — no local model connected"
                print(f"Ollama unavailable; using demo mode: {exc}")

            self.after(
                0,
                lambda r=response, h=new_history, s=status:
                    self.finish_response(r, h, s),
            )

        except Exception as exc:
            self.after(
                0,
                lambda error=str(exc):
                    self.finish_response(
                        f"Something went wrong: {error}",
                        self.history,
                        "● Error",
                    ),
            )

    def finish_response(self, response, history, status):
        self.hide_thinking()
        self.busy = False
        self.history = history
        self.add_message("assistant", response or "(No response returned)")
        self.send_button.configure(state="normal")
        self.status_label.configure(text=status)
        self.refresh_files()

    # ---------------- Sidebar actions ----------------

    def new_chat(self):
        if self.busy:
            return

        self.history = []
        self.messages = []
        self.clear_chat_widgets()
        self.show_welcome()

    def export_chat(self):
        if not self.messages:
            messagebox.showinfo(APP_NAME, "There is no chat to export yet.")
            return

        filename = filedialog.asksaveasfilename(
            title="Export chat",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile="ai_local_agent_chat.txt",
        )
        if not filename:
            return

        try:
            with open(filename, "w", encoding="utf-8") as file:
                file.write(f"{APP_NAME}\n")
                file.write("=" * 50 + "\n\n")

                for item in self.messages:
                    label = "You" if item["role"] == "user" else APP_NAME
                    file.write(f"{label}:\n{item['content']}\n\n")

            messagebox.showinfo(APP_NAME, "Chat exported successfully.")
        except OSError as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def attach_file(self):
        filename = filedialog.askopenfilename(
            title="Select a file",
            filetypes=[("All files", "*.*")],
        )
        if filename:
            messagebox.showinfo(
                APP_NAME,
                "File selected:\n"
                + filename
                + "\n\nAttachment upload is not implemented yet.",
            )

    def voice_placeholder(self):
        messagebox.showinfo(
            APP_NAME,
            "Voice input is not implemented yet.",
        )

    def change_model(self, value):
        self.model_name = value
        self.status_label.configure(
            text=f"● Selected local model: {value}"
        )

    # ---------------- Files panel ----------------

    def toggle_files(self):
        self.files_visible = not self.files_visible
        self.rebuild()

    def build_files_panel(self):
        header = ctk.CTkFrame(
            self.files_panel,
            fg_color="transparent",
        )
        header.pack(fill="x", padx=12, pady=15)

        ctk.CTkLabel(
            header,
            text="Agent Files",
            font=("Segoe UI", 17, "bold"),
            text_color=self.colors["text"],
        ).pack(side="left")

        ctk.CTkButton(
            header,
            text="×",
            width=30,
            command=self.toggle_files,
        ).pack(side="right")

        ctk.CTkLabel(
            self.files_panel,
            text=str(GENERATED_DIR),
            wraplength=260,
            justify="left",
            text_color=self.colors["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=12, pady=(0, 12))

        self.files_list = ctk.CTkScrollableFrame(
            self.files_panel,
            fg_color="transparent",
        )
        self.files_list.pack(fill="both", expand=True, padx=8, pady=4)

        ctk.CTkButton(
            self.files_panel,
            text="Refresh Files",
            command=self.refresh_files,
        ).pack(fill="x", padx=12, pady=12)

    def refresh_files(self):
        if not self.files_visible or not hasattr(self, "files_list"):
            return

        for widget in self.files_list.winfo_children():
            widget.destroy()

        files = get_agent_files()

        if not files:
            ctk.CTkLabel(
                self.files_list,
                text="No agent-created files yet.",
                text_color=self.colors["muted"],
                wraplength=230,
            ).pack(pady=12)
            return

        for item in files:
            card = ctk.CTkFrame(
                self.files_list,
                fg_color=self.colors["card"],
                corner_radius=10,
            )
            card.pack(fill="x", pady=5, padx=2)

            ctk.CTkLabel(
                card,
                text="▤  " + item["name"],
                font=("Segoe UI", 12, "bold"),
                text_color=self.colors["text"],
                wraplength=225,
                justify="left",
            ).pack(anchor="w", padx=10, pady=(9, 2))

            ctk.CTkLabel(
                card,
                text=item["path"],
                font=("Segoe UI", 10),
                text_color=self.colors["muted"],
                wraplength=225,
                justify="left",
            ).pack(anchor="w", padx=10, pady=(0, 7))

            buttons = ctk.CTkFrame(card, fg_color="transparent")
            buttons.pack(fill="x", padx=7, pady=(0, 8))

            ctk.CTkButton(
                buttons,
                text="Copy Path",
                height=28,
                command=lambda p=item["path"]: self.copy_path(p),
            ).pack(side="left", expand=True, fill="x", padx=2)

            ctk.CTkButton(
                buttons,
                text="Open Folder",
                height=28,
                command=lambda p=item["path"]: self.open_path(p),
            ).pack(side="left", expand=True, fill="x", padx=2)

    def copy_path(self, path):
        self.clipboard_clear()
        self.clipboard_append(path)
        self.update()
        self.status_label.configure(text="● File path copied")

    def open_path(self, path):
        try:
            open_file_location(path)
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    # ---------------- Rebuild after theme changes ----------------

    def rebuild(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.apply_theme()
        self.build_layout()
        self.refresh_files()

    def destroy(self):
        try:
            self.hide_thinking()
        except Exception:
            pass
        super().destroy()


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    app = AILocalAgent()
    app.mainloop()
