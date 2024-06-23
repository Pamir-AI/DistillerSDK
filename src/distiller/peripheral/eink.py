from ast import List
import os
import time
import logging
from typing import Optional
import numpy as np
import bisect
from numba import jit
import asyncio
from functools import cache

from PIL import Image
from distiller.drivers.eink_dsp import EinkDSP
from distiller.constants import EINK_WIDTH, EINK_HEIGHT
from distiller.utils.commons import ThreadWorker

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


@jit(nopython=True, cache=True)
def dump_1bit(pixels: np.ndarray) -> list[int]:
    """
    Convert an image to 1-bit representation.

    :param pixels: The input pixel array.
    :return: A list of integers representing the 1-bit image.
    """
    # Flatten the array for processing
    # Ensure pixels are in valid range after dithering
    pixels = np.clip(pixels, 0, 255)
    pixels_quantized = np.digitize(pixels, bins=[64, 128, 192], right=True)

    # Calculate the needed size for the result
    result_size = (pixels.size + 7) // 8
    int_pixels = np.zeros(result_size, dtype=np.uint8)

    index = 0
    for i in range(pixels_quantized.size):
        bit = 1 if pixels_quantized.flat[i] in [2, 3] else 0
        if i % 8 == 0 and i > 0:
            index += 1
        int_pixels[index] |= bit << (7 - (i % 8))
    return [int(x) for x in int_pixels]


@jit(nopython=True, cache=True)
def dump_1bit_with_dithering(pixels: np.ndarray) -> list[int]:
    """
    Convert an image to 1-bit representation with dithering.

    :param pixels: The input pixel array.
    :return: A list of integers representing the 1-bit image with dithering.
    """
    pixels = floydSteinbergDithering_numba(pixels)
    return dump_1bit(pixels)


@jit(nopython=True, cache=True)
def floydSteinbergDithering_numba(pixels: np.ndarray) -> np.ndarray:
    """
    Apply Floyd-Steinberg dithering to an image.

    :param pixels: The input pixel array.
    :return: The dithered pixel array.
    """
    for y in range(pixels.shape[0] - 1):
        for x in range(1, pixels.shape[1] - 1):
            old_pixel = pixels[y, x]
            new_pixel = np.round(old_pixel / 85) * 85
            pixels[y, x] = new_pixel
            quant_error = old_pixel - new_pixel
            pixels[y, x + 1] += quant_error * 7 / 16
            pixels[y + 1, x - 1] += quant_error * 3 / 16
            pixels[y + 1, x] += quant_error * 5 / 16
            pixels[y + 1, x + 1] += quant_error * 1 / 16
    return pixels


def paste_image(image: Image.Image, canvas_image: Image.Image, position: tuple[int, int] = None, border: bool = False, type: str = None) -> Image.Image:
    canvas_ref = canvas_image.copy().convert(type) if type else canvas_image.copy()
    if border:
        image = ImageOps.expand(image, border=10, fill='white')
        image = ImageOps.expand(image, border=2, fill='black')
    if not position:
        position = ((canvas_image.width - image.width) // 2, (canvas_image.height - image.height) // 2)
    canvas_ref.paste(image, position)
    return canvas_ref


class Eink:
    def __init__(self) -> None:
        """Initialize the Eink class."""
        self.display = EinkDSP()
        self.locked = False
        self.in_4g = True
        self.thread_worker: Optional[ThreadWorker] = None
        self.last_image_cache: Optional[Image.Image] = None

    @cache
    def run_animation(self, thread_event, image_folder: str) -> None:
        """
        Run an animation by cycling through images in a folder.

        :param thread_event: The threading event to control the animation loop.
        :param image_folder: The folder containing the images.
        """
        image_files = [f for f in os.listdir(
            image_folder) if f.endswith(('.png', '.jpg', '.jpeg'))]
        images = [Image.open(os.path.join(image_folder, file))
                  for file in image_files]
        while thread_event.is_set():
            for image in images:
                frame = paste_image(image, self.last_image_cache)
                self.update_screen_1bit(frame)
                time.sleep(0.1)  # Adjust time per frame as needed

    def start_animation(self, canvas_image: Image.Image, image_folder: str) -> None:
        """
        Start the animation.

        :param canvas_image: The background image.
        :param image_folder: The folder containing the images.
        """
        logging.info(f"{canvas_image} , {image_folder}")
        self.last_image_cache = canvas_image
        self.thread_worker = ThreadWorker()
        self.thread_worker.start(self.run_animation, (image_folder,))

    def stop_animation(self) -> None:
        """Stop the animation."""
        if self.thread_worker:
            self.thread_worker.stop()

    def transit_to_1bit(self) -> None:
        """Transition the display to 1-bit mode."""
        self.display.epd_init_fast()
        self.display.pic_display_clear()
        logging.info('transit to 2 grad')

    def clear_screen(self) -> None:
        """Clear the e-ink screen."""
        logging.info('clear screen')
        image = Image.new("L", (EINK_WIDTH, EINK_HEIGHT), "white")
        hex_pixels = dump_1bit(self.preprocess_1bit(image, np.uint8))
        self.display.epd_init_part()
        self.display.pic_display(hex_pixels)
        self.display.pic_display_clear()

    def update_screen_1bit(self, image: Image.Image, dithering: bool = True) -> None:
        """
        Update the e-ink screen with a 1-bit image.

        :param image: The image to display.
        :param dithering: Whether to apply dithering.
        """
        logging.info('running update_screen_1bit')
        self._status_check()
        pixels = self.preprocess_1bit(
            image) if dithering else self.preprocess_1bit(image, np.uint8)
        hex_pixels = dump_1bit_with_dithering(
            pixels) if dithering else dump_1bit(pixels)
        self.display.epd_init_part()
        self.display.pic_display(hex_pixels)
        self.last_image_cache = image

    def update_screen_2bit(self, image: Image.Image) -> None:
        """
        Update the e-ink screen with a 2-bit image.

        :param image: The image to display.
        """
        logging.info('running update_screen_2bit')
        self.in_4g = True
        hex_pixels = self.preprocess_2bit(image)
        self.display.epd_w21_init_4g()
        self.display.pic_display_4g(hex_pixels)
        self.display.epd_sleep()
        self.last_image_cache = image

    def reflush(self) -> None:
        self.update_screen_2bit(self.last_image_cache)

    def _status_check(self) -> None:
        """Check and update the display status."""
        if self.in_4g:
            self.transit_to_1bit()
            self.in_4g = False

    def preprocess_1bit(self, image: Image.Image, dtype=np.float32) -> np.ndarray:
        """
        Preprocess the image for 1-bit display.

        :param image: The image to preprocess.
        :param dtype: The data type for the numpy array.
        :return: The preprocessed image as a numpy array.
        """
        return np.array(image.transpose(Image.FLIP_TOP_BOTTOM).convert('L'), dtype=dtype)

    def preprocess_2bit(self, image: Image.Image) -> list[int]:
        """
        Preprocess the image for 2-bit display.

        :param image: The image to preprocess.
        :return: A list of integers representing the 2-bit image.
        """
        pixels = np.array(image.convert('L'), dtype=np.float32)
        pixels = floydSteinbergDithering_numba(pixels)
        pixels = np.clip(pixels, 0, 255)
        pixels_quantized = np.digitize(pixels, bins=[64, 128, 192], right=True)

        pixel_map = {0: '00', 1: '01', 2: '10', 3: '11'}
        pixels_string = np.vectorize(pixel_map.get)(pixels_quantized).flatten()

        group_size = 4
        grouped_pixels = [''.join(pixels_string[i:i+group_size])
                          for i in range(0, len(pixels_string), group_size)]
        int_pixels = [int(bits, 2) for bits in grouped_pixels]

        return [int(x) for x in int_pixels]
