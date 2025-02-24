import logging
import time
from lib.llm_tools import load_llm, generate_sentence, stream_sentence
from distiller.gui import * 
from distiller.gui.components import Box, TextBox, GUI
from distiller.utils.commons import ThreadWorker
from distiller.peripheral.mic import AudioRecorder
from lib.whisper_tools import Whisper
from PIL import Image
from distiller.constants import EINK_WIDTH, EINK_HEIGHT
from distiller.utils.image import paste_image, show_text
from pkg_resources import resource_filename
import os
import threading
from functools import partial
from lib.piper_tts_tools import text_to_speech
from queue import Queue
import re
from lib.kororo_tts_tools import KokoroTTS

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Paths and configurations
dialog_box_path = resource_filename(
    'distiller', os.path.join('resources', 'dialogBox_240x97.png'))
dialog_box_size = (240, 97)
dialog_box_bounding_box = (15, 15, 225, 80)
dialog_font_size = 20
font_path = resource_filename('distiller', os.path.join(
    'resources', 'fonts', 'Monorama-Bold.ttf'))
model_folder = "/home/distiller/models"
llm_model_path = "http://127.0.0.1:8080/completion"  # Assuming endpoint
display_box = [15, 15, EINK_WIDTH-15, EINK_HEIGHT-15]
padding = 10
text_bounding_box = (display_box[0]+padding, display_box[1] +
                     padding, display_box[2]-padding, display_box[3]-padding)

class DemoPage(Page):
    def __init__(self, app):
        super().__init__(app)

        # Initialize audio recorder and Whisper
        self.audio_recorder = AudioRecorder()
        self.whisper = Whisper()

        # Initialize LLM client
        self.llm = load_llm(llm_model_path, temperature=0.6, max_tokens=500)

        # Initialize GUI
        self.ui = GUI()
        self.ui.canvas.draw_plus_pattern()
        # self.ui.add_component(Box(
        #     display_box[:2], (display_box[2]-display_box[0],
        #                       display_box[3]-display_box[1]),
        # ))

        # Dialog interface
        self.interface = TextBox(text="[Press any button to talk]", font_path=font_path, font_size=dialog_font_size)
        self.ui.add_component(self.interface)

        # Render UI
        self.ui.render_all()
        self.ui.canvas.register_canvas_image()
        self.render_page(self.ui.get_image())

        # Thread worker for handling LLM responses
        self.thread_worker = None
        self.current_text = ""
        self.llm_generator = None  # Store the generator instead of response

        # Initialize TTS components
        self.tts = KokoroTTS()
        self.tts_queue = Queue()
        self.tts_worker = None
        self.current_sentence = ""

    def handle_input(self, input):
        if self.audio_recorder.thread_worker and self.audio_recorder.thread_worker.active.is_set():
            # Stop recording
            self.audio_recorder.stop_record()
            self.audio_recorder.save_wav()
            self.show_transcription()
            time.sleep(3)
        else:
            # Start recording
            self.stop_thread()  # stop anything running in the thread first
            self.stop_tts_worker()  # stop TTS
            self.tts_queue = Queue()  # Clear TTS queue
            # stop the llm
            self.llm.stop_generation()
            self.audio_recorder.start_record()
            self.show_recording()

    def show_recording(self):
        self.ui.canvas.flush()
        show_text(self.ui.canvas, "[Recording... Press again to stop]", font_path, 15)
        self.render_page(self.ui.get_image())

    def show_transcription(self):
        self.ui.canvas.flush()
        self.render_page(self.ui.get_image())
        # Start transcription
        self.thread_worker = ThreadWorker()
        self.thread_worker.start(self.transcribe_audio)

    def transcribe_audio(self, active: threading.Event, *args):
        if active.is_set():
            transcription = self.perform_transcription()
            self.update_ui_thread_safe(transcription)
            self.stop_thread()  # Ensure the thread stops after transcription

    def perform_transcription(self):
        transcription = self.whisper.transcribe()
        logging.info(f"Transcription: {transcription}")
        return transcription

    def update_ui_thread_safe(self, transcription):
        user_text = ""
        for sentence in transcription:
            user_text += sentence
            self.display_user_text(user_text)
        print("[LLM] user_text", user_text)
        self.start_tts_worker()
        self.send_to_llm(user_text)

    def display_user_text(self, text):
        self.ui.canvas.flush()
        show_text(self.ui.canvas, f"You: {text}", font_path, 17)
        self.render_page(self.ui.get_image())

    def send_to_llm(self, text):
        self.show_text("LLM is thinking...")
        bound_func = partial(self.generate_llm_response, text=text)
        self.thread_worker.start(bound_func)

    def generate_llm_response(self, active, text, *args, **kwargs):
        if not active.is_set():
            return

        prompt = f"<|user|>\n{text}\n<|assistant|> : \n <think> " # provoke think 
        try:
            self.llm_generator = self.llm.generate(prompt, stream=True)
            for sentence in stream_sentence(self.llm_generator):
                print("[LLM] sentence ", sentence)
                self.display_llm_text(sentence)
                if "answer: --->" in sentence:
                    print("[TTS] queueing ", sentence)
                    self.tts_queue.put(sentence.split("answer: --->")[1].strip())

        except Exception as e:
            logging.error(f"LLM generation error: {e}")
            self.show_text("Error generating response.")
        finally:
            self.llm_generator = None
            # Wait for TTS queue to empty before stopping
            while not self.tts_queue.empty():
                time.sleep(0.1)
            self.stop_tts_worker()

    def display_llm_text(self, text):
        self.ui.canvas.flush()
        show_text(self.ui.canvas, text, font_path, 17)
        self.render_page(self.ui.get_image())

    def show_text(self, text):
        self.ui.canvas.flush()
        show_text(self.ui.canvas, text, font_path, 15)
        self.render_page(self.ui.get_image())

    def stop_thread(self):
        if self.thread_worker and self.thread_worker.active.is_set():
            self.thread_worker.stop()
            self.thread_worker = None

    def process_tts_queue(self, active: threading.Event, *args):
        logging.info("Processing TTS queue")
        while active.is_set():
            if not self.tts_queue.empty():
                text = self.tts_queue.get()
                if text:
                    try:
                        logging.info(f"Speaking: {text}")
                        self.tts.speak(text)
                    except Exception as e:
                        logging.error(f"TTS error: {e}")
            time.sleep(0.1)  # Small delay to prevent CPU hogging

    def start_tts_worker(self):
        logging.info("Starting TTS worker")
        if not self.tts_worker or not self.tts_worker.active.is_set():
            self.tts_worker = ThreadWorker()
            self.tts_worker.start(self.process_tts_queue)

    def stop_tts_worker(self):
        if self.tts_worker and self.tts_worker.active.is_set():
            self.tts_worker.stop()
            self.tts_worker = None

    def queue_tts(self, text):
        text = text.strip()
        if text:
            try:
                self.tts.speak(text)
            except Exception as e:
                logging.error(f"TTS error: {e}")

class App(Application):
    def __init__(self):
        super().__init__()
        self.current_page = DemoPage(self)

if __name__ == '__main__':
    App()
    while True:
        logging.info('DS demo app ping')
        time.sleep(5)

        