
import machine
import utime
#TODO unblock the eink await 

class einkDSP_SAM:
    def __init__(self) -> None:
        self.oldData = 0x00

        # Pin Definition
        self.DC_PIN = machine.Pin(12, machine.Pin.OUT)
        self.RST_PIN = machine.Pin(11, machine.Pin.OUT)
        self.BUSY_PIN = machine.Pin(10, machine.Pin.IN, machine.Pin.PULL_UP)

        self.EPD_WIDTH = 240
        self.EPD_HEIGHT = 416
    
        # Initialize SPI
        
        self.spi = machine.SPI(1,baudrate=25000000,sck=machine.Pin(14, machine.Pin.OUT), mosi=machine.Pin(15, machine.Pin.OUT), miso=machine.Pin(8, machine.Pin.OUT))
        self.cs = machine.Pin(13, mode=machine.Pin.OUT, value=1)
        self.init = True
        self.watchdogCounter = 0
    
    def de_init(self):
        self.spi.deinit()
        self.DC_PIN = machine.Pin(12, machine.Pin.IN, None)
        self.RST_PIN = machine.Pin(11, machine.Pin.IN, None)
        self.BUSY_PIN = machine.Pin(10, machine.Pin.IN, None)
        self.cs = machine.Pin(13, machine.Pin.IN, None)
        machine.Pin(14, machine.Pin.IN, None)
        machine.Pin(15, machine.Pin.IN, None)
        machine.Pin(8, machine.Pin.IN, None)
        self.init = False
            
    
    def re_init(self):
        self.DC_PIN = machine.Pin(12, machine.Pin.OUT)
        self.RST_PIN = machine.Pin(11, machine.Pin.OUT)
        self.BUSY_PIN = machine.Pin(10, machine.Pin.IN, machine.Pin.PULL_UP)

        self.spi = machine.SPI(1,baudrate=25000000,sck=machine.Pin(14, machine.Pin.OUT), mosi=machine.Pin(15, machine.Pin.OUT), miso=machine.Pin(8, machine.Pin.OUT))
        self.cs = machine.Pin(13, mode=machine.Pin.OUT, value=1) 
        self.init = True

   
    def SPI_Delay(self):
        utime.sleep_us(10)  # 10 microseconds

    def SPI_Write(self, value):
        self.cs.low()
        self.spi.write(bytearray([value]))
        self.cs.high()

    def epd_w21_write_cmd(self, command):
        self.SPI_Delay()
        self.DC_PIN.low()
        self.SPI_Write(command)

    def epd_w21_write_data(self, data):
        self.SPI_Delay()
        self.DC_PIN.high()
        self.SPI_Write(data)

    def delay_xms(self, xms):
        utime.sleep_us(xms*1000)

    def epd_w21_init(self):
        self.delay_xms(10)  # At least 10ms delay
        self.RST_PIN.low()
        self.delay_xms(20)
        self.RST_PIN.high()
        self.delay_xms(20)

   
    def EPD_Display(self,image):
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
        # You would need to implement self.lcd_chkstatus here

    def lcd_chkstatus(self):
        while self.BUSY_PIN.value() == 0 and self.watchdogCounter < 100:
            self.delay_xms(10)  # Wait 10ms before checking again
            self.watchdogCounter += 1
        print(f"counter: {self.watchdogCounter}")
        self.watchdogCounter = 0

    def epd_sleep(self):
        self.epd_w21_write_cmd(0x02)  # Power off
        self.lcd_chkstatus()  # Implement this to check the display's busy status
        
        self.epd_w21_write_cmd(0x07)  # Deep sleep
        self.epd_w21_write_data(0xA5)

    def epd_init(self):
        self.epd_w21_init()  # Reset the e-paper display
        
        self.epd_w21_write_cmd(0x04)  # Power on
        self.lcd_chkstatus()  # Implement this to check the display's busy status

        self.epd_w21_write_cmd(0x50)  # VCOM and data interval setting
        self.epd_w21_write_data(0x97)  # Settings for your display

    def epd_init_fast(self):
        self.epd_w21_init()  # Reset the e-paper display
        
        self.epd_w21_write_cmd(0x04)  # Power on
        self.lcd_chkstatus()  # Implement this to check the display's busy status

        self.epd_w21_write_cmd(0xE0)
        self.epd_w21_write_data(0x02)

        self.epd_w21_write_cmd(0xE5)
        self.epd_w21_write_data(0x5A)

    def epd_init_part(self):
        self.epd_w21_init()  # Reset the e-paper display
        
        self.epd_w21_write_cmd(0x04)  # Power on
        self.lcd_chkstatus()  # Implement this to check the display's busy status

        self.epd_w21_write_cmd(0xE0)
        self.epd_w21_write_data(0x02)

        self.epd_w21_write_cmd(0xE5)
        self.epd_w21_write_data(0x6E)

        self.epd_w21_write_cmd(0x50)
        self.epd_w21_write_data(0xD7)

    def power_off(self):
        self.epd_w21_write_cmd(0x02)
        self.lcd_chkstatus()

    def PIC_display(self, old_file_path, file_path):
        # Assuming oldData is properly initialized and accessible
    
        # Transfer old data
        self.epd_w21_write_cmd(0x10)
        self.DC_PIN.on()  # Data mode

        if old_file_path is not None:
            with open(old_file_path, 'rb') as file:
                byte = file.read(1)
                while byte:
                    self.cs.low()
                    self.spi.write(bytes(byte))  # Convert each byte to bytearray for SPI
                    self.cs.high()
                    byte = file.read(1)
                    utime.sleep_us(10)
        else:
            for _ in range(0,(self.EPD_WIDTH * self.EPD_HEIGHT) // 8):
                self.cs.low()
                self.spi.write(bytes(0xFF))  # Convert data to bytes before sending
                self.cs.high()
                utime.sleep_us(1)


        # Transfer new data
        self.epd_w21_write_cmd(0x13)
        self.DC_PIN.on()  # Data mode          
        count = 0
        with open(file_path, 'rb') as file:
            byte = file.read(1)
            while byte:
                self.cs.low()
                self.spi.write(bytes(byte))  # Convert each byte to bytearray for SPI
                self.cs.high()
                byte = file.read(1)
                utime.sleep_us(10)
                count += 1
                # print(str(byte))
        print(count)

        # self.oldData = new_data[:]  # Copying data, ensure this is appropriate for your memory constraints

        # Refresh display
        self.epd_w21_write_cmd(0x12)
        self.delay_xms(1)  # Necessary delay for the display refresh
        self.lcd_chkstatus()  # Check if the display is ready
    
    def PIC_clear(self):
        # Assuming oldData is properly initialized and accessible
    
        # Transfer old data
        self.epd_w21_write_cmd(0x10)
        self.DC_PIN.on()  # Data mode

      
        for _ in range(0,(self.EPD_WIDTH * self.EPD_HEIGHT) // 8):
            self.cs.low()
            self.spi.write(bytes(0x00))  # Convert data to bytes before sending
            self.cs.high()
            utime.sleep_us(1)


        # Transfer new data
        self.epd_w21_write_cmd(0x13)
        self.DC_PIN.on()  # Data mode          
        for _ in range(0,(self.EPD_WIDTH * self.EPD_HEIGHT) // 8):
            self.cs.low()
            self.spi.write(bytes(0x00))  # Convert data to bytes before sending
            self.cs.high()
            utime.sleep_us(1)

        # self.oldData = new_data[:]  # Copying data, ensure this is appropriate for your memory constraints

        # Refresh display
        self.epd_w21_write_cmd(0x12)
        self.delay_xms(1)  # Necessary delay for the display refresh
        self.lcd_chkstatus()  # Check if the display is ready

# einkMux = machine.Pin(22, machine.Pin.OUT)
# einkStatus = machine.Pin(9, machine.Pin.OUT)
# einkMux.high()  # inverted logic
# einkStatus.high() # provide power to eink

# eink = einkDSP_SAM()
# # eink.epd_init()
# eink.epd_init_fast()
# eink.PIC_display(None, './loading1.bin')

# for i in range(1, 3):
#     eink.epd_init_part()
#     eink.PIC_display('./loading1.bin', './loading2.bin')
#     eink.epd_init_part()
#     eink.PIC_display('./loading2.bin', './loading1.bin')

# eink.PIC_display('./loading1.bin', './loading2.bin')
