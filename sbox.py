import tkinter as tk
import ctypes
import sys
import keyboard

# --- Windows API Constants ---
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
WDA_EXCLUDEFROMCAPTURE = 17

# Constants for Intangibility (Click-Through)
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020


class StealthTeleprompter:
    """
    A translucent, borderless overlay that evades screen capture, toggles visibility
    without stealing focus, features an interactive UI, and can become intangible.
    """

    def __init__(self, root):
        self.root = root
        self.key_buffer = []

        # State Tracking
        self.is_visible = True
        self.is_dark_mode = True
        self.is_intangible = False

        # State variables for custom drag physics
        self._drag_start_x = 0
        self._drag_start_y = 0

        self._initialize_ui()
        self._apply_stealth_mechanics()
        self._bind_events()

    def _initialize_ui(self):
        """Bootstraps the Tkinter interface."""
        self.root.geometry("550x250")

        # Strip OS window decorations and remove from Taskbar/Alt-Tab roster
        self.root.attributes("-toolwindow", True)
        self.root.overrideredirect(True)

        # Establish translucency and Z-index prioritization
        self.root.attributes("-alpha", 0.80)
        self.root.attributes("-topmost", True)

        # --- THEME SWITCHER BUTTON ---
        self.theme_btn = tk.Button(
            self.root,
            text="🌓",
            font=("Arial", 12),
            bd=0,
            cursor="hand2",
            command=self._toggle_theme,
        )
        self.theme_btn.place(relx=0.98, rely=0.02, anchor="ne")

        # --- PAYLOAD CONTENT ---
        mlk_speech = (
            "I am happy to join with you today in what will go down in history\n"
            "as the greatest demonstration for freedom in the history of our nation.\n\n"
            "Five score years ago, a great American, in whose symbolic shadow\n"
            "as the greatest demonstration for freedom in the history of our nation.\n\n"
            "Five score years ago, a great American, in whose symbolic shadow\n"
            "we stand today, signed the Emancipation Proclamation."
        )

        self.content_label = tk.Label(
            self.root,
            text=mlk_speech,
            font=("Georgia", 13, "italic"),
            justify="center",
        )
        self.content_label.pack(expand=True, padx=20, pady=20)

        self.quit_label = tk.Label(
            self.root,
            text="[Click here and press ESC to completely close]",
            font=("Arial", 7),
        )
        self.quit_label.pack(side="bottom", pady=5)

        # Apply the initial dark theme colors
        self._apply_colors()

    def _apply_colors(self):
        """Updates the color palette based on the current theme state."""
        # If the window is intangible, force the text to be green to warn the user
        if self.is_intangible:
            self.content_label.configure(fg="#00FF00")
            return

        if self.is_dark_mode:
            bg_color = "black"
            fg_color = "#E0E0E0"
            btn_active = "#333333"
        else:
            bg_color = "#F5F5F5"
            fg_color = "#111111"
            btn_active = "#CCCCCC"

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
        """Flips the boolean state and triggers a color repaint."""
        self.is_dark_mode = not self.is_dark_mode
        self._apply_colors()

    def _apply_stealth_mechanics(self):
        """Interfaces with the OS Compositor to exclude the window from capture pipelines."""
        self.root.update()
        self.hwnd = int(self.root.wm_frame(), 16)

        if sys.platform == "win32":
            success = ctypes.windll.user32.SetWindowDisplayAffinity(
                self.hwnd, WDA_EXCLUDEFROMCAPTURE
            )
            if not success:
                print(
                    "[Warning] OS rejected display affinity. Capture protection failed."
                )

    def _bind_events(self):
        """Attaches custom mouse tracking and global keyboard hooks."""
        self.root.bind("<Button-1>", self._on_drag_start)
        self.root.bind("<B1-Motion>", self._on_drag_motion)
        self.root.bind("<Escape>", self._shutdown)
        keyboard.hook(self._on_global_key)

    def _on_drag_start(self, event):
        """Records the initial coordinate vector upon mouse click."""
        if event.widget == self.theme_btn:
            return

        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag_motion(self, event):
        """Calculates delta position and translates the window geometry."""
        if event.widget == self.theme_btn:
            return

        x = self.root.winfo_x() - self._drag_start_x + event.x
        y = self.root.winfo_y() - self._drag_start_y + event.y
        self.root.geometry(f"+{x}+{y}")

    def _on_global_key(self, event):
        """Listens to the OS input stream for the hide/reveal/intangible sequences."""
        if event.event_type == keyboard.KEY_DOWN and len(event.name) == 1:
            self.key_buffer.append(event.name.lower())

            if len(self.key_buffer) > 4:
                self.key_buffer.pop(0)

            seq = "".join(self.key_buffer)

            # Visibility Toggles
            if seq == "asdf" and not self.is_visible:
                self.root.after(0, self._reveal_without_focus)
            elif seq == "fdsa" and self.is_visible:
                self.root.after(0, self._hide_window)

            # Intangibility Toggles
            elif seq == "zxcv" and self.is_visible and not self.is_intangible:
                self.root.after(0, self._make_intangible)
            elif seq == "vcxz" and self.is_visible and self.is_intangible:
                self.root.after(0, self._make_solid)

    def _reveal_without_focus(self):
        """Forces the OS to draw the window without transferring focus."""
        if sys.platform == "win32":
            ctypes.windll.user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            self.is_visible = True

    def _hide_window(self):
        """Forces the OS to stop drawing the window."""
        if sys.platform == "win32":
            ctypes.windll.user32.ShowWindow(self.hwnd, SW_HIDE)
            self.is_visible = False

    def _make_intangible(self):
        """Adds WS_EX_TRANSPARENT so mouse clicks pass through the window."""
        if sys.platform == "win32":
            ex_style = ctypes.windll.user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            ex_style |= WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, ex_style)

            self.is_intangible = True
            self._apply_colors()  # Triggers the green text warning
            print("[System] Teleprompter is INTANGIBLE. Clicks pass right through it.")

    def _make_solid(self):
        """Removes WS_EX_TRANSPARENT so the window can be clicked and dragged again."""
        if sys.platform == "win32":
            ex_style = ctypes.windll.user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            ex_style &= ~WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, ex_style)

            self.is_intangible = False
            self._apply_colors()  # Reverts to the standard Light/Dark theme
            print(
                "[System] Teleprompter is SOLID. You can drag it or click the theme button."
            )

    def _shutdown(self, event=None):
        """Cleans up global hooks and destroys the application."""
        print("[System] Detaching OS hooks and shutting down...")
        keyboard.unhook_all()
        self.root.destroy()


if __name__ == "__main__":
    print("[System] Initializing Ghost Teleprompter Engine...")
    print("  -> Type 'fdsa' ANYWHERE to vanish.")
    print("  -> Type 'asdf' ANYWHERE to reveal (No Focus Steal).")
    print("  -> Type 'zxcv' to lock it in place and click THROUGH it.")
    print("  -> Type 'vcxz' to make it solid again.")

    root_window = tk.Tk()
    app = StealthTeleprompter(root_window)
    root_window.mainloop()
