import cv2
from distiller.utils.commons import ThreadWorker
from distiller.utils.image import fast_image
from distiller.constants import EINK_WIDTH, EINK_HEIGHT
import math
from picamera2 import Picamera2
import libcamera
import numpy as np
import os
import sys
import time
import random
import json
from pathlib import Path
from typing import Optional
from PIL import Image, ImageFilter, ImageOps
import threading  # Import threading module
import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class Cam:
    def __init__(self, eink) -> None:
        """
        Initialize the Cam class.

        :param eink: The e-ink display object.
        """
        self.eink = eink
        self.camera: Optional[Picamera2] = None
        self.thread_worker: Optional[ThreadWorker] = None
        self.captured_image: Optional[Image.Image] = None

    def _config(self) -> None:
        """Configure the camera settings."""
        preview_config = self.camera.create_preview_configuration(
            {"size": (256, 384)})
        self.capture_config = self.camera.create_still_configuration(
            main={"size": (256, 384)},
            transform=libcamera.Transform(hflip=1, vflip=1)
        )
        self.camera.configure(preview_config)
        self.camera.controls.AeEnable = True

    def preview(self) -> None:
        """Start the camera preview in a separate thread."""
        self.thread_worker = ThreadWorker()
        self.thread_worker.start(self._start_cam)

    def _start_cam(self, thread_event: threading.Event) -> None:
        """Initialize and start the camera, capturing images in a loop."""
        self.camera = Picamera2()
        self._config()
        self.camera.start()
        time.sleep(2)

        while thread_event.is_set():
            time.sleep(0.25)  # Adjust for frame rate
            self.captured_image = self.camera.switch_mode_and_capture_image(
                self.capture_config)
            self.eink.update_screen_1bit(fast_image(self.captured_image))

    def capture(self) -> Optional[Image.Image]:
        """Capture an image, stop the camera, and save the image.

        :return: The captured image.
        """
        try : 
            # stop capture first
            if self.thread_worker:
                self.thread_worker.stop()
                self.thread_worker = None

            if self.camera:
                self.camera.stop()
                time.sleep(0.1)
                self.camera.close()
                
            if self.captured_image:
                self.captured_image.save('./cam_capture_image.png')

        except Exception as e:
            logging.error(f"Error cam.capture: {e}") 

        return self.captured_image
