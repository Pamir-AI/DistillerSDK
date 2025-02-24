import re
import logging
import requests
import json  # for streaming json lines

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

STOP_WORDS = ["</s>", "<|im_end|>", "<|endoftext|>", "<|user|>", "<|assistant|>"]


def is_sentence_ending(s):
    return s and s[-1] in {"!", "?", ".", "\n"}


class LlamaServerClient:
    """
    A client for interacting with a running llama.cpp server endpoint.
    """
    def __init__(self, endpoint, **kwargs):
        """
        Initializes the client.
        :param endpoint: URL of the llama.cpp server endpoint.
        :param kwargs: Optional default parameters (e.g. temperature, max_tokens) to be sent in every request.
        """
        self.endpoint = endpoint
        self.default_params = kwargs
        self.current_response = None  # Add this to track the response object
        self.default_prompt = "You are a helpful companion named PAMIR-R1, you speak in empathetic and friendly tone. Try to answer question in a very concise sentence in a casual chatting way. DO NOT OVERTHINK. \n "

    def generate(self, prompt, stream=False, **kwargs):
        """
        Generates text using llama.cpp server.
        :param prompt: The input prompt to send.
        :param stream: If True, yields each piece of the response as it is received.
        :param kwargs: Additional parameters (can override default_params).
        :return: If stream is False, returns the full JSON response; otherwise, yields JSON objects.
        """
        # Combine parameters with defaults and caller overrides.
        params = {"prompt": self.default_prompt + prompt}
        params.update(self.default_params)
        params.update(kwargs)
        params["stream"] = stream

        if stream:
            self.current_response = requests.post(self.endpoint, json=params, stream=True)
            self.current_response.raise_for_status()
            try:
                for line in self.current_response.iter_lines():
                    if line:  # filter out keep-alive new lines.
                        try:
                            decoded_line = line.decode('utf-8').strip()
                            logging.debug(f"Received line after decoding: {decoded_line}")

                            if decoded_line.startswith('data:'):
                                json_str = decoded_line[len('data:'):].strip()
                                
                                if json_str:
                                    data = json.loads(json_str)
                                    yield data
                                else:
                                    logging.warning("Received 'data:' line with no content.")
                            else:
                                logging.warning(f"Unexpected line format: {decoded_line}")
                        except json.JSONDecodeError as e:
                            logging.error(f"JSON decoding failed: {e} - Line content: {decoded_line}")
                            continue
                        except UnicodeDecodeError as e:
                            logging.error(f"Unicode decoding failed: {e} - Line content: {line}")
                            continue
            finally:
                if self.current_response:  # Add check before closing
                    self.current_response.close()
                self.current_response = None
        else:
            response = requests.post(self.endpoint, json=params)
            response.raise_for_status()
            return response.json()

    def stop_generation(self):
        """Stop the current streaming generation if any."""
        if self.current_response:
            self.current_response.close()
            self.current_response = None


def load_llm(server_endpoint, **kwargs):
    """
    Connects to a llama.cpp server endpoint.
    
    :param server_endpoint: The URL of the llama.cpp server endpoint.
    :param kwargs: Default generation parameters to pass to the client.
    :return: An instance of LlamaServerClient.
    """
    return LlamaServerClient(server_endpoint, **kwargs)


def clean_response(s):
    s = s.replace("\n", ",").replace('"', '').replace(".", ",")
    pattern = r"\d+, "
    return re.sub(pattern, "", s)


def stream_sentence(stream):
    sentence = ""
    is_thinking = True  # Track if we're still in thinking phase
    for output in stream:
        print("[LLM] output", output)
        content = output.get("content", "")
        stop = output.get("stop", False)
        if not content:
            continue
        if stop:
            break

        # Check for </think> tag
        if "</think>" in content:
            # Split content at </think> tag
            thinking_part, answer_part = content.split("</think>", 1)
            
            # Process any remaining thinking content
            if thinking_part:
                for temp in thinking_part.replace('\n', " "):
                    sentence += temp
                    
                    # early stop if stop words are in the content
                    if any(word in sentence.lower() for word in STOP_WORDS):
                        # trim the sentence to the last complete sentence
                        sentence = sentence.rsplit(' ', 1)[0]
                        yield "thinking: ---> " + sentence.strip()
                        sentence = ""
                        break
                    
                    if is_sentence_ending(temp):
                        yield "thinking: ---> " + sentence.strip()
                        sentence = ""
            
            # Start processing answer part
            sentence = answer_part
            is_thinking = False
            continue

        # Process regular content
        for temp in content.replace('\n', " "):
            sentence += temp
            if is_sentence_ending(temp):
                prefix = "thinking: ---> " if is_thinking else "answer: ---> "
                yield prefix + sentence.strip()
                sentence = ""

    # Handle any remaining sentence
    if sentence:
        prefix = "thinking: ---> " if is_thinking else "answer: ---> "
        yield prefix + sentence.strip()


def generate_sentence(output):
    logging.info(output)
    sentence = ""
    content = extract_content(output)
    if not content:
        return  # or handle as appropriate

    for temp in content.replace('\n', " "):
        sentence += temp
        if is_sentence_ending(temp):
            yield sentence
            sentence = ""  # reset
    if sentence:
        yield sentence


def extract_content(output):
    """
    Extracts the generated text from the output dictionary.
    Supports multiple possible keys for flexibility.
    """
    if "content" in output:
        return output["content"]
    elif "choices" in output and len(output["choices"]) > 0 and "text" in output["choices"][0]:
        return output["choices"][0]["text"]
    else:
        logging.error("Neither 'content' nor 'choices[0].text' found in the output.")
        return ""
