import sys
import wave
import getopt
import alsaaudio
from typing import Optional

# Constants
DEVICE = "hw:2"  # TODO fix this for all firmwares

def _get_format(sampwidth: int) -> int:
    """Get the ALSA format based on sample width."""
    if sampwidth == 1:
        return alsaaudio.PCM_FORMAT_U8
    elif sampwidth == 2:
        return alsaaudio.PCM_FORMAT_S16_LE
    elif sampwidth == 3:
        return alsaaudio.PCM_FORMAT_S24_3LE
    elif sampwidth == 4:
        return alsaaudio.PCM_FORMAT_S32_LE
    else:
        raise ValueError('Unsupported format')

def _play(f: wave.Wave_read) -> None:
    """Play the audio from the wave file."""
    format = _get_format(f.getsampwidth())
    periodsize = f.getframerate() // 8

    print(f'{f.getnchannels()} channels, {f.getframerate()} sampling rate, format {format}, periodsize {periodsize}\n')

    device = alsaaudio.PCM(channels=f.getnchannels(), rate=f.getframerate(), format=format, periodsize=periodsize, device=DEVICE)
    
    data = f.readframes(periodsize)
    while data:
        if device.write(data) < 0:
            print("Playback buffer underrun! Continuing nonetheless ...")
        data = f.readframes(periodsize)

def play_audio(audio_path: str) -> None:
    try : 
        """Play audio from the given file path."""
        with wave.open(audio_path, 'rb') as f:
            _play(f)
    except Exception as e:
        logging.error(f"Error speaker.play_audio: {e}")