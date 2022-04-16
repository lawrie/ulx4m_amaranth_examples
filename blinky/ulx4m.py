import os
import argparse
import subprocess
import shutil

from amaranth.build import *
from amaranth.vendor.lattice_ecp5 import *
from amaranth_boards.resources import *


__all__ = [
    "ULX4M_12F_Platform",
    "ULX4M_45F_Platform", "ULX4M_85F_Platform"
]


class _ULX4MPlatform(LatticeECP5Platform):
    package                = "BG381"
    speed                  = "6"
    default_clk            = "clk25"

    resources = [
        Resource("clk25", 0, Pins("G2", dir="i"), Clock(25e6), Attrs(IO_TYPE="LVCMOS33")),

        # Used to reload FPGA configuration.
        Resource("program", 0, PinsN("M4", dir="o"), Attrs(IO_TYPE="LVCMOS33", PULLMODE="UP")),

        *LEDResources(pins="B2 B1 B3 C1",
            attrs=Attrs(IO_TYPE="LVCMOS33", DRIVE="4")),
        *ButtonResources(pins="H4 C3 C2 E3 E4 E5 H5",
            attrs=Attrs(IO_TYPE="LVCMOS33", PULLMODE="DOWN")
        ),
        *ButtonResources("switch", pins="G3",
            attrs=Attrs(IO_TYPE="LVCMOS33", PULLMODE="DOWN")
        ),

        # Semantic aliases by button label.
        Resource("button_fire",  0, Pins("C3",  dir="i"), Attrs(IO_TYPE="LVCMOS33", PULLMODE="DOWN")),
        Resource("button_fire",  1, Pins("C2",  dir="i"), Attrs(IO_TYPE="LVCMOS33", PULLMODE="DOWN")),

        # FTDI connection.
        UARTResource(0, 
            rx="N4", tx="N3", role="dce",
            attrs=Attrs(IO_TYPE="LVCMOS33")
        ),
        Resource("uart_tx_enable", 0, Pins("T1", dir="o"), Attrs(IO_TYPE="LVCMOS33")),

        *SDCardResources(0,
            clk="H2", cmd="J1", dat0="J3", dat1="H1", dat2="K1", dat3="K2",
            attrs=Attrs(IO_TYPE="LVCMOS33", SLEW="FAST")
        ),

        # SPI Flash clock is accessed via USR_MCLK instance.
        Resource("spi_flash", 0,
            Subsignal("cs",   PinsN("R2", dir="o")),
            Subsignal("copi", Pins("W2", dir="o")),
            Subsignal("cipo", Pins("V2", dir="i")),
            Subsignal("hold", PinsN("W1", dir="o")),
            Subsignal("wp",   PinsN("Y2", dir="o")),
            Attrs(PULLMODE="NONE", DRIVE="4", IO_TYPE="LVCMOS33")
        ),

        SDRAMResource(0,
            clk="G19", cke="G20", cs_n="P18", we_n="N20", cas_n="N18", ras_n="M18", dqm="P20 D19",
            ba="L18 M20", a="L19 L20 M19 H17 F20 F18 E19 F19 E20 C20 N19 D20 E18",
            dq="U20 T20 U19 T19 T18 T17 R20 P19 H20 J19 K18 J18 H18 J16 K19 J17",
            attrs=Attrs(PULLMODE="NONE", DRIVE="4", SLEWRATE="FAST", IO_TYPE="LVCMOS33")
        )
    ]

    connectors = [
        Connector("gpio", 0, {
            "0" : "R16", "1" :  "R17", 
            "2" : "K5" , "3" :  "J5" , 
            "4" : "K4" , "5" :  "H16", 
            "6" : "R1" , "7" :  "P3" , 
            "8" : "P4" , "9" :  "G16", 
            "10": "N17", "11":  "L16", 
            "12": "C4" , "13":  "T1" , 
            "14": "L4" , "15":  "L5" , 
            "16": "B4" , "17":  "M17", 
            "18": "N5" , "19":  "U1" , 
            "20": "E4" , "21":  "D5" , 
            "22": "U18", "23":  "N4" , 
            "24": "N3" , "25":  "P5" , 
            "26": "V1" , "27":  "N16"
        })
    ]

    @property
    def required_tools(self):
        return super().required_tools + [
            "openFPGALoader"
        ]

    def toolchain_prepare(self, fragment, name, **kwargs):
        overrides = dict(ecppack_opts="--compress")
        overrides.update(kwargs)
        return super().toolchain_prepare(fragment, name, **overrides)

    def toolchain_program(self, products, name, tool):
        if tool == "dfu":
            dfu_util = os.environ.get("DFU_UTIL", "dfu-util")
            with products.extract("{}.bit".format(name)) as bitstream_filename:
                subprocess.run([dfu_util, "-a", "0", "-D", bitstream_filename, "-R"])
        elif tool == "openFPGALoader": 
            loader = os.environ.get("OPENFPGALOADER", "openFPGALoader")
            with products.extract("{}.bit".format(name)) as bitstream_filename:
                subprocess.check_call([loader, "-b", "ulx3s", '-m', bitstream_filename])
        elif tool == "fujprog" or tool == "ujprog": 
            with products.extract("{}.bit".format(name)) as bitstream_filename:
                subprocess.check_call([tool, bitstream_filename])
        else:
            print("Unknown tool")


class ULX4M_12F_Platform(_ULX4MPlatform):
    device                 = "LFE5UM-12F"


class ULX4M_45F_Platform(_ULX4MPlatform):
    device                 = "LFE5UM-45F"


class ULX4M_85F_Platform(_ULX4MPlatform):
    device                 = "LFE5UM-85F"


if __name__ == "__main__":
    from .test.blinky import *
    
    variants = {
        '12F': ULX4M_12F_Platform,
        '45F': ULX4M_45F_Platform,
        '85F': ULX4M_85F_Platform
    }
    
    # Figure out which FPGA variant we want to target...
    parser = argparse.ArgumentParser()
    parser.add_argument('variant', choices=variants.keys())
    args = parser.parse_args()

    # ... and run Blinky on it.
    platform = variants[args.variant]
    platform().build(Blinky(), do_program=True)
