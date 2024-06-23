import os
import time
import json
import logging
from pathlib import Path
from PIL import Image
from lib.stable_diffusion_tools import StableDiffusionRender, StableDiffusionXSRender, PromptGenerator
from distiller.peripheral.speaker import play_audio
from distiller.utils.image import paste_image, scale_image
from distiller.constants import EINK_WIDTH, EINK_HEIGHT
from distiller.gui.components import *
from distiller.gui import Page, Application

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
model_folder = "/home/distiller/models"

# Load resources
sound_bite = resource_filename('distiller', os.path.join('resources', 'audios', 'anime-wow-sound-effect.wav'))
dialog_box_path = resource_filename('distiller', os.path.join('resources', 'dialogBox_240x97.png'))
dialog_box_size = (240, 97)
dialog_box_bounding_box = (15, 15, 225, 80)
font_path = resource_filename('distiller', os.path.join('resources', 'fonts', 'Monorama-Bold.ttf'))
loading_animation_folder = resource_filename('distiller', os.path.join('resources', 'animations', 'loading_screen'))

class ModelSelectionBox(Box):
    def __init__(self, position, size, next_page, model_config, **kwargs):
        super().__init__(position, size, **kwargs)
        self.next_page = next_page
        self.model_config = model_config

    def click(self, app):
        app.switch_page(self.next_page, model_config=self.model_config)

class ModelSelectionPage(Page):
    def __init__(self, app):
        super().__init__(app)
        self.index = 0
        config_name = "model_config.json"
        self.model_list = [file_path for file_path in Path(model_folder).rglob(f"*/{config_name}")]
        self.thumbnail_list = [str(file_path).replace(config_name, "thumbnail.png") for file_path in self.model_list]
        self.boxes = []
        self.thumbnails = []
        self.model_configs = []
        for model_file, thumbnail_file in zip(self.model_list, self.thumbnail_list):
            with open(model_file) as f:
                self.model_configs.append(json.load(f))
            thumbnail = Image.open(thumbnail_file)
            if thumbnail.width >= EINK_WIDTH or thumbnail.height >= EINK_HEIGHT:
                thumbnail = scale_image(thumbnail)
            top_left = ((EINK_WIDTH-thumbnail.width)//2, (EINK_HEIGHT-thumbnail.height)//2)
            self.thumbnails.append(thumbnail)
            self.boxes.append(ModelSelectionBox(top_left, (thumbnail.width, thumbnail.height + 25), next_page=EditingPage, model_config=self.model_configs[-1]))
        self.gui = GUI()
        self.gui.canvas.draw_plus_pattern()
        self.render_page(self.prepare_page_image())

    def handle_input(self, input):
        if input == 0:
            self.index = (self.index - 1) % len(self.boxes)
            self.render_page(self.prepare_page_image())
        elif input == 1:
            self.index = (self.index + 1) % len(self.boxes)
            self.render_page(self.prepare_page_image())
        elif input == 2:
            self.boxes[self.index].click(self.app)

    def prepare_page_image(self):
        model_name = self.model_configs[self.index]['model_name']
        title = Text(model_name, font_path, 20)
        temp_canvas = self.gui.canvas.copy()
        self.boxes[self.index].draw(temp_canvas)
        title.draw(temp_canvas, position=(0, self.boxes[self.index].position[1] + self.thumbnails[self.index].size[1] + 5), centered=True)
        return paste_image(image=self.thumbnails[self.index], canvas_image=temp_canvas.image, position=self.boxes[self.index].position)

class EditingPage(Page):
    image_size = (128*2, 128*3)
    dialog_box_size = (240, 97)

    def __init__(self, app, model_config):
        super().__init__(app)
        self.model_config = model_config
        self.pipe = None
        self.file_cache = f"./temp-{self.model_config['model_name']}.png"
        self.ui = GUI()
        self.image_display = GUI(width=self.image_size[0], height=self.image_size[1], init_image=self.get_init_image())
        self.dialog = ScrollGUI(dialog_box_size[0], dialog_box_size[1], dialog_box_bounding_box, init_image=Image.open(dialog_box_path), position=(0, EINK_HEIGHT - dialog_box_size[1]))
        dialog_font_size = 15
        self.dialog.add_component(TextBox(text="generate_new", font_path=font_path, font_size=dialog_font_size))
        self.dialog.add_component(TextBox(text="refresh", font_path=font_path, font_size=dialog_font_size))
        self.dialog.add_component(TextBox(text="back", font_path=font_path, font_size=dialog_font_size))
        self.dialog_text = ScrollGUI(dialog_box_size[0], dialog_box_size[1], dialog_box_bounding_box, init_image=Image.open(dialog_box_path), position=(0, EINK_HEIGHT - dialog_box_size[1]))
        self.interface = self.dialog
        self.loading_text = Text("Loading model ... ", font_path, 20)
        self.prompt_text = Text("placeholder", font_path, 12)
        self.interface.render_scroll()
        self.ui.paste_image(self.image_display.get_image())
        self.ui.paste_image(self.interface.get_image(), self.interface.kwargs.get('position'))
        self.render_page(self.ui.get_image(), format='2bit')


        self.run_number = 0  # Track number of runs
        self.run_time = 0  # Track durations of runs

    def show_image(self, prompt_text):
        perf = f"Run: {self.run_number} | Last Time: {self.run_time:.2f}s | "
        self.interface = self.dialog_text
        self.ui.paste_image(Image.open(self.file_cache))
        self.interface.canvas.flush()
        self.interface.inject_texts(perf + prompt_text, font_path, 15)
        self.interface.render_scroll()
        self.ui.paste_image(self.interface.get_image(), self.interface.kwargs.get('position'))
        self.render_page(self.ui.get_image(), format='2bit')

    def get_init_image(self):
        if os.path.exists(self.file_cache):
            image = Image.open(self.file_cache)
            prompt_str = image.info.get("prompt")
        else:
            image = paste_image(image=Image.open(resource_filename('distiller', os.path.join('resources', 'logo.png'))), canvas_image=Image.new("L", (EINK_WIDTH, EINK_HEIGHT), "white"))
        return image

    def handle_input(self, input):
        if input == 0 or input == 1:
            self.interface.index_up() if input == 0 else self.interface.index_down()
            self.interface.render_scroll()
            self.ui.paste_image(self.interface.get_image(), self.interface.kwargs.get('position'))
            self.render_page(self.ui.get_image())
            return
        if input == 2:
            method = getattr(self, self.interface.get_selected_component().get_text(), self.refresh)
            if callable(method):
                method()
            else:
                logging.error(f"Command not recognized.")

    def _load_model(self):
        self.loading_text.draw(self.ui.canvas, (EINK_WIDTH//2, EINK_HEIGHT//2), centered=True)
        self.render_page(self.ui.get_image())
        self.pipe = StableDiffusionRender(config=self.model_config) if "vae_path" not in self.model_config else StableDiffusionXSRender(config=self.model_config)
        self.pipe.load_model()

    def generate_new(self):
        if not self.pipe:
            self._load_model()
        try:
            self.app.buttons.lock()
            self.app.screen.start_animation(self.ui.get_image(), loading_animation_folder)
            prompt = PromptGenerator(f'{model_folder}/prompt_pool.json').gen()
            start_time = time.time()  # Start time
            self.pipe(prompt)
            end_time = time.time()  # End time
            self.app.screen.stop_animation()
            # update tracker
            self.run_number += 1
            self.run_time = end_time - start_time
            play_audio(sound_bite)
            # logging.info(f"generate_new run time: {end_time - start_time} seconds")  # Log the running time
        except Exception as e:
            logging.error(f"Error EditingPage.generate_new: {e}")
            self.app.screen.stop_animation()
        self.show_image(prompt)
        self.app.buttons.unlock()

    def refresh(self):
        logging.info('refresh screen to 4g display')
        self.interface = self.dialog
        self.interface.render_scroll()
        self.ui.paste_image(self.interface.get_image(), self.interface.kwargs.get('position'))
        self.render_page(self.ui.get_image(), format='2bit')

    def back(self):
        self.app.switch_page(ModelSelectionPage)

class App(Application):
    def __init__(self):
        super().__init__()
        self.current_page = ModelSelectionPage(self)

def run_load_test():
    iter_t = 0
    app = App()
    editing_page = EditingPage(app, app.current_page.model_configs[0])  # Assuming we have at least one model config
    while True:
        logging.info(f'run time {iter_t}')
        editing_page.generate_new()
        time.sleep(1)  # Add a small delay to avoid overwhelming the system
        iter_t += 1

if __name__ == '__main__':
    run_load_test()