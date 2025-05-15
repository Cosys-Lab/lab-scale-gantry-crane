import logging
import re
import struct
import time
import numpy as np
from pyparsing import deque
import serial
import sys
import csv

class UARTTest:

    def __init__(self, port = "COM6", baudrate = 115200):
        self.angleUART = serial.Serial(port, 115200)
        self.buffer = bytearray(b'')
        self.packet_size = 13
        self.start_byte = 0x01
        self.lastAngle = 0
        self.lastOmega = 0
        self.lastwindspeed = 0
        self.pattern = re.compile(b'\x01(.{12})')

    def readAngle(self):
        """Reads the latest received angle from the angleUART

        Returns:
            tuple(float, float): Tuple(theta, omega)
        """
        if self.angleUART is not None:
            # Add incoming data to the buffer
            self.buffer += bytearray(self.angleUART.read(self.angleUART.in_waiting))

            # find all matches in the buffer
            matches = self.pattern.findall(self.buffer)

            # check if a match was found
            if matches:
                # Get the last match
                last = matches[-1]

                # Unpack the bytes into floats
                floats = struct.unpack('<fff', last)

                # Remove the processed bytes from the buffer
                self.buffer = self.buffer.split(last)[-1]
                self.lastAngle = floats[0]
                self.lastOmega = floats[1]
                self.lastwindspeed = floats[2]
                return self.lastAngle, self.lastOmega, self.lastwindspeed
            else:
                return self.lastAngle, self.lastOmega, self.lastwindspeed
        else:
            return (0, 0, 0)

if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    uart = UARTTest()
    t = []
    theta = []
    omega = []
    windspeed = []

    logging.info("Press Ctrl+C to stop the program and save data to angle_data.csv")
    
    try:
        start_time = time.time()
        while True:
            current_time = time.time()
            theta_val, omega_val, windspeed_val = uart.readAngle()
            t.append(current_time - start_time)
            theta.append(theta_val)
            omega.append(omega_val)
            windspeed.append(windspeed_val)
            
            # Sleep until next 0.01s interval (100Hz)
            next_time = current_time + 0.01
            time.sleep(max(0, next_time - time.time()))
            
    except KeyboardInterrupt:
        # Write data to CSV when Ctrl+C is pressed

        # correct for scaling factor.
        theta = [-1/0.806*angle*2*np.pi/360 for angle in theta]
        omega = [-1/0.806*angular_vel*2*np.pi/360 for angular_vel in omega]

        # add rope length
        length = [0.21 for _ in range(len(theta))]  # 0.26 is the length of the rope in meters
        with open('calibration_data.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['time', 'theta [rad]', 'length [m]'])
            for ti, thi, li in zip(t, theta, length):
                writer.writerow([ti, thi, li])
        print("Data saved to angle_data.csv")

        # Create a figure with subplots
        import matplotlib.pyplot as plt
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

        # Plot angle vs time
        ax1.plot(t, theta)
        ax1.set_xlabel('Time [s]')
        ax1.set_ylabel('Angle [rad]')
        ax1.grid(True)

        # Plot angular velocity vs time
        ax2.plot(t, omega)
        ax2.set_xlabel('Time [s]')
        ax2.set_ylabel('Angular velocity [rad/s]')
        ax2.grid(True)

        plt.tight_layout()
        plt.show()

        sys.exit(0)

