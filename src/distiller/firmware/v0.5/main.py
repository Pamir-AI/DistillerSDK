import machine
import utime
from eink_driver_sam import einkDSP_SAM
import _thread
from machine import WDT

#Instruction Set
EncodeTable = {"BTN_UP": 0b1, "BTN_DOWN": 0b10, "BTN_SELECT": 0b100, "SHUT_DOWN": 0b1000}

wdt = WDT(timeout=2000)
# Set up GPIO pins
selectBTN = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_DOWN)
upBTN = machine.Pin(17, machine.Pin.IN, machine.Pin.PULL_DOWN)
downBTN = machine.Pin(18, machine.Pin.IN, machine.Pin.PULL_DOWN)
powerStatus = machine.Pin(21, machine.Pin.OUT)
einkStatus = machine.Pin(9, machine.Pin.OUT)
sam_interrupt = machine.Pin(2, machine.Pin.OUT)

nukeUSB = machine.Pin(19, machine.Pin.OUT, value = 0)

# Setup UART0 on GPIO0 (TX) and GPIO1 (RX)
uart0 = machine.UART(0, baudrate=9600, tx=machine.Pin(0), rx=machine.Pin(1))
powerStatus.low()
einkStatus.low()

eink = einkDSP_SAM()

# Debounce time in milliseconds
debounce_time = 50

print("Starting...")

# Function to debounce button press
def debounce(pin):
    state = pin.value()
    utime.sleep_ms(debounce_time)
    if pin.value() != state:
        return False
    return True

def get_debounced_state(pin):
    return pin.value() and debounce(pin) 

def send_button_state():
    state_byte = 0
    state_byte |= get_debounced_state(selectBTN) * EncodeTable["BTN_SELECT"]
    state_byte |= get_debounced_state(upBTN)  * EncodeTable["BTN_UP"]
    state_byte |= get_debounced_state(downBTN) * EncodeTable["BTN_DOWN"]
    uart0.write(f"{state_byte}\n")

# Interrupt handler for down button
def button_handler(pin):
    if debounce(pin):
        send_button_state()

def loading_terminator(pin):
    global einkRunning
    if einkRunning:
        einkRunning = False
        eink.de_init()

# Set up interrupt handlers
selectBTN.irq(trigger=machine.Pin.IRQ_RISING, handler=button_handler)
upBTN.irq(trigger=machine.Pin.IRQ_RISING, handler=button_handler)
downBTN.irq(trigger=machine.Pin.IRQ_RISING, handler=button_handler)
sam_interrupt.irq(trigger=machine.Pin.IRQ_RISING, handler=loading_terminator)

einkRunning = False

def eink_task():
    global einkRunning  # Declare einkRunning as a global variable
    repeat = 0
    try:
        if eink.init == False:
            eink.re_init()
        eink.epd_init_fast()
        eink.PIC_display(None, './loading1.bin')
        while einkRunning and repeat < 3:
            eink.epd_init_part()
            eink.PIC_display('./loading1.bin', './loading2.bin')
            eink.epd_init_part()
            eink.PIC_display('./loading2.bin', './loading1.bin')
            wdt.feed()
            repeat += 1
        eink.de_init()
        einkRunning = False
        print("Eink Task Returned")
    except Exception as e:
        print(f"Exception {e}")
        eink.de_init()
        einkRunning = False

def delayed_power_off():
    global powerStatus
    global einkStatus
    global nukeUSB
    global einkRunning
    start_time = utime.ticks_ms()
    while utime.ticks_diff(utime.ticks_ms(), start_time) < 4000:
        utime.sleep_ms(10)
    powerStatus.low()
    einkStatus.low()  # inverted logic
    nukeUSB.low()

    try:
        if eink.init == False:
            eink.re_init()
        eink.epd_init_fast()
        eink.PIC_clear()
        eink.de_init()
        einkRunning = False
        print("Eink Task Returned")
    except Exception as e:
        print(f"Exception {e}")
        eink.de_init()
        einkRunning = False

while True:
    wdt.feed()
    if powerStatus.value() == 1 and uart0.any():
        data = str(uart0.readline()).strip()  # Read a line of data from the UART
        uart0.write(f"xSAM_INFO: {int(data)}\n")
        try:
            if int(data) == 15:  # Check if the received value matches 0b1111
                _thread.start_new_thread(delayed_power_off, ())
        except ValueError:
            print("Received non-binary data or malformed data")

    if debounce(selectBTN) and selectBTN.value() == 1 and upBTN.value() == 0 and downBTN.value() == 0:
        start_time = utime.ticks_ms()
        while utime.ticks_diff(utime.ticks_ms(), start_time) < 2000:
            if selectBTN.value() == 0:
                break
            wdt.feed()
            utime.sleep_ms(10)
        if utime.ticks_diff(utime.ticks_ms(), start_time) >= 2000 and powerStatus.value() == 0:
            powerStatus.high()
            einkStatus.high()  # inverted logic
            uart0.write("xPOWER_ON\n")
            nukeUSB.high()
            # Turn on the power on loading screen
            if einkRunning == False:
                try:
                    einkRunning = True
                    _thread.start_new_thread(eink_task, ())
                    print("Non Blocking")
                except Exception as e:
                    print(f"Exception {e}")
                    eink.de_init()
                    einkRunning = False

    
    if debounce(upBTN) and selectBTN.value() == 1:
        start_time = utime.ticks_ms()
        while utime.ticks_diff(utime.ticks_ms(), start_time) < 10000:
            if upBTN.value() == 0 or selectBTN.value() == 0:
                break
            if utime.ticks_diff(utime.ticks_ms(), start_time) >= 2000:
                uart0.write(f"{EncodeTable['SHUT_DOWN']}\n")
            wdt.feed()
            utime.sleep_ms(10)
        if utime.ticks_diff(utime.ticks_ms(), start_time) >= 10000 and powerStatus.value() == 1:
            powerStatus.low()
            einkStatus.low()  # inverted logic
            uart0.write("xFORCE_POWER_OFF\n")
            nukeUSB.low()
            einkRunning = False

    utime.sleep_ms(1)






