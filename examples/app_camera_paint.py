
# TODO change context of this
# add exit for all apps

import cv2
from lib.stable_diffusion_tools import StableDiffusionInpaintRender
import math
import torch
from distiller.peripheral.speaker import play_audio
from ultralytics.models.fastsam import FastSAMPrompt
from ultralytics import FastSAM
import os
import sys
import time
from datetime import datetime
import random
import json

from pathlib import Path
from PIL import Image, ImageFilter, ImageOps
import threading  # Import threading module
from pkg_resources import resource_filename

from distiller.gui import Page, Application
from distiller.peripheral.eink import Eink
from distiller.peripheral.camera import Cam
from distiller.gui.components import *
from distiller.utils.image import paste_image, scale_image, show_text, merge_inpaint

import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


# UI constants
font_path = resource_filename('distiller', os.path.join(
    'resources', 'fonts', 'Monorama-Bold.ttf'))
dialog_font_size = 20
file_cache = './cam_capture_image.png'
loading_animation_folder = resource_filename(
    'distiller', os.path.join('resources', 'animations', 'loading_screen'))
dialog_box_path = resource_filename(
    'distiller', os.path.join('resources', 'dialogBox_240x97.png'))
dialog_box_size = (240, 97)
dialog_box_bounding_box = (15, 15, 225, 80)
dialog_font_size = 20
display_box = [15, 100, EINK_WIDTH-15, EINK_HEIGHT-100]

# model specific
sam_model_path = '/home/distiller/models/FastSAM-x.pt'
inpaint_model_config = {
    "model_name": "inpaint",
    "model_path": '/home/distiller/models/dreamshaper-8-inpainting-fused-onnx',
    "neg_prompt": 'bad hand, bad face, worst quality, low quality, logo, text, watermark, username, harsh shadow, shadow, artifacts, blurry, smooth texture, bad quality, distortions, unrealistic, distorted image, bad proportions, duplicate',
    "prompt": 'masterpiece, best quality, a cute kitten', # edit this for the inpaint prompt
    'sam_prompt': 'face' # edit this fot SAM prompt
}
inpaint_path = "./temp-inpaint.png"
saving_path = "/home/distiller/DistillerSDK/assets"

# others
sound_bite = resource_filename('distiller', os.path.join(
    'resources', 'audios', 'anime-wow-sound-effect.wav'))


class CamPage(Page):
    def __init__(self, app):
        super().__init__(app)

        # sd & sam
        self.pipe = None
        self.fast_sam = None
        self.captured_image = None

        # cam
        self.cam = Cam(self.app.screen)

        # ui
        self.ui = GUI(init_image=self.get_init_image())
        # self.ui.canvas.draw_plus_pattern()
        self.ui.canvas.register_canvas_image()  # cache image for future flash

        # options page 1
        self.dialog = ScrollGUI(
            dialog_box_size[0],
            dialog_box_size[1],
            dialog_box_bounding_box,
            init_image=Image.open(dialog_box_path),
            position=(0, EINK_HEIGHT - dialog_box_size[1]))
        self.dialog.add_component(
            TextBox(text="new_picture", font_path=font_path, font_size=dialog_font_size))
        self.dialog.add_component(
            TextBox(text="inpaint", font_path=font_path, font_size=dialog_font_size))
        self.dialog.add_component(
            TextBox(text="display", font_path=font_path, font_size=dialog_font_size))

        self.dialog_temp = ScrollGUI(
            dialog_box_size[0],
            dialog_box_size[1],
            dialog_box_bounding_box,
            init_image=Image.open(dialog_box_path),
            position=(0, EINK_HEIGHT - dialog_box_size[1]))
        self.dialog_temp.add_component(
            TextBox(text="temp_display", font_path=font_path, font_size=dialog_font_size))
        
        # cam preview interface
        self.dialog2 = ScrollGUI(
            dialog_box_size[0],
            dialog_box_size[1],
            dialog_box_bounding_box,
            init_image=Image.open(dialog_box_path),
            position=(0, EINK_HEIGHT - dialog_box_size[1]))
        self.dialog2.add_component(
            TextBox(text="take_picture", font_path=font_path, font_size=dialog_font_size))

        # pick segmentations interface, dummy interface
        self.dialog3 = ScrollGUI(
            dialog_box_size[0],
            dialog_box_size[1],
            dialog_box_bounding_box,
            init_image=Image.open(dialog_box_path),
            position=(0, EINK_HEIGHT - dialog_box_size[1]))
        self.annotations = []

        # render
        self.interface = self.dialog
        self.interface.render_scroll()
        self.ui.paste_image(self.interface.get_image(),
                            self.interface.kwargs.get('position'))
        self.render_page(self.ui.get_image(), format='2bit')

    def _show_text(self, text, size=15):
        self.ui.canvas.flush()  # flush
        show_text(self.ui.canvas, text, font_path, size)  # draw at center
        self.render_page(self.ui.get_image())

    def get_init_image(self):
        if os.path.exists(file_cache):  # reload
            self.captured_image = Image.open(file_cache)  # init
            image = paste_image(
                image=self.captured_image,
                canvas_image=Image.new("L", (EINK_WIDTH, EINK_HEIGHT), "white")
            )
        else:  # show logo, init dependencies
            image = paste_image(
                image=Image.open(resource_filename(
                    'distiller', os.path.join('resources', 'logo.png'))),
                canvas_image=Image.new("L", (EINK_WIDTH, EINK_HEIGHT), "white")
            )
        return image

    def _get_mask(self):
        index = self.dialog3.index % len(self.annotations)
        mask = Image.fromarray(np.array(self.annotations[index]["segmentation"]))
        mask = mask.filter(ImageFilter.MaxFilter(size=5))  # grow mask
        return mask


    def show_mask(self): 
        mask = self._get_mask()
        # intermidiate display
        combined_image = merge_inpaint(self.captured_image, Image.new(
            'RGBA', (self.captured_image.width, self.captured_image.height), "black"), mask)
        logging.info("**masking finished**")
        self.ui.paste_image(combined_image)
        self.render_page(self.ui.get_image())

    def handle_input(self, input):
        if self.interface == self.dialog3: # picking segments, just need to track index
            if input == 0 : self.interface.index+=1 
            elif input == 1 : self.interface.index -= 1
            elif input == 2 : 
                # confirm annotations 
                self.confirm_inpaint()
                return 
            # render annotations
            self.show_mask()
            # continue to next stage
            return

        if input == 0 or input == 1:
            # skip if in cam preview mode
            if self.interface == self.dialog_temp or self.interface == self.dialog2: return # disable up/down button for those 2

            self.interface.index_up() if input == 0 else self.interface.index_down()
            self.interface.render_scroll()  # update dialog scroll
            # main ui render
            self.ui.paste_image(self.interface.get_image(
            ), self.interface.kwargs.get('position'))  # update on main ui
            self.render_page(self.ui.get_image())  # render
            return  # early stopping

        if input == 2:
            # load model and run based on input, I have to customize them here
            method = getattr(
                self, self.interface.get_selected_component().get_text(), None)
            if callable(method):
                method()
            else:
                logging.error(f"Command not recognized.")

    def _load_model(self):
        self._show_text("[loading models ...]")
        self.pipe = StableDiffusionInpaintRender(config=inpaint_model_config)
        self.pipe.load_model()
        self.fastsam = FastSAM(sam_model_path)

    def run_sam(self):
        self._show_text("[segmenting ...]")
        everything_results = self.fastsam(
            file_cache, device='cpu', retina_masks=True, imgsz=512, conf=0.15, iou=0.3)
        prompt_process = FastSAMPrompt(
            file_cache, everything_results, device='cpu')
        logging.info(f"sam_prompt {inpaint_model_config['sam_prompt']}")
        
        # you can leverage text to pick but not always stable
        # ann = prompt_process.text_prompt(
        #     text=inpaint_model_config['sam_prompt'])
        # masks = ann[0].masks.data.numpy()
        # mask = Image.fromarray(masks[0, :, :])
        # mask = mask.filter(ImageFilter.MaxFilter(size=5))  # grow mask
        # mask.save('./mask.png')
        # return mask
        # publish annotations to pick
        return prompt_process._format_results(everything_results[0])

    def refresh(self):
        self.interface.render_scroll()
        self.ui.paste_image(self.interface.get_image(),
                            self.interface.kwargs.get('position'))
        self.ui.canvas.register_canvas_image() # cache image 
        self.render_page(self.ui.get_image(), format='2bit')

    def display(self, image=None):
        if image:
            self.render_page(paste_image(image, self.ui.get_image(), border=True), format='2bit')
            return
        
        if os.path.exists(inpaint_path):  # reload inpaint
            self.render_page(paste_image(Image.open(
                inpaint_path), self.ui.get_image(), border=True), format='2bit')
        elif os.path.exists(file_cache):  # reload last pic
            self.render_page(paste_image(Image.open(
                file_cache), self.ui.get_image(), border=True), format='2bit')
        else : 
            pass

    def pick_inpaint_area(self):
        self.interface = self.dialog3 # over take control 
        self._show_text("[pick inpaint area]")

    def confirm_inpaint(self):
        try:
            self.app.buttons.lock()  # lock button
            self.app.screen.start_animation(
                self.ui.get_image(), loading_animation_folder)

            # get mask
            mask = self._get_mask()
            mask.save('./mask.png')
            
            # inpaint step
            combined_image = self.pipe(
                inpaint_model_config['prompt'], self.captured_image, mask)
            self.app.screen.stop_animation()  # Stop the animation after the task completes
            play_audio(sound_bite)  # play sound bite :)
            self.ui.paste_image(combined_image)  # paste image display
            self.interface = self.dialog # update dialog box
            self.refresh()
        except Exception as e:
            logging.error(f"Error inpaint: {e}")
            self.app.screen.stop_animation()
        self.app.buttons.unlock()  # button unlock

    # interface functions
    def inpaint(self):
        if not self.pipe:
            self._load_model()
        try:
            self.app.buttons.lock()  # lock button
            # parse inpaint parts
            self.annotations = self.run_sam()            
            self.pick_inpaint_area() # switch dialog
            play_audio(sound_bite)  # play sound bite :)
            self.show_mask() # display
        except Exception as e:
            logging.error(f"Error inpaint: {e}")
        self.app.buttons.unlock()  # button unlock

    def new_picture(self):
        self._show_text("[open cam ...]")
        self.cam.preview()  # start cam
        self.interface = self.dialog2  # change interface for taking picture

    def temp_display(self):
        # return to main menu 
        self.interface = self.dialog
        self.refresh()

    def take_picture(self):
        try : 
            if self.cam.thread_worker and self.cam.thread_worker.active.is_set():  # cam started
                self.captured_image = self.cam.capture()  # stop cam, save pic
                # save to asset folder so we can revisit in gallery
                self.captured_image.save(f"{saving_path}/{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.png")
                # show captured image in display
                self.ui.canvas.flush()  # flush out texts
                self.display(self.captured_image)
                
                 # cache the image 
                self.ui.paste_image(self.captured_image)
                self.ui.canvas.register_canvas_image()

                time.sleep(0.5)
        except Exception as e:
            logging.error(f"Error take_picture: {e}")
        finally : 
            logging.info("**image taken**")
            self.interface = self.dialog_temp
            # self.refresh() # skip the dialog overlap

class App(Application):
    def __init__(self):
        super().__init__()
        self.current_page = CamPage(self)


if __name__ == '__main__':
    App()
    while True:
        logging.info('camera app ping')
        time.sleep(5)
