import pyaudio
import wave
from typing import Generator
from faster_whisper import WhisperModel
from distiller.utils.commons import ThreadWorker, timeit
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

FORMAT = pyaudio.paInt16  # 16-bit resolution
CHANNELS = 1  # 1 channel
RATE = 44100  # 44.1kHz sampling rate
CHUNK = 4096  # 2^12 samples for buffer
record_secs = 3  # seconds to record
dev_index = 2  # device index found by p.get_device_info_by_index(ii)
wav_output_filename = './temp.wav'  # name of .wav file


class Whisper:
    audio = wav_output_filename

    def __init__(self):
        """
        Initializes the Whisper class with a default model.
        """
        self.model = WhisperModel(
            'tiny', device="cpu", compute_type="int8")  # TODO: Customize the default model for your use

    @timeit
    def transcribe(self) -> Generator[str, None, None]:
        """
        Transcribes the audio file to text.

        Yields:
            str: Transcribed text segments.
        """
        segments, info = self.model.transcribe(
            self.audio, beam_size=5, language='en')
        logging.info("Detected language '%s' with probability %f" %
                     (info.language, info.language_probability))
        for segment in segments:
            logging.info("[%.2fs -> %.2fs] %s" %
                         (segment.start, segment.end, segment.text))
            yield segment.text

    def translate(self):
        """
        Placeholder for translation functionality.
        """
        pass  # TODO: Potentially only OK when translating to English
