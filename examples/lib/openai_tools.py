from typing import List, Dict, Optional, Tuple, Any
import json
import os
import time
import requests
from PIL import Image
import openai
import re
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

client = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))

# Constants
ASSISTANT_ID = "asst_3cgygF6dmPzXWn9z2zUlfgCO" # if you already had one created 
GAME_CONFIG_PATH = "./game_config.json"


def extract_url(text: str) -> Optional[str]:
    """
    Extracts the first URL found in the given text.

    Args:
        text (str): The text to search for URLs.

    Returns:
        Optional[str]: The first URL found, or None if no URL is found.
    """
    url_pattern = r'https?://[^\s)]+'
    url = re.search(url_pattern, text)
    return url.group(0) if url else None


def clean_text(text: str) -> str:
    """
    Cleans the given text by removing markdown image links and their URLs.

    Args:
        text (str): The text to clean.

    Returns:
        str: The cleaned text.
    """
    clean_text = re.sub(r'!\[.*?\]\(https?://[^\s)]+\)', '', text)
    return clean_text.strip()


def generate_image(prompt: str, n: int = 1, size: str = "1024x1024") -> str:
    """
    Generates an image using the DALL-E model based on the given prompt.

    Args:
        prompt (str): The prompt to generate the image.
        n (int, optional): The number of images to generate. Defaults to 1.
        size (str, optional): The size of the generated image. Defaults to "1024x1024".

    Returns:
        str: The URL of the generated image.
    """
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size=size,
        quality="standard",
        n=n
    )
    image_url = response.data[0].url
    im = Image.open(requests.get(image_url, stream=True).raw)
    im.resize((256, 256)).save("./gpt-story.png")
    return image_url


class AdventureGameAssistant:
    def __init__(self):
        """
        Initializes the AdventureGameAssistant with default instructions and sets up the game configuration.
        """
        self.instructions = """
        You will create adventure game scenes with story progression. You have 2 return options:

        1. Return text dialog and use generate_image function to generate a new scene whenever a scene changes.
        2. Return text dialog when a character speaks.

        Always start new game with an image return. 
        Try to proceed with the story one step at a time, limit return to 2 to 3 sentences max. 
        No need to return the next move for the user.
        """
        
        # try create asistant first time using it.
        # if not ASSISTANT_ID: ASSISTANT_ID, thread_id = self.setup_assistant(self.instructions)
        
        self.assistant_id = ASSISTANT_ID 
        thread_id = self.create_thread(self.instructions)
        self.game_config = {
            "assistant_id": ASSISTANT_ID,
            "thread_id": thread_id
        }
        with open(GAME_CONFIG_PATH, "w") as f:
            json.dump(self.game_config, f)

        self.clear_non_expire_run()

    def create_thread(self, script_code: str) -> str:
        """
        Creates a new thread with the given script code.

        Args:
            script_code (str): The script code to initialize the thread.

        Returns:
            str: The ID of the created thread.
        """
        thread = client.beta.threads.create()
        client.beta.threads.messages.create(
            thread.id,
            role="user",
            content=script_code,
        )
        return thread.id

    def setup_assistant(self, script_code: str) -> Tuple[str, str]:
        """
        Sets up the assistant with the given script code.

        Args:
            script_code (str): The script code to initialize the assistant.

        Returns:
            Tuple[str, str]: The IDs of the created assistant and thread.
        """
        assistant = client.beta.assistants.create(
            name="adventure_game",
            instructions=self.instructions,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "generate_image",
                        "description": "Generate image by DALL-E 3 for a new scene",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "prompt": {"type": "string", "description": "The prompt to generate image"}
                            },
                            "required": ["prompt"]
                        }
                    }
                }
            ],
            tool_choice='auto',
            model="gpt-4o",
        )
        thread = client.beta.threads.create()
        client.beta.threads.messages.create(
            thread.id,
            role="user",
            content=script_code,
        )
        return assistant.id, thread.id

    def send_message(self, text: str, image_url: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Sends a message to the assistant and processes the response.

        Args:
            text (str): The text message to send.
            image_url (Optional[str], optional): The URL of the image to include. Defaults to None.

        Returns:
            Tuple[Optional[str], Optional[str]]: The extracted URL and cleaned text from the response.
        """
        thread_id = self.game_config["thread_id"]
        content = [{"type": "text", "text": text}]
        if image_url:
            content.append(
                {"type": "image_url", "image_url": {
                    "url": image_url, "detail": "low"}}
            )
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=content
        )
        try:
            messages = self.run_assistant()
            message_dict = json.loads(messages.model_dump_json())
            content = message_dict['data'][0]['content'][0]["text"]["value"]
            if "](https" in content:
                return extract_url(content), clean_text(content)
            else:
                return None, content
        except Exception as e:
            logging.error(e)
            return None, None

    def run_assistant(self) -> List[Dict[str, Any]]:
        """
        Runs the assistant and retrieves the messages.

        Returns:
            List[Dict[str, Any]]: The list of messages from the assistant.
        """
        thread_id = self.game_config["thread_id"]
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID
        )
        while run.status in ["in_progress", "queued"]:
            time.sleep(3)
            run = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            if run.status == "completed":
                return client.beta.threads.messages.list(thread_id=thread_id)
            if run.status == "requires_action":
                tool_outputs = []
                for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                    if tool_call.function.name == "generate_image":
                        prompt = json.loads(tool_call.function.arguments)[
                            'prompt']
                        image_url = generate_image(prompt)
                        tool_outputs.append(
                            {"tool_call_id": tool_call.id, "output": image_url})
                if run.required_action.type == "submit_tool_outputs":
                    run = client.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread_id,
                        run_id=run.id,
                        tool_outputs=tool_outputs
                    )

    def clear_non_expire_run(self):
        """
        Clears any non-expired runs for the current thread.
        """
        thread_id = self.game_config["thread_id"]
        runs = client.beta.threads.runs.list(thread_id)
        for run in runs:
            if run.status in ["queued", "in_progress", "requires_action"]:
                run = client.beta.threads.runs.cancel(
                    thread_id=thread_id,
                    run_id=run.id
                )
