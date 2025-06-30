from abc import ABC, abstractmethod
import re
import struct
import threading

import serial

class CraneIOUC(ABC):
    """
    Abstract base class representing a Crane I/O microcontroller interface.
    """

    def __init__(self):
        self.angle = 0.0
        self.omega = 0.0
        self.windspeed = 0.0
        # Zero offsets for wind and angle measurements
        self.wind_offset = 0.0
        self.angle_offset = 0.0

    @abstractmethod
    def getStatus(self):
        pass

    def zeroWind(self):
        _, _, windspeed = self.getStatus()
        self.wind_offset = windspeed + self.wind_offset

    def zeroAngle(self):
        angle, _, _ = self.readAngle()
        self.angle_offset = angle + self.angle_offset

class MockCraneIOUC(CraneIOUC):
    """
    Mock implementation of Crane I/O microcontroller interface for testing purposes.
    """

    def __init__(self):
        super().__init__()

    def getStatus(self):
        return (0.0, 0.0, 0.0)

class SerialCraneIOUC(CraneIOUC):
    """
    Serial implementation of Crane I/O microcontroller interface.
    """

    def __init__(self, config: dict) -> None:
        super().__init__()
        # init serial variables
        self.port = config["CraneIOUCPort"]
        self.baudrate = config["CraneIOUCBaudrate"]
        self.pattern = re.compile(b'\x01(.{12})') # new pattern for bytearrays and uncompressed floats.
        self.packet_size = 13
        self.start_byte = 0x01
        self.buffer = bytearray(b'')
        # lock to make getStatus thread safe
        self.get_status_lock = threading.Lock()
        # open the connection
        self.conn = serial.Serial(self.port, self.baudrate)

    def getStatus(self):
        with self.get_status_lock:
            # Add incoming data to the buffer
            self.buffer += bytearray(self.conn.read(self.conn.in_waiting))

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
                self.angle = floats[0] - self.angle_offset
                self.omega = floats[1]
                self.windspeed = floats[2] - self.wind_offset
                return self.angle, self.omega, self.windspeed
            else:
                return self.angle, self.omega, self.windspeed

