import re
import logging
from llama_cpp import Llama

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

STOP_WORDS = ["</s>", "<|im_end|>", "<|endoftext|>", "\n"]


def is_sentence_ending(s):
    return s and s[-1] in {"!", "?", ".", "\n"}


def load_llm(model_path, **kwargs):
    return Llama(
        model_path=model_path,
        **kwargs
    )


def clean_response(s):
    s = s.replace("\n", ",").replace('"', '').replace(".", ",")
    pattern = r"\d+, "
    return re.sub(pattern, "", s)


def stream_sentence(stream):
    sentence = ""
    for output in stream:
        temp = output["choices"][0]["text"].replace('\n', " ")  # no multi-line
        sentence += temp
        if is_sentence_ending(temp):
            yield sentence
            sentence = ""  # reset
    if sentence:
        yield sentence


def generate_sentence(output):
    logging.info(output)
    sentence = ""
    for temp in output["choices"][0]["text"].replace('\n', " "):
        sentence += temp
        if is_sentence_ending(temp):
            yield sentence
            sentence = ""  # reset
    if sentence:
        yield sentence
