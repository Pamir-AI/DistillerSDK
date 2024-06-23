from typing import Any, Dict, Tuple, Optional
import time
import torch
import random
import numpy as np
import json
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from optimum.onnxruntime import ORTStableDiffusionPipeline, ORTStableDiffusionInpaintPipeline
from distiller.utils.commons import timeit
from distiller.utils.image import merge_inpaint
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class PromptGenerator:
    def __init__(self, prompt_file_path: str):
        """
        Initializes the PromptGenerator with a path to the prompt file.

        Args:
            prompt_file_path (str): Path to the JSON file containing prompts.
        """
        with open(prompt_file_path) as f:
            self.prompts_bank = json.load(f)

    def gen(self) -> str:
        """
        Generates a random prompt from the prompts bank.

        Returns:
            str: A randomly generated prompt.
        """
        return ", ".join([random.sample(prompts, 1)[0] for _, prompts in self.prompts_bank.items()])


class StableDiffusionBase:
    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the StableDiffusionBase with a configuration.

        Args:
            config (Dict[str, Any]): Configuration dictionary.
        """
        assert config, "config is required"
        logging.info('stable diffusion instance created')
        self.config = config
        self.pipe = None

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        pass

    def _get_generator(self) -> Tuple[np.random.RandomState, int]:
        """
        Generates a random seed and sets it for torch and numpy.

        Returns:
            Tuple[np.random.RandomState, int]: A tuple containing the random state and the seed.
        """
        seed = np.random.randint(0, 1000000)
        torch.manual_seed(seed)
        return np.random.RandomState(seed), seed

    def _save_img(self, image: Image.Image, metadata: PngInfo, image_prefix: Optional[str]):
        """
        Saves the image with metadata.

        Args:
            image (Image.Image): The image to save.
            metadata (PngInfo): The metadata to include in the image.
            image_prefix (Optional[str]): The prefix for the image file name.
        """
        file_name = f"./temp-{self.config['model_name']}.png" if not image_prefix else image_prefix + ".png"
        image.save(file_name, pnginfo=metadata, optimize=True)


class StableDiffusionXSRender(StableDiffusionBase):
    def _reset(self):
        self.pipe = None
        self.vae = None

    @timeit
    def load_model(self):
        """
        Loads the model and VAE for the StableDiffusionXSRender.
        """
        from diffusers import AutoencoderTiny  # use diffuser's AE
        self._reset()
        self.pipe = ORTStableDiffusionPipeline.from_pretrained(
            self.config["model_path"])
        assert "vae_path" in self.config, "please provide vae_path for sdxs model in model_config.json"
        self.vae = AutoencoderTiny.from_pretrained(self.config["vae_path"])

    @timeit
    def __call__(self, prompt: str, width: Optional[int] = None, height: Optional[int] = None,
                 callback: Optional[Any] = None, image_prefix: Optional[str] = None):
        """
        Generates an image based on the prompt and other parameters.

        Args:
            prompt (str): The prompt for image generation.
            width (Optional[int]): The width of the generated image.
            height (Optional[int]): The height of the generated image.
            callback (Optional[Any]): A callback function to handle the generated image.
            image_prefix (Optional[str]): The prefix for the image file name.
        """
        prompt = f"{self.config.get('default_prompt','')}, {self.config.get('lora_trigger_words','')}, {prompt},"
        negative_prompt = self.config.get("negative_prompt", "")
        num_inference_steps = self.config.get("num_inference_steps", 3)
        guidance_scale = self.config.get("guidance_scale", 1.0)

        logging.info(f" ingesting prompt : {prompt}")
        g, seed = self._get_generator()
        height = height or self.config.get("height", 128 * 3)
        width = width or self.config.get("width", 128 * 2)

        latents = self.pipe(prompt,
                            negative_prompt=negative_prompt,
                            height=height,
                            width=width,
                            num_inference_steps=num_inference_steps,
                            generator=g,
                            guidance_scale=guidance_scale,
                            output_type="latent").images
        with torch.no_grad():  # decode image
            latents = self.vae.decode(torch.from_numpy(
                latents) / self.vae.config.scaling_factor, return_dict=False)[0]
            do_denormalize = [True] * latents.shape[0]
            image = self.pipe.image_processor.postprocess(
                latents.numpy(), output_type='pil', do_denormalize=do_denormalize)[0]

        # encode meta data and cache
        metadata = PngInfo()
        metadata.add_text("seed", str(seed))
        metadata.add_text("default_prompt",
                          self.config.get('default_prompt', ''))
        metadata.add_text("prompt", prompt)
        metadata.add_text("neg_prompt", negative_prompt)
        metadata.add_text("height", str(height))
        metadata.add_text("width", str(width))
        metadata.add_text("num_inference_steps", str(num_inference_steps))
        metadata.add_text("guidance_scale", str(guidance_scale))
        self._save_img(image, metadata, image_prefix)

        if callback:
            callback(image)  # return back the image


class StableDiffusionRender(StableDiffusionBase):
    def _reset(self):
        self.pipe = None

    @timeit
    def load_model(self):
        """
        Loads the model for the StableDiffusionRender.
        """
        self._reset()
        self.pipe = ORTStableDiffusionPipeline.from_pretrained(
            self.config["model_path"])

    @timeit
    def __call__(self, prompt: str, width: Optional[int] = None, height: Optional[int] = None,
                 callback: Optional[Any] = None, image_prefix: Optional[str] = None):
        """
        Generates an image based on the prompt and other parameters.

        Args:
            prompt (str): The prompt for image generation.
            width (Optional[int]): The width of the generated image.
            height (Optional[int]): The height of the generated image.
            callback (Optional[Any]): A callback function to handle the generated image.
            image_prefix (Optional[str]): The prefix for the image file name.
        """
        prompt = f"{self.config.get('default_prompt','')}, {self.config.get('lora_trigger_words','')}, {prompt},"
        negative_prompt = self.config.get("negative_prompt", "")
        num_inference_steps = self.config.get("num_inference_steps", 3)
        guidance_scale = self.config.get("guidance_scale", 1.0)

        logging.info(f" ingesting prompt : {prompt}")
        g, seed = self._get_generator()
        height = height or self.config.get("height", 128 * 3)
        width = width or self.config.get("width", 128 * 2)

        image = self.pipe(prompt,
                          negative_prompt=negative_prompt,
                          height=height,
                          width=width,
                          num_inference_steps=num_inference_steps,
                          generator=g,
                          guidance_scale=guidance_scale).images[0]

        # encode meta data and cache
        metadata = PngInfo()
        metadata.add_text("seed", str(seed))
        metadata.add_text("default_prompt",
                          self.config.get('default_prompt', ''))
        metadata.add_text("prompt", prompt)
        metadata.add_text("neg_prompt", negative_prompt)
        metadata.add_text("height", str(height))
        metadata.add_text("width", str(width))
        metadata.add_text("num_inference_steps", str(num_inference_steps))
        metadata.add_text("guidance_scale", str(guidance_scale))
        self._save_img(image, metadata, image_prefix)

        if callback:
            callback(image)  # return back the image


class StableDiffusionInpaintRender(StableDiffusionBase):
    def _reset(self):
        self.pipe = None

    @timeit
    def load_model(self):
        """
        Loads the model for the StableDiffusionInpaintRender.
        """
        self._reset()
        self.pipe = ORTStableDiffusionInpaintPipeline.from_pretrained(
            self.config["model_path"])

    @timeit
    def __call__(self, prompt: str, image: Image.Image, mask: Image.Image, image_prefix: Optional[str] = None):
        """
        Generates an inpainted image based on the prompt, original image, and mask.

        Args:
            prompt (str): The prompt for image generation.
            image (Image.Image): The original image to be inpainted.
            mask (Image.Image): The mask indicating the region to be inpainted.
            image_prefix (Optional[str]): The prefix for the image file name.
        """
        width, height = image.size
        num_inference_steps = self.config.get("num_inference_steps", 3)
        guidance_scale = self.config.get("guidance_scale", 1.0)
        negative_prompt = self.config.get("negative_prompt", "")

        out_image = self.pipe(prompt,
                              negative_prompt=negative_prompt,
                              image=image,
                              mask_image=mask,
                              width=width,
                              height=height,
                              num_inference_steps=num_inference_steps,
                              guidance_scale=guidance_scale).images[0]

        combined_image = merge_inpaint(image, out_image, mask)

        metadata = PngInfo()
        metadata.add_text("prompt", prompt)
        metadata.add_text("neg_prompt", negative_prompt)
        metadata.add_text("height", str(height))
        metadata.add_text("width", str(width))
        metadata.add_text("num_inference_steps", str(num_inference_steps))
        metadata.add_text("guidance_scale", str(guidance_scale))
        self._save_img(combined_image, metadata, image_prefix)
        return combined_image
