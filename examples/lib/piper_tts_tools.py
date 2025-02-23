import subprocess
import tempfile
from typing import Optional

def text_to_speech(
    text: str,
    model_path: str,
    sample_rate: int = 22050,
    play_audio: bool = True
) -> Optional[bytes]:
    """
    Convert text to speech using Piper TTS and optionally play it.
    
    Args:
        text: The text to convert to speech
        model_path: Path to the Piper ONNX model file
        sample_rate: Audio sample rate (default: 22050)
        play_audio: Whether to play the audio immediately (default: True)
    
    Returns:
        bytes: Raw audio data if play_audio is False, None otherwise
    """
    # Create the Piper TTS process
    piper_process = subprocess.Popen(
        [
            'piper',
            '--model', model_path,
            '--output-raw'
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Send text to Piper
    audio_data, errors = piper_process.communicate(input=text.encode())
    
    if piper_process.returncode != 0:
        raise RuntimeError(f"Piper TTS failed: {errors.decode()}")

    if play_audio:
        # Play audio using aplay
        aplay_process = subprocess.Popen(
            [
                'aplay',
                '-r', str(sample_rate),
                '-f', 'S16_LE',
                '-t', 'raw',
                '-'
            ],
            stdin=subprocess.PIPE
        )
        aplay_process.communicate(input=audio_data)
        return None
    
    return audio_data

# Example usage:
if __name__ == "__main__":
    MODEL_PATH = "/home/distiller/DistillerSDK/tts-model/en_US-amy-medium.onnx"
    text = "Welcome to the world of speech synthesis, Enjoy the fun of AI"
    
    # Play audio immediately
    text_to_speech(text, MODEL_PATH)
    
    # Or get raw audio data without playing
    # audio_data = text_to_speech(text, MODEL_PATH, play_audio=False)
