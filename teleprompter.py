import tkinter as tk
import ctypes
import sys
import keyboard
import queue

# --- Windows API Constants ---
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
WDA_EXCLUDEFROMCAPTURE = 17
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000  # <- The Holy Grail of non-interrupting overlays


class StealthTeleprompter:
    """
    A daemonized Tkinter instance that polls a thread-safe queue for live
    updates from the ASGI web server, ensuring no GIL deadlocks.
    """

    def __init__(self, root, command_queue: queue.Queue):
        self.root = root
        self.q = command_queue
        self.key_buffer = []

        self.is_visible = True
        self.is_dark_mode = True
        self.is_intangible = False
        self._drag_start_x = 0
        self._drag_start_y = 0

        self._initialize_ui()
        self._apply_stealth_mechanics()
        self._bind_events()

        # Start the queue polling loop (executes strictly on the Tkinter thread)
        self.root.after(50, self._process_queue)

    def _process_queue(self):
        """Pulls network commands from the web server and updates the UI state."""
        try:
            while True:
                msg = self.q.get_nowait()
                action = msg.get("action")

                if action == "PROMPTER_SYNC":
                    self.content_label.configure(text=msg.get("text", ""))
                elif action == "PROMPTER_CLEAR":
                    self.content_label.configure(text="")
                elif action == "PROMPTER_HIDE":
                    self._hide()
                elif action == "PROMPTER_SHOW":
                    self._reveal()
                elif action == "PROMPTER_LOCK":
                    self._make_intangible()
                elif action == "PROMPTER_UNLOCK":
                    self._make_solid()
                elif action == "PROMPTER_THEME":
                    self._toggle_theme()

        except queue.Empty:
            pass

        self.root.after(50, self._process_queue)

    def _initialize_ui(self):
        self.root.geometry("550x250")
        self.root.attributes("-toolwindow", True)
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 0.80)
        self.root.attributes("-topmost", True)

        self.theme_btn = tk.Button(
            self.root,
            text="🌓",
            font=("Arial", 12),
            bd=0,
            cursor="hand2",
            command=self._toggle_theme,
        )
        self.theme_btn.place(relx=0.98, rely=0.02, anchor="ne")

        self.content_label = tk.Label(
            self.root,
            text="[ Awaiting Live Sync... ]",
            font=("Georgia", 14, "italic"),
            justify="center",
            wraplength=500,
        )
        self.content_label.pack(expand=True, padx=20, pady=20)

        self.quit_label = tk.Label(
            self.root,
            text="[Click and press ESC to close] | zxcv/vcxz = Intangibility | asdf/fdsa = Visibility",
            font=("Arial", 7),
        )
        self.quit_label.pack(side="bottom", pady=5)
        self._apply_colors()

    def _apply_colors(self):
        if self.is_intangible:
            self.content_label.configure(fg="#00FF00")
            return

        bg_color, fg_color, btn_active = (
            ("black", "#E0E0E0", "#333333")
            if self.is_dark_mode
            else ("#F5F5F5", "#111111", "#CCCCCC")
        )

        self.root.configure(bg=bg_color)
        self.content_label.configure(bg=bg_color, fg=fg_color)
        self.quit_label.configure(bg=bg_color, fg=fg_color)
        self.theme_btn.configure(
            bg=bg_color,
            fg=fg_color,
            activebackground=btn_active,
            activeforeground=fg_color,
        )

    def _toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self._apply_colors()

    def _apply_stealth_mechanics(self):
        self.root.update()
        self.hwnd = int(self.root.wm_frame(), 16)
        if sys.platform == "win32":
            # 1. Exclude from screen capture
            ctypes.windll.user32.SetWindowDisplayAffinity(
                self.hwnd, WDA_EXCLUDEFROMCAPTURE
            )
            # 2. Prevent window from stealing focus when physically clicked
            ex_style = ctypes.windll.user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                self.hwnd, GWL_EXSTYLE, ex_style | WS_EX_NOACTIVATE
            )

    def _bind_events(self):
        self.root.bind("<Button-1>", self._on_drag_start)
        self.root.bind("<B1-Motion>", self._on_drag_motion)
        self.root.bind("<Escape>", self._shutdown)
        keyboard.hook(self._on_global_key)

    def _on_drag_start(self, event):
        if event.widget == self.theme_btn:
            return
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag_motion(self, event):
        if event.widget == self.theme_btn:
            return
        x = self.root.winfo_x() - self._drag_start_x + event.x
        y = self.root.winfo_y() - self._drag_start_y + event.y
        self.root.geometry(f"+{x}+{y}")

    def _on_global_key(self, event):
        if event.event_type == keyboard.KEY_DOWN and len(event.name) == 1:
            self.key_buffer.append(event.name.lower())
            if len(self.key_buffer) > 4:
                self.key_buffer.pop(0)
            seq = "".join(self.key_buffer)

            if seq == "asdf" and not self.is_visible:
                self.root.after(0, self._reveal)
            elif seq == "fdsa" and self.is_visible:
                self.root.after(0, self._hide)
            elif seq == "zxcv" and self.is_visible and not self.is_intangible:
                self.root.after(0, self._make_intangible)
            elif seq == "vcxz" and self.is_visible and self.is_intangible:
                self.root.after(0, self._make_solid)

    def _reveal(self):
        if sys.platform == "win32":
            ctypes.windll.user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            self.is_visible = True

    def _hide(self):
        if sys.platform == "win32":
            ctypes.windll.user32.ShowWindow(self.hwnd, SW_HIDE)
            self.is_visible = False

    def _make_intangible(self):
        if sys.platform == "win32":
            ex_style = (
                ctypes.windll.user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
                | WS_EX_TRANSPARENT
            )
            ctypes.windll.user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, ex_style)
            self.is_intangible = True
            self._apply_colors()

    def _make_solid(self):
        if sys.platform == "win32":
            ex_style = (
                ctypes.windll.user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
                & ~WS_EX_TRANSPARENT
            )
            ctypes.windll.user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, ex_style)
            self.is_intangible = False
            self._apply_colors()

    def _shutdown(self, event=None):
        keyboard.unhook_all()
        self.root.destroy()
