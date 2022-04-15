from amaranth import *
from amaranth.build import Platform


class Blink(Elaboratable):
    def __init__(self, bits):
        self.o_led = Signal(4)
        # Configuration
        self.bits = bits
    
    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        R_counter = Signal(self.bits)
        m.d.pixel += R_counter.eq(R_counter + 1)
        m.d.comb += self.o_led.eq(R_counter[(self.bits - 4):])

        return m
