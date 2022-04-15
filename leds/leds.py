import argparse

from amaranth import *
from ulx4m import *

class Leds(Elaboratable):
    def elaborate(self, platform):
        led   = [platform.request("led", i) for i in range(4)]
        timer = Signal(30)

        m = Module()
        m.d.sync += timer.eq(timer + 1)
        m.d.comb += Cat([i.o for i in led]).eq(timer[-5:-1])
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
    platform.build(Leds(), do_program=True)
