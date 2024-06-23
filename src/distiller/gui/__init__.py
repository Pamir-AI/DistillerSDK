import os
import logging
from typing import Type
from PIL import Image

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

try:
    from distiller.peripheral.eink import Eink
    from distiller.peripheral.button import Button
except ImportError as e:
    logging.error(f"ImportError: {e}")


class Page:
    def __init__(self, app):
        """
        Initialize a Page instance.

        :param app: The application instance to which this page belongs.
        """
        self.app = app
        self.current_ui = None

    def render_page(self, image: Image.Image, **kwargs) -> None:
        """
        Render the page with the given image.

        :param image: The image to render on the page.
        :param kwargs: Additional keyword arguments for rendering.
        """
        self.app.update_screen(image, **kwargs)

    def display(self) -> None:
        """Async method to define how the page displays itself."""
        pass

    def handle_input(self, input: str) -> None:
        """
        Async method to handle user input.

        :param input: The user input to handle.
        """
        pass


class Application:
    def __init__(self):
        """
        Initialize the Application instance.
        """
        self.current_page = Page(self)
        self.screen = Eink()
        self.buttons = Button(callback=self.press_callback)

    def switch_page(self, NewPage: Type[Page], **kwargs) -> None:
        """
        Switch to a new page.

        :param NewPage: The new page class to switch to.
        :param kwargs: Additional keyword arguments for the new page.
        """
        self.current_page = NewPage(self, **kwargs)

    def update_screen(self, image: Image.Image, format: str = '1bit', dithering: bool = True) -> None:
        """
        Update the e-ink screen with the given image.

        :param image: The image to display.
        :param format: The format of the image ('1bit' or '2bit').
        :param dithering: Whether to apply dithering (only for '1bit' format).
        """
        logging.info('Updating screen')
        if format == '1bit':
            self.screen.update_screen_1bit(image, dithering=dithering)
        elif format == '2bit':
            self.screen.update_screen_2bit(image)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def press_callback(self, key: str) -> None:
        """
        Callback function for button presses.

        :param key: The key that was pressed.
        """
        # handle universal case, reflush screen
        if key == -1:
            self.screen.reflush()
            return 

        # proceed as normal
        self.current_page.handle_input(key)

    def update_system_stats(self) -> None:
        """
        Update the system statistics on the screen.
        """
        # TODO: Use self.screen.last_image_cache and repaint the top bar
        pass

    def _get_system_stats(self) -> str:
        """
        Get the current system statistics.

        :return: A string representing the CPU and RAM usage.
        """
        command = '''top -bn1 | awk '/Cpu\\(s\\):/ {cpu_usage = 100 - $8} /MiB Mem :/ {mem_usage = ($8/$6)*100} END {printf "%.2f%% CPU, %.2f%% RAM\\n", cpu_usage, mem_usage}' '''
        return str(os.system(command)).strip()
