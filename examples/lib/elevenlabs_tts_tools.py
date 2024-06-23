# elevenlab support
import time
import os
import logging
import threading
import subprocess
from typing import Iterator, Optional
from elevenlabs.client import ElevenLabs
from elevenlabs import stream, save
from distiller.utils.commons import timeit
from distiller.utils.audio import get_volume
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

TIME_LIMIT = 30  # time limit in seconds


class TTS:
    def __init__(self):
        """
        Initialize the TTS (Text-to-Speech) instance.
        """
        self.client = ElevenLabs(api_key=os.getenv("ELEVEN_API_KEY"))
        self.volume = 0
        self.timer: Optional[threading.Timer] = None

    @timeit
    def stream(self, text: str) -> None:
        """
        Stream the generated audio for the given text.

        :param text: The text to convert to speech.
        """
        audio_stream = self.client.generate(
            text=text,
            voice="BnZFkf02KXFrnB2Pex6P",
            stream=True
        )

        logging.info(f"[DEBUG] -> TTS stream started at time {time.time()}")

        # Start the timer to stop after 30 seconds
        self.timer = threading.Timer(TIME_LIMIT, self._stop_stream)
        self.timer.start()

        self._stream(audio_stream)

    def _stream(self, audio_stream: Iterator[bytes]) -> bytes:
        """
        Stream the audio data to the MPV player.

        :param audio_stream: The audio data stream.
        :return: The concatenated audio data.
        """
        mpv_command = ["mpv", "--no-cache", "--no-terminal", "--", "fd://0"]
        mpv_process = subprocess.Popen(
            mpv_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        audio = b""

        for chunk in audio_stream:
            if chunk is not None:
                mpv_process.stdin.write(chunk)  # type: ignore
                mpv_process.stdin.flush()  # type: ignore
                audio += chunk

        if mpv_process.stdin:
            mpv_process.stdin.close()
        mpv_process.wait()

        # Cancel the timer if it's still running
        if self.timer:
            self.timer.cancel()
            self.timer = None

        return audio

    def _stop_stream(self) -> None:
        """
        Stop the audio stream.
        """
        logging.info("Stopping the audio stream due to time limit.")
        if self.timer:
            self.timer.cancel()
            self.timer = None
