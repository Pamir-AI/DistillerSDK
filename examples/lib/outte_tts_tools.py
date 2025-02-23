import requests
import re
import struct
import numpy as np
from concurrent.futures import ThreadPoolExecutor


def fill_hann_window(size, periodic=True):
    if periodic:
        return np.hanning(size + 1)[:-1]
    return np.hanning(size)


def irfft(n_fft, complex_input):
    return np.fft.irfft(complex_input, n=n_fft)


def fold(buffer, n_out, n_win, n_hop, n_pad):
    result = np.zeros(n_out)
    n_frames = len(buffer) // n_win

    for i in range(n_frames):
        start = i * n_hop
        end = start + n_win
        result[start:end] += buffer[i * n_win:(i + 1) * n_win]

    return result[n_pad:-n_pad] if n_pad > 0 else result


def process_frame(args):
    l, n_fft, ST, hann = args
    frame = irfft(n_fft, ST[l])
    frame = frame * hann
    hann2 = hann * hann
    return frame, hann2


def embd_to_audio(embd, n_codes, n_embd, n_thread=4):
    embd = np.asarray(embd, dtype=np.float32).reshape(n_codes, n_embd)

    n_fft = 1280
    n_hop = 320
    n_win = 1280
    n_pad = (n_win - n_hop) // 2
    n_out = (n_codes - 1) * n_hop + n_win

    hann = fill_hann_window(n_fft, True)

    E = np.zeros((n_embd, n_codes), dtype=np.float32)
    for l in range(n_codes):
        for k in range(n_embd):
            E[k, l] = embd[l, k]

    half_embd = n_embd // 2
    S = np.zeros((n_codes, half_embd + 1), dtype=np.complex64)

    for k in range(half_embd):
        for l in range(n_codes):
            mag = E[k, l]
            phi = E[k + half_embd, l]

            mag = np.clip(np.exp(mag), 0, 1e2)
            S[l, k] = mag * np.exp(1j * phi)

    res = np.zeros(n_codes * n_fft)
    hann2_buffer = np.zeros(n_codes * n_fft)

    with ThreadPoolExecutor(max_workers=n_thread) as executor:
        args = [(l, n_fft, S, hann) for l in range(n_codes)]
        results = list(executor.map(process_frame, args))

        for l, (frame, hann2) in enumerate(results):
            res[l*n_fft:(l+1)*n_fft] = frame
            hann2_buffer[l*n_fft:(l+1)*n_fft] = hann2

    audio = fold(res, n_out, n_win, n_hop, n_pad)
    env = fold(hann2_buffer, n_out, n_win, n_hop, n_pad)

    mask = env > 1e-10
    audio[mask] /= env[mask]

    return audio


def save_wav(filename, audio_data, sample_rate):
    num_channels = 1
    bits_per_sample = 16
    bytes_per_sample = bits_per_sample // 8
    data_size = len(audio_data) * bytes_per_sample
    byte_rate = sample_rate * num_channels * bytes_per_sample
    block_align = num_channels * bytes_per_sample
    chunk_size = 36 + data_size  # 36 = size of header minus first 8 bytes

    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        chunk_size,
        b'WAVE',
        b'fmt ',
        16,                # fmt chunk size
        1,                 # audio format (PCM)
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b'data',
        data_size
    )

    audio_data = np.clip(audio_data * 32767, -32768, 32767)
    pcm_data = audio_data.astype(np.int16)

    with open(filename, 'wb') as f:
        f.write(header)
        f.write(pcm_data.tobytes())


def process_text(text: str):
    text = re.sub(r'\d+(\.\d+)?', lambda x: x.group(), text.lower()) # TODO this needs to be fixed
    text = re.sub(r'[-_/,\.\\]', ' ', text)
    text = re.sub(r'[^a-z\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text.split()



class TTSStreamGenerator:
    def __init__(self, llm_host, dec_host):
        self.llm_host = llm_host
        self.dec_host = dec_host
        self.prefix = """<|im_start|>
<|text_start|>the<|text_sep|>overall<|text_sep|>package<|text_sep|>from<|text_sep|>just<|text_sep|>two<|text_sep|>people<|text_sep|>is<|text_sep|>pretty<|text_sep|>remarkable<|text_sep|>sure<|text_sep|>i<|text_sep|>have<|text_sep|>some<|text_sep|>critiques<|text_sep|>about<|text_sep|>some<|text_sep|>of<|text_sep|>the<|text_sep|>gameplay<|text_sep|>aspects<|text_sep|>but<|text_sep|>its<|text_sep|>still<|text_sep|>really<|text_sep|>enjoyable<|text_sep|>and<|text_sep|>it<|text_sep|>looks<|text_sep|>lovely<|text_sep|>"""

    def process_text(self, text: str):
        text = re.sub(r'\d+(\.\d+)?', lambda x: x.group(), text.lower())
        text = re.sub(r'[-_/,\.\\]', ' ', text)
        text = re.sub(r'[^a-z\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text.split()

    def generate_audio(self, text, output_file=None, sample_rate=24000):
        """
        Generate audio from text and optionally save to file
        
        Args:
            text (str): Input text to convert to speech
            output_file (str, optional): Path to save WAV file. If None, audio data is returned
            sample_rate (int): Sample rate for audio (default 24000)
            
        Returns:
            If output_file is None: tuple(numpy.array, int) - (audio data, sample rate)
            If output_file is specified: str - Path to saved WAV file
        """
        print(f"Processing text: '{text}'")
        
        # Process text
        words = self.process_text(text)
        formatted_words = "<|text_sep|>".join([i.strip() for i in words])
        formatted_words += "<|text_end|>\n"
        print(f"Processed into {len(words)} words")

        # Get LLM response
        print("Requesting LLM completion...")
        response = requests.post(
            self.llm_host + "/completion",
            json={
                "prompt": [self.prefix + formatted_words],
                "n_predict": 1024,
                "cache_prompt": True,
                "return_tokens": True,
                "samplers": ["top_k"],
                "top_k": 16,
                "seed": 1003,
            }
        )
        
        response_json = response.json()
        codes = [t - 151672 for t in response_json["tokens"] if t >= 151672 and t <= 155772]
        print(f"Received {len(codes)} tokens from LLM")

        # Get embeddings
        print("Requesting audio embeddings...")
        response = requests.post(
            self.dec_host + "/embeddings",
            json={
                "input": [*codes],
            }
        )
        
        response_json = response.json()
        embd = response_json[0]["embedding"]
        
        n_codes = len(embd)
        n_embd = len(embd[0])
        print(f"Received embeddings with shape: {n_codes}x{n_embd}")

        # Convert to audio
        print("Converting embeddings to audio waveform...")
        audio = embd_to_audio(embd, n_codes, n_embd)
        
        # Zero out first 0.25 seconds
        audio[:sample_rate // 4] = 0.0
        print(f"Generated {len(audio)/sample_rate:.2f} seconds of audio")

        if output_file:
            print(f"Saving audio to {output_file}")
            save_wav(output_file, audio, sample_rate)
            return output_file
        
        return audio, sample_rate

# Example usage:
"""
tts = TTSStreamGenerator("http://server-llm:port", "http://server-dec:port")

# Save to file
tts.generate_audio("Hello world!", "output.wav")

# Get audio data
audio_data, sample_rate = tts.generate_audio("Hello world!")
"""

if __name__ == "__main__":
    tts = TTSStreamGenerator("http://127.0.0.1:8020", "http://127.0.0.1:8021")
    tts.generate_audio("Hello world!", "./tts_test_output.wav")
