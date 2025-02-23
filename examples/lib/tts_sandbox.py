import os
import numpy as np
from onnxruntime import InferenceSession
from kokoro_onnx import Tokenizer
import subprocess
import time
import io
import wave

# You can generate token ids as follows:
#   1. Convert input text to phonemes using https://github.com/hexgrad/misaki
#   2. Map phonemes to ids using https://huggingface.co/hexgrad/Kokoro-82M/blob/785407d1adfa7ae8fbef8ffd85f34ca127da3039/config.json#L34-L148
# tokens = [50, 157, 43, 135, 16, 53, 135, 46, 16, 43, 102, 16, 56, 156, 57, 135, 6, 16, 102, 62, 61, 16, 70, 56, 16, 138, 56, 156, 72, 56, 61, 85, 123, 83, 44, 83, 54, 16, 53, 65, 156, 86, 61, 62, 131, 83, 56, 4, 16, 54, 156, 43, 102, 53, 16, 156, 72, 61, 53, 102, 112, 16, 70, 56, 16, 138, 56, 44, 156, 76, 158, 123, 56, 16, 62, 131, 156, 43, 102, 54, 46, 16, 102, 48, 16, 81, 47, 102, 54, 16, 54, 156, 51, 158, 46, 16, 70, 16, 92, 156, 135, 46, 16, 54, 156, 43, 102, 48, 4, 16, 81, 47, 102, 16, 50, 156, 72, 64, 83, 56, 62, 16, 156, 51, 158, 64, 83, 56, 16, 44, 157, 102, 56, 16, 44, 156, 76, 158, 123, 56, 4]
tokenizer = Tokenizer()
sample_text = "Hey Kevin, how are you doing today? I'd like to order a large pepperoni pizza with extra cheese and a side of wings."
phonemes = tokenizer.phonemize(sample_text, lang="en-us")
tokens = tokenizer.tokenize(phonemes)

# Context length is 512, but leave room for the pad token 0 at the start & end
assert len(tokens) <= 510, len(tokens)

# Style vector based on len(tokens), ref_s has shape (1, 256)
voices = np.fromfile('/home/distiller/DistillerSDK/tts-model/kororo/af_nicole.bin', dtype=np.float32).reshape(-1, 1, 256)
ref_s = voices[len(tokens)]

# Add the pad ids, and reshape tokens, should now have shape (1, <=512)
tokens = [[0, *tokens, 0]]

model_name = '/home/distiller/DistillerSDK/tts-model/kororo/kokoro-v1.0.uint8.onnx' # Options: model.onnx, model_fp16.onnx, model_quantized.onnx, model_q8f16.onnx, model_uint8.onnx, model_uint8f16.onnx, model_q4.onnx, model_q4f16.onnx

# Time the model loading
start_time = time.time()
sess = InferenceSession(os.path.join('onnx', model_name))
model_load_time = time.time() - start_time
print(f"Model loading time: {model_load_time:.2f} seconds")

# Add verbose output before inference
print(f"Input tokens length: {len(tokens[0])}")
print(f"Style vector shape: {ref_s.shape}")
print(f"Using model: {model_name}")

# Time the inference
start_time = time.time()
audio = sess.run(None, dict(
    input_ids=tokens,
    style=ref_s,
    speed=np.ones(1, dtype=np.float32),
))[0]
inference_time = time.time() - start_time
print(f"Inference time: {inference_time:.2f} seconds")

# Add verbose output after inference
print(f"Generated audio shape: {audio.shape}")
print(f"Audio sample rate: 24000 Hz")

# Time the audio saving process
start_time = time.time()
temp_file = "/tmp/tts_output.wav"
audio_int16 = (audio * 32767).astype(np.int16)
audio_int16.tofile(temp_file)
save_time = time.time() - start_time
print(f"Audio save time: {save_time:.2f} seconds")

# Time the playback
start_time = time.time()
try:
    # Create WAV format in memory
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(24000)  # sample rate
        wav_file.writeframes(audio_int16.tobytes())
    
    # Play using MPV with pipe
    mpv_command = ["mpv", "--no-cache", "--no-terminal", "--", "fd://0"]
    print(f"Playing audio with MPV (sample rate: 24000Hz)")
    mpv_process = subprocess.Popen(
        mpv_command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
    mpv_process.stdin.write(wav_buffer.getvalue())
    mpv_process.stdin.close()
    mpv_process.wait()
    playback_time = time.time() - start_time
    print(f"Playback time: {playback_time:.2f} seconds")
except Exception as e:
    print(f"Error playing audio: {str(e)}")
