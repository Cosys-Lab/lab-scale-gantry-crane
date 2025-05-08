import tkinter as tk
from tkinter import ttk
import sys
import threading
import time

class StdoutRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        self.text_widget.insert(tk.END, message)
        self.text_widget.see(tk.END)

    def flush(self):
        pass

class MotionGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Motion Control GUI")

        # Configure top-level grid for responsiveness
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        # Velocity state
        self.vel_x = tk.DoubleVar()
        self.vel_y = tk.DoubleVar()
        self.extra_velocity = tk.DoubleVar()

        # Top-left: Control (D-pad, Home, Status)
        control_frame = ttk.Frame(root)
        control_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        control_frame.grid_columnconfigure(0, weight=1)

        dpad_frame = ttk.LabelFrame(control_frame, text="D-Pad")
        dpad_frame.grid(row=0, column=0, padx=5, sticky="nw")

        self.make_dpad(dpad_frame)

        home_frame = ttk.LabelFrame(control_frame, text="Homing")
        home_frame.grid(row=0, column=1, padx=5, sticky="n")

        self.make_home_buttons(home_frame)

        zero_frame = ttk.LabelFrame(control_frame, text="Zeroing")
        zero_frame.grid(row=0, column=2, padx=5, sticky="n")

        self.make_zero_buttons(zero_frame)

        status_frame = ttk.LabelFrame(control_frame, text="Status")
        status_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 0))

        self.make_status_display(status_frame)

        # Right side: Velocity sliders
        slider_frame = ttk.LabelFrame(root, text="Velocity Control")
        slider_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        slider_frame.grid_columnconfigure(0, weight=1)

        self.make_sliders(slider_frame)

        # Movement control row
        pos_frame = ttk.LabelFrame(root, text="Movement Control")
        pos_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        self.make_position_controls(pos_frame)

        # Stdout display
        stdout_frame = ttk.LabelFrame(root, text="Output Console")
        stdout_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        stdout_frame.grid_rowconfigure(0, weight=1)
        stdout_frame.grid_columnconfigure(0, weight=1)

        self.make_stdout_display(stdout_frame)

        # Simulated state
        self.current_pos = [0.0, 0.0]
        self.current_vel = [0.0, 0.0]

        self.update_status()
        self.start_status_loop()

    def make_dpad(self, parent):
        self.dpad_buttons = {}

        def make_button(text, row, col):
            btn = tk.Button(parent, text=text, width=5, height=2)
            btn.grid(row=row, column=col)
            btn.bind("<ButtonPress>", lambda e, d=text: self.move_pressed(d))
            btn.bind("<ButtonRelease>", lambda e, d=text: self.move_released(d))
            self.dpad_buttons[text] = btn

        make_button("↑", 0, 1)
        make_button("←", 1, 0)
        make_button("→", 1, 2)
        make_button("↓", 2, 1)

    def move_pressed(self, direction):
        print(f"Pressed {direction}")

    def move_released(self, direction):
        print(f"Released {direction}")

    def make_sliders(self, parent):
        ttk.Label(parent, text="Left-Right Velocity").pack()
        tk.Scale(parent, from_=-10, to=10, orient="horizontal", variable=self.vel_x).pack(fill="x")
        ttk.Label(parent, text="Up-Down Velocity").pack()
        tk.Scale(parent, from_=-10, to=10, orient="horizontal", variable=self.vel_y).pack(fill="x")

    def make_position_controls(self, parent):
        parent.grid_columnconfigure(4, weight=1)

        self.pos_entry = tk.Entry(parent)
        self.pos_entry.grid(row=0, column=0, padx=5, sticky="ew")

        self.start_btn = tk.Button(parent, text="Start", command=self.start_movement)
        self.start_btn.grid(row=0, column=1, padx=5)

        self.stop_btn = tk.Button(parent, text="Stop", command=self.stop_movement)
        self.stop_btn.grid(row=0, column=2, padx=5)

        self.move_type = tk.BooleanVar(value=False)
        self.toggle = ttk.Checkbutton(parent, text="Toggle Type", variable=self.move_type, command=self.toggle_changed)
        self.toggle.grid(row=0, column=3, padx=5)

        # Additional velocity slider, only for Type A
        self.extra_slider = tk.Scale(parent, from_=0, to=10, orient="horizontal", variable=self.extra_velocity,
                                     label="Extra Velocity")
        self.extra_slider.grid(row=0, column=4, sticky="ew", padx=10)
        self.toggle_changed()  # Set initial state

    def toggle_changed(self):
        if self.move_type.get():  # Type B
            self.extra_slider.config(state="disabled")
        else:  # Type A
            self.extra_slider.config(state="normal")

    def make_home_buttons(self, parent):
        tk.Button(parent, text="Home X", command=self.home_x).pack(padx=5, pady=5, fill="x")
        tk.Button(parent, text="Home Y", command=self.home_y).pack(padx=5, pady=5, fill="x")

    def make_zero_buttons(self, parent):
        tk.Button(parent, text="Zero Angle", command=self.home_x).pack(padx=5, pady=5, fill="x")
        tk.Button(parent, text="Zero Wind", command=self.home_y).pack(padx=5, pady=5, fill="x")

    def make_status_display(self, parent):
        self.status_header = ttk.Label(parent, text="\t(Pos, Vel)")
        self.status_header.pack(anchor="w", padx=5, pady=2)
        self.cart_label = ttk.Label(parent, text="Cart:\t(0.0, 0.0)")
        self.cart_label.pack(anchor="w", padx=5, pady=2)
        self.hoist_label = ttk.Label(parent, text="Hoist:\t(0.0, 0.0)")
        self.hoist_label.pack(anchor="w", padx=5, pady=2)
        self.angle_label = ttk.Label(parent, text="Angle:\t(0.0, 0.0)")
        self.angle_label.pack(anchor="w", padx=5, pady=2)
        self.wind_label = ttk.Label(parent, text="Wind:\t(n/a, 0.0)")
        self.wind_label.pack(anchor="w", padx=5, pady=2)

    def make_stdout_display(self, parent):
        self.stdout_text = tk.Text(parent, height=10, wrap="word")
        self.stdout_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = tk.Scrollbar(parent, command=self.stdout_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.stdout_text.config(yscrollcommand=scrollbar.set)
        sys.stdout = StdoutRedirector(self.stdout_text)

    def update_status(self):
        self.current_vel = [self.vel_x.get(), self.vel_y.get()]
        self.current_pos[0] += self.current_vel[0] / 60.0
        self.current_pos[1] += self.current_vel[1] / 60.0

        self.cart_label.config(text=f"Position: ({self.current_pos[0]:.2f}, {self.current_pos[1]:.2f})")
        self.hoist_label.config(text=f"Velocity: ({self.current_vel[0]:.2f}, {self.current_vel[1]:.2f})")

    def start_status_loop(self):
        def loop():
            while True:
                self.update_status()
                time.sleep(1 / 60)
        threading.Thread(target=loop, daemon=True).start()

    def start_movement(self):
        pos = self.pos_entry.get()
        mode = "Type B" if self.move_type.get() else "Type A"
        extra_vel = self.extra_velocity.get() if not self.move_type.get() else "N/A"
        print(f"Start moving to position {pos} with mode {mode}, extra velocity {extra_vel}")

    def stop_movement(self):
        print("Stop movement")

    def home_x(self):
        print("Homing X axis")

    def home_y(self):
        print("Homing Y axis")

if __name__ == "__main__":
    root = tk.Tk()
    app = MotionGUI(root)
    root.mainloop()
