# main page to display and call apps
from pkg_resources import resource_filename
from distiller.gui import Application, Page
from distiller.gui.components import *
from distiller.utils.commons import get_current_connection, get_ip_address
from distiller.utils.image import show_text
from distiller.constants import EINK_WIDTH, EINK_HEIGHT
import os
import time
import subprocess
import logging
from pathlib import Path
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class HomePageUI(ScrollGUI):
    def __init__(self):
        bounding_box = (5, 40, EINK_WIDTH, EINK_HEIGHT)
        line_thickness = 3
        line_space = 15
        super().__init__(EINK_WIDTH, EINK_HEIGHT, bounding_box, line_space=line_space)
        # main UI
        self.canvas.draw_plus_pattern()

        # statics
        self.handle_static()

        # dynamics
        size = (EINK_WIDTH-10, 60)
        
        # UNCOMMENT IF YOU WANT TO PLAY WITH APIs but check with README first on api keys 
        # self.add_component(TextBox(text="soul",
        #                            size=size, font_size=20, line_thickness=line_thickness, corner_radius=5,
        #                            icon_path=resource_filename('distiller', os.path.join(
        #                                'resources', 'icons', 'ghost.png'))))
        # self.add_component(TextBox(text="game_engine",
        #                            size=size, font_size=20, line_thickness=line_thickness, corner_radius=5,
        #                            icon_path=resource_filename('distiller', os.path.join(
        #                                'resources', 'icons', 'game.png'))))

        self.add_component(TextBox(text="wifi_setting",
                                   size=size, font_size=20, line_thickness=line_thickness, corner_radius=5,
                                   icon_path=resource_filename('distiller', os.path.join(
                                       'resources', 'icons', 'wifi.png'))))
        self.add_component(TextBox(text="tiny_diffusion",
                                   size=size, font_size=20, line_thickness=line_thickness, corner_radius=5,
                                        icon_path=resource_filename('distiller', os.path.join(
                                            'resources', 'icons', 'paint.png'))
                                   ))
        self.add_component(TextBox(text="ebook_kid",
                                   size=size, font_size=20, line_thickness=line_thickness, corner_radius=5,
                                   icon_path=resource_filename('distiller', os.path.join(
                                       'resources', 'icons', 'book.bmp'))))
        # transcription - not much to show as an app, comment out 
        # self.add_component(TextBox(text="transcription",
        #                            size=size, font_size=20, line_thickness=line_thickness, corner_radius=5,
        #                            icon_path=resource_filename('distiller', os.path.join(
        #                                'resources', 'icons', 'mic.png'))))
        self.add_component(TextBox(text="camera_paint",
                                   size=size, font_size=20, line_thickness=line_thickness, corner_radius=5,
                                   icon_path=resource_filename('distiller', os.path.join(
                                       'resources', 'icons', 'camera.png'))))
        self.add_component(TextBox(text="gallery",
                                   size=size, font_size=20, line_thickness=line_thickness, corner_radius=5,
                                   icon_path=resource_filename('distiller', os.path.join(
                                       'resources', 'icons', 'images.png'))))


    def handle_static(self):
        # static components
        Box((0, 0), (EINK_WIDTH, 30), corner_radius=5,
            padding=0, line_thickness=0).draw(self.canvas)
        wifi_name = get_current_connection()

        if not wifi_name:  # no internet connection
            Text("No Internet ",
                 font_size=17).draw(self.canvas, (5, 5), centered=False)
            Icon(icon_path=resource_filename(
                'distiller', os.path.join('resources', 'icons', 'wifi_off.png')), position=(EINK_WIDTH-50, 2), padding=2).draw(self.canvas)
        else:
            ip = get_ip_address()
            if ip:
                Text(ip,
                     font_size=17).draw(self.canvas, (5, 5), centered=False)
                Icon(icon_path=resource_filename(
                    'distiller', os.path.join('resources', 'icons', 'wifi.png')), position=(EINK_WIDTH-50, 2), padding=5).draw(self.canvas)

        # invert the top bar
        self.update_canvas_image(Box((0, 0), (EINK_WIDTH, 30), corner_radius=5,
                                     padding=0, line_thickness=0).invert_region(self.canvas))
        Box((0, 0), (EINK_WIDTH, 5), corner_radius=0, padding=0, line_thickness=0,
            fill='black').draw(self.canvas)  # hack to fill the top corners
        # cache the background since scroll refreshes entire canvas
        self.canvas.register_canvas_image()

    def click(self):
        app_name = self.get_selected_component().get_text()
        # app list
        for app_path in Path('/home/distiller/DistillerSDK/examples/').rglob('*.py'):
            if app_name in str(app_path):
                process = subprocess.Popen(['venv/bin/python', str(app_path)],)
                process.wait()  # Wait for the subprocess to complete
                return


class HomePage(Page):
    def __init__(self, app):
        super().__init__(app)

        # interface components, app boxes
        position = (5, 40)
        line_thickness = 3
        line_space = 15
        self.gui = HomePageUI()
        self.gui.render_scroll()
        # self.gui.canvas.register_canvas_image() # cache
        # init render
        self.render_page(self.gui.get_image())

    # TODO package this to a utility call
    def _show_text(self, text):
        show_text(self.gui.canvas, text)  # draw at center
        self.render_page(self.gui.get_image())

    def handle_input(self, input):
        # up or down
        if input == 0 or input == 1:
            self.gui.index_up() if input == 0 else self.gui.index_down()
            self.gui.render_scroll()  # update dialog scroll
            self.render_page(self.gui.get_image())  # render

        if input == 2:
            box = self.gui.get_selected_component()
            logging.info(f"{box.get_text()} entered!!!")
            self._show_text('Loading App ...')
            self.gui.click()  # enter next page
            logging.info(f"{box.get_text()} exited!!!")

            # if exit from wifi setting, rerender top bar
            if box.get_text() == "wifi_setting":
                self.gui.canvas.flush() # clear old
                self.gui.handle_static() # add new 

            self.app.screen.clear_screen()
            self.gui.canvas.flush()
            self.gui.render_scroll()
            self.render_page(self.gui.get_image())
            

class App(Application):
    def __init__(self):
        super().__init__()
        self.current_page = HomePage(self)


# TODO
# iter per box and chose render actions [rerender box or invert box]

def main():
    app = App()
    while True:
        logging.info("ping ...")
        time.sleep(10)
        # app.get_system_stats()


if __name__ == "__main__":
    main()
