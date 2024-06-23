import numpy as np
from PIL import Image, ImageOps
from typing import Optional
from distiller.gui.components import Box, Text
from distiller.constants import EINK_WIDTH, EINK_HEIGHT, DEFAULT_FONT_PATH
from distiller.utils.text import trim_text_chunk

def invert_pixels_within_region(image: Image.Image, mask: Image.Image, top_left: tuple[int, int]) -> Image.Image:
    """
    Inverts pixels within a specified region of a binary image using a mask.
    Assumes image is in '1' (binary) mode and mask is correctly aligned.

    :param image: The PIL Image object to modify, in '1' mode.
    :param mask: A PIL Image object representing the mask, same size as the region.
    :param top_left: A tuple (x, y) specifying the top left corner of the region.
    """
    image = image.convert('L')
    mask = mask.convert('L')
    image_array = np.array(image, dtype=np.uint8)
    mask_array = np.array(mask, dtype=np.uint8)
    x_start, y_start = top_left
    x_end, y_end = x_start + mask.width, y_start + mask.height
    region = image_array[y_start:y_end, x_start:x_end]
    region_inverted = np.where(mask_array == 255, 255 - region, region)
    image_array[y_start:y_end, x_start:x_end] = region_inverted
    return Image.fromarray(image_array, 'L').convert('1')


def scale_image(image: Image.Image, buffer: int = 5) -> Image.Image:
    max_width = EINK_WIDTH - buffer * 2
    max_height = EINK_HEIGHT - buffer * 2
    # Calculate the scaling factor
    width_ratio = max_width / image.width
    height_ratio = max_height / image.height
    scale_factor = min(width_ratio, height_ratio)
    # Calculate new dimensions
    new_width = int(image.width * scale_factor)
    new_height = int(image.height * scale_factor)
    return image.resize((new_width, new_height), Image.ANTIALIAS)


def paste_image(image: Image.Image, canvas_image: Image.Image, position: tuple[int, int] = None, border: bool = False, type: str = None) -> Image.Image:
    canvas_ref = canvas_image.copy().convert(type) if type else canvas_image.copy()
    if border:
        image = ImageOps.expand(image, border=10, fill='white')
        image = ImageOps.expand(image, border=2, fill='black')
    if not position:
        position = ((canvas_image.width - image.width) // 2, (canvas_image.height - image.height) // 2)
    canvas_ref.paste(image, position)
    return canvas_ref


def fast_image(image: Image.Image, border: bool = False) -> Image.Image:
    canvas_ref = Image.new("L", (EINK_WIDTH, EINK_HEIGHT), "white")
    if border:
        image = ImageOps.expand(image, border=10, fill='white')
        image = ImageOps.expand(image, border=2, fill='black')
    position = ((canvas_ref.width - image.width) // 2, (canvas_ref.height - image.height) // 2)
    canvas_ref.paste(image, position)
    return canvas_ref


def show_text(canvas: Image.Image, text: str, font_path: Optional[str] = DEFAULT_FONT_PATH, size: int = 20) -> None:
    _text = Text(text, font_path, size)
    # max box
    box_width, box_height = EINK_WIDTH - 20, EINK_HEIGHT - 20
    padding = size // 4
    # check if multiple line
    if _text.size[0] >= EINK_WIDTH:  # multi line
        lines = trim_text_chunk(text, font_path, _text.size[1], bounding_box=[padding, padding, box_width - padding, box_height - padding])
        box_height = (len(lines) + 1) * _text.fontsize
        pos = ((EINK_WIDTH - box_width) // 2, (EINK_HEIGHT - box_height) // 2)
        # box start from center
        Box(pos, (box_width, box_height), corner_radius=5, padding=0, line_thickness=4).draw(canvas)
        _text.draw_wrapped(canvas, bounding_box=(pos[0] + padding, pos[1] + padding, pos[0] + box_width - padding, pos[1] + box_height - padding))
    else:  # single center
        pos = ((EINK_WIDTH - box_width) // 2, EINK_HEIGHT // 2)
        Box((EINK_WIDTH // 2 - _text.size[0] // 2 - 5, pos[1]), (_text.size[0] + 10, _text.size[1] + 10), corner_radius=5, padding=0, line_thickness=4).draw(canvas)
        _text.draw(canvas, (0, pos[1] + padding), centered=True)


def merge_inpaint(init_image: Image.Image, image: Image.Image, mask: Image.Image) -> Image.Image:
    init_image = init_image.convert("RGBA")
    alpha_image = image.copy()
    mask_image = mask.convert("L")
    alpha_image.putalpha(mask_image)
    combined_image = Image.alpha_composite(init_image, alpha_image)
    return combined_image