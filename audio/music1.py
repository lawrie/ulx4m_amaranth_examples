import argparse

from amaranth import *
from amaranth.build import *
from ulx4m import *

mono = [
    Resource("mono", 0,
        Subsignal("l", Pins("27", dir="o", conn=("gpio", 0)))
    )
]

class Music1(Elaboratable):
    def elaborate(self, platform):
        mono  = platform.request("mono")

        m = Module()

        left = mono.l.o
        clkdivider = int(platform.default_clk_frequency / 440 / 2)
        counter = Signal(clkdivider.bit_length())

        with m.If(counter == 0):
           m.d.sync += [
               counter.eq(clkdivider - 1),
               left.eq(~left)
           ]
        with m.Else():
           m.d.sync += counter.eq(counter - 1)
          
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
    parser.add_argument("--tool", default="dfu")
    args = parser.parse_args()

    platform = variants[args.variant]()
    platform.add_resources(mono)
    platform.build(Music1(), do_program=True, program_opts={"tool":args.tool})
