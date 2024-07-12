# main page to display and call apps
from distiller.utils.commons import ThreadWorker
from distiller.utils.image import paste_image, scale_image, show_text
from distiller.constants import EINK_WIDTH, EINK_HEIGHT
from distiller.gui.components import *
from distiller.gui import Page, Application
from PIL import Image
from pkg_resources import resource_filename
import os
from pathlib import Path
import time
import json
import asyncio
import subprocess  # Import subprocess module
import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


dialog_box_path = resource_filename(
    'distiller', os.path.join('resources', 'dialogBox_240x97.png'))
dialog_box_size = (240, 97)
dialog_box_bounding_box = (15, 15, 220, 85)
dialog_font_size = 15

loading_animation_folder = resource_filename(
    'distiller', os.path.join('resources', 'animations', 'loading_screen'))
font_path = resource_filename('distiller', os.path.join(
    'resources', 'fonts', 'Monorama-Bold.ttf'))
assets_folder = "./assets"


class SelectionPage(Page):
    def __init__(self, app):
        super().__init__(app)
        # find all files ending with .png in the assets folder
        self.images = []
        for file in os.listdir(assets_folder):
            if file.endswith(".png"):
                self.images.append(os.path.join(assets_folder, file))

        # main ui, init with first image
        self.ui = GUI(init_image=self.get_image())

        # dialog box
        self.dialog = ScrollGUI(
            dialog_box_size[0],
            dialog_box_size[1],
            dialog_box_bounding_box,
            init_image=Image.open(dialog_box_path),
            position=(0, EINK_HEIGHT - dialog_box_size[1])
        )

        # add image path to dialog
        for image in self.images:
            name = os.path.basename(image)
            self.dialog.add_component(
                TextBox(text=name, font_path=font_path, font_size=dialog_font_size))

        # render dialog
        self.dialog.render_scroll()
        self.ui.paste_image(self.dialog.get_image(),
                            self.dialog.kwargs.get('position'))

        self.render_page(self.ui.get_image(), format='2bit')

    def get_image(self, index=0):
        return paste_image(
            image=Image.open(self.images[index]),
            canvas_image=Image.new("L", (EINK_WIDTH, EINK_HEIGHT), "white")
        )

    def handle_input(self, input):
        if input == 0 or input == 1:
            self.dialog.index_up() if input == 0 else self.dialog.index_down()
            image = self.get_image(self.dialog.index)
            self.ui.paste_image(image, (0, 0))
            self.dialog.render_scroll()  # update dialog scroll
            # main ui render
            self.ui.paste_image(self.dialog.get_image(), self.dialog.kwargs.get(
                'position'))  # update on main ui
            self.render_page(self.ui.get_image(), format='2bit')  # render
            return
        
        if input == 2:
            # full screen display
            self.display(self.get_image(self.dialog.index))
            return

    def display(self, image):
        self.render_page(paste_image(image, self.ui.get_image(), border=True), format='2bit')


class App(Application):
    def __init__(self):
        super().__init__()
        self.current_page = SelectionPage(self)


if __name__ == '__main__':
    App()
    while True:
        logging.info('gallery app ping')
        time.sleep(5)
