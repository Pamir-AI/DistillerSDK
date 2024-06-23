# main page to display and call apps
from lib.whisper_tools import Whisper
from distiller.utils.commons import ThreadWorker
from pkg_resources import resource_filename
from distiller.utils.image import paste_image, scale_image, show_text
from distiller.constants import EINK_WIDTH, EINK_HEIGHT
from distiller.gui.components import *
from distiller.gui import Page, Application
from distiller.peripheral.mic import AudioRecorder
import os
from pathlib import Path
import time
import json
import asyncio
import subprocess  # Import subprocess module
import logging
from PIL import Image
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


# list of some static assets here
# dialog box
dialog_box_path = resource_filename(
    'distiller', os.path.join('resources', 'dialogBox_240x97.png'))
dialog_box_size = (240, 97)
dialog_box_bounding_box = (15, 15, 225, 80)
dialog_font_size = 20

# font
font_path = resource_filename('distiller', os.path.join(
    'resources', 'fonts', 'Monorama-Bold.ttf'))

# main content display

display_box = [15, 100, EINK_WIDTH-15, EINK_HEIGHT-100]
padding = 10
text_bounding_box = (display_box[0]+padding, display_box[1] +
                     padding, display_box[2]-padding, display_box[3]-padding)


class AudioPage(Page):
    def __init__(self, app):
        super().__init__(app)

        # audio models, should be fast
        self.audio_recorder = AudioRecorder()
        self.whisper = Whisper()

        # a box for text display
        self.ui = GUI()
        self.ui.canvas.draw_plus_pattern()
        self.ui.add_component(Box(
            display_box[:2], (display_box[2]-display_box[0],
                              display_box[3]-display_box[1]),
        ))

        # put UI all together
        self.ui.render_all()  # render boxes
        self.ui.canvas.register_canvas_image()  # cache image for future flash

        # show loading screen
        self._show_text('[press any button to record]')

        # render
        self.render_page(self.ui.get_image())

    def _show_text(self, text, size=15):
        self.ui.canvas.flush()  # flush
        show_text(self.ui.canvas, text, font_path, size)  # draw at center
        self.render_page(self.ui.get_image())

    def handle_input(self, input):
        # TODO simple example, just take any key for now
        # check if recroding
        if self.audio_recorder.thread_worker and self.audio_recorder.thread_worker.active.is_set():  # in recording, stop
            self.audio_recorder.stop_record()

            # trigger translation
            self.app.buttons.lock()
            self._show_text('[...]')  # show default text
            self.audio_recorder.save_wav()
            self.show_transcribe()  # show transcribed text
            time.sleep(3)  # display for 3 sec
            # show default text
            self._show_text('[press any button to record]')
            self.app.buttons.unlock()
        else:
            self.audio_recorder.start_record()
            # display notification
            self._show_text("[press any button to stop]")

    def show_transcribe(self):
        self.ui.canvas.flush()  # clean screen
        for sentence in self.whisper.transcribe():
            # display Text
            Text(sentence, font_path, 17).draw_wrapped(
                self.ui.canvas, text_bounding_box)
            self.render_page(self.ui.get_image())


class App(Application):
    def __init__(self):
        super().__init__()
        self.current_page = AudioPage(self)


if __name__ == '__main__':
    App()
    while True:
        logging.info('audio app ping')
        time.sleep(5)
