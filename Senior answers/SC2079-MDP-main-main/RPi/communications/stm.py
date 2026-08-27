from typing import Optional
import serial
import os

from dotenv import load_dotenv
load_dotenv()

SERIAL_PORT = os.getenv("SERIAL_PORT")
BAUD_RATE = int(os.getenv("BAUD_RATE"))

class STM:

    def __init__(self):
        """
        Constructor for STMLink.
        """
        super().__init__()
        self.serial = None
        self.received = []

    def connect(self):
        """Connect to STM32 using serial UART connection, given the serial port and the baud rate"""
        self.serial = serial.Serial(SERIAL_PORT, BAUD_RATE)
        print("Connected to STM32")

    def disconnect(self):
        """Disconnect from STM32 by closing the serial link that was opened during connect()"""
        self.serial.close()
        self.serial = None
        print("Disconnected from STM32")

    def send(self, message: str) -> None:
        """Send a message to STM32, utf-8 encoded

        Args:
            message (str): message to send
        """
        self.serial.write(bytes(message, "utf-8"))
        print("Sent to STM32:", str(message).rstrip())

    def wait_receive(self, ticks=5000) -> Optional[str]:
        """Receive a message from STM32, utf-8 decoded

        Returns:
            Optional[str]: message received
        """
        while True:
            if self.serial.in_waiting > 0:
                return str(self.serial.read_all(), "utf-8")
            
    def receive(self) -> Optional[str]:
        """Receive a message from STM32, utf-8 decoded

        Returns:
            Optional[str]: message received
        """
        if self.serial.in_waiting > 0:
            msg = str(self.serial.read_all(), "utf-8")
            return msg
        return None

    def send_cmd(self, flag, speed, angle, val):
        """Send command and wait for acknowledge."""
        cmd = flag
        if flag not in ["S", "D", "M"]:
            cmd += f"{speed}|{round(angle, 2)}|{round(val, 2)}"
        cmd += "\n"
        self.send(cmd)