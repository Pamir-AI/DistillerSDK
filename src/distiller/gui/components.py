from pkg_resources import resource_filename
import os
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from distiller.constants import *
import numpy as np
from distiller.utils.text import split_text_chunks, trim_text_chunk

import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class Canvas:
    def __init__(self, width, height, background_color='white', init_image=None):
        self.width = width
        self.height = height
        self.background_color = background_color
        self.init_image = init_image
        self.image = Image.new(
            '1', (width, height), background_color) if not init_image else init_image

    def register_canvas_image(self):
        # cache the image checkpoint
        self.init_image = self.image.copy()

    def flush(self):
        self.image = Image.new('1', (self.width, self.height),
                               self.background_color) if not self.init_image else self.init_image.copy()

    def get_draw(self):
        return ImageDraw.Draw(self.image)

    def draw_plus_pattern(self, density=10, start_pos=(5, 5), size=5):
        """
        Draw a '+' pattern on the canvas starting from start_pos, with specified size and density.

        :param canvas: PIL Image object where the '+' pattern will be drawn.
        :param density: Determines how close each '+' is to its neighbor.
        :param start_pos: A tuple (x, y) indicating the starting position for the pattern.
        :param size: The size of the '+', which also dictates the width of each stroke. Minimum value is 3.
        """
        draw = self.get_draw()
        width, height = self.image.size
        x_start, y_start = start_pos

        # Ensure size is at least 3
        size = max(size, 3)
        half_size = size // 2

        # Calculate the step between each '+' based on density
        step = max(size, density)

        for y in range(y_start, height, step):
            for x in range(x_start, width, step):
                # Vertical line of '+'
                draw.line([(x, y - half_size), (x, y + half_size)],
                          fill='black')
                # Horizontal line of '+'
                draw.line([(x - half_size, y), (x + half_size, y)],
                          fill='black')

    def copy(self):
        cls = self.__class__
        result = cls.__new__(cls)
        result.__dict__.update(self.__dict__)
        return result


class GUIComponent:
    def __init__(self, position: tuple[int, int] = (0, 0)):
        """
        Initialize a GUI component with a position.

        :param position: A tuple representing the x and y coordinates.
        """
        self.position = position

    def get_text(self) -> Optional[str]:
        """
        Return the text associated with the GUI component, if any.

        :return: Text as a string or None if no text is associated.
        """
        raise NotImplementedError("Subclasses should implement this!")

    def draw(self, canvas) -> None:
        """
        Draw the component on the given canvas. Must be implemented by subclasses.

        :param canvas: The canvas on which to draw the component.
        """
        raise NotImplementedError("Subclasses should implement this!")


class Text(GUIComponent):
    def __init__(self, text: str, font_path: Optional[str] = DEFAULT_FONT_PATH, font_size: Optional[int] = 20):
        super().__init__()
        self.text = text
        self.font = self.load_font(font_path, font_size)
        self.fontsize = font_size + 2  # add some buffer space
        self.size = self.calculate_text_size()

    @staticmethod
    def load_font(font_path: str, font_size: int) -> ImageFont:
        """
        Load the font from the specified path and size.

        :param font_path: Path to the font file.
        :param font_size: Size of the font.
        :return: Loaded font.
        """
        try:
            return ImageFont.truetype(font_path, font_size)
        except IOError:
            logging.error(f"Failed to load font from {font_path}")
            raise

    def calculate_text_size(self) -> tuple[int, int]:
        """
        Calculate the size of the text.

        :return: Tuple of width and height of the text.
        """
        draw = ImageDraw.Draw(Image.new('1', (EINK_WIDTH, EINK_HEIGHT)))
        width = int(draw.textlength(self.text, font=self.font))
        return (width, self.fontsize)

    def get_text(self) -> str:
        return self.text

    def update_text(self, text: str):
        self.text = text
        self.size = self.calculate_text_size()

    def draw(self, canvas, position: tuple[int, int], centered: bool = False, max_width: Optional[int] = None) -> None:
        # Draw text on the given canvas
        draw = canvas.get_draw()
        x, y = position
        if centered:
            x = (EINK_WIDTH-self.size[0])//2
        # trim and add ...
        temp_text = self.text
        if max_width and self.size[0] > max_width:
            temp_text = self.trim_text_to_fit_width(temp_text, max_width, draw)
        draw.text((x, y), temp_text, fill="black", font=self.font)

    def trim_text_to_fit_width(self, text: str, max_width: int, draw: ImageDraw) -> str:
        """
        Trim the text to fit within the specified width and append ellipsis.

        :param text: Original text.
        :param max_width: Maximum width allowed.
        :param draw: ImageDraw instance used for measuring text.
        :return: Trimmed text with ellipsis if needed.
        """
        while draw.textlength(text + '...', font=self.font) > max_width:
            text = text[:-1]
        return text + '...'

    def draw_wrapped(self, canvas, bounding_box: tuple[int, int, int, int]) -> bool:
        """
        Draw text within a specified bounding box with word wrapping and vertical limit checking.

        Args:
            canvas (Canvas): The canvas to draw on.
            bounding_box (tuple): A tuple (x, y, x_end, y_end) specifying the bounding box for the text.
        """
        draw = canvas.get_draw()
        x, y = bounding_box[:2]
        max_width, max_height = bounding_box[2] - x, bounding_box[3] - y
        words = self.text.split()
        lines = []
        line = []
        # Assuming line height is roughly equal to font size
        line_height = self.fontsize

        for word in words:
            # Test if adding this word to the current line would exceed the max width
            test_line = ' '.join(line + [word])
            w, _ = draw.textsize(test_line, font=self.font)

            if w <= max_width:
                line.append(word)  # If not, add the word to the current line
            else:
                # If the line is too long, start a new line
                if (len(lines) + 1) * line_height >= max_height:
                    logging.warn(
                        "Warning: text is too long to fit in the bunding box")
                    return False

                # draw processed line
                draw.text((x, y), ' '.join(line), font=self.font, fill="black")
                y += line_height
                lines.append(' '.join(line))
                line = [word]

        # Check if adding the last line still fits
        if (len(lines) + 1) * line_height < max_height:
            draw.text((x, y), ' '.join(line), font=self.font, fill="black")
            # lines.append(' '.join(line))

        return True


class Icon(GUIComponent):
    def __init__(self, position: tuple[int, int], icon_path: str, height: int = 32, padding: int = 5):
        super().__init__(position)
        self.icon = self.load_and_process_icon(icon_path, height, padding)

    def load_and_process_icon(self, icon_path: str, height: int, padding: int) -> Image.Image:
        """
        Load an icon from the path, resize it, and apply transparency based on white color.

        :param icon_path: Path to the icon image.
        :param height: Desired height of the icon.
        :param padding: Padding to reduce the effective height.
        :return: Processed icon image.
        """
        try:
            icon = Image.open(icon_path).convert('RGBA')
            aspect_ratio = icon.width / icon.height
            new_height = height - 2 * padding
            new_width = int(aspect_ratio * new_height)
            icon = icon.resize((new_width, new_height), Image.ANTIALIAS)
            return self.apply_transparency(icon)
        except IOError:
            logging.error(f"Failed to load icon from {icon_path}")
            raise

    def apply_transparency(self, icon: Image.Image) -> Image.Image:
        """
        Apply transparency to an icon based on white color detection.

        :param icon: Icon image.
        :return: Icon with transparency applied.
        """
        mask = Image.new("L", icon.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        for x in range(icon.width):
            for y in range(icon.height):
                r, g, b, a = icon.getpixel((x, y))
                if r > 200 and g > 200 and b > 200:
                    mask_draw.point((x, y), 0)
                else:
                    mask_draw.point((x, y), 255)
        icon.putalpha(mask)
        return icon

    def draw(self, canvas) -> None:
        # Draw icon on the given canvas
        # self.transparent_icon()
        canvas.image.paste(self.icon, self.position)


class Box(GUIComponent):
    def __init__(self, position: tuple[int, int], size: tuple[int, int], fill: bool = False, corner_radius: int = 0, line_thickness: int = 2, padding: int = 3):
        """
        Initialize a Box component.

        :param position: A tuple representing the x and y coordinates.
        :param size: A tuple representing the width and height of the box.
        :param fill: Whether the box should be filled.
        :param corner_radius: The radius of the box corners.
        :param line_thickness: The thickness of the box lines.
        :param padding: The padding inside the box.
        """
        super().__init__(position)
        self.size = size
        self.fill = fill
        self.corner_radius = corner_radius
        self.line_thickness = line_thickness
        self.padding = padding
        self.mask = None

    def generate_mask(self) -> None:
        """Generate a mask for the box."""
        width, height = self.size
        mask = Image.new('1', self.size, 'black')
        draw_mask = ImageDraw.Draw(mask)
        padded_rectangle = (self.padding, self.padding,
                            width - self.padding, height - self.padding)
        draw_mask.rounded_rectangle(padded_rectangle, radius=self.corner_radius,
                                    fill='white', outline='black', width=self.line_thickness)
        self.mask = mask

    def get_mask(self) -> Image.Image:
        """Get the mask for the box, generating it if necessary."""
        if self.mask is None:
            self.generate_mask()
        return self.mask

    def draw(self, canvas) -> None:
        """Draw the box on the given canvas."""
        image = Image.new('1', self.size, 'white')
        draw_image = ImageDraw.Draw(image)
        x, y = self.position
        width, height = self.size
        padded_rectangle = (self.padding, self.padding,
                            width - self.padding, height - self.padding)
        fill_color = 'black' if self.fill else 'white'
        draw_image.rounded_rectangle(padded_rectangle, radius=self.corner_radius,
                                     fill=fill_color, outline='black', width=self.line_thickness)
        canvas.image.paste(image, self.position)

    def invert_region(self, canvas) -> Image.Image:
        """
        Invert pixels within a specified region of a binary image using a mask.

        :param canvas: The canvas containing the image to invert.
        :return: The image with the specified region inverted.
        """
        image = canvas.image
        mask = self.get_mask()
        image_array = np.array(image.convert('L'), dtype=np.uint8)
        mask_array = np.array(mask.convert('L'), dtype=np.uint8)
        x_start, y_start = self.position
        x_start = max(0, x_start)
        y_start = max(0, y_start)
        x_end, y_end = x_start + mask.width, y_start + mask.height
        region = image_array[y_start:y_end, x_start:x_end]
        region_inverted = np.where(mask_array == 255, 255 - region, region)
        image_array[y_start:y_end, x_start:x_end] = region_inverted
        return Image.fromarray(image_array, 'L').convert('1')

    def click(self) -> None:
        """Handle click events for the box."""
        pass


class TextBox(Box):
    """
    As of now, TextBox only supports 1 line text. Any part of the text that exceeds 
    the width of the box will be replaced with '...'. This is designed to serve as a button, so don't write it too long.
    """

    def __init__(self, text: str, font_path: Optional[str] = DEFAULT_FONT_PATH, font_size: Optional[int] = 20, icon_path: Optional[str] = None, size: Optional[tuple[int, int]] = None, position: tuple[int, int] = (0, 0), fill: bool = False, corner_radius: int = 1, line_thickness: int = 0, padding: int = 0):
        self.text = Text(text, font_path, font_size)
        if self.text.size[0] >= EINK_WIDTH:
            logging.warn('Multi-line text box not supported yet')
        size = self.text.size if size is None else size
        super().__init__(position, size, fill, corner_radius, line_thickness, padding)
        self.icon = Icon(position=(0, 0), icon_path=icon_path,
                         height=self.size[1] - line_thickness * 2, padding=2) if icon_path else None

    def get_text(self) -> str:
        return self.text.text

    def update_position(self, position: tuple[int, int]) -> None:
        self.position = position
        self.text.position = (position[0] + self.line_thickness * 2,
                              position[1] + self.size[1] // 2 - self.text.fontsize // 2)
        if self.icon:
            self.icon.position = (position[0] + self.size[0] - self.icon.icon.width -
                                  self.line_thickness * 2, position[1] + self.line_thickness)

    def draw(self, canvas) -> None:
        super().draw(canvas)
        self.text.draw(canvas, self.text.position,
                       max_width=canvas.image.width)
        if self.icon:
            self.icon.draw(canvas)


class GUI:
    def __init__(self, width: int = EINK_WIDTH, height: int = EINK_HEIGHT, **kwargs):
        """
        Initialize the GUI with a specific width and height, and optional keyword arguments.

        :param width: The width of the GUI canvas.
        :param height: The height of the GUI canvas.
        :param kwargs: Additional keyword arguments.
        """
        self.init_image = kwargs.get("init_image", None)
        self.canvas = Canvas(width, height, init_image=self.init_image)
        self.kwargs = kwargs
        self.index = 0
        self.components = []
        self.clickables = []

    def index_reset(self) -> None:
        """Reset the index to 0."""
        self.index = 0

    def index_up(self) -> None:
        """Move the index up by one position."""
        if len(self.components) == 0:
            return
        self.index = (self.index - 1) % len(self.components)

    def index_down(self) -> None:
        """Move the index down by one position."""
        if len(self.components) == 0:
            return
        self.index = (self.index + 1) % len(self.components)
        print("idx, components", self.index, len(self.components))

    def update_canvas_image(self, image: Image.Image) -> None:
        """Update the canvas image."""
        self.canvas.image = image

    def get_image(self) -> Image.Image:
        """Get the current image from the canvas."""
        return self.canvas.image

    def add_component(self, component: GUIComponent) -> None:
        """Add a component to the GUI."""
        self.components.append(component)
        if isinstance(component, Box):  # if component is clickable
            self.clickables.append(component)

    def render_all(self) -> None:
        """Render all components on the canvas."""
        for component in self.components:
            if isinstance(component, (Box, Icon)):  # only render static components
                component.draw(self.canvas)

    def paste_image(self, image: Image.Image, position: tuple[int, int] = (0, 0)) -> None:
        """Paste an image onto the canvas at the specified position."""
        self.canvas.image.paste(image, position)

    def click(self) -> None:
        """Handle click events."""
        pass

    def next_page(self) -> None:
        """Handle the event to move to the next page."""
        pass


class ScrollGUI(GUI):
    def __init__(self, width: int, height: int, bounding_box: tuple[int, int, int, int], line_space: int = 1, **kwargs):
        """
        Initialize a ScrollGUI component.

        :param width: The width of the ScrollGUI.
        :param height: The height of the ScrollGUI.
        :param bounding_box: A tuple (x, y, max_x, max_y) specifying the bounding box for the text.
        :param line_space: The space between lines of text.
        :param kwargs: Additional keyword arguments.
        """
        super().__init__(width, height, **kwargs)
        self.line_space = line_space
        self.bounding_box = bounding_box
        icon_size = 15
        self.down_icon = Icon(
            position=(bounding_box[2] - icon_size,
                      bounding_box[3] - icon_size),
            icon_path=resource_filename('distiller', os.path.join(
                'resources', 'icons', 'down.png')),
            height=icon_size,
            padding=0
        )

    def get_selected_component(self) -> GUIComponent:
        """
        Get the currently selected component.

        :return: The selected component.
        """
        return self.components[self.index]

    def inject_texts(self, content: str, font_path: Optional[str] = DEFAULT_FONT_PATH, font_size: Optional[int] = 20) -> None:
        """
        Inject text content into the ScrollGUI.

        :param content: The text content to inject.
        :param font_path: The path to the font file.
        :param font_size: The size of the font.
        """
        self.components.clear()
        for chunk in split_text_chunks(content, self.bounding_box, font_path, font_size):
            if chunk:
                self.components.append(Text(chunk, font_path, font_size))

    def render_scroll(self, use_index: bool = True, use_footer: bool = True) -> None:
        """
        Render a scrollable list of components on the canvas.

        :param use_index: Whether to use the index for rendering.
        :param use_footer: Whether to use the footer icon.
        """
        if not self.components:
            return

        self.canvas.flush()
        index = self.index
        x, y = self.bounding_box[:2]
        _, max_height = self.bounding_box[2:]
        max_rows = max_height // self.components[0].size[1]

        if isinstance(self.components[0], TextBox):
            for i in range(max(0, index - max_rows // 2), min(index + max_rows, len(self.components))):
                self.components[i].update_position((x, y))
                if y + self.components[i].size[1] > max_height : break # early stop
                y += self.components[i].size[1] + self.line_space
                self.components[i].draw(self.canvas)
            if use_index:
                self.update_canvas_image(
                    self.components[index].invert_region(self.canvas))
        elif isinstance(self.components[0], Text):
            self.components[self.index].draw_wrapped(
                self.canvas, self.bounding_box)

        if use_footer and self.index < len(self.components) - 1:
            self.down_icon.draw(self.canvas)

        logging.info(
            f'- {self.index}, {self.get_selected_component().get_text()}')
