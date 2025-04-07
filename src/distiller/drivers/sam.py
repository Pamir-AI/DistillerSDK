import serial
import time
import threading
import logging
from typing import Callable, Optional

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
SERIAL_PORT = '/dev/ttyAMA2'
BAUD_RATE = 9600
TIMEOUT = 1


class SAM:
    def __init__(self, callback: Callable[[int], None]) -> None:
        """
        Initialize the SAM class.

        :param callback: A callback function to process button states.
        """
        self.encode_table = {
            "BTN_UP": 1,
            "BTN_DOWN": 2,
            "BTN_SELECT": 4,
            "SHUTDOWN": 8
        }
        self.callback = callback
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.button_lock = False
        self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT)
        self.start_monitoring()

    def lock(self) -> None:
        """Lock the button to prevent state changes."""
        self.button_lock = True

    def unlock(self) -> None:
        """Unlock the button to allow state changes."""
        # release queued up inputs 
        self.ser.read_all()
        self.button_lock = False

    def process_button_state(self, state: int) -> None:
        """Override this function to process button state."""
        raise NotImplementedError("Subclasses should implement this method.")

    def start_monitoring(self) -> None:
        """Start monitoring the serial port for button states."""
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            self.running = True
            self.monitor_thread = threading.Thread(target=self.monitor_pins)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()

    def monitor_pins(self) -> None:
        """Monitor the serial port for button states."""
        while self.running:
            line = self.ser.readline().decode().strip()
            if line.isdigit():
                button_state = int(line)
                if self.button_lock : continue
                self.process_button_state(button_state)
            else:
                logging.info(f"SAM INFO MESSAGE: {line}")
                logging.info(f"SAM MESSAGE LENGTH: {len(line)}")
        
        self.cleanup()

    def stop_monitoring(self) -> None:
        """Stop monitoring the serial port for button states."""
        self.running = False
        if self.monitor_thread is not None and threading.current_thread() != self.monitor_thread:
            self.monitor_thread.join()
        self.ser.close()

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.ser.is_open:
            self.ser.close()
