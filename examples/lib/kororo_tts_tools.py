import os
import numpy as np
from onnxruntime import InferenceSession
from kokoro_onnx import Tokenizer
import subprocess
import io
import wave
import time
import logging

class KokoroTTS:
    def __init__(self, 
                 model_path: str = "/home/distiller/DistillerSDK/tts-model/kororo/kokoro-v1.0.uint8.onnx",
                 voice_path: str = "/home/distiller/DistillerSDK/tts-model/kororo/af_nicole.bin",
                 sample_rate: int = 24000):
        """
        Initialize Kokoro TTS with direct ONNX inference.
        
        Args:
            model_path: Path to the Kokoro ONNX model file
            voice_path: Path to the voice file (.bin)
            sample_rate: Audio sample rate (default: 24000)
        """
        start_time = time.time()
        logging.info(f"Initializing KokoroTTS with model: {model_path}")
        
        self.sample_rate = sample_rate
        self.tokenizer = Tokenizer()
        self.session = InferenceSession(model_path)
        
        # Load voice data
        self.voices = np.fromfile(voice_path, dtype=np.float32).reshape(-1, 1, 256)
        
        load_time = time.time() - start_time
        logging.info(f"KokoroTTS initialization complete (took {load_time:.2f} seconds)")

    def _prepare_inputs(self, text: str, speed: float = 1.0, language: str = "en-us"):
        """Prepare input tokens and style vector for inference"""
        # Convert text to phonemes and tokens
        phonemes = self.tokenizer.phonemize(text, lang=language)
        tokens = self.tokenizer.tokenize(phonemes)
        
        # Ensure tokens fit within context window (leaving room for pad tokens)
        if len(tokens) > 510:
            logging.warning(f"Text too long ({len(tokens)} tokens), truncating to 510")
            tokens = tokens[:510]
        
        # Add pad tokens and reshape
        tokens = [[0, *tokens, 0]]
        
        # Get style vector based on sequence length
        ref_s = self.voices[len(tokens[0])-2]  # -2 to account for pad tokens
        
        # Prepare speed factor
        speed_factor = np.array([speed], dtype=np.float32)
        
        return tokens, ref_s, speed_factor

    def generate_audio(self, text: str, speed: float = 1.0, language: str = "en-us") -> np.ndarray:
        """
        Generate audio samples for the given text.
        
        Args:
            text: Text to synthesize
            speed: Speech speed multiplier (default: 1.0)
            language: Language code (default: "en-us")
            
        Returns:
            numpy.ndarray: Audio samples
        """
        start_time = time.time()
        
        # Prepare inputs
        tokens, style, speed_factor = self._prepare_inputs(text, speed, language)
        
        # Run inference
        audio = self.session.run(None, {
            "input_ids": tokens,
            "style": style,
            "speed": speed_factor,
        })[0]
        
        generation_time = time.time() - start_time
        logging.info(f"Audio generated in {generation_time:.2f} seconds")
        
        return audio

    def play_audio(self, audio: np.ndarray) -> None:
        """
        Play audio using MPV player.
        
        Args:
            audio: Numpy array of audio samples
        """
        try:
            # Convert to 16-bit integers
            audio_int16 = (audio * 32767).astype(np.int16)
            
            # Create WAV format in memory
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(audio_int16.tobytes())
            
            # Play using MPV
            mpv_command = ["mpv", "--no-cache", "--no-terminal", "--", "fd://0"]
            mpv_process = subprocess.Popen(
                mpv_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            
            mpv_process.stdin.write(wav_buffer.getvalue())
            mpv_process.stdin.close()
            mpv_process.wait()
            
        except Exception as e:
            logging.error(f"Error playing audio: {str(e)}")

    def speak(self, text: str, speed: float = 1.0, language: str = "en-us") -> None:
        """
        Generate and play speech for the given text.
        
        Args:
            text: Text to speak
            speed: Speech speed multiplier (default: 1.0)
            language: Language code (default: "en-us")
        """
        audio = self.generate_audio(text, speed, language)
        self.play_audio(audio)

# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize TTS
    tts = KokoroTTS()
    
    # Example text
    sample_text = "Hey Kevin, how are you doing today? I'd like to order a large pepperoni pizza with extra cheese and a side of wings."
    
    # Generate and play speech
    tts.speak(sample_text)
    