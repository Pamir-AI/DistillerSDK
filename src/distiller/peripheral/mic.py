from typing import List, Optional
import pyaudio
import wave

from distiller.utils.commons import ThreadWorker

import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


def get_deice_id():
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if "seeed-2mic-voicecard" in dev['name']:
            return i
    return None


FORMAT = pyaudio.paInt16  # 16-bit resolution
CHANNELS = 1  # 1 channel
RATE = 44100  # 44.1kHz sampling rate
CHUNK = 4096  # 2^12 samples for buffer
record_secs = 3  # seconds to record
dev_index = get_deice_id()  # device index found by p.get_device_info_by_index(ii)
wav_output_filename = './temp.wav'  # name of .wav file


class AudioRecorder:
    """Handles audio recording using pyaudio."""

    def __init__(self) -> None:
        """Initialize the AudioRecorder."""
        self.p: pyaudio.PyAudio = pyaudio.PyAudio()  # create pyaudio instantiation
        self.frames: List[bytes] = []
        self.recording: bool = False
        self.thread_worker: Optional[ThreadWorker] = None

    def record_control(self) -> bool:
        if not self.recording:
            self.start_record()
            return True
        self.stop_record()
        return False

    def start_record(self) -> None:
        self.frames = []
        self.stream = self.p.open(
            format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

        self.thread_worker = ThreadWorker()  # new a thread worker
        # recording start, pass empty arg
        self.thread_worker.start(self._record_loop)

    def stop_record(self) -> None:  # reset thread
        self.thread_worker.stop()
        self.thread_worker = None

    def _record_loop(self, thread_event) -> None:
        while thread_event.is_set():  # start mic recording
            data = self.stream.read(CHUNK)
            self.frames.append(data)
            logging.info("* recording")
        self.stream.close()

    def save_wav(self) -> None:
        wf = wave.open(wav_output_filename, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(self.p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(self.frames))
        wf.close()
