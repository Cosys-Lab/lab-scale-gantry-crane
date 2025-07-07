import logging
import tkinter as tk
from tkinter import ttk
import sys

from gantrylib.gantry_controller import PhysicalGantryController
import yaml

class StdoutRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        self.text_widget.insert(tk.END, message)
        self.text_widget.see(tk.END)

    def flush(self):
        pass

class TextWidgetHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.after(0, self.write_message, msg)

    def write_message(self, msg):
        self.text_widget.insert(tk.END, msg + '\n')
        self.text_widget.see(tk.END)

class MotionGUI:
    def __init__(self, root, crane_controller, cfg):
        self.root = root
        self.root.title("Motion Control GUI")

        self.crane_controller = crane_controller
        self.crane = crane_controller.crane

        # Configure top-level grid for responsiveness
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        # Velocity state
        self.vel_x = tk.DoubleVar()
        self.vel_y = tk.DoubleVar()
        self.pos_move_vel = tk.DoubleVar()
        self.hoist_pos_move_vel = tk.DoubleVar()

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

        # Right-hand container
        right_frame = ttk.Frame(root)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        right_frame.grid_rowconfigure(1, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        # Velocity Control section
        slider_frame = ttk.LabelFrame(right_frame, text="Velocity Control")
        slider_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.make_sliders(slider_frame)

        # Writeout Frame below the sliders, in right_frame
        writeout_frame = ttk.LabelFrame(right_frame, text="Writeout")
        writeout_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=5)

        self.write_to_db = tk.BooleanVar()
        self.validate_results = tk.BooleanVar()

        ttk.Checkbutton(writeout_frame, text="Write to database", variable=self.write_to_db).pack(anchor="w", padx=10, pady=2)
        ttk.Checkbutton(writeout_frame, text="Validate results", variable=self.validate_results).pack(anchor="w", padx=10, pady=2)

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

        # add destruction of window functions
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # get limits from config
        self.cart_position_limit = cfg.get("cart_position_limit")
        self.hoist_position_limit = cfg.get("hoist_position_limit")
        self.rope_angle_limit = cfg.get("rope_angle_limit")
        self.wind_speed_limit = cfg.get("wind_speed_limit")

        self.update_status()

    def on_close(self):
        logging.info("Closing GUI")
        # stop movement
        self.stop_movement()
        # cleanup continuous logging
        self.crane_controller.cleanup()
        # destroy window
        self.root.destroy()

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
        logging.info(f"Pressed {direction}")
        vel = self.vel_x.get() if direction in ["←", "→"] else self.vel_y.get()
        if direction == "↑":
            self.crane.moveHoistVelocity(-vel)
        elif direction == "↓":
            self.crane.moveHoistVelocity(vel)
        elif direction == "←":
            self.crane.moveCartVelocity(vel)
        elif direction == "→":
            self.crane.moveCartVelocity(-vel)

    def move_released(self, direction):
        logging.info(f"Released {direction}")
        self.crane.moveCartVelocity(0)
        self.crane.moveHoistVelocity(0)

    def make_sliders(self, parent):
        ttk.Label(parent, text="Left-Right Velocity").pack(anchor="w", padx=5, pady=(5, 0))
        tk.Scale(parent, from_=10, to=2000, orient="horizontal", variable=self.vel_x).pack(fill="x", padx=5, pady=2)
        self.vel_x.set(200)

        ttk.Label(parent, text="Up-Down Velocity").pack(anchor="w", padx=5, pady=(10, 0))
        tk.Scale(parent, from_=1, to=100, orient="horizontal", variable=self.vel_y).pack(fill="x", padx=5, pady=2)
        self.vel_y.set(50)


    def make_position_controls(self, parent):
        parent.grid_columnconfigure(5, weight=1)  # Increase column count to accommodate new labels

        # Row 0 - Cart Controls
        tk.Label(parent, text="Cart:").grid(row=0, column=0, padx=5, sticky="w")

        self.pos_entry = tk.Entry(parent)
        self.pos_entry.grid(row=0, column=1, padx=5, sticky="ew")

        self.start_btn = tk.Button(parent, text="Start", command=self.start_movement)
        self.start_btn.grid(row=0, column=2, padx=5)

        self.stop_btn = tk.Button(parent, text="Stop", command=self.stop_movement)
        self.stop_btn.grid(row=0, column=3, padx=5)

        self.move_type = tk.BooleanVar(value=False)
        self.opti_move_toggle = ttk.Checkbutton(parent, text="Optimal Move", variable=self.move_type, command=self.toggle_changed)
        self.opti_move_toggle.grid(row=0, column=4, padx=5)

        self.pos_move_velocity_slider = tk.Scale(parent, from_=10, to=2000, orient="horizontal", variable=self.pos_move_vel,
                                    label="Movement Velocity")
        self.pos_move_velocity_slider.grid(row=0, column=5, sticky="ew", padx=10)
        self.pos_move_vel.set(200)
        self.toggle_changed()  # Set initial state

        # Row 1 - Hoist Controls
        tk.Label(parent, text="Hoist:").grid(row=1, column=0, padx=5, sticky="w")

        self.hoist_pos_entry = tk.Entry(parent)
        self.hoist_pos_entry.grid(row=1, column=1, padx=5, sticky="ew")

        self.hoist_start_btn = tk.Button(parent, text="Start", command=self.start_hoist_movement)
        self.hoist_start_btn.grid(row=1, column=2, padx=5)

        self.hoist_stop_btn = tk.Button(parent, text="Stop", command=self.stop_movement)
        self.hoist_stop_btn.grid(row=1, column=3, padx=5)

        self.hoist_pos_move_velocity_slider = tk.Scale(parent, from_=10, to=100, orient="horizontal", variable=self.hoist_pos_move_vel,
                                    label="Hoist Velocity")
        self.hoist_pos_move_velocity_slider.grid(row=1, column=5, sticky="ew", padx=10)
        self.hoist_pos_move_vel.set(50)


    def toggle_changed(self):
        if self.move_type.get():  # Optimal move
            logging.info(f"Optimal Move:{self.move_type.get()}")
            self.pos_move_velocity_slider.config(state="disabled")
        else:  # Optimal move
            logging.info(f"Optimal Move:{self.move_type.get()}")
            self.pos_move_velocity_slider.config(state="normal")

    def make_home_buttons(self, parent):
        tk.Button(parent, text="Home Cart", command=self.home_cart).pack(padx=5, pady=5, fill="x")
        tk.Button(parent, text="Home Hoist", command=self.home_hoist).pack(padx=5, pady=5, fill="x")

    def make_zero_buttons(self, parent):
        tk.Button(parent, text="Zero Angle", command=self.zero_angle).pack(padx=5, pady=5, fill="x")
        tk.Button(parent, text="Zero Wind", command=self.zero_wind).pack(padx=5, pady=5, fill="x")

    def make_status_display(self, parent):
        self.status_header = ttk.Label(parent, text="\t(Pos, Vel)")
        self.status_header.pack(anchor="w", padx=5, pady=2)
        self.cart_label = ttk.Label(parent, text="Cart:\t(0.0, 0.0)")
        self.cart_label.pack(anchor="w", padx=5, pady=2)
        self.hoist_label = ttk.Label(parent, text="Hoist:\t(0.0, 0.0)")
        self.hoist_label.pack(anchor="w", padx=5, pady=2)

        angle_frame = ttk.Frame(parent)
        angle_frame.pack(anchor="w", padx=5, pady=2, fill="x")
        self.angle_label = ttk.Label(angle_frame, text="Angle:\t(0.0, 0.0)")
        self.angle_label.pack(side="left")
        self.angle_validity = ttk.Label(angle_frame, text="\tValid", foreground="green")
        self.angle_validity.pack(side="right", padx=10)

        wind_frame = ttk.Frame(parent)
        wind_frame.pack(anchor="w", padx=5, pady=2, fill="x")
        self.wind_label = ttk.Label(wind_frame, text="Wind:\t(n/a, 0.0)")
        self.wind_label.pack(side="left")
        self.wind_validity = ttk.Label(wind_frame, text="\tValid", foreground="green")
        self.wind_validity.pack(side="right", padx=10)


    def make_stdout_display(self, parent):
        self.stdout_text = tk.Text(parent, height=10, wrap="word")
        self.stdout_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = tk.Scrollbar(parent, command=self.stdout_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.stdout_text.config(yscrollcommand=scrollbar.set)
        # Optional: still redirect print() if you want
        sys.stdout = StdoutRedirector(self.stdout_text)

        # Add logging handler
        log_handler = TextWidgetHandler(self.stdout_text)
        log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logger.addHandler(log_handler)


    def update_status(self):
        (cart_pos, cart_vel, hoist_pos, hoist_vel, angle_pos, angle_vel, wind_vel) = self.crane.getState()

        self.cart_label.config(text=f"Cart:\t({cart_pos:.2f}, {cart_vel:.2f})")
        self.hoist_label.config(text=f"Hoist:\t({hoist_pos:.2f}, {hoist_vel:.2f})")
        self.angle_label.config(text=f"Angle:\t({angle_pos:.2f}, {angle_vel:.2f})")
        self.wind_label.config(text=f"Wind:\t(n/a, {wind_vel:.2f})")

        # Validity for angle
        if abs(angle_pos) < self.rope_angle_limit:
            self.angle_validity.config(text="Valid", foreground="green")
        else:
            self.angle_validity.config(text="Invalid", foreground="red")

        # Validity for wind
        if abs(wind_vel) < self.wind_speed_limit:
            self.wind_validity.config(text="Valid", foreground="green")
        else:
            self.wind_validity.config(text="Invalid", foreground="red")

        self.root.after(60, self.update_status)

    def start_movement(self):
        logging.info("Start pressed")
        pos = float(self.pos_entry.get())
        if pos < 0 or pos > self.cart_position_limit/1000:
            logging.error(f"Error: Position out of range [0, {self.cart_position_limit/1000}]")
            self.pos_entry.delete(0, tk.END)
            return
        else:
            if self.move_type.get():
                logging.info(f"Performing optimal move to {pos}")
                self.crane_controller.moveOptimally(pos, 
                                    write_to_db=self.write_to_db.get(), 
                                    validate=self.validate_results.get())
            else:
                vel = self.pos_move_velocity_slider.get()
                logging.info(f"Performing normal move to {pos} with velocity {vel}")
                self.crane.moveCartPosition(pos, vel)

    def stop_movement(self):
        logging.info("Stop pressed")
        self.crane.moveCartVelocity(0)
        self.crane.moveHoistVelocity(0)

    def home_cart(self):
        logging.info("Home Cart pressed")
        self.crane.homeCart()

    def home_hoist(self):
        logging.info("Home Hoist pressed")
        self.crane.homeHoist()

    def zero_angle(self):
        logging.info("Zero Angle pressed")
        self.crane.zeroAngle()

    def zero_wind(self):
        logging.info("Zero Wind pressed")
        self.crane.zeroWind()

    def start_hoist_movement(self):
        logging.info("Start Hoist pressed")
        pos = float(self.hoist_pos_entry.get())
        if pos < 0 or pos > self.hoist_position_limit/1000:
            logging.error(f"Error: Position out of range [0, {self.hoist_position_limit/1000}]")
            self.hoist_pos_entry.delete(0, tk.END)
            return
        else:
            vel = self.hoist_pos_move_velocity_slider.get()
            logging.info(f"Performing normal hoist move to {pos} with velocity {vel}")
            self.crane.moveHoistPosition(pos, vel)


if __name__ == "__main__":
    root = tk.Tk()
    with PhysicalGantryController("../examples/crane-properties.yaml") as crane_controller:
        cfg = yaml.safe_load(open("../examples/crane-properties.yaml"))
        app = MotionGUI(root, crane_controller, cfg)
        root.mainloop()