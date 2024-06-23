from lib.whisper_tools import Whisper
from lib.openai_tools import AdventureGameAssistant
from distiller.constants import EINK_WIDTH, EINK_HEIGHT
from distiller.peripheral.mic import AudioRecorder
from distiller.utils.commons import timeit, check_internet_connection
from distiller.utils.image import paste_image, scale_image, show_text
from distiller.peripheral.speaker import play_audio
from distiller.gui.components import *
from distiller.gui import Page, Application
import os
import sys
from pathlib import Path
import time
import json
import asyncio
from PIL import Image
from pkg_resources import resource_filename
import subprocess  # Import subprocess module
import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


# check if internet is available
if not check_internet_connection():
    logging.error("Internet connection not available")
    os.system("pkill -f " + sys.argv[0])

sound_bite = resource_filename('distiller', os.path.join(
    'resources', 'audios', 'anime-wow-sound-effect.wav'))

dialog_box_path = resource_filename(
    'distiller', os.path.join('resources', 'dialogBox_240x97.png'))
dialog_box_size = (240, 97)
dialog_box_bounding_box = (15, 15, 225, 80)
dialog_font_size = 20

dialog_box_path = resource_filename(
    'distiller', os.path.join('resources', 'dialogBox_240x97.png'))
font_path = resource_filename('distiller', os.path.join(
    'resources', 'fonts', 'Monorama-Bold.ttf'))

render_png_path = "./gpt-story.png"


class GamePage(Page):
    def __init__(self, app):
        super().__init__(app)

        # openai client
        self.game_engine = AdventureGameAssistant()
        # audio models
        self.audio_recorder = AudioRecorder()
        self.whisper = Whisper()
        # self.tts = TTS()
        self.last_image = self.get_init_image()
        # a box for text display
        self.ui = GUI()
        self.ui.canvas.draw_plus_pattern()
        # add top bars
        Box((0, 0), (EINK_WIDTH, 30), corner_radius=5,
            padding=0, line_thickness=0).draw(self.ui.canvas)
        Icon(icon_path=resource_filename(
            'distiller', os.path.join('resources', 'icons', 'cpu.png')), position=(10, 2)).draw(self.ui.canvas)
        Text("100% ", font_path=font_path,
             font_size=17).draw(self.ui.canvas, (40, 5), centered=False)
        Icon(icon_path=resource_filename(
            'distiller', os.path.join('resources', 'icons', 'ram.png')), position=(95, 2)).draw(self.ui.canvas)
        Text("100% ", font_path=font_path,
             font_size=17).draw(self.ui.canvas, (125, 5), centered=False)
        Icon(icon_path=resource_filename(
            'distiller', os.path.join('resources', 'icons', 'wifi.png')), position=(EINK_WIDTH-50, 2), padding=5).draw(self.ui.canvas)

        # invert the top bar
        self.ui.update_canvas_image(Box((0, 0), (EINK_WIDTH, 30), corner_radius=5,
                                        padding=0, line_thickness=0).invert_region(self.ui.canvas))
        Box((0, 0), (EINK_WIDTH, 5), corner_radius=0, padding=0, line_thickness=0,
            fill='black').draw(self.ui.canvas)  # hack to fill the top corners
        self.ui.canvas.register_canvas_image()  # cache image for future flash

        # interface
        self.dialog = ScrollGUI(
            dialog_box_size[0],
            dialog_box_size[1],
            dialog_box_bounding_box,
            init_image=Image.open(dialog_box_path),
            position=(0, EINK_HEIGHT - dialog_box_size[1]))

        # init render
        self.update_dialog("[press enter to start game]")

        # init image
        image = paste_image(self.last_image, self.ui.canvas.image, position=(
            0, 50), type="RGB") if self.last_image else self.ui.get_image()
        self.render_page(image, format='2bit')
        
        # revert back to 1 bit
        self.ui.update_canvas_image(paste_image(self.last_image, self.ui.canvas.image, position=(0, 50)))  # paste image display
        self.ui.canvas.register_canvas_image()  # cache image for future flash

    def get_init_image(self):
        if os.path.exists(render_png_path):  # reload
            return Image.open(render_png_path)  # init
        # dummy image from resources
        dialog_box_path = resource_filename(
            'distiller', os.path.join('resources', 'game.png'))
        return Image.open(dialog_box_path)

    def _show_text(self, text, size=15):
        self.ui.canvas.flush()  # flush
        show_text(self.ui.canvas, text, font_path, size)  # draw at center
        self.render_page(self.ui.get_image())

    def update_dialog(self, text):
        self.dialog.canvas.flush()
        Text(text, font_path, 15).draw(
            self.dialog.canvas, (15, 15), centered=True)
        self.ui.paste_image(self.dialog.get_image(),
                            self.dialog.kwargs.get('position'))

    @timeit
    def send_transcribe(self):
        question = []
        for sentence in self.whisper.transcribe():
            for word in sentence.split():
                if question and word == question[-1]:  # avoid repeating words
                    continue
                question.append(word)

        # send message to game engine
        image_url, reply = self.game_engine.send_message(" ".join(question))
        logging.info(f"{image_url}, {reply}")

        # update dialog
        self.dialog.inject_texts(reply, font_path, 15)
        self.dialog.index_reset()
        self.dialog.render_scroll()
        # final render
        self.ui.paste_image(self.dialog.get_image(),
                            self.dialog.kwargs.get('position'))
        # update image
        self.render_page(paste_image(Image.open(
            render_png_path), self.ui.canvas.image, position=(0, 50), type='RGB'), format='2bit')
        # revert back to 1bit
        self.ui.update_canvas_image(paste_image(Image.open(
            render_png_path), self.ui.canvas.image, position=(0, 50)))  # paste image display
        self.ui.canvas.register_canvas_image()  # cache image for future flash

    def handle_input(self, input):
        if input == 0 or input == 1:
            if len(self.dialog.components) == 0:
                return
            self.dialog.index_up() if input == 0 else self.dialog.index_down()
            self.dialog.render_scroll()  # update dialog scroll
            self.ui.paste_image(self.dialog.get_image(), self.dialog.kwargs.get(
                'position'))  # update on main ui
            self.render_page(self.ui.get_image())  # render
            return

        if input == 2:  # start recording
            if self.audio_recorder.thread_worker and self.audio_recorder.thread_worker.active.is_set():  # in recording, stop
                self.audio_recorder.stop_record()
                # trigger translation
                self.app.buttons.lock()

                self.update_dialog("[rendering game ...]")
                self.render_page(self.ui.get_image())
                self.audio_recorder.save_wav()
                self.send_transcribe()  # show transcribed text

                # notification
                play_audio(sound_bite)  # play sound bite :)

                self.app.buttons.unlock()
            else:
                self.audio_recorder.start_record()
                # display notification
                # init render
                self.update_dialog("[press any button to stop]")
                self.render_page(self.ui.get_image(), format='2bit')


class App(Application):
    def __init__(self):
        super().__init__()
        self.current_page = GamePage(self)


if __name__ == '__main__':
    App()
    while True:
        logging.info('game app ping')
        time.sleep(10)
