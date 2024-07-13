import os
import sys
import time
from PIL import Image
from pkg_resources import resource_filename
from distiller.drivers.sam import SAM
from distiller.gui.components import ScrollGUI, Box, TextBox, Text, Canvas
from distiller.constants import EINK_WIDTH, EINK_HEIGHT
from distiller.utils.commons import HijackEink
import logging
from typing import Callable, Optional

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
FONT_PATH = resource_filename('distiller', os.path.join(
    'resources', 'fonts', 'Monorama-Bold.ttf'))
BOX_SIZE = (175, 200)
PADDING = 10


def shutdown_screen_ui() -> ScrollGUI:
    """
    Create the shutdown confirmation UI.

    :return: An instance of ScrollGUI with the shutdown confirmation UI.
    """
    box_pos = (EINK_WIDTH - BOX_SIZE[0]) // 2, (EINK_HEIGHT - BOX_SIZE[1]) // 2
    bounding_box = (box_pos[0], box_pos[1], box_pos[0] +
                    BOX_SIZE[0], box_pos[1] + BOX_SIZE[1])
    scroll_bounding_box = (box_pos[0] + 10, box_pos[1] + BOX_SIZE[1] //
                           2 + 10, box_pos[0] + BOX_SIZE[0], box_pos[1] + BOX_SIZE[1])

    # Create a canvas
    gui = ScrollGUI(EINK_WIDTH, EINK_HEIGHT, scroll_bounding_box, line_space=5)

    # Statics
    text_bounding_box = (bounding_box[0] + PADDING, bounding_box[1] +
                         PADDING, bounding_box[2] - PADDING, bounding_box[3] - PADDING)
    Box(box_pos, BOX_SIZE, corner_radius=10).draw(gui.canvas)
    Text("Shutdown Device, Are you sure?", FONT_PATH,
         20).draw_wrapped(gui.canvas, text_bounding_box)
    gui.canvas.register_canvas_image()  # Cache

    # Dynamics
    if 'main.py' in sys.argv[0]:
        gui.add_component(
            TextBox(text="shutdown", font_path=FONT_PATH, font_size=20, line_thickness=0))
    else:
        gui.add_component(
            TextBox(text="exit_app", font_path=FONT_PATH, font_size=20, line_thickness=0))
    gui.add_component(TextBox(text="back", font_path=FONT_PATH,
                      font_size=20, line_thickness=0))
    gui.render_scroll()
    return gui


class Button(SAM):
    def __init__(self, callback: Callable[[int], None]) -> None:
        """
        Initialize the Button class.

        :param callback: A callback function to process button states.
        """
        super().__init__(callback)
        self.gui: Optional[ScrollGUI] = None
        self.last_call_back: Optional[Callable[[int], None]] = None
        self.hijacked_eink: Optional[HijackEink] = None

    def process_button_state(self, state: int) -> None:
        """Process the button state byte."""
        if self.button_lock:
            return  # Button locked
        if state == self.encode_table["BTN_UP"]:
            self.callback(0)
        elif state == self.encode_table["BTN_DOWN"]:
            self.callback(1)
        elif state == self.encode_table["BTN_SELECT"]:
            self.callback(2)
        elif state == self.encode_table["SHUTDOWN"] and not self.hijacked_eink:
            logging.info("SHUTDOWN DETECTED")
            self._confirm_screen()

    def _confirm_screen(self) -> None:
        """Display the shutdown confirmation screen. switch callbacks"""
        self.last_call_back = self.callback
        self.callback = self.press_callback
        self.hijacked_eink = HijackEink()
        self.gui = shutdown_screen_ui()
        self._render_page()

    def _render_page(self) -> None:
        """Render the current page on the e-ink display."""
        if self.hijacked_eink and self.gui:
            self.hijacked_eink.update_screen_1bit(self.gui.get_image())

    def press_callback(self, key: int) -> None:
        """Handle button press events on the confirmation screen."""
        if key == 0:
            self.gui.index_up()
        elif key == 1:
            self.gui.index_down()
        elif key == 2:
            selected_text = self.gui.get_selected_component().get_text()
            logging.info(f'{selected_text}')
            method = getattr(self, selected_text, None)
            if callable(method):
                method()
        if self.gui and self.hijacked_eink:
            self.gui.render_scroll()
            self._render_page()

    def shutdown(self) -> None:
        """Shutdown the device."""
        self._shutdown()

    def back(self) -> None:
        """Cancel the shutdown and restore the previous state."""
        self.callback = self.last_call_back
        self.reset()
        self.callback(-1)  # Indicate back to screen actions

    def reset(self) -> None:
        """Reset the button state and e-ink display."""
        self.gui = None
        self.last_call_back = None
        if self.hijacked_eink:
            self.hijacked_eink.destroy()
        self.hijacked_eink = None

    def exit_app(self) -> None:
        """Exit the application."""
        logging.info("exit back to main")
        os.system("pkill -f " + sys.argv[0])

    def _shutdown(self) -> None:
        """Perform the shutdown operation."""
        logging.info("SHUTDOWN TRIGGERED")
        if self.hijacked_eink:
            self.hijacked_eink.eink.clear_screen()
            self.hijacked_eink.update_screen_1bit(Image.open(resource_filename(
    'distiller', os.path.join('resources', 'idle-frame.png'))))

        self.ser.write('15\n'.encode())
        self.ser.write('15\n'.encode())
        time.sleep(1)
        os.system("sudo shutdown now")
