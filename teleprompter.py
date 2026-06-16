import tkinter as tk
import ctypes
import sys
import keyboard
import queue
import threading
import re

# --- Windows API Constants ---
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
WDA_EXCLUDEFROMCAPTURE = 17
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000


class StealthTeleprompter:
    def __init__(
        self,
        root,
        command_queue: queue.Queue,
        config: dict,
        on_analyze_callback=None,
        on_capture_callback=None,
    ):
        self.root = root
        self.q = command_queue
        self.config = config
        self.on_analyze = on_analyze_callback
        self.on_capture = on_capture_callback
        self.key_buffer = []

        self.is_visible = True
        self.is_dark_mode = True
        self.is_intangible = False
        self.current_model = "fast"

        self.history = ["[ Awaiting Live Sync... ]"]
        self.history_idx = 0

        self._drag_start_x = 0
        self._drag_start_y = 0
        self._resize_start_x = 0
        self._resize_start_y = 0
        self._resize_start_w = 0
        self._resize_start_h = 0

        self._initialize_ui()
        self._apply_stealth_mechanics()
        self._bind_events()

        self.root.after(50, self._process_queue)

    def _process_queue(self):
        try:
            while True:
                msg = self.q.get_nowait()
                action = msg.get("action")

                if action == "PROMPTER_SYNC":
                    text = msg.get("text", "")
                    if text != self.history[-1]:
                        self.history.append(text)
                        self.history_idx = len(self.history) - 1
                    self._render_markdown(text)
                elif action == "PROMPTER_CLEAR":
                    self._render_markdown("")
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
                elif action == "PROMPTER_CONFIG":
                    self.config = msg.get("config", self.config)
                    self._apply_config_ui()
                elif action == "PROMPTER_BUFFER_UPDATE":
                    count = msg.get("count", 0)
                    self.btn_plus.configure(text=f"➕ ({count})" if count > 0 else "➕")

        except queue.Empty:
            pass

        self.root.after(50, self._process_queue)

    def _initialize_ui(self):
        self.root.geometry("650x400")
        self.root.attributes("-toolwindow", True)
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 0.85)
        self.root.attributes("-topmost", True)

        # --- TOP CONTROL BAR ---
        self.top_bar = tk.Frame(self.root, height=35)
        self.top_bar.pack(side="top", fill="x")
        self.top_bar.pack_propagate(False)

        # Left Group: Nav & Model Toggle
        self.btn_prev = tk.Button(
            self.top_bar,
            text="◄",
            font=("Arial", 10, "bold"),
            bd=0,
            cursor="hand2",
            command=self._history_prev,
        )
        self.btn_prev.pack(side="left", padx=(5, 2), pady=5)

        self.btn_next = tk.Button(
            self.top_bar,
            text="►",
            font=("Arial", 10, "bold"),
            bd=0,
            cursor="hand2",
            command=self._history_next,
        )
        self.btn_next.pack(side="left", padx=(0, 5), pady=5)

        # Removed the invalid 'title' argument here
        self.btn_model = tk.Button(
            self.top_bar,
            text="⚡",
            font=("Arial", 10),
            bd=0,
            cursor="hand2",
            command=self._toggle_model,
        )
        self.btn_model.pack(side="left", padx=2, pady=5)

        # Right Group: Utilities (Packed right-to-left)
        self.btn_hide = tk.Button(
            self.top_bar,
            text="✖",
            font=("Arial", 10),
            bd=0,
            cursor="hand2",
            command=self._hide,
        )
        self.btn_hide.pack(side="right", padx=(2, 5), pady=5)

        self.btn_theme = tk.Button(
            self.top_bar,
            text="🌓",
            font=("Arial", 10),
            bd=0,
            cursor="hand2",
            command=self._toggle_theme,
        )
        self.btn_theme.pack(side="right", padx=2, pady=5)

        self.btn_analyze = tk.Button(
            self.top_bar,
            text="✨",
            font=("Arial", 10),
            bd=0,
            cursor="hand2",
            command=self._trigger_analyze,
        )
        self.btn_analyze.pack(side="right", padx=2, pady=5)

        # Right Group: The 4 Presets
        self.preset_btns = []
        for i in reversed(range(4)):
            btn = tk.Button(
                self.top_bar, text="?", font=("Arial", 10), bd=0, cursor="hand2"
            )
            btn.pack(side="right", padx=1, pady=5)
            self.preset_btns.insert(0, btn)  # Maintain visual left-to-right 0-3 order

        # Right Group: Batch Capture
        self.btn_plus = tk.Button(
            self.top_bar,
            text="➕",
            font=("Arial", 10),
            bd=0,
            cursor="hand2",
            command=self._trigger_capture,
        )
        self.btn_plus.pack(side="right", padx=(2, 5), pady=5)

        # Center: Drag Handle (Updated Text)
        self.drag_handle = tk.Label(
            self.top_bar,
            text="",
            font=("Arial", 8, "bold"),
            cursor="fleur",
        )
        self.drag_handle.pack(side="left", fill="both", expand=True)

        # --- MAIN CONTENT AREA ---
        self.content_frame = tk.Frame(self.root)
        self.content_frame.pack(side="top", fill="both", expand=True, padx=15, pady=10)

        self.text_area = tk.Text(
            self.content_frame,
            wrap="word",
            font=("Segoe UI", 12),
            bd=0,
            highlightthickness=0,
            cursor="arrow",
        )
        self.text_area.pack(side="left", fill="both", expand=True)

        self.text_area.tag_configure(
            "h1", font=("Segoe UI", 18, "bold"), spacing1=10, spacing3=5
        )
        self.text_area.tag_configure(
            "h2", font=("Segoe UI", 16, "bold"), spacing1=8, spacing3=4
        )
        self.text_area.tag_configure(
            "h3", font=("Segoe UI", 14, "bold"), spacing1=5, spacing3=2
        )
        self.text_area.tag_configure("bold", font=("Segoe UI", 12, "bold"))
        self.text_area.tag_configure("italic", font=("Segoe UI", 12, "italic"))
        self.text_area.tag_configure(
            "code", font=("Consolas", 11), background="#2d2d2d", foreground="#a6e22e"
        )
        self.text_area.tag_configure("bullet", font=("Segoe UI", 14, "bold"))

        # --- RESIZE GRIP ---
        self.resize_grip = tk.Label(
            self.root, text="◢", font=("Arial", 10), cursor="size_nw_se"
        )
        self.resize_grip.place(relx=1.0, rely=1.0, anchor="se")

        self._apply_config_ui()
        self._apply_colors()
        self._render_markdown(self.history[0])

    def _apply_config_ui(self):
        presets = self.config.get("presets", [])
        for i, btn in enumerate(self.preset_btns):
            if i < len(presets):
                btn.configure(text=presets[i]["emoji"])
                # Captures the variable securely in the lambda closure
                btn.configure(
                    command=lambda p=presets[i]["text"]: self._trigger_analyze(p)
                )
            else:
                btn.configure(text="")
                btn.configure(command=lambda: None)

    def _render_markdown(self, text):
        self.text_area.config(state="normal")
        self.text_area.delete(1.0, tk.END)

        lines = text.split("\n")
        in_code_block = False

        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                self.text_area.insert(tk.END, line + "\n", "code")
                continue

            if line.startswith("# "):
                self.text_area.insert(tk.END, line[2:] + "\n", "h1")
                continue
            elif line.startswith("## "):
                self.text_area.insert(tk.END, line[3:] + "\n", "h2")
                continue
            elif line.startswith("### "):
                self.text_area.insert(tk.END, line[4:] + "\n", "h3")
                continue

            is_bullet = False
            if line.strip().startswith("- ") or line.strip().startswith("* "):
                self.text_area.insert(tk.END, "  •  ", "bullet")
                line = line.strip()[2:]
                is_bullet = True

            tokens = re.split(r"(\*\*.*?\*\*|\*.*?\*|_.*?_)", line)
            for token in tokens:
                if token.startswith("**") and token.endswith("**"):
                    self.text_area.insert(tk.END, token[2:-2], "bold")
                elif (token.startswith("*") and token.endswith("*")) or (
                    token.startswith("_") and token.endswith("_")
                ):
                    self.text_area.insert(tk.END, token[1:-1], "italic")
                else:
                    self.text_area.insert(tk.END, token)

            self.text_area.insert(tk.END, "\n")

        self.text_area.config(state="disabled")
        self.text_area.yview_moveto(1.0)

    def _history_prev(self):
        if self.history_idx > 0:
            self.history_idx -= 1
            self._render_markdown(self.history[self.history_idx])

    def _history_next(self):
        if self.history_idx < len(self.history) - 1:
            self.history_idx += 1
            self._render_markdown(self.history[self.history_idx])

    def _toggle_model(self):
        if self.current_model == "fast":
            self.current_model = "deep"
            self.btn_model.configure(text="🧠")
        else:
            self.current_model = "fast"
            self.btn_model.configure(text="⚡")

    def _trigger_capture(self):
        if self.on_capture:
            threading.Thread(target=self.on_capture, daemon=True).start()

    def _trigger_analyze(self, prompt_text=None):
        if prompt_text is None:
            prompt_text = self.config.get(
                "auto_prompt", "Analyze this screen and provide key takeaways."
            )
        if self.on_analyze:
            threading.Thread(
                target=self.on_analyze,
                args=(prompt_text, self.current_model),
                daemon=True,
            ).start()

    def _apply_colors(self):
        if self.is_intangible:
            self.text_area.config(fg="#00FF00")
            return

        bg_color, fg_color, top_bg = (
            ("black", "#E0E0E0", "#111111")
            if self.is_dark_mode
            else ("#F5F5F5", "#111111", "#E0E0E0")
        )

        self.root.configure(bg=bg_color)
        self.content_frame.configure(bg=bg_color)
        self.text_area.configure(bg=bg_color, fg=fg_color, insertbackground=bg_color)

        self.top_bar.configure(bg=top_bg)
        self.drag_handle.configure(bg=top_bg, fg=fg_color)
        self.resize_grip.configure(bg=bg_color, fg=fg_color)

        buttons = [
            self.btn_prev,
            self.btn_next,
            self.btn_model,
            self.btn_plus,
            self.btn_analyze,
            self.btn_theme,
            self.btn_hide,
        ] + self.preset_btns
        for btn in buttons:
            btn.configure(
                bg=top_bg,
                fg=fg_color,
                activebackground=bg_color,
                activeforeground=fg_color,
            )

    def _toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self._apply_colors()

    def _apply_stealth_mechanics(self):
        self.root.update()
        self.hwnd = int(self.root.wm_frame(), 16)
        if sys.platform == "win32":
            ctypes.windll.user32.SetWindowDisplayAffinity(
                self.hwnd, WDA_EXCLUDEFROMCAPTURE
            )
            ex_style = ctypes.windll.user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                self.hwnd, GWL_EXSTYLE, ex_style | WS_EX_NOACTIVATE
            )

    def _bind_events(self):
        self.drag_handle.bind("<Button-1>", self._on_drag_start)
        self.drag_handle.bind("<B1-Motion>", self._on_drag_motion)
        self.resize_grip.bind("<Button-1>", self._on_resize_start)
        self.resize_grip.bind("<B1-Motion>", self._on_resize_motion)

        self.text_area.bind("<MouseWheel>", self._on_mousewheel)
        self.drag_handle.bind("<MouseWheel>", self._on_mousewheel)

        self.root.bind("<Escape>", self._shutdown)
        keyboard.hook(self._on_global_key)

    def _on_drag_start(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag_motion(self, event):
        x = self.root.winfo_x() - self._drag_start_x + event.x
        y = self.root.winfo_y() - self._drag_start_y + event.y
        self.root.geometry(f"+{x}+{y}")

    def _on_resize_start(self, event):
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_start_w = self.root.winfo_width()
        self._resize_start_h = self.root.winfo_height()

    def _on_resize_motion(self, event):
        new_w = max(350, self._resize_start_w + (event.x_root - self._resize_start_x))
        new_h = max(200, self._resize_start_h + (event.y_root - self._resize_start_y))
        self.root.geometry(f"{new_w}x{new_h}")

    def _on_mousewheel(self, event):
        self.text_area.yview_scroll(int(-1 * (event.delta / 120)), "units")

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
