# main page to display and call apps
from lib.stable_diffusion_tools import StableDiffusionRender, StableDiffusionXSRender,  PromptGenerator
from distiller.peripheral.speaker import play_audio
from PIL import Image
from pkg_resources import resource_filename
from distiller.utils.image import paste_image, scale_image
from distiller.constants import EINK_WIDTH, EINK_HEIGHT
from distiller.gui.components import *
from distiller.gui import Page, Application
import os
from pathlib import Path
import time
import json
import asyncio
import subprocess  # Import subprocess module
import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


# load from lib provided


sound_bite = resource_filename('distiller', os.path.join(
    'resources', 'audios', 'anime-wow-sound-effect.wav'))

dialog_box_path = resource_filename(
    'distiller', os.path.join('resources', 'dialogBox_240x97.png'))
dialog_box_size = (240, 97)
dialog_box_bounding_box = (15, 15, 225, 80)
dialog_font_size = 20

loading_animation_folder = resource_filename(
    'distiller', os.path.join('resources', 'animations', 'loading_screen'))
dialog_box_path = resource_filename(
    'distiller', os.path.join('resources', 'dialogBox_240x97.png'))
font_path = resource_filename('distiller', os.path.join(
    'resources', 'fonts', 'Monorama-Bold.ttf'))
model_folder = "/home/distiller/models"


class ModelSelectionBox(Box):
    def __init__(self, position, size, next_page, model_config, **kwargs):
        super().__init__(position, size, **kwargs)
        self.next_page = next_page
        self.model_config = model_config

    def click(self, app):  # switch page
        # get into the stable diffusion editor
        app.switch_page(self.next_page, model_config=self.model_config)

    def cursor_render(self, canvas):
        pass


class ModelSelectionPage(Page):
    """
        render box per index selection 
    """

    def __init__(self, app):
        super().__init__(app)
        self.index = 0
        # list of models to use
        config_name = "model_config.json"
        self.model_list = [file_path for file_path in Path(
            model_folder).rglob(f"*/{config_name}")]
        self.thumbnail_list = [str(file_path).replace(
            config_name, "thumbnail.png") for file_path in self.model_list]

        # create box and read all models
        self.boxes = []
        self.thumbnails = []
        self.model_configs = []
        for model_file, thumbnail_file in zip(self.model_list, self.thumbnail_list):
            with open(model_file) as f:
                self.model_configs.append(json.load(f))

            thumbnail = Image.open(thumbnail_file)
            if thumbnail.width >= EINK_WIDTH or thumbnail.height >= EINK_HEIGHT:
                thumbnail = scale_image(thumbnail)
            top_left = ((EINK_WIDTH-thumbnail.width)//2,
                        (EINK_HEIGHT-thumbnail.height)//2)
            self.thumbnails.append(thumbnail)
            self.boxes.append(ModelSelectionBox(
                top_left, (thumbnail.width, thumbnail.height + 25), line_thickness=0,
                next_page=EditingPage,
                model_config=self.model_configs[-1]
            ))

        # init render
        self.gui = GUI()
        self.gui.canvas.draw_plus_pattern()
        self.render_page(self.prepare_page_image())

    def handle_input(self, input):
        # up or down
        if input == 0:
            self.index = (self.index - 1) % len(self.boxes)
            self.render_page(self.prepare_page_image())  # switch page context
        elif input == 1:
            self.index = (self.index + 1) % len(self.boxes)
            self.render_page(self.prepare_page_image())  # switch page context
        # enter
        elif input == 2:
            self.boxes[self.index].click(self.app)  # enter next page

    def prepare_page_image(self):
        model_name = self.model_configs[self.index]['model_name']
        title = Text(model_name, font_path, 20)
        temp_canvas = self.gui.canvas.copy()
        self.boxes[self.index].draw(temp_canvas)  # show box
        title.draw(temp_canvas, position=(
            0, self.boxes[self.index].position[1] + self.thumbnails[self.index].size[1] + 5), centered=True)  # show text
        # add thumbnail
        return paste_image(image=self.thumbnails[self.index], canvas_image=temp_canvas.image, position=self.boxes[self.index].position)


class EditingPage(Page):
    image_size = (128*2, 128*3)
    dialog_box_size = (240, 97)

    def __init__(self, app, model_config):
        super().__init__(app)
        # sd objects
        self.model_config = model_config
        self.pipe = None
        self.file_cache = f"./temp-{self.model_config['model_name']}.png"

        # UIs components
        self.ui = GUI()
        self.image_display = GUI(
            width=self.image_size[0], height=self.image_size[1], init_image=self.get_init_image())
        # dialog boxes
        self.dialog = ScrollGUI(
            dialog_box_size[0],
            dialog_box_size[1],
            dialog_box_bounding_box,
            init_image=Image.open(dialog_box_path),
            position=(0, EINK_HEIGHT - dialog_box_size[1])
        )
        dialog_font_size = 15
        self.dialog.add_component(
            TextBox(text="generate_new", font_path=font_path, font_size=dialog_font_size))
        self.dialog.add_component(
            TextBox(text="refresh", font_path=font_path, font_size=dialog_font_size))
        self.dialog.add_component(
            TextBox(text="back", font_path=font_path, font_size=dialog_font_size))

        self.dialog_text = ScrollGUI(
            dialog_box_size[0],
            dialog_box_size[1],
            dialog_box_bounding_box,
            init_image=Image.open(dialog_box_path),
            position=(0, EINK_HEIGHT - dialog_box_size[1])
        )

        # limit to 1 interface at a time
        self.interface = self.dialog

        # one time notifications
        self.loading_text = Text("Loading model ... ", font_path, 20)
        self.prompt_text = Text("placeholder", font_path, 12)

        # init dialog
        self.interface.render_scroll()

        # put all ui parts together
        self.ui.paste_image(self.image_display.get_image())
        self.ui.paste_image(self.interface.get_image(),
                            self.interface.kwargs.get('position'))

        # init render
        self.render_page(self.ui.get_image(), format='2bit')

    def show_image(self, prompt_text):
        # switch interface
        self.interface = self.dialog_text

        # render
        self.ui.paste_image(Image.open(self.file_cache))  # paste image display
        self.interface.canvas.flush()  # flush out old texts

        # take care of text
        self.interface.inject_texts(prompt_text, font_path, 15)
        self.interface.render_scroll()

        # update ui
        self.ui.paste_image(self.interface.get_image(
        ), self.interface.kwargs.get('position'))  # paste dialog box
        self.render_page(self.ui.get_image(), format='2bit')

    def get_init_image(self):
        if os.path.exists(self.file_cache):  # reload
            image = Image.open(self.file_cache)
            prompt_str = image.info.get("prompt")
        else:  # show logo, init dependencies
            image = paste_image(
                image=Image.open(resource_filename(
                    'distiller', os.path.join('resources', 'logo.png'))),
                canvas_image=Image.new("L", (EINK_WIDTH, EINK_HEIGHT), "white")
            )
        return image

    def handle_input(self, input):
        if input == 0 or input == 1:
            self.interface.index_up() if input == 0 else self.interface.index_down()
            self.interface.render_scroll()  # update dialog scroll
            # main ui render
            self.ui.paste_image(self.interface.get_image(
            ), self.interface.kwargs.get('position'))  # update on main ui
            self.render_page(self.ui.get_image())  # render
            return

        if input == 2:
            # load model and run based on input, I have to customize them here
            method = getattr(
                self, self.interface.get_selected_component().get_text(), self.refresh)
            if callable(method):
                method()
            else:
                logging.error(f"Command not recognized.")

    def _load_model(self):
        self.loading_text.draw(
            self.ui.canvas, (EINK_WIDTH//2, EINK_HEIGHT//2), centered=True)
        self.render_page(self.ui.get_image())
        # load model SD1.5 or SDXS
        self.pipe = StableDiffusionRender(
            config=self.model_config) if "vae_path" not in self.model_config else StableDiffusionXSRender(config=self.model_config)
        self.pipe.load_model()

    def generate_new(self):
        # blocked loading
        if not self.pipe:
            self._load_model()
        try:
            self.app.buttons.lock()  # lock button
            self.app.screen.start_animation(
                self.ui.get_image(), loading_animation_folder)
            # create prompt
            prompt = PromptGenerator(f'{model_folder}/prompt_pool.json').gen()
            # inference
            self.pipe(prompt)
            self.app.screen.stop_animation()  # Stop the animation after the task completes
            play_audio(sound_bite)  # play sound bite :)
        except Exception as e:
            logging.error(f"Error EditingPage.generate_new: {e}")
            self.app.screen.stop_animation()

        # trigger image display once done
        self.show_image(prompt)
        time.sleep(0.5)
        self.app.buttons.unlock()  # button unlock

    def refresh(self):
        logging.info('refresh screen to 4g display')
        # back to main dialog
        self.interface = self.dialog
        # re-render dialog
        self.interface.render_scroll()
        # put ui parts together
        self.ui.paste_image(self.interface.get_image(),
                            self.interface.kwargs.get('position'))
        # init render
        self.render_page(self.ui.get_image(), format='2bit')

    def back(self):
        self.app.switch_page(ModelSelectionPage)


class App(Application):
    def __init__(self):
        super().__init__()
        self.current_page = ModelSelectionPage(self)


if __name__ == '__main__':
    App()
    while True:
        logging.info('diffusion app ping')
        time.sleep(5)
