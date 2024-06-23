from gpiod.line import Direction, Value, Bias
import gpiod

class RockGPIO:
    def __init__(self):
        self.lines = {}

    def _parse_pin(self, pin: str) -> tuple[int, int]:
        bank, sub_bank, index = int(pin[4]), pin[6], int(pin[7])
        line_number = int((ord(sub_bank) - ord('A')) * 8 + index)
        return bank, line_number

    def setup(self, pin: str, direction: Direction, initial_value: Value = Value.INACTIVE, bias: Bias = Bias.AS_IS) -> None:
        chip_number, line_number = self._parse_pin(pin)
        line_settings = gpiod.LineSettings(direction=direction, output_value=initial_value, bias=bias)
        line_request = gpiod.request_lines(f'/dev/gpiochip{chip_number}', consumer='RockGPIO', config={line_number: line_settings})
        self.lines[pin] = line_request

    def output(self, pin: str, value: Value) -> None:
        line_request = self.lines.get(pin)
        if line_request:
            _, line_number = self._parse_pin(pin)
            line_request.set_value(line_number, value)

    def input(self, pin: str) -> Value:
        line_request = self.lines.get(pin)
        if line_request:
            _, line_number = self._parse_pin(pin)
            return line_request.get_value(line_number)

    def cleanup(self) -> None:
        for pin, line_request in self.lines.items():
            line_request.close()
        self.lines.clear()
