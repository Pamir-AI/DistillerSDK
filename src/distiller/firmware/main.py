import machine
import utime
from eink_driver_sam import einkDSP_SAM
import _thread
from machine import WDT

FLASH = True #for production flash, set to true for usb debug

#Instruction Set
EncodeTable = {"BTN_UP": 0b1, "BTN_DOWN": 0b10, "BTN_SELECT": 0b100, "SHUT_DOWN": 0b1000}

wdt = WDT(timeout=2000)
# Set up GPIO pins
selectBTN = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_DOWN)
upBTN = machine.Pin(17, machine.Pin.IN, machine.Pin.PULL_DOWN)
downBTN = machine.Pin(18, machine.Pin.IN, machine.Pin.PULL_DOWN)
einkStatus = machine.Pin(9, machine.Pin.OUT)
einkMux = machine.Pin(22, machine.Pin.OUT)

sam_interrupt = machine.Pin(2, machine.Pin.OUT)

nukeUSB = machine.Pin(19, machine.Pin.OUT, value = 0)
if FLASH:
    nukeUSB.high() # Disable SAM USB
# Setup UART0 on GPIO0 (TX) and GPIO1 (RX)
uart0 = machine.UART(0, baudrate=9600, tx=machine.Pin(0), rx=machine.Pin(1))
einkMux.low()
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
    print(f"state_byte: {state_byte}")
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

# Add lock for shared variable
eink_lock = _thread.allocate_lock()
einkRunning = False

def eink_task():
    global einkRunning
    repeat = 0
    try:
        if eink.init == False:
            eink.re_init()
        eink.epd_init_fast()
        try:
            eink.PIC_display(None, './loading1.bin')
        except OSError:
            print("Loading files not found")
            einkRunning = False
            return
        while True:
            with eink_lock:
                if not einkRunning or repeat >= 3:
                    break
            eink.epd_init_part()
            eink.PIC_display('./loading1.bin', './loading2.bin')
            eink.epd_init_part()
            eink.PIC_display('./loading2.bin', './loading1.bin')
            wdt.feed()
            repeat += 1
        eink.de_init()
        with eink_lock:
            einkRunning = False
        einkMux.low()
        print("Eink Task Returned")
    except Exception as e:
        print(f"Exception {e}")
        eink.de_init()
        with eink_lock:
            einkRunning = False

einkStatus.high() # provide power to eink
einkMux.high()
uart0.write("StartScreen\n")
    
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

while True:
    wdt.feed()
    try:
        raw_data = uart0.readline()
        if raw_data:
            data = str(raw_data).strip()
            try:
                uart0.write(f"xSAM_INFO: {int(data)}\n")
            except ValueError:
                print(f"Invalid integer data received: {data}")
    except Exception as e:
        print(f"Error reading UART: {e}")
       
    if debounce(selectBTN) and selectBTN.value() == 1 and upBTN.value() == 0 and downBTN.value() == 0:
        print("selectBTN pressed")
       

    if debounce(upBTN) and selectBTN.value() == 1:
        start_time = utime.ticks_ms()
        while utime.ticks_diff(utime.ticks_ms(), start_time) < 10000:
            if upBTN.value() == 0 or selectBTN.value() == 0:
                break
            if utime.ticks_diff(utime.ticks_ms(), start_time) >= 2000:
                uart0.write(f"{EncodeTable['SHUT_DOWN']}\n")
            wdt.feed()
            utime.sleep_ms(10)
        if utime.ticks_diff(utime.ticks_ms(), start_time) >= 10000:
            einkStatus.low()  
            einkMux.low() # Let SAM take back control of the eink
            uart0.write("xSAM_USB\n")
            if FLASH:
                nukeUSB.low()
           
            einkRunning = False

    utime.sleep_ms(1)






