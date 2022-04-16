import argparse

from amaranth import *
from amaranth.build import *
from ulx4m import *

mono = [
    Resource("mono", 0,
        Subsignal("l", Pins("27", dir="o", conn=("gpio",0)))
    )
]

class Music2a(Elaboratable):
    def elaborate(self, platform):
        mono  = platform.request("mono", 0)

        m = Module()

        left = mono.l.o
        counter = Signal(15)
        clkdivider = Signal(15)
        tone = Signal(28)
        fastsweep = Signal(7)
        slowsweep = Signal(7)

        m.d.sync += tone.eq(tone + 1)

        with m.If(tone[22]):
            m.d.comb += fastsweep.eq(tone[15:22])
        with m.Else():
            m.d.comb += fastsweep.eq(~tone[15:22])

        with m.If(tone[25]):
            m.d.comb += slowsweep.eq(tone[18:25])
        with m.Else():
            m.d.comb += slowsweep.eq(~tone[18:25])

        with m.If(tone[27]):
            m.d.comb += clkdivider.eq(Cat([Const(0,6),slowsweep,Const(1,2)]))
        with m.Else():
            m.d.comb += clkdivider.eq(Cat([Const(0,6),fastsweep,Const(1,2)]))

        with m.If(counter == 0):
            m.d.sync += [
                left.eq(~left),
                counter.eq(clkdivider)
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
    platform.build(Music2a(), do_program=True, program_opts={"tool":args.tool})
