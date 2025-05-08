import logging
import re
import struct
import time
from pyparsing import deque
import serial
import sys

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
                return floats
            else:
                return self.lastAngle, self.lastOmega, self.lastwindspeed
        else:
            return (0, 0, 0)

if __name__ == "__main__":
    uart = UARTTest()
    while True:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO)
        angle = uart.readAngle()
        print(angle)
        time.sleep(0.5)

