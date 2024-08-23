import machine
import struct

class BatteryManagementSystem:
    def __init__(self, address=0x55):  # default I2C address of the fuel gauge
        self.i2c =  machine.I2C(0, sda=machine.Pin(24), scl=machine.Pin(25))
        self.address = address

    def read_register(self, register, length):
        return self.i2c.readfrom_mem(self.address, register, length)

    def read_word(self, register):
        data = self.read_register(register, 2)
        # Adjust endianess if necessary
        return struct.unpack('>H', data)[0]

    def write_word(self, register, data):
        data = struct.pack('>H', data)
        self.i2c.writeto_mem(self.address, register, data)

    def print_formatted(self, label, value, unit):
        print(f"{label}: {value} {unit}")

    def get_control(self):
        value = self.read_word(0x00)
        self.print_formatted("Control", value, "")

    def get_temperature(self):
        value = self.read_word(0x02) * 0.1
        self.print_formatted("Temperature", value, "°C")

    def get_voltage(self):
        value = self.read_word(0x04)
        self.print_formatted("Voltage", value, "mV")

    def get_flags(self):
        value = self.read_word(0x06)
        self.print_formatted("Flags", value, "")

    def get_remaining_capacity(self):
        value = self.read_word(0x0C)
        self.print_formatted("Remaining Capacity", value, "mAh")

    # Add additional methods here for other registers you need to interface with

# Usage example
# bms = BatteryManagementSystem()
# bms.get_control()
# bms.get_temperature()
# bms.get_voltage()
# bms.get_remaining_capacity()
