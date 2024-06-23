import os
import threading
import pyaudio
import audioop
import numpy as np
from distiller.utils.audio import get_volume
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
    Microphone
)
import logging
from typing import Any
from dotenv import load_dotenv
from distiller.peripheral.mic import (
    FORMAT,
    CHANNELS,
    RATE,
    CHUNK,
    record_secs,
    dev_index
)

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

API_KEY = os.getenv("DG_API_KEY")
TIME_LIMIT = 30  # time limit in seconds


class STT:
    def __init__(self):
        """
        Initialize the STT (Speech-to-Text) instance.
        """
        try:
            config = DeepgramClientOptions(options={"keepalive": "true"})
            self.client = DeepgramClient(API_KEY, config)
            self.dg_connection = self.client.listen.live.v("1")
            self.dg_connection.on(LiveTranscriptionEvents.Open, self.on_open)
            self.dg_connection.on(
                LiveTranscriptionEvents.Transcript, self.on_message)
            self.dg_connection.on(
                LiveTranscriptionEvents.Metadata, self.on_metadata)
            self.dg_connection.on(LiveTranscriptionEvents.Error, self.on_error)
            self.options = LiveOptions(
                model="nova-2",
                language="en-US",
                smart_format=True,
                encoding="linear16",
                channels=CHANNELS,
                sample_rate=RATE,
                interim_results=True,
                utterance_end_ms="1000",
                vad_events=True,
                endpointing=300,
            )
            self.transcript = ""
            self.is_finals = []

            self.microphone = Microphone(
                self.process_audio, rate=RATE, verbose=logging.DEBUG, chunk=CHUNK, channels=CHANNELS
            )

            self.volume = 0
            self.streaming = False
            self.timer = None
        except Exception as e:
            logging.error(f"STT.init : {e}")

    def process_audio(self, data: bytes) -> None:
        """
        Process the audio data and send it to Deepgram.

        :param data: The audio data to process.
        """
        self.dg_connection.send(data)
        self.volume = get_volume(data)

    def on_open(self, event: str, *args, **kwargs) -> None:
        """
        Handle the event when the connection is opened.

        :param event: The event name.
        """
        logging.info(f"Connection Open with event: {event} and args: {args}")

    def start(self) -> None:
        """
        Start the speech-to-text streaming.
        """
        logging.info('[Debug] stt.start clicked')
        self.streaming = True
        self.is_finals = []

        addons = {"no_delay": "true"}

        if not self.dg_connection.start(self.options, addons=addons):
            logging.error("Failed to connect to Deepgram")
            return

        self.microphone.start()

        self.timer = threading.Timer(TIME_LIMIT, self.stop)
        self.timer.start()

    def stop(self) -> None:
        """
        Stop the speech-to-text streaming.
        """
        self.streaming = False
        self.volume = 0
        self.microphone.finish()
        self.dg_connection.finish()
        logging.info("Finished")

        if self.timer:
            self.timer.cancel()
            self.timer = None

    def on_message(self, event: str, result: Any, **kwargs) -> None:
        """
        Handle the event when a message is received.

        :param event: The event name.
        :param result: The result data.
        """
        sentence = result.channel.alternatives[0].transcript
        if not sentence:
            return
        if result.is_final:
            self.is_finals.append(sentence)
            if result.speech_final:
                utterance = " ".join(self.is_finals)
                logging.info(f"Speech Final: {utterance}")
        else:
            logging.info(f"Interim Results: {sentence}")

    def on_metadata(self, event: str, metadata: Any, **kwargs) -> None:
        """
        Handle the event when metadata is received.

        :param event: The event name.
        :param metadata: The metadata.
        """
        logging.info(f"Metadata: {metadata}")

    def on_error(self, event: str, error: Any, **kwargs) -> None:
        """
        Handle the event when an error occurs.

        :param event: The event name.
        :param error: The error data.
        """
        logging.error(f"Error: {error}")

    def get_transcript(self) -> str:
        """
        Get the final transcript.

        :return: The final transcript as a string.
        """
        return " ".join(self.is_finals)
