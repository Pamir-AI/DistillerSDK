
import time
import spidev
import platform
import uuid
from typing import List

_ROCK = 'rockchip' in platform.release()

if not _ROCK:
    import RPi.GPIO as GPIO
else:
    from gpiod.line import Direction, Value, Bias
    from .rock_gpio import RockGPIO


class EinkDSP:
    def __init__(self) -> None:

        self.LUT_ALL: List[int] = [
            0x01,	0x05,	0x20,	0x19,	0x0A,	0x01,	0x01,
            0x05,	0x0A,	0x01,	0x0A,	0x01,	0x01,	0x01,
            0x05,	0x09,	0x02,	0x03,	0x04,	0x01,	0x01,
            0x01,	0x04,	0x04,	0x02,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x01,	0x05,	0x20,	0x19,	0x0A,	0x01,	0x01,
            0x05,	0x4A,	0x01,	0x8A,	0x01,	0x01,	0x01,
            0x05,	0x49,	0x02,	0x83,	0x84,	0x01,	0x01,
            0x01,	0x84,	0x84,	0x82,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x01,	0x05,	0x20,	0x99,	0x8A,	0x01,	0x01,
            0x05,	0x4A,	0x01,	0x8A,	0x01,	0x01,	0x01,
            0x05,	0x49,	0x82,	0x03,	0x04,	0x01,	0x01,
            0x01,	0x04,	0x04,	0x02,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x01,	0x85,	0x20,	0x99,	0x0A,	0x01,	0x01,
            0x05,	0x4A,	0x01,	0x8A,	0x01,	0x01,	0x01,
            0x05,	0x49,	0x02,	0x83,	0x04,	0x01,	0x01,
            0x01,	0x04,	0x04,	0x02,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x01,	0x85,	0xA0,	0x99,	0x0A,	0x01,	0x01,
            0x05,	0x4A,	0x01,	0x8A,	0x01,	0x01,	0x01,
            0x05,	0x49,	0x02,	0x43,	0x04,	0x01,	0x01,
            0x01,	0x04,	0x04,	0x42,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x09,	0x10,	0x3F,	0x3F,	0x00,	0x0B,
        ]
        self.emptyImage: List[int] = [0xFF] * 24960
        self.oldData: List[int] = [0] * 12480

        # Pin Def

        if _ROCK:
            self.RK_DC_PIN = "GPIO1_C6"
            self.RK_RST_PIN = "GPIO1_B1"
            self.RK_BUSY_PIN = "GPIO0_D3"
        else:
            self.DC_PIN = 6
            self.RST_PIN = 13
            self.BUSY_PIN = 9

        self.EPD_WIDTH = 240
        self.EPD_HEIGHT = 416

        if _ROCK:
            self.RockGPIO = RockGPIO()
        else:
            self.GPIO = GPIO

        self.spi = self.EPD_GPIO_Init()
        self.epd_w21_init_4g()

    def cleanup(self) -> None:
        if _ROCK:
            self.RockGPIO.cleanup()

    def EPD_GPIO_Init(self) -> spidev.SpiDev:
        if not _ROCK:
            self.GPIO.setwarnings(False)
            self.GPIO.setmode(GPIO.BCM)
            self.GPIO.setup(self.DC_PIN, GPIO.OUT)
            self.GPIO.setup(self.RST_PIN, GPIO.OUT)
            self.GPIO.setup(self.BUSY_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        else:
            self.RockGPIO.setup(self.RK_DC_PIN, Direction.OUTPUT)
            self.RockGPIO.setup(self.RK_RST_PIN, Direction.OUTPUT)
            self.RockGPIO.setup(
                self.RK_BUSY_PIN, Direction.INPUT, bias=Bias.PULL_UP)

        bus = 0
        device = 0
        spi = spidev.SpiDev()
        spi.open(bus, device)
        spi.max_speed_hz = 30000000
        spi.mode = 0
        return spi

    def SPI_Delay(self) -> None:
        """ Delay for SPI communication, used to tune frequency """
        time.sleep(0.000001)

    def SPI_Write(self, value: int) -> List[int]:
        return self.spi.xfer2([value])

    def epd_w21_write_cmd(self, command: int) -> None:
        self.SPI_Delay()
        if _ROCK:
            self.RockGPIO.output(self.RK_DC_PIN, Value.INACTIVE)  # Data mode
        else:
            self.GPIO.output(self.DC_PIN, GPIO.LOW)
        self.SPI_Write(command)

    def epd_w21_write_data(self, data: int) -> None:
        self.SPI_Delay()
        if _ROCK:
            self.RockGPIO.output(self.RK_DC_PIN, Value.ACTIVE)  # Data mode
        else:
            self.GPIO.output(self.DC_PIN, GPIO.HIGH)
        self.SPI_Write(data)

    def delay_xms(self, xms: int) -> None:
        time.sleep(xms / 1000.0)

    def epd_w21_init(self) -> None:
        self.delay_xms(100)
        if _ROCK:
            self.RockGPIO.output(self.RK_RST_PIN, Value.INACTIVE)
            self.delay_xms(20)
            self.RockGPIO.output(self.RK_RST_PIN, Value.ACTIVE)
            self.delay_xms(20)
        else:
            self.GPIO.output(self.RST_PIN, False)
            self.delay_xms(20)
            self.GPIO.output(self.RST_PIN, True)
            self.delay_xms(20)

    def EPD_Display(self, image: List[int]) -> None:
        width = (self.EPD_WIDTH + 7) // 8
        height = self.EPD_HEIGHT

        self.epd_w21_write_cmd(0x10)
        for j in range(height):
            for i in range(width):
                self.epd_w21_write_data(image[i + j * width])

        self.epd_w21_write_cmd(0x13)
        for _ in range(height * width):
            self.epd_w21_write_data(0x00)

        self.epd_w21_write_cmd(0x12)
        self.delay_xms(1)  # Necessary delay
        self.lcd_chkstatus()

    def lcd_chkstatus(self) -> None:
        if _ROCK:
            # Assuming LOW means busy
            while self.RockGPIO.input(self.RK_BUSY_PIN) == Value.INACTIVE:
                time.sleep(0.01)
        else:
            while self.GPIO.input(self.BUSY_PIN) == GPIO.LOW:  # Assuming LOW means busy
                time.sleep(0.01)  # Wait 10ms before checking again

    def epd_sleep(self) -> None:
        self.epd_w21_write_cmd(0x02)  # Power off
        self.lcd_chkstatus()  # Implement this to check the display's busy status

        self.epd_w21_write_cmd(0x07)  # Deep sleep
        self.epd_w21_write_data(0xA5)

    def epd_init(self) -> None:
        self.epd_w21_init()  # Reset the e-paper display

        self.epd_w21_write_cmd(0x04)  # Power on
        self.lcd_chkstatus()  # Implement this to check the display's busy status

        self.epd_w21_write_cmd(0x50)  # VCOM and data interval setting
        self.epd_w21_write_data(0x97)  # Settings for your display

    def epd_init_fast(self) -> None:
        self.epd_w21_init()  # Reset the e-paper display

        self.epd_w21_write_cmd(0x04)  # Power on
        self.lcd_chkstatus()  # Implement this to check the display's busy status

        self.epd_w21_write_cmd(0xE0)
        self.epd_w21_write_data(0x02)

        self.epd_w21_write_cmd(0xE5)
        self.epd_w21_write_data(0x5A)

    def epd_init_part(self) -> None:
        self.epd_w21_init()  # Reset the e-paper display

        self.epd_w21_write_cmd(0x04)  # Power on
        self.lcd_chkstatus()  # Implement this to check the display's busy status

        self.epd_w21_write_cmd(0xE0)
        self.epd_w21_write_data(0x02)

        self.epd_w21_write_cmd(0xE5)
        self.epd_w21_write_data(0x6E)

        self.epd_w21_write_cmd(0x50)
        self.epd_w21_write_data(0xD7)

    def power_off(self) -> None:
        self.epd_w21_write_cmd(0x02)
        self.lcd_chkstatus()

    def write_full_lut(self) -> None:
        self.epd_w21_write_cmd(0x20)  # Write VCOM register
        for i in range(42):
            self.epd_w21_write_data(self.LUT_ALL[i])

        self.epd_w21_write_cmd(0x21)  # Write LUTWW register
        for i in range(42, 84):
            self.epd_w21_write_data(self.LUT_ALL[i])

        self.epd_w21_write_cmd(0x22)  # Write LUTR register
        for i in range(84, 126):
            self.epd_w21_write_data(self.LUT_ALL[i])

        self.epd_w21_write_cmd(0x23)  # Write LUTW register
        for i in range(126, 168):
            self.epd_w21_write_data(self.LUT_ALL[i])

        self.epd_w21_write_cmd(0x24)  # Write LUTB register
        for i in range(168, 210):
            self.epd_w21_write_data(self.LUT_ALL[i])

    def epd_w21_init_4g(self) -> None:
        self.epd_w21_init()  # Reset the e-paper display

        # Panel Setting
        self.epd_w21_write_cmd(0x00)
        self.epd_w21_write_data(0xFF)  # LUT from MCU
        self.epd_w21_write_data(0x0D)

        # Power Setting
        self.epd_w21_write_cmd(0x01)
        self.epd_w21_write_data(0x03)  # Enable internal VSH, VSL, VGH, VGL
        self.epd_w21_write_data(self.LUT_ALL[211])  # VGH=20V, VGL=-20V
        self.epd_w21_write_data(self.LUT_ALL[212])  # VSH=15V
        self.epd_w21_write_data(self.LUT_ALL[213])  # VSL=-15V
        self.epd_w21_write_data(self.LUT_ALL[214])  # VSHR

        # Booster Soft Start
        self.epd_w21_write_cmd(0x06)
        self.epd_w21_write_data(0xD7)  # D7
        self.epd_w21_write_data(0xD7)  # D7
        self.epd_w21_write_data(0x27)  # 2F

        # PLL Control - Frame Rate
        self.epd_w21_write_cmd(0x30)
        self.epd_w21_write_data(self.LUT_ALL[210])  # PLL

        # CDI Setting
        self.epd_w21_write_cmd(0x50)
        self.epd_w21_write_data(0x57)

        # TCON Setting
        self.epd_w21_write_cmd(0x60)
        self.epd_w21_write_data(0x22)

        # Resolution Setting
        self.epd_w21_write_cmd(0x61)
        self.epd_w21_write_data(0xF0)  # HRES[7:3] - 240
        self.epd_w21_write_data(0x01)  # VRES[15:8] - 320
        self.epd_w21_write_data(0xA0)  # VRES[7:0]

        self.epd_w21_write_cmd(0x65)
        # Additional resolution setting, if needed
        self.epd_w21_write_data(0x00)

        # VCOM_DC Setting
        self.epd_w21_write_cmd(0x82)
        self.epd_w21_write_data(self.LUT_ALL[215])  # -2.0V

        # Power Saving Register
        self.epd_w21_write_cmd(0xE3)
        self.epd_w21_write_data(0x88)  # VCOM_W[3:0], SD_W[3:0]

        # LUT Setting
        self.write_full_lut()

        # Power ON
        self.epd_w21_write_cmd(0x04)
        self.lcd_chkstatus()  # Check if the display is ready

    def pic_display_4g(self, datas: List[int]) -> None:
        # Command to start transmitting old data
        buffer = []
        self.epd_w21_write_cmd(0x10)
        if _ROCK:
            self.RockGPIO.output(self.RK_DC_PIN, Value.ACTIVE)
        else:
            self.GPIO.output(self.DC_PIN, GPIO.HIGH)  # Data mode

        print("Start Old Data Transmission")
        # Iterate over each byte of the image data
        for i in range(12480):  # Assuming 416x240 resolution, adjust accordingly
            temp3 = 0
            for j in range(2):  # For each half-byte in the data
                temp1 = datas[i * 2 + j]
                for k in range(4):  # For each bit in the half-byte
                    temp2 = temp1 & 0xC0
                    if temp2 == 0xC0:
                        temp3 |= 0x01  # White
                    elif temp2 == 0x00:
                        temp3 |= 0x00  # Black
                    elif temp2 == 0x80:
                        temp3 |= 0x01  # Gray1
                    elif temp2 == 0x40:
                        temp3 |= 0x00  # Gray2

                    if j == 0:
                        temp1 <<= 2
                        temp3 <<= 1
                    if j == 1 and k != 3:
                        temp1 <<= 2
                        temp3 <<= 1
            buffer.append(temp3)
        self.spi.xfer3(buffer, self.spi.max_speed_hz, 1, 8)

        buffer = []
        print("Start New Data Transmission")
        # Command to start transmitting new data
        self.epd_w21_write_cmd(0x13)
        if _ROCK:
            self.RockGPIO.output(self.RK_DC_PIN, Value.ACTIVE)
        else:
            self.GPIO.output(self.DC_PIN, GPIO.HIGH)  # Data mode

        for i in range(12480):  # Repeat the process for new data
            temp3 = 0
            for j in range(2):
                temp1 = datas[i * 2 + j]
                for k in range(4):
                    temp2 = temp1 & 0xC0
                    # The logic for determining color values remains the same
                    if temp2 == 0xC0:
                        temp3 |= 0x01  # White
                    elif temp2 == 0x00:
                        temp3 |= 0x00  # Black
                    elif temp2 == 0x80:
                        temp3 |= 0x00  # Gray1
                    elif temp2 == 0x40:
                        temp3 |= 0x01  # Gray2

                    if j == 0:
                        temp1 <<= 2
                        temp3 <<= 1
                    if j == 1 and k != 3:
                        temp1 <<= 2
                        temp3 <<= 1
            buffer.append(temp3)

        self.spi.xfer3(buffer, self.spi.max_speed_hz, 1, 8)

        # Refresh command
        print("Refreshing")
        self.epd_w21_write_cmd(0x12)
        self.delay_xms(1)  # Necessary delay for the display refresh
        self.lcd_chkstatus()  # Check the display status

    def pic_display(self, new_data: List[int]) -> None:
        # Assuming oldData is globally defined or accessible

        # Transfer old data
        self.epd_w21_write_cmd(0x10)
        if _ROCK:
            self.RockGPIO.output(self.RK_DC_PIN, Value.ACTIVE)
        else:
            self.GPIO.output(self.DC_PIN, GPIO.HIGH)  # Data mode
        self.spi.xfer3(self.oldData, self.spi.max_speed_hz, 1, 8)

        # Transfer new data
        self.epd_w21_write_cmd(0x13)
        if _ROCK:
            self.RockGPIO.output(self.RK_DC_PIN, Value.ACTIVE)
        else:
            self.GPIO.output(self.DC_PIN, GPIO.HIGH)  # Data mode
        self.spi.xfer3(new_data, self.spi.max_speed_hz, 1, 8)
        self.oldData = new_data.copy()

        # Refresh display
        self.epd_w21_write_cmd(0x12)
        self.delay_xms(1)  # Necessary delay for the display refresh
        self.lcd_chkstatus()  # Check if the display is ready

    def pic_display_clear(self, poweroff: bool = False) -> None:
        # Transfer old data
        self.epd_w21_write_cmd(0x10)
        if _ROCK:
            self.RockGPIO.output(self.RK_DC_PIN, Value.ACTIVE)
        else:
            self.GPIO.output(self.DC_PIN, GPIO.HIGH)  # Data mode
        self.spi.xfer3(self.oldData, self.spi.max_speed_hz, 1, 8)

        # Transfer new data, setting all to 0xFF (white or clear)
        self.epd_w21_write_cmd(0x13)
        if _ROCK:
            self.RockGPIO.output(self.RK_DC_PIN, Value.ACTIVE)
        else:
            self.GPIO.output(self.DC_PIN, GPIO.HIGH)  # Data mode
        self.spi.xfer3([0] * 12480, self.spi.max_speed_hz, 1, 8)
        self.oldData = [0] * 12480

        # Refresh the display
        self.epd_w21_write_cmd(0x12)
        self.delay_xms(1)  # Ensure a small delay for the display to process
        self.lcd_chkstatus()  # Check the display status

        if poweroff:
            self.power_off()  # Optionally power off the display after clearing
