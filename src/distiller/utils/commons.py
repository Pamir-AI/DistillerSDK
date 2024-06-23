import time
import socket
import psutil
import logging
import asyncio
import requests
import subprocess
import threading
from PIL import Image, ImageOps
from typing import TypeVar, Generic
from typing import Any, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_current_connection() -> Optional[str]:
    """
    Get the current Wi-Fi connection SSID.

    :return: The SSID of the current Wi-Fi connection or None if not connected.
    """
    result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True)
    lines = result.stdout.splitlines()
    return lines[0] if lines else None

def get_ip_address(interface: str = 'wlan0') -> Optional[str]:
    """
    Get the IP address of a network interface.

    :param interface: The name of the network interface.
    :return: The IP address or None if not found.
    """
    try:
        for iface_name, iface_addrs in psutil.net_if_addrs().items():
            if iface_name == interface:
                for addr in iface_addrs:
                    if addr.family == socket.AF_INET:
                        return addr.address
        return None
    except Exception as e:
        logging.error(f"get_ip_address: {e}")
        return None

def check_internet_connection(url: str = 'http://www.google.com/', timeout: int = 5) -> bool:
    """
    Check if there is an internet connection.

    :param url: The URL to test the connection.
    :param timeout: The timeout for the connection test.
    :return: True if connected, False otherwise.
    """
    try:
        requests.get(url, timeout=timeout)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False
    
def timeit(func):
    """
    Decorator to measure the execution time of a function.
    """
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        logging.info(f"{func.__name__} executed in {end_time - start_time:.8f} seconds")
        return result
    return wrapper

class ThreadWorker:
    def __init__(self) -> None:
        """
        Initialize the ThreadWorker class.
        """
        self.worker_thread: Optional[threading.Thread] = None
        self.active = threading.Event()  # Event to manage the thread's active state

    def _run(self, func: Any, args: tuple) -> None:
        """
        The function that runs in the thread, wraps the user function to handle shutdown.

        :param func: The function to run in the thread.
        :param args: The arguments to pass to the function.
        """
        try:
            func(self.active, *args)
        except Exception as e:
            logging.error(f"Error in thread: {e}")
        finally:
            logging.info("Thread exiting...")

    def start(self, func: Any, args: tuple = ()) -> None:
        """
        Start the worker thread.

        :param func: The function to run in the thread.
        :param args: The arguments to pass to the function.
        """
        self.active.set()  # Mark the thread as active
        self.worker_thread = threading.Thread(target=self._run, args=(func, args))
        self.worker_thread.start()

    def stop(self) -> None:
        """
        Stop the worker thread gracefully.
        """
        self.active.clear()  # Clear the active flag to signal the thread to stop
        time.sleep(0.1)  # Split second for the worker to join
        if self.worker_thread:
            self.worker_thread.join()  # Wait for the thread to finish

    def is_running(self) -> bool:
        """
        Check if the thread is running.

        :return: True if the thread is alive, False otherwise.
        """
        return self.worker_thread.is_alive() if self.worker_thread else False

class HijackEink:
    def __init__(self) -> None:
        """
        Initialize the HijackEink class.
        """
        from distiller.peripheral.eink import Eink
        self.eink = Eink()
    
    def update_screen_1bit(self, image: Image.Image) -> None:
        """
        Update the e-ink screen with a 1-bit image.

        :param image: The image to display.
        """
        self.eink.update_screen_1bit(image)

    def destroy(self) -> None:
        """
        Destroy the e-ink object.
        """
        del self.eink
