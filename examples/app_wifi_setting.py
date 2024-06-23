# main page to display and call apps
import socket
from pkg_resources import resource_filename
from distiller.utils.commons import get_current_connection, get_ip_address
from distiller.utils.image import show_text
from distiller.constants import EINK_WIDTH, EINK_HEIGHT
from distiller.gui.components import *
from distiller.gui import Page, Application
import os
import re
import sys
import time
import subprocess  # Import subprocess module
import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


# list of some static assets here
font_path = resource_filename('distiller', os.path.join(
    'resources', 'fonts', 'NicoBold-Regular.ttf'))
dialog_box_path = resource_filename(
    'distiller', os.path.join('resources', 'dialogBox_240x97.png'))
dialog_box_size = (240, 97)
dialog_box_bounding_box = (15, 15, 225, 80)
dialog_font_size = 20
display_box = [15, 15, EINK_WIDTH-15, EINK_HEIGHT-15]
padding = 10
text_bounding_box = (display_box[0]+padding, display_box[1] +
                     padding, display_box[2]-padding, display_box[3]-padding)


def parse_scan_results(scan_output):
    networks = []
    lines = scan_output.splitlines()
    if not lines:
        return []
    for line in lines[1:]:  # Skip the header line
        ssid = line.strip()
        if ssid and ssid != '--':  # Ignore empty lines and '--' entries
            networks.append(ssid)
    return list(set(networks))


def scan_wifi():
    # TODO this is a bug does not show all wifi unless sudo is used 
    result = subprocess.run(['sudo', '-u', 'distiller', 'nmcli', '-f',
                            'SSID', 'd', 'wifi', 'list'], capture_output=True, text=True)
    return result.stdout


def get_numbers_set():
    return list('0123456789')


def get_letters_set():
    return list('abcdefghijklmnopqrstuvwxyz')


def get_cap_letters_set():
    return list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')


def get_special_set():
    return list('!@#$%^&*()-_=+[]{}|;:\'",.<>?/')


class WifiPage(Page):
    def __init__(self, app):
        super().__init__(app)

        # vars
        self.current_wifi_ssid = get_current_connection()
        self.wifi = None
        self.wifi_pw = ""

        # full canvas
        self.gui = GUI()
        self.gui.canvas.draw_plus_pattern()

        # display ssh at top
        # Text(get_ip_address(), font_path, 15).draw(self.gui.canvas, (15,5), centered=True)

        # wifi list panel
        size = (EINK_WIDTH-10, 30)
        position = (5, 25)
        line_thickness = 3
        line_space = 5
        wifi_display_end_height = (size[1]+line_space) * 5 + 25
        # UI design
        self.gui_main = ScrollGUI(size[0], (size[1]+line_space)*5,
                                  (0, 0, size[0], (size[1]+line_space)*5),
                                  line_space=line_space, position=position)
        # check for wifi
        scan_output = scan_wifi()
        logging.info(f'wifi list scanned : {scan_output}')
        networks = parse_scan_results(scan_output)
        # render
        for network in networks:
            if not network:
                continue
            self.gui_main.add_component(TextBox(text=network,
                                                font_path=font_path, size=size, font_size=20, line_thickness=line_thickness, corner_radius=5))

        # wifi setting/inputs panel
        size = (140, 30)
        position = ((EINK_WIDTH-size[0])//2, wifi_display_end_height)
        line_thickness = 3
        self.gui_selections = ScrollGUI(
            size[0], (size[1]+line_space)*3, (0, 0, size[0], (size[1]+line_space)*3), line_space=line_space, position=position)
        self.gui_selections.add_component(TextBox(
            text="numbers", font_path=font_path, size=size, font_size=20, line_thickness=line_thickness, corner_radius=5))
        self.gui_selections.add_component(TextBox(
            text="letters", font_path=font_path, size=size, font_size=20, line_thickness=line_thickness, corner_radius=5))
        self.gui_selections.add_component(TextBox(
            text="cap_letters", font_path=font_path, size=size, font_size=20, line_thickness=line_thickness, corner_radius=5))
        self.gui_selections.add_component(TextBox(
            text="special", font_path=font_path, size=size, font_size=20, line_thickness=line_thickness, corner_radius=5))
        self.gui_selections.add_component(TextBox(
            text="backspace", font_path=font_path, size=size, font_size=20, line_thickness=line_thickness, corner_radius=5))
        self.gui_selections.add_component(TextBox(
            text="connect", font_path=font_path, size=size, font_size=20, line_thickness=line_thickness, corner_radius=5))
        self.gui_selections.add_component(TextBox(
            text="back", font_path=font_path, size=size, font_size=20, line_thickness=line_thickness, corner_radius=5))
        self.gui_selections.add_component(TextBox(
            text="exit", font_path=font_path, size=size, font_size=20, line_thickness=line_thickness, corner_radius=5))

        # wifi passward inputs
        size = (25, 30)
        position = ((EINK_WIDTH-140)//2 + 140 + 10, wifi_display_end_height)
        line_thickness = 3
        line_space = 3
        self.gui_input = ScrollGUI(
            size[0], (size[1]+line_space)*3, (0, 0, size[0], (size[1]+line_space)*3), line_space=line_space, position=position)

        # last dialog to display entered passwords
        self.display = ScrollGUI(
            dialog_box_size[0],
            dialog_box_size[1],
            dialog_box_bounding_box,
            init_image=Image.open(dialog_box_path),
            position=(0, EINK_HEIGHT - dialog_box_size[1])
        )
        # init pw render
        self.render_pw()

        # render/update
        self.interface = self.gui_main   # init as the detault interface
        self.interface.render_scroll()
        self.gui_selections.render_scroll(use_index=False, use_footer=False)
        self.render_keys()
        if len(self.gui_input.components) != 0:
            self.gui_input.render_scroll(use_index=False, use_footer=False)

        self.gui.paste_image(self.gui_main.get_image(),
                             self.gui_main.kwargs.get('position'))
        self.gui.paste_image(self.gui_selections.get_image(),
                             self.gui_selections.kwargs.get('position'))
        self.gui.paste_image(self.gui_input.get_image(),
                             self.gui_input.kwargs.get('position'))
        self.gui.paste_image(self.display.get_image(),
                             self.display.kwargs.get('position'))

        self.render_page(self.gui.get_image())

    def handle_input(self, input):
        if input == 0 or input == 1:
            if len(self.interface.components) == 0:
                return
            self.interface.index_up() if input == 0 else self.interface.index_down()
            self.interface.render_scroll(
                use_footer=False)  # update dialog scroll
            self.gui.paste_image(self.interface.get_image(
            ), self.interface.kwargs.get('position'))  # update on main ui
            self.render_page(self.gui.get_image())  # render
            return

        if input == 2:
            # switch cases
            if self.interface == self.gui_main:  # select the wifi
                self.wifi = self.interface.get_selected_component().get_text()
                self.interface = self.gui_selections  # switch to next
            elif self.interface == self.gui_selections:  # select password types or functions
                # call for types or functions
                func_name = self.gui_selections.get_selected_component().get_text()
                self.execute_functions(func_name)
            elif self.interface == self.gui_input:
                char = self.gui_input.get_selected_component().get_text()
                self.wifi_pw += char
                self.render_pw()  # TODO update pw render
                # switch back
                self.interface.render_scroll(
                    use_index=False, use_footer=False)  # unselect
                self.gui.paste_image(self.interface.get_image(
                ), self.interface.kwargs.get('position'))  # update on main ui
                self.interface = self.gui_selections
            else:
                return

            self.interface.render_scroll(use_footer=False)
            self.gui.paste_image(self.interface.get_image(
            ), self.interface.kwargs.get('position'))  # update on main ui
            self.gui.paste_image(self.display.get_image(), self.display.kwargs.get(
                'position'))  # update on main ui
            self.render_page(self.gui.get_image())  # render

    def render_pw(self):
        text = ""
        if self.current_wifi_ssid and not self.wifi_pw:  # init
            text += f"{self.current_wifi_ssid} | "
            text += f"distiller@{get_ip_address()} | "
            self.display.inject_texts(text, font_path, 15)
        else:
            self.display.inject_texts("PW : " + self.wifi_pw, font_path, 15)

        self.display.index_reset()
        self.display.render_scroll(use_footer=False)

    def execute_functions(self, text):
        # update keyboard
        method = globals().get(f"get_{text}_set", None)
        if callable(method):
            self.render_keys()
            self.interface.render_scroll(
                use_index=False, use_footer=False)  # unselect
            self.gui.paste_image(self.interface.get_image(
            ), self.interface.kwargs.get('position'))  # update on main ui
            self.interface = self.gui_input
            return

        # other func
        method = getattr(self, text, None)
        if callable(method):
            method()
        else:
            logging.error(f"Command not recognized.")

    def backspace(self):
        if self.wifi_pw:
            self.wifi_pw = self.wifi_pw[:-1]
        self.render_pw()

    def connect(self):
        cmd = ['sudo', 'nmcli', 'd', 'wifi', 'connect', self.wifi,
               'password', self.wifi_pw, 'ifname', 'wlan0']
        logging.info(f"cmd {cmd} ")
        logging.info(f"connecting to {self.wifi} ... ")
        show_text(self.gui.canvas, "connecting",
                  font_path, 20)  # draw at center
        self.render_page(self.gui.get_image())
        result = subprocess.run(['sudo', 'nmcli', 'd', 'wifi', 'connect', self.wifi,
                                'password', self.wifi_pw, 'ifname', 'wlan0'], capture_output=True, text=True)
        lines = result.stdout.splitlines()
        for line in lines:
            logging.info(line)
        self.exit()

    def exit(self):
        # logging.info("pkill -f " + sys.argv[0])
        os.system("pkill -f " + sys.argv[0])

    def back(self):
        self.interface.index_reset()
        # switch back
        self.interface.render_scroll(use_index=False)
        self.gui.paste_image(self.interface.get_image(
        ), self.interface.kwargs.get('position'))  # update on main ui
        self.interface = self.gui_main

    def render_keys(self):
        size = (25, 30)
        line_thickness = 3
        line_space = 3
        # flush
        self.gui_input.index_reset()
        self.gui_input.components.clear()
        for key in self.get_keys():
            self.gui_input.add_component(TextBox(
                text=key, font_path=font_path, size=size, font_size=20, line_thickness=line_thickness, corner_radius=5))

    def get_keys(self):
        method = globals().get(
            f"get_{self.gui_selections.get_selected_component().get_text()}_set", None)
        if callable(method):
            return method()
        return []


class App(Application):
    def __init__(self):
        super().__init__()
        self.current_page = WifiPage(self)


def main():
    app = App()
    while True:
        logging.info("WIFI setting ping ...")
        time.sleep(10)


if __name__ == "__main__":
    main()
