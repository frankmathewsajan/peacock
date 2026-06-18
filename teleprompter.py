import tkinter as tk
import ctypes
import sys
import queue
import threading
import json
import os
import re
import gc  # Aggressive memory management

# --- Windows API Constants ---
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
WDA_EXCLUDEFROMCAPTURE = 17
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080

STATE_FILE = "peacock_state.json"


class StealthTeleprompter:
    def __init__(
        self,
        root,
        command_queue: queue.Queue,
        config: dict,
        on_analyze_callback=None,
        on_capture_callback=None,
        on_network_toggle=None,
    ):
        self.root = root
        self.q = command_queue
        self.config = config
        self.on_analyze = on_analyze_callback
        self.on_capture = on_capture_callback
        self.on_network_toggle = on_network_toggle

        self.current_model = "fast"
        self.is_server_online = True
        self.saved_state = self._load_state()

        self.is_dark_mode = self.saved_state.get("is_dark_mode", True)
        self.is_minimized = self.saved_state.get("is_minimized", False)
        self.history = self.saved_state.get("history", ["-> <3"])
        self.history_idx = self.saved_state.get("history_idx", len(self.history) - 1)

        self._initialize_ui()
        self._initialize_icon_window()
        self._apply_stealth_mechanics(self.root)
        self._bind_events()

        self._render_markdown(self.history[self.history_idx])
        self._apply_colors()

        self.root.after(50, self._apply_initial_visibility)
        self.root.after(100, self._process_queue)

    def _load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_state(self):
        state = {
            "main_geo": self.root.geometry(),
            "icon_geo": self.icon_root.geometry(),
            "is_dark_mode": self.is_dark_mode,
            "is_minimized": self.is_minimized,
            "history": self.history[-50:],
            "history_idx": self.history_idx,
        }
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(state, f)
        except Exception:
            pass

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
                        self._save_state()
                    self._render_markdown(text)
                elif action == "PROMPTER_CLEAR":
                    self._render_markdown("")
                elif action == "PROMPTER_HIDE":
                    self._minimize_to_icon()
                elif action == "PROMPTER_SHOW":
                    self._restore_from_icon()
                elif action == "PROMPTER_THEME":
                    self._toggle_theme()
                elif action == "PROMPTER_CONFIG":
                    self.config = msg.get("config", self.config)
                    self._rebuild_presets()
                elif action == "PROMPTER_BUFFER_UPDATE":
                    self._update_buffer_count(msg.get("count", 0))
        except queue.Empty:
            pass
        self.root.after(50, self._process_queue)

    def _initialize_ui(self):
        self.root.geometry(self.saved_state.get("main_geo", "650x400+200+200"))
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#111111")

        self.top_bar = tk.Frame(self.root, height=35, bg="#111111")
        self.top_bar.pack(side="top", fill="x")
        self.top_bar.pack_propagate(False)

        # --- LEFT SUB-FRAME ---
        self.left_frame = tk.Frame(self.top_bar, bg="#111111")
        self.left_frame.pack(side="left", fill="y")

        tk.Button(
            self.left_frame, text="◄", bd=0, takefocus=0, command=self._history_prev
        ).pack(side="left", padx=(5, 1))
        tk.Button(
            self.left_frame, text="►", bd=0, takefocus=0, command=self._history_next
        ).pack(side="left", padx=1)
        self.btn_model = tk.Button(
            self.left_frame, text="⚡", bd=0, takefocus=0, command=self._toggle_model
        )
        self.btn_model.pack(side="left", padx=2)

        tk.Frame(self.left_frame, width=10, bg="#111111").pack(side="left")
        tk.Button(
            self.left_frame,
            text="🧹",
            bd=0,
            takefocus=0,
            command=lambda: self._render_markdown(""),
        ).pack(side="left", padx=2)
        tk.Button(
            self.left_frame,
            text="🌗",
            bd=0,
            takefocus=0,
            font=("Arial", 10),
            command=lambda: self._set_opacity(0.50),
        ).pack(side="left", padx=2)
        tk.Button(
            self.left_frame,
            text="🌑",
            bd=0,
            takefocus=0,
            font=("Arial", 10),
            command=lambda: self._set_opacity(0.85),
        ).pack(side="left", padx=2)

        # Network Toggle Button
        tk.Frame(self.left_frame, width=10, bg="#111111").pack(side="left")
        self.btn_net = tk.Button(
            self.left_frame,
            text="🛜",
            fg="#00FF00",
            bd=0,
            takefocus=0,
            font=("Arial", 10),
            command=self._toggle_network,
        )
        self.btn_net.pack(side="left", padx=2)

        # --- RIGHT SUB-FRAME ---
        self.right_frame = tk.Frame(self.top_bar, bg="#111111")
        self.right_frame.pack(side="right", fill="y")

        tk.Button(
            self.right_frame,
            text="✖",
            bd=0,
            takefocus=0,
            command=self._minimize_to_icon,
        ).pack(side="right", padx=(2, 5))
        tk.Button(
            self.right_frame, text="🌓", bd=0, takefocus=0, command=self._toggle_theme
        ).pack(side="right", padx=2)

        self.lbl_buffer = tk.Label(
            self.right_frame,
            text="",
            bg="#111111",
            fg="#00FF00",
            font=("Arial", 8, "bold"),
            takefocus=0,
        )
        self.lbl_buffer.pack(side="right", padx=1)

        tk.Button(
            self.right_frame,
            text="➕",
            bd=0,
            takefocus=0,
            command=self._trigger_capture,
        ).pack(side="right", padx=1)
        tk.Button(
            self.right_frame,
            text="✨",
            bd=0,
            takefocus=0,
            command=self._trigger_analyze,
        ).pack(side="right", padx=2)

        tk.Frame(self.right_frame, width=15, bg="#111111").pack(side="right")

        self.preset_frame = tk.Frame(self.right_frame, bg="#111111")
        self.preset_frame.pack(side="right", fill="y")

        # --- TEXT AREA ---
        self.text_area = tk.Text(
            self.root,
            wrap="word",
            font=("Segoe UI", 12),
            bd=0,
            highlightthickness=0,
            bg="#111111",
            fg="#E0E0E0",
            takefocus=0,
            cursor="arrow",
        )
        self.text_area.pack(side="top", fill="both", expand=True, padx=10, pady=10)

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

        self.resize_grip = tk.Label(
            self.root, text="◢", bg="#111111", fg="gray", cursor="size_nw_se"
        )
        self.resize_grip.place(relx=1.0, rely=1.0, anchor="se")

        self._rebuild_presets()

    def _toggle_network(self):
        if self.on_network_toggle:
            self.is_server_online = not self.is_server_online
            self.btn_net.config(fg="#00FF00" if self.is_server_online else "#FF0000")
            threading.Thread(
                target=self.on_network_toggle,
                args=(self.is_server_online,),
                daemon=True,
            ).start()

    def _update_buffer_count(self, count):
        self.lbl_buffer.config(text=f"[{count}]" if count > 0 else "")

    def _rebuild_presets(self):
        for widget in self.preset_frame.winfo_children():
            widget.destroy()

        presets = self.config.get("presets", [])
        for p in presets:
            emoji = p.get("emoji", "❓")
            text = p.get("text", "")
            btn = tk.Button(
                self.preset_frame,
                text=emoji,
                bd=0,
                takefocus=0,
                command=lambda t=text: self._trigger_analyze(t),
            )
            btn.pack(side="left", padx=2)
        self._apply_colors()

    def _set_opacity(self, value):
        self.root.attributes("-alpha", value)
        # Re-weld OS armor in case Windows strips it during transparency calculation
        self.root.update()
        self._apply_stealth_mechanics(self.root)
        self._save_state()

    def _initialize_icon_window(self):
        self.icon_root = tk.Toplevel(self.root)
        self.icon_root.geometry(self.saved_state.get("icon_geo", "50x50+1800+50"))
        self.icon_root.overrideredirect(True)
        self.icon_root.attributes("-topmost", True)

        chroma_key = "#000001"
        self.icon_root.configure(bg=chroma_key)
        if sys.platform == "win32":
            self.icon_root.wm_attributes("-transparentcolor", chroma_key)

        self.peacock_lbl = tk.Label(
            self.icon_root,
            text="🦚",
            font=("Segoe UI Emoji", 28),
            bg=chroma_key,
            fg="white",
            cursor="hand2",
            takefocus=0,
        )
        self.peacock_lbl.pack()

        self.peacock_lbl.bind("<ButtonPress-1>", self._on_icon_press)
        self.peacock_lbl.bind("<B1-Motion>", self._on_icon_motion)
        self.peacock_lbl.bind("<ButtonRelease-1>", self._on_icon_release)

        if sys.platform == "win32":
            ctypes.windll.user32.ShowWindow(int(self.icon_root.wm_frame(), 16), SW_HIDE)
        else:
            self.icon_root.withdraw()

        self._apply_stealth_mechanics(self.icon_root)

    def _apply_initial_visibility(self):
        if self.is_minimized:
            self._minimize_to_icon()
        else:
            self._restore_from_icon()

    def _on_icon_press(self, e):
        self._icon_drag_start_x = e.x_root
        self._icon_drag_start_y = e.y_root
        self._icon_win_start_x = self.icon_root.winfo_x()
        self._icon_win_start_y = self.icon_root.winfo_y()
        self._icon_moved = False
        return "break"

    def _on_icon_motion(self, e):
        if (
            abs(e.x_root - self._icon_drag_start_x) > 3
            or abs(e.y_root - self._icon_drag_start_y) > 3
        ):
            self._icon_moved = True
            x = self._icon_win_start_x + (e.x_root - self._icon_drag_start_x)
            y = self._icon_win_start_y + (e.y_root - self._icon_drag_start_y)
            self.icon_root.geometry(f"+{x}+{y}")
        return "break"

    def _on_icon_release(self, e):
        if self._icon_moved:
            self._save_state()
            self._icon_moved = False
        else:
            self._restore_from_icon()
        return "break"

    def _apply_stealth_mechanics(self, window):
        window.update()
        hwnd = int(window.wm_frame(), 16)
        if sys.platform == "win32":
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE, ex_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            )

    def _minimize_to_icon(self):
        self.is_minimized = True
        self._save_state()
        if sys.platform == "win32":
            ctypes.windll.user32.ShowWindow(int(self.root.wm_frame(), 16), SW_HIDE)
            ctypes.windll.user32.ShowWindow(
                int(self.icon_root.wm_frame(), 16), SW_SHOWNOACTIVATE
            )
        else:
            self.root.withdraw()
            self.icon_root.deiconify()

        # FIX: Re-weld OS armor in case the un-hide operation reset DWM memory states
        self._apply_stealth_mechanics(self.icon_root)

        # AGGRESSIVE MEMORY MANAGEMENT: Flush RAM when hiding to save resources 24/7
        gc.collect()

    def _restore_from_icon(self):
        self.is_minimized = False
        self._save_state()
        if sys.platform == "win32":
            ctypes.windll.user32.ShowWindow(int(self.icon_root.wm_frame(), 16), SW_HIDE)
            ctypes.windll.user32.ShowWindow(
                int(self.root.wm_frame(), 16), SW_SHOWNOACTIVATE
            )
        else:
            self.icon_root.withdraw()
            self.root.deiconify()

        # FIX: Re-weld OS armor in case the un-hide operation reset DWM memory states
        self._apply_stealth_mechanics(self.root)

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
            self._save_state()

    def _history_next(self):
        if self.history_idx < len(self.history) - 1:
            self.history_idx += 1
            self._render_markdown(self.history[self.history_idx])
            self._save_state()

    def _toggle_model(self):
        self.current_model = "deep" if self.current_model == "fast" else "fast"
        self.btn_model.configure(text="🧠" if self.current_model == "deep" else "⚡")

    def _trigger_capture(self):
        if self.on_capture:
            threading.Thread(target=self.on_capture, daemon=True).start()

    def _trigger_analyze(self, prompt_text=None):
        if prompt_text is None:
            prompt_text = self.config.get("auto_prompt", "Analyze this screen.")
        if self.on_analyze:
            threading.Thread(
                target=self.on_analyze,
                args=(prompt_text, self.current_model),
                daemon=True,
            ).start()

    def _apply_colors(self):
        bg, fg = ("#111111", "#E0E0E0") if self.is_dark_mode else ("#F5F5F5", "#111111")
        btn_bg = "#222222" if self.is_dark_mode else "#E0E0E0"

        self.root.configure(bg=bg)
        self.top_bar.configure(bg=bg)

        for frame in [self.left_frame, self.right_frame, self.preset_frame]:
            frame.configure(bg=bg)
            for child in frame.winfo_children():
                if isinstance(child, tk.Button):
                    child.configure(bg=btn_bg, fg=fg)
                elif isinstance(child, tk.Frame) or isinstance(child, tk.Label):
                    child.configure(bg=bg)

        self.lbl_buffer.configure(bg=bg, fg="#00FF00")
        self.text_area.configure(bg=bg, fg=fg)
        self.btn_net.config(fg="#00FF00" if self.is_server_online else "#FF0000")

    def _toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self._apply_colors()
        self._save_state()

    def _bind_events(self):
        passive_surfaces = [
            self.root,
            self.top_bar,
            self.left_frame,
            self.right_frame,
            self.preset_frame,
        ]

        for widget in passive_surfaces:
            widget.bind("<ButtonPress-1>", self._on_drag_start)
            widget.bind("<B1-Motion>", self._on_drag_motion)
            widget.bind("<ButtonRelease-1>", lambda e: self._save_state())

        self.text_area.bind("<ButtonPress-1>", self._on_text_drag_start)
        self.text_area.bind("<B1-Motion>", self._on_drag_motion)
        self.text_area.bind("<ButtonRelease-1>", lambda e: self._save_state())

        self.resize_grip.bind("<ButtonPress-1>", self._on_resize_start)
        self.resize_grip.bind("<B1-Motion>", self._on_resize_motion)
        self.resize_grip.bind("<ButtonRelease-1>", lambda e: self._save_state())

        # FIX: Apply global mousewheel bind so dynamic preset buttons don't act as scroll black holes
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

    # --- ABSOLUTE EVENT ROUTING ---
    def _on_text_drag_start(self, e):
        self._on_drag_start(e)
        return "break"

    def _on_drag_start(self, e):
        self._drag_start_x = e.x_root
        self._drag_start_y = e.y_root
        self._win_start_x = self.root.winfo_x()
        self._win_start_y = self.root.winfo_y()
        return "break"  # Murders native focus steal

    def _on_drag_motion(self, e):
        x = self._win_start_x + (e.x_root - self._drag_start_x)
        y = self._win_start_y + (e.y_root - self._drag_start_y)
        self.root.geometry(f"+{x}+{y}")
        return "break"  # Prevents event bubbling chaos

    def _on_resize_start(self, e):
        self._resize_start_x = e.x_root
        self._resize_start_y = e.y_root
        self._resize_start_w = self.root.winfo_width()
        self._resize_start_h = self.root.winfo_height()
        return "break"  # Murders native focus steal

    def _on_resize_motion(self, e):
        w = max(350, self._resize_start_w + (e.x_root - self._resize_start_x))
        h = max(200, self._resize_start_h + (e.y_root - self._resize_start_y))
        self.root.geometry(f"{w}x{h}")
        return "break"  # Stops resize events from triggering drag events

    def _on_mousewheel(self, e):
        self.text_area.yview_scroll(int(-1 * (e.delta / 120)), "units")
        return "break"
