
import customtkinter as ctk
from tkinter import messagebox, filedialog
from pathlib import Path

from ui.backend import (
    save_agent_file,
    get_agent_files,
    open_file_location,
)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class AILocalAgent(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("AI LOCAL AGENT")
        self.geometry("1250x780")
        self.minsize(900, 600)

        self.selected_theme = "Dark"
        self.files_visible = False
        self.busy = False
        self.messages = []
        self.placeholder = "Ask anything"
        self.attached_files = []
        self.thinking_active = False
        self.thinking_dots = 0
        self.thinking_frame = None
        self.theme_rebuilding = False

        self.set_colors()
        self.configure(fg_color=self.colors["bg"])

        self.create_layout()
        self.show_welcome()

    # ==================================================
    # COLORS AND THEMES
    # ==================================================

    def set_colors(self):
        if self.selected_theme == "Light":
            self.colors = {
                "bg": "#F4F7FC",
                "sidebar": "#FFFFFF",
                "panel": "#FFFFFF",
                "card": "#EAF0F8",
                "border": "#D6DFEB",
                "text": "#172033",
                "muted": "#66758C",
                "blue": "#155EEF",
                "green": "#07875D",
            }
        else:
            self.colors = {
                "bg": "#08111F",
                "sidebar": "#0B1628",
                "panel": "#0D1B30",
                "card": "#10213A",
                "border": "#1D3556",
                "text": "#E8F0FF",
                "muted": "#9AB0D0",
                "blue": "#155EEF",
                "green": "#27D9A0",
            }

    def change_theme(self, choice):
        if self.theme_rebuilding:
            return

        self.selected_theme = choice
        self.set_colors()

        # Custom colors require rebuilding the widgets.
        # Preserve the conversation and Files panel state.
        saved_messages = list(self.messages)
        was_files_visible = self.files_visible

        self.theme_rebuilding = True
        self.hide_thinking()
        self.configure(fg_color=self.colors["bg"])

        for widget in self.winfo_children():
            widget.destroy()

        self.files_visible = False
        self.create_layout()

        for message in saved_messages:
            self.add_message(
                message["role"],
                message["content"]
            )

        if was_files_visible:
            self.toggle_files()

        self.refresh_files()
        self.theme_rebuilding = False

    # ==================================================
    # MAIN LAYOUT
    # ==================================================

    def create_layout(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)
        self.grid_rowconfigure(0, weight=1)

        self.create_sidebar()

        self.main_area = ctk.CTkFrame(
            self,
            fg_color=self.colors["bg"],
            corner_radius=0
        )
        self.main_area.grid(
            row=0, column=1,
            sticky="nsew",
            padx=5, pady=8
        )

        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_rowconfigure(1, weight=1)

        self.create_header()
        self.create_chat_area()
        self.create_composer()
        self.create_files_panel()

    # ==================================================
    # SIDEBAR
    # ==================================================

    def create_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self,
            width=220,
            fg_color=self.colors["sidebar"],
            corner_radius=0
        )
        self.sidebar.grid(
            row=0, column=0,
            sticky="nsew",
            padx=(0, 5)
        )
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.sidebar,
            text="✦  AI LOCAL AGENT",
            font=("Segoe UI", 18, "bold"),
            text_color=self.colors["text"]
        ).grid(
            row=0, column=0,
            padx=14, pady=(25, 30),
            sticky="w"
        )

        self.nav_button("＋  New Chat", self.new_chat, 1)
        self.nav_button("▤  Files", self.toggle_files, 2)
        self.nav_button("⚙  Settings", self.show_settings, 3)

        ctk.CTkLabel(
            self.sidebar,
            text="RECENT ACTIVITY",
            text_color=self.colors["muted"],
            font=("Segoe UI", 11, "bold")
        ).grid(
            row=4, column=0,
            padx=18, pady=(28, 10),
            sticky="w"
        )

        ctk.CTkLabel(
            self.sidebar,
            text="Current conversation",
            text_color=self.colors["muted"],
            font=("Segoe UI", 12),
            anchor="w"
        ).grid(
            row=5, column=0,
            padx=18, pady=4,
            sticky="ew"
        )

        ctk.CTkLabel(
            self.sidebar,
            text="THEME",
            text_color=self.colors["muted"],
            font=("Segoe UI", 11, "bold")
        ).grid(
            row=6, column=0,
            padx=18, pady=(28, 8),
            sticky="w"
        )

        self.theme_choice = ctk.CTkOptionMenu(
            self.sidebar,
            values=["Dark", "Light", "System"],
            command=self.change_theme,
            fg_color=self.colors["card"],
            button_color=self.colors["blue"],
            button_hover_color="#3478FF",
            text_color=self.colors["text"]
        )
        self.theme_choice.set(self.selected_theme)
        self.theme_choice.grid(
            row=7, column=0,
            padx=14, pady=4,
            sticky="ew"
        )

        # Voice assistant button in the sidebar.
        ctk.CTkButton(
            self.sidebar,
            text="🎙  Voice Assistant",
            command=self.voice_input,
            height=42,
            fg_color=self.colors["card"],
            hover_color=self.colors["border"],
            text_color=self.colors["text"]
        ).grid(
            row=8, column=0,
            padx=12, pady=(22, 8),
            sticky="ew"
        )

        self.sidebar.grid_rowconfigure(9, weight=1)

        ctk.CTkLabel(
            self.sidebar,
            text="●  Local mode\n    Model connection pending",
            text_color=self.colors["green"],
            font=("Segoe UI", 11),
            justify="left",
            anchor="w"
        ).grid(
            row=10, column=0,
            padx=16, pady=18,
            sticky="sw"
        )

    def nav_button(self, text, command, row):
        ctk.CTkButton(
            self.sidebar,
            text=text,
            command=command,
            anchor="w",
            height=42,
            fg_color="transparent",
            hover_color=self.colors["card"],
            text_color=self.colors["text"]
        ).grid(
            row=row, column=0,
            padx=12, pady=4,
            sticky="ew"
        )

    # ==================================================
    # HEADER
    # ==================================================

    def create_header(self):
        self.header = ctk.CTkFrame(
            self.main_area,
            fg_color="transparent",
            height=58
        )
        self.header.grid(
            row=0, column=0,
            sticky="ew",
            padx=12
        )
        self.header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.header,
            text="Chat",
            font=("Segoe UI", 23, "bold"),
            text_color=self.colors["text"]
        ).grid(
            row=0, column=0,
            sticky="w", pady=10
        )

        self.files_toggle = ctk.CTkButton(
            self.header,
            text="▤  Files  ▸",
            width=105,
            command=self.toggle_files,
            fg_color=self.colors["card"],
            hover_color=self.colors["blue"],
            text_color=self.colors["text"]
        )
        self.files_toggle.grid(
            row=0, column=1,
            padx=6
        )

    # ==================================================
    # CHAT AREA
    # ==================================================

    def create_chat_area(self):
        self.chat_frame = ctk.CTkScrollableFrame(
            self.main_area,
            fg_color="transparent",
            scrollbar_button_color=self.colors["border"]
        )
        self.chat_frame.grid(
            row=1, column=0,
            sticky="nsew",
            padx=10, pady=5
        )
        self.chat_frame.grid_columnconfigure(0, weight=1)

    def show_welcome(self):
        self.add_message(
            "AI LOCAL AGENT",
            "Hello! How can I help you today?\n\n"
            "Ask a question, get help with code, or request a file."
        )

    def add_message(self, sender, content):
        row = ctk.CTkFrame(
            self.chat_frame,
            fg_color="transparent"
        )
        row.pack(fill="x", padx=4, pady=8)

        is_user = sender == "You"

        bubble = ctk.CTkFrame(
            row,
            fg_color=(
                self.colors["blue"]
                if is_user else self.colors["card"]
            ),
            corner_radius=14
        )
        bubble.pack(
            anchor="e" if is_user else "w",
            padx=(70, 0) if is_user else (0, 70)
        )

        ctk.CTkLabel(
            bubble,
            text=sender,
            font=("Segoe UI", 11, "bold"),
            text_color=(
                "#FFFFFF" if is_user else self.colors["green"]
            ),
            anchor="w"
        ).pack(
            anchor="w", padx=14, pady=(10, 2)
        )

        ctk.CTkLabel(
            bubble,
            text=content,
            font=("Segoe UI", 14),
            text_color="#FFFFFF" if is_user else self.colors["text"],
            justify="left",
            anchor="w",
            wraplength=620
        ).pack(
            anchor="w", padx=14, pady=(2, 12)
        )

        self.after(60, self.scroll_to_bottom)

    def scroll_to_bottom(self):
        if hasattr(self, "chat_frame"):
            self.chat_frame._parent_canvas.yview_moveto(1.0)

    # ==================================================
    # THINKING INDICATOR
    # ==================================================

    def show_thinking(self):
        self.hide_thinking()

        self.thinking_frame = ctk.CTkFrame(
            self.chat_frame,
            fg_color=self.colors["card"],
            corner_radius=12
        )
        self.thinking_frame.pack(
            anchor="w", padx=4, pady=8
        )

        self.thinking_label = ctk.CTkLabel(
            self.thinking_frame,
            text="Thinking...",
            font=("Segoe UI", 14),
            text_color=self.colors["muted"]
        )
        self.thinking_label.pack(
            padx=14, pady=10
        )

        self.thinking_active = True
        self.thinking_dots = 0
        self.animate_thinking()

    def animate_thinking(self):
        if not self.thinking_active:
            return

        if not self.thinking_frame or not self.thinking_frame.winfo_exists():
            return

        self.thinking_dots = (self.thinking_dots + 1) % 4
        self.thinking_label.configure(
            text="Thinking" + "." * self.thinking_dots
        )

        self.after(400, self.animate_thinking)

    def hide_thinking(self):
        self.thinking_active = False

        frame = getattr(self, "thinking_frame", None)

        if frame is not None:
            try:
                frame.destroy()
            except Exception:
                pass

        self.thinking_frame = None

    # ==================================================
    # CHATGPT-STYLE COMPOSER
    # ==================================================

    def create_composer(self):
        self.composer = ctk.CTkFrame(
            self.main_area,
            fg_color=self.colors["panel"],
            corner_radius=24,
            border_width=1,
            border_color=self.colors["border"]
        )
        self.composer.grid(
            row=2, column=0,
            sticky="ew",
            padx=12, pady=(6, 12)
        )

        self.composer.grid_columnconfigure(1, weight=1)

        self.attach_button = ctk.CTkButton(
            self.composer,
            text="＋",
            width=40, height=40,
            corner_radius=20,
            font=("Segoe UI", 23),
            fg_color="transparent",
            hover_color=self.colors["card"],
            text_color=self.colors["text"],
            command=self.attach_file
        )
        self.attach_button.grid(
            row=0, column=0,
            padx=(8, 2), pady=8
        )

        self.message_input = ctk.CTkTextbox(
            self.composer,
            height=48,
            wrap="word",
            fg_color="transparent",
            border_width=0,
            text_color=self.colors["muted"],
            font=("Segoe UI", 14)
        )
        self.message_input.grid(
            row=0, column=1,
            sticky="ew",
            padx=4, pady=8
        )

        self.message_input.insert("1.0", "Ask anything")

        self.message_input.bind(
            "<FocusIn>", self.clear_placeholder
        )
        self.message_input.bind(
            "<FocusOut>", self.restore_placeholder
        )
        self.message_input.bind(
            "<Control-Return>", self.send_message
        )

        self.mic_button = ctk.CTkButton(
            self.composer,
            text="🎙",
            width=42, height=42,
            corner_radius=21,
            font=("Segoe UI Emoji", 18),
            fg_color="transparent",
            hover_color=self.colors["card"],
            text_color=self.colors["text"],
            command=self.voice_input
        )
        self.mic_button.grid(
            row=0, column=2,
            padx=3, pady=8
        )

        self.send_button = ctk.CTkButton(
            self.composer,
            text="↑",
            width=42, height=42,
            corner_radius=21,
            font=("Segoe UI", 24, "bold"),
            fg_color=self.colors["blue"],
            hover_color="#3478FF",
            command=self.send_message
        )
        self.send_button.grid(
            row=0, column=3,
            padx=(3, 9), pady=8
        )

    def clear_placeholder(self, event=None):
        current = self.message_input.get(
            "1.0", "end"
        ).strip()

        if current == self.placeholder:
            self.message_input.delete("1.0", "end")
            self.message_input.configure(
                text_color=self.colors["text"]
            )

    def restore_placeholder(self, event=None):
        current = self.message_input.get(
            "1.0", "end"
        ).strip()

        if not current:
            self.message_input.insert(
                "1.0", self.placeholder
            )
            self.message_input.configure(
                text_color=self.colors["muted"]
            )

    def send_message(self, event=None):
        prompt = self.message_input.get(
            "1.0", "end"
        ).strip()

        if prompt == self.placeholder or not prompt:
            return "break"

        if self.busy:
            return "break"

        self.busy = True

        self.message_input.delete("1.0", "end")
        self.message_input.configure(
            text_color=self.colors["text"]
        )

        self.messages.append({
            "role": "You",
            "content": prompt
        })

        self.add_message("You", prompt)
        self.send_button.configure(state="disabled")
        self.show_thinking()

        # Temporary demonstration response.
        # Connect Ollama in the next backend step.
        self.after(
            1200,
            lambda: self.finish_demo_response(prompt)
        )

        return "break"

    def finish_demo_response(self, prompt):
        if not self.winfo_exists():
            return

        self.hide_thinking()
        self.busy = False

        response = (
            "Your message was received successfully.\n\n"
            "The Ollama model is not connected yet, so this is "
            "a demonstration response. Once we connect the model, "
            "AI LOCAL AGENT will generate real answers and can "
            "create files from your instructions."
        )

        self.messages.append({
            "role": "AI LOCAL AGENT",
            "content": response
        })

        self.add_message("AI LOCAL AGENT", response)
        self.send_button.configure(state="normal")
        self.message_input.focus_set()

    def new_chat(self):
        if self.busy:
            self.hide_thinking()
            self.busy = False
            self.send_button.configure(state="normal")

        for widget in self.chat_frame.winfo_children():
            widget.destroy()

        self.messages.clear()
        self.attached_files.clear()
        self.show_welcome()

    def export_chat(self):
        if not self.messages:
            messagebox.showinfo(
                "Export Chat", "There are no messages to export."
            )
            return

        path = filedialog.asksaveasfilename(
            title="Export conversation",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")]
        )

        if not path:
            return

        with open(path, "w", encoding="utf-8") as file:
            for item in self.messages:
                file.write(
                    f"{item['role']}: {item['content']}\n\n"
                )

        messagebox.showinfo(
            "Export Chat", f"Conversation saved to:\n{path}"
        )

    # ==================================================
    # ATTACHMENTS AND VOICE
    # ==================================================

    def attach_file(self):
        path = filedialog.askopenfilename(
            title="Choose a file to attach"
        )

        if path:
            self.attached_files.append(path)
            messagebox.showinfo(
                "File selected",
                f"Selected:\n{path}\n\n"
                "The file has been selected. Reading its contents "
                "and sending them to the AI will be connected later."
            )

    def voice_input(self):
        messagebox.showinfo(
            "Voice Assistant",
            "The microphone button is visible and ready for "
            "integration. Speech recognition has not been "
            "connected yet."
        )

    # ==================================================
    # GENERATED FILES PANEL
    # ==================================================

    def create_files_panel(self):
        self.files_panel = ctk.CTkFrame(
            self,
            width=320,
            fg_color=self.colors["sidebar"],
            corner_radius=12,
            border_width=1,
            border_color=self.colors["border"]
        )

        self.files_panel.grid_propagate(False)
        self.files_panel.grid_columnconfigure(0, weight=1)
        self.files_panel.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(
            self.files_panel,
            fg_color="transparent"
        )
        top.grid(
            row=0, column=0,
            sticky="ew", padx=12, pady=12
        )
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            top,
            text="Generated Files",
            font=("Segoe UI", 18, "bold"),
            text_color=self.colors["text"]
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            top,
            text="✕",
            width=32,
            command=self.toggle_files,
            fg_color="transparent",
            hover_color=self.colors["card"],
            text_color=self.colors["text"]
        ).grid(row=0, column=1)

        ctk.CTkLabel(
            self.files_panel,
            text="Only files in the agent's generated-files folder.",
            font=("Segoe UI", 10),
            text_color=self.colors["muted"],
            wraplength=280,
            justify="left"
        ).grid(
            row=1, column=0,
            sticky="ew", padx=12, pady=(0, 8)
        )

        self.files_list = ctk.CTkScrollableFrame(
            self.files_panel,
            fg_color="transparent"
        )
        self.files_list.grid(
            row=2, column=0,
            sticky="nsew", padx=8, pady=4
        )

        self.refresh_files()

    def toggle_files(self):
        if self.files_visible:
            self.files_panel.grid_forget()
            self.files_visible = False
            self.files_toggle.configure(text="▤  Files  ▸")
        else:
            self.files_panel.grid(
                row=0, column=2,
                sticky="nsew",
                padx=(0, 8), pady=8
            )
            self.files_visible = True
            self.files_toggle.configure(text="▤  Files  ◂")
            self.refresh_files()

    def refresh_files(self):
        if not hasattr(self, "files_list"):
            return

        for widget in self.files_list.winfo_children():
            widget.destroy()

        try:
            files = get_agent_files()
        except Exception as exc:
            ctk.CTkLabel(
                self.files_list,
                text=f"Could not load generated files:\n{exc}",
                text_color=self.colors["muted"],
                wraplength=250
            ).pack(padx=10, pady=20)
            return

        if not files:
            ctk.CTkLabel(
                self.files_list,
                text="No generated files yet.\n\n"
                     "Files created by the agent will appear here.",
                text_color=self.colors["muted"],
                justify="center",
                wraplength=250
            ).pack(padx=12, pady=25)
            return

        for item in files:
            self.add_file_card(item)

    def add_file_card(self, item):
        card = ctk.CTkFrame(
            self.files_list,
            fg_color=self.colors["card"],
            corner_radius=12
        )
        card.pack(fill="x", padx=4, pady=6)

        ctk.CTkLabel(
            card,
            text=f"📄  {item['name']}",
            font=("Segoe UI", 13, "bold"),
            text_color=self.colors["text"],
            anchor="w",
            wraplength=250
        ).pack(
            fill="x", padx=10, pady=(10, 4)
        )

        # Full location directly below the filename.
        ctk.CTkLabel(
            card,
            text=item["path"],
            font=("Segoe UI", 10),
            text_color=self.colors["muted"],
            anchor="w",
            justify="left",
            wraplength=260
        ).pack(
            fill="x", padx=10, pady=3
        )

        actions = ctk.CTkFrame(
            card, fg_color="transparent"
        )
        actions.pack(
            fill="x", padx=8, pady=(5, 8)
        )

        ctk.CTkButton(
            actions,
            text="Copy Path",
            width=95,
            command=lambda p=item["path"]: self.copy_path(p)
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            actions,
            text="Open Folder",
            width=105,
            command=lambda p=item["path"]: self.open_folder(p)
        ).pack(side="left", padx=2)

    def copy_path(self, path):
        self.clipboard_clear()
        self.clipboard_append(path)
        self.update()
        messagebox.showinfo(
            "Copied", "The full file path was copied."
        )

    def open_folder(self, path):
        try:
            open_file_location(path)
        except Exception as exc:
            messagebox.showerror(
                "Open Folder", str(exc)
            )

    # ==================================================
    # SETTINGS
    # ==================================================

    def show_settings(self):
        messagebox.showinfo(
            "Settings",
            "AI LOCAL AGENT\n\n"
            "Theme: Choose Dark, Light, or System in the sidebar.\n"
            "Files: Open the Files panel from the header or sidebar.\n"
            "Local model: Ollama integration is the next step.\n"
            "Voice: Speech recognition is not connected yet."
        )


if __name__ == "__main__":
    app = AILocalAgent()
    app.mainloop()
