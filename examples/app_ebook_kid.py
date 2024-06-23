# main page to display and call apps
from lib.llm_tools import load_llm, clean_response, is_sentence_ending, stream_sentence, generate_sentence
from lib.stable_diffusion_tools import StableDiffusionXSRender
from distiller.utils.commons import ThreadWorker
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


# Add the project directory to the system path


# list of some static assets here
image_size = (128*2, 128*3)
dialog_box_path = resource_filename(
    'distiller', os.path.join('resources', 'dialogBox_240x97.png'))
dialog_box_size = (240, 97)
dialog_box_bounding_box = (15, 15, 225, 80)
dialog_font_size = 20
font_path = resource_filename('distiller', os.path.join(
    'resources', 'fonts', 'Monorama-Bold.ttf'))
model_folder = "/home/distiller/models"
llm_model_path = model_folder + '/140M-TinyLLama-Mini-Cinder.F16.gguf'
sdxs_model_config_path = model_folder + \
    '/sdxs-512-dreamshaper-onnx/model_config.json'
display_box = [15, 15, EINK_WIDTH-15, EINK_HEIGHT-15]
padding = 10
text_bounding_box = (display_box[0]+padding, display_box[1] +
                     padding, display_box[2]-padding, display_box[3]-padding)

image_prefix = "book_illustration"
add_prompt = "lineart, cute drawing, detailed story illustration, fantacy story,"


class StoryGenPage(Page):
    def __init__(self, app):
        super().__init__(app)
        # a box for text display
        self.ui = GUI()
        self.ui.canvas.draw_plus_pattern()
        self.ui.add_component(Box(
            display_box[:2], (display_box[2]-display_box[0],
                              display_box[3]-display_box[1]),
        ))

        # a dialog for selections
        self.interface = ScrollGUI(
            dialog_box_size[0],
            dialog_box_size[1],
            dialog_box_bounding_box,
            init_image=Image.open(dialog_box_path),
            position=(0, EINK_HEIGHT - dialog_box_size[1])
        )
        self.interface.add_component(
            TextBox(text="play", font_path=font_path, font_size=dialog_font_size))
        self.interface.render_scroll()
        # put UI all together
        self.ui.render_all()  # render boxes
        self.ui.canvas.register_canvas_image()  # cache image for future flash

        # self.render_page(self.ui.get_image())s

        # show loading screen
        self.show_text('Loading LLM ...')

        # prepare llm
        self.llm = self._load_llm(llm_model_path)

        # prepare SD
        self.show_text('Loading SD ...')
        self.pipe = self._load_sd(sdxs_model_config_path)

        # ready to use
        self.ui.canvas.flush()
        # show dialog
        self.ui.paste_image(self.interface.get_image(),
                            self.interface.kwargs.get('position'))
        self.render_page(self.ui.get_image())

        # threads for sd gen
        self.thread_worker = None

    def show_text(self, text):
        self.ui.canvas.flush()  # flush
        Text(text, font_path, 20).draw(self.ui.canvas,
                                       (EINK_WIDTH//2, EINK_HEIGHT//2), centered=True)
        self.render_page(self.ui.get_image())

    def _load_sd(self, model_config_file):
        with open(model_config_file) as f:
            model_config = json.load(f)
        pipe = StableDiffusionXSRender(config=model_config)
        pipe.load_model()
        return pipe

    def _load_llm(self, model_path):
        return load_llm(model_path, n_ctx=512)

    def handle_input(self, input):
        if input == 0 or input == 1:
            self.interface.index_up() if input == 0 else self.interface.index_down()
            self.interface.render_scroll()  # update dialog scroll
            # main ui render
            self.ui.paste_image(self.interface.get_image(
            ), self.interface.kwargs.get('position'))  # update on main ui
            self.render_page(self.ui.get_image())  # render
            return  # early stopping

        if input == 2:
            # load model and run based on input, I have to customize them here
            method = getattr(
                self, self.interface.get_selected_component().get_text(), None)
            if callable(method):
                method()
            else:
                logging.error(f"Command not recognized.")

    def sd_gen(self, thread_event, prompt):
        self.pipe(add_prompt + prompt, image_prefix=image_prefix)
        thread_event.clear()  # indicate stop man fuck this thread shit

    def sd_gen_thread(self, prompt):
        self.thread_worker = ThreadWorker()  # new a thread worker
        self.thread_worker.start(self.sd_gen, (prompt,))

    # TODO better off run non parallel, running llm stream + SD gen the same time got I/O bottleneck ...
    # but I will leave it like this for now

    def play(self):
        self.app.buttons.lock()
        # if stream ->
        # stream = self.llm(
        #     "<|user|>\nCan you tell me a bed time story?</s>\n<|assistant|>",
        #     max_tokens=200,
        #     temperature=1.5,
        #     stop=["<|user|>", "</s>"],
        #     stream=True,
        # )
        # non async call
        self.show_text("thinking ...")
        t_out = ""
        for sentence in generate_sentence(
            self.llm(
                "<|user|>\nCan you tell me a bed time story?</s>\n<|assistant|>",
                max_tokens=200,
                temperature=1.5,
                stop=["<|user|>", "</s>"],)
        ):
            self.ui.canvas.flush()
            # if any image ready
            if self.thread_worker and not self.thread_worker.active.is_set():
                # clear and reset thread
                self.thread_worker.stop()
                self.thread_worker = None
                # display last finished image
                self.render_page(paste_image(Image.open(
                    f"{image_prefix}.png"), self.ui.get_image(), border=True))
                # wait for 10 to block the thread
                time.sleep(10)

            if t_out and not self.thread_worker:
                # trigger sd_gen and skip first sentence
                self.sd_gen_thread(sentence)

            # render per word
            for word in sentence.split():
                t_out += word + " "
                self.ui.canvas.flush()  # flush screen
                if not Text(t_out, font_path, 17).draw_wrapped(self.ui.canvas, text_bounding_box):  # page flip
                    t_out = word + " "  # reset
                # render each sentence ending
                self.render_page(self.ui.get_image())

        # last check
        if self.thread_worker and not self.thread_worker.active.is_set():
            # clear and reset thread
            self.thread_worker.stop()
            self.thread_worker = None
            # display last finished image
            self.render_page(paste_image(Image.open(
                f"{image_prefix}.png"), self.ui.get_image(), border=True))
            # wait for 10 to block the thread
            time.sleep(10)

        self.app.buttons.unlock()  # done
        # show dialog back
        self.ui.paste_image(self.interface.get_image(),
                            self.interface.kwargs.get('position'))
        self.render_page(self.ui.get_image())


class App(Application):
    def __init__(self):
        super().__init__()
        self.current_page = StoryGenPage(self)


if __name__ == '__main__':
    App()
    while True:
        logging.info('kid ebook app ping')
        time.sleep(5)
