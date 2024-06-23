# TODO return ERROR on Internet needed
# TODO timeout error on stt, client, tts

from lib.elevenlabs_tts_tools import TTS
from lib.deepgram_stt_tools import STT
import os
import sys
import json
import time
import signal
import numpy as np
import websocket
import threading
import subprocess

from PIL import Image
from pkg_resources import resource_filename

from distiller.gui import Page, Application
from distiller.gui.components import *
from distiller.constants import EINK_WIDTH, EINK_HEIGHT
from distiller.utils.image import paste_image, scale_image
from distiller.utils.commons import ThreadWorker, timeit, check_internet_connection
from distiller.peripheral.mic import AudioRecorder

from distiller.utils.image import paste_image, scale_image, show_text
import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


# check if internet is available
if not check_internet_connection():
    logging.error("Internet connection not available")
    os.system("pkill -f " + sys.argv[0])

# ws
PORT = 5001

# UI statics
display_box = [15, 100, EINK_WIDTH-15, EINK_HEIGHT-100]
dialog_box_path = resource_filename(
    'distiller', os.path.join('resources', 'dialogBox_240x97.png'))
dialog_box_size = (240, 97)
dialog_box_bounding_box = (15, 15, 225, 85)
dialog_font_size = 20
font_path = resource_filename('distiller', os.path.join(
    'resources', 'fonts', 'Monorama-Bold.ttf'))
chat_box_size = (EINK_WIDTH, EINK_HEIGHT - dialog_box_size[1])
chat_box_bounding_box = (0, 0, EINK_WIDTH, EINK_HEIGHT - dialog_box_size[1])


class SoulPage(Page):
    def __init__(self, app):
        super().__init__(app)

        # stt and tts instance
        self.tts = TTS()
        self.stt = STT()

        # audio related
        icon_size = 50
        self.start_recording_icon = Icon(icon_path=resource_filename(
            'distiller', os.path.join('resources', 'icons', 'microphone.png')), position=(0, (EINK_HEIGHT-icon_size)//2), padding=0)
        self.stop_recording_icon = Icon(icon_path=resource_filename(
            'distiller', os.path.join('resources', 'icons', 'recording.png')), position=(0, (EINK_HEIGHT-icon_size)//2), padding=0)
        # add think bubble icon
        self.bubble_icon = Icon(icon_path=resource_filename(
            'distiller', os.path.join('resources', 'icons', 'think_bubble.png')), position=(5, EINK_HEIGHT-dialog_box_size[1]-icon_size//2-5), padding=0)

        # audio animation
        self.thread_worker = None

        # transcription
        self.transcriptions = []

        # a box for text display
        self.ui = GUI()
        self.ui.canvas.draw_plus_pattern()
        self.ui.canvas.register_canvas_image()  # cache image for future flash
        self.ui.add_component(Box(
            (0, 0), (EINK_WIDTH, EINK_HEIGHT - dialog_box_size[1]),
        ))

        # interface
        self.dialog = ScrollGUI(
            dialog_box_size[0],
            dialog_box_size[1],
            dialog_box_bounding_box,
            init_image=Image.open(dialog_box_path),
            position=(0, EINK_HEIGHT - dialog_box_size[1]))

        # init render
        # self.update_dialog("[press any button]")
        # add record icon indicator
        self.start_recording_icon.draw(self.ui.canvas)
        self.render_page(self.ui.get_image())

    def run_stt_volume_animation(self, thread_event):
        box_base_size = 10
        while thread_event.is_set():  # render start
            self.ui.canvas.flush()  # reset
            nonlinear_volume = int(
                self.stt.volume * 0.6) if self.stt.volume < 60 else int(self.stt.volume * 1.6)
            box_size = box_base_size + nonlinear_volume
            logging.info(f"box_size {box_size}")
            Box(((EINK_WIDTH-box_size)//2, (EINK_HEIGHT-box_size)//2),
                (box_size, box_size),
                corner_radius=10,
                padding=0,
                line_thickness=0,
                fill=True).draw(self.ui.canvas)

            # add record icon indicator
            self.stop_recording_icon.draw(self.ui.canvas)
            # render
            self.render_page(self.ui.get_image(),
                             format='1bit', dithering=False)
        self.ui.canvas.flush()  # reset

    def run_tts_volume_animation(self, thread_event):
        box_base_size = 10
        use_large_box = False
        while thread_event.is_set():  # render start
            self.ui.canvas.flush()  # reset
            # Switch between two hardcoded sizes
            if use_large_box:
                nonlinear_volume = 80
            else:
                nonlinear_volume = 60
            use_large_box = not use_large_box  # Toggle the flag
            box_size = box_base_size + nonlinear_volume
            logging.info(f"box_size {box_size}")
            Box(((EINK_WIDTH-box_size)//2, (EINK_HEIGHT-box_size)//2),
                (box_size, box_size),
                corner_radius=10,
                padding=0,
                line_thickness=10,
                fill=False).draw(self.ui.canvas)
            self.render_page(self.ui.get_image(),
                             format='1bit', dithering=False)
        self.ui.canvas.flush()  # reset

    def animation_start(self, func):
        self.thread_worker = ThreadWorker()  # new a thread worker
        self.thread_worker.start(func)  # send *arg in tuple

    def animation_stop(self):
        self.thread_worker.stop()
        self.thread_worker = None

    def update_dialog(self, text):
        self.dialog.canvas.flush()
        Text(text, font_path, 15).draw(
            self.dialog.canvas, (15, 15), centered=True)
        self.ui.paste_image(self.dialog.get_image(),
                            self.dialog.kwargs.get('position'))

    def add_chat(self, text):  # pass reply to tts
        self.animation_start(self.run_tts_volume_animation)
        self.tts.stream(text)  # start the voice while we prepare for display
        self.animation_stop()
        # show_text(self.ui.canvas, "> " + text, font_path) # draw at center
        # self.render_page(self.ui.get_image())

    def add_thought(self, text):  # display inner thoughts
        self.dialog.inject_texts(text, font_path, 15)
        self.dialog.index_reset()
        self.dialog.render_scroll()
        self.ui.paste_image(self.dialog.get_image(),
                            self.dialog.kwargs.get('position'))
        self.add_icons()
        # renders
        self.render_page(self.ui.get_image(), format='1bit', dithering=False)

    def _show_text(self, text, size=15):
        self.ui.canvas.flush()  # flush
        show_text(self.ui.canvas, text, font_path, size)  # draw at center
        self.render_page(self.ui.get_image())

    @timeit
    def send_transcribe(self):
        logging.info(
            f"[Debug] stream out transcription {self.stt.get_transcript()}")
        # send to server
        self.app.ws.ws.send(json.dumps({"message": self.stt.get_transcript()}))
        logging.info(f"[Debug] transcription out at ->  {time.time()}")

    def stt_stream(self):
        # start recording
        self.stt.start()
        # self.audio_recorder.start_record()
        # running in thread and stream audio in another thread

    def add_icons(self):
        self.start_recording_icon.draw(self.ui.canvas)
        self.bubble_icon.draw(self.ui.canvas)

    def handle_input(self, input):
        if input == 0 or input == 1 and self.dialog.components:
            self.dialog.index_up() if input == 0 else self.dialog.index_down()
            self.dialog.render_scroll()
            self.add_icons()
            self.ui.paste_image(self.dialog.get_image(),
                                self.dialog.kwargs.get('position'))
            self.render_page(self.ui.get_image())
            return

        if self.stt.streaming:
            # stop recording
            # self.audio_recorder.stop_record()
            self.app.buttons.lock()
            self.stt.stop()
            # pass the transcription to soul engine
            self.animation_stop()
            self.send_transcribe()
            self.app.buttons.unlock()
        else:
            # start recording and stream transcription
            self.stop_recording_icon.draw(self.ui.canvas)
            self.stt_stream()
            self.animation_start(self.run_stt_volume_animation)


class App(Application):
    def __init__(self, ws):
        super().__init__()
        self.current_page = SoulPage(self)
        self.ws = ws


class WebSocketClient:
    def __init__(self, port):
        self.port = port
        websocket.enableTrace(True)
        self.ws = websocket.WebSocketApp(f"ws://localhost:{self.port}",
                                         on_open=self.on_open,
                                         on_message=self.on_message,
                                         on_error=self.on_error,
                                         on_close=self.on_close)

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            message_type = data.get('type')
            content = data.get('content')

            logging.info(f"Received {message_type} from server: " + content)
            logging.info(f"[DEBUG] -> at time {time.time()}")

            if message_type == "says":
                # Handle 'says' messages
                app.current_page.add_chat(content)
            elif message_type == "thinks":
                # Handle 'thinks' messages
                app.current_page.add_thought(content)
            else:
                logging.warning(f"Unknown message type: {message_type}")
        except json.JSONDecodeError:
            logging.error("Failed to decode message from server: " + message)

    def on_error(self, ws, error):
        print("Error: " + str(error))

    def on_close(self, ws, close_status_code, close_msg):
        print("### closed ###")

    def on_open(self, ws):
        def run(*args):
            logging.info("server connected ! ")
            # data = {"message": "Hello!"}
            # ws.send(json.dumps(data))
            # print("Sent to server: " + json.dumps(data))

        threading.Thread(target=run).start()

    def run_forever(self):
        self.ws.run_forever()


def signal_handler(sig, frame):
    logging.info("Received signal to terminate. Stopping server...")
    os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
    sys.exit(0)


if __name__ == "__main__":
    # Start the server
    logging.info("Starting server...")
    server_process = subprocess.Popen(
        ["npx", "tsx", "websocket/index.ts"],
        cwd="/home/distiller/community/demos/distiller/server",  # TODO move this to env/sh
        preexec_fn=os.setsid  # To ensure the process gets its own process group
    )

    # Wait a bit to ensure the server starts up
    time.sleep(5)  # Adjust the sleep time as needed

    # Set up signal handler to clean up server process
    signal.signal(signal.SIGINT, signal_handler)

    # Run the WebSocket client
    logging.info("Starting WebSocket client...")

    ws = WebSocketClient(PORT)
    app = App(ws)
    ws.run_forever()
