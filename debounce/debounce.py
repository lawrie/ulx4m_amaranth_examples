import argparse

from amaranth import *
from ulx4m import *

from debouncer import *

class Debounce(Elaboratable):
    def elaborate(self, platform):
        led  = [platform.request("led", i) for i in range(4)]
        btn1 = platform.request("button_fire", 0)
        leds = Cat([led[i].o for i in range(4)])

        m = Module()

        debouncer = Debouncer()
        m.submodules.debouncer = debouncer

        m.d.comb += debouncer.btn.eq(btn1)

        with m.If(debouncer.btn_up):
            m.d.sync += leds.eq(leds + 1)

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
    platform.build(Debounce(), do_program=True)
