import argparse

from amaranth import *
from amaranth.build import *

from ulx4m import *

pmod_led8_0 = [
    Resource("led8_0", 0,
        Subsignal("leds", Pins("2 3 4 5 6 7 8 9", dir="o", conn=("gpio",0))),
        Attrs(IO_TYPE="LVCMOS33", DRIVE="4"))
]

class Gpio(Elaboratable):
    def elaborate(self, platform):
        led   = platform.request("led", 0)
        led8_0 = platform.request("led8_0")
        led8 = Cat([l for l in led8_0.leds])

        timer = Signal(24)

        m = Module()
        m.d.sync += timer.eq(timer + 1)
        m.d.comb += led.o.eq(timer[-1])

        m.d.comb += led8.eq(C(0b10101010, 8))

        return m


if __name__ == "__main__":
    variants = {
        '12F': ULX4M_12F_Platform,
        '45F': ULX4M_45F_Platform,
        '85F': ULX4M_85F_Platform
    }

    # Figure out which FPGA variant we want to target...
    parser = argparse.ArgumentParser()
    parser.add_argument('variant', choices=variants.keys())
    args = parser.parse_args()

    platform = variants[args.variant]()
    platform.add_resources(pmod_led8_0)

    platform.build(Gpio(), do_program=True)
