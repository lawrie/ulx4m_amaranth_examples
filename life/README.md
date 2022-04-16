# Conway's Game of Life on Ulx3s ECP5 FPGA board

## Introduction

This is an implementation of the [Game of Life](https://en.wikipedia.org/wiki/Conway%27s_Game_of_Life) on a [Ulx3s](https://radiona.org/ulx3s/) FPGA board.

It in written in [Amaranth](https://github.com/amaranth-lang/amaranth), which is a python-based Hardware Description Language (HDL).

The output is on a 1024x768 HDMI display. The Universe is limited to this size, with no border and surrounded by dead cells.

Because of the finite size of the universe, things tend to explode when they hit the edge of the screen, which can cause debris that destroys things. 

8-bit depth BRAM is used to store the cells, with an extra BRAM buffer one row wide for holding the row before the one currently being written.

The display updates at a maximum of once per frame, or sixty times a second, but the speed can be increased with btn 1, and decreased with btn 0.

Each pixel is updated as the video beam reaches it, if speed is set to maximum, otherwise they are updated every nth frame. The data is written out 8-pixels at a time, to the BRAM.

An OSD is implemented to allow loading of initial configurations from the ESP32. A selection of configurations are in the mem directory. They are uncompressed binary files of 98304 (1024 x 768) bytes.

You can modify the background and foreground colors by modifying top-level parameters in life.py.

There are python functions in life.py to create various Life patterns such as gliders, guns etc. in the initial configuration, which is written to cells.bin when you build life.py.

There is also a python method for loading plaintext versions of patterns. It would be quite easy to add support for RLE files.

The [Game of Life Wiki](https://conwaylife.com/wiki/Main_Page) is a good source of these patterns.

All Ulx3s boards are supported. To build for an 85F, you do `python3 life.py 85F`.

This implementation has some similarities to the [Mister version](https://github.com/MiSTer-devel/Life_MiSTer) but shares no code with it. That version has a bigger screen (1920 x 1080) with an invisible border around it and the universe wraps round.

It is easy to change the screen resolution but timing will fail and the bitstream will not work for resolutions higher than 1024x768@60Hz. Also the initial configuration binary files only work at 1024x768.

[![Game of Life Ulx3s](https://img.youtube.com/vi/gPiPkYLUqqU/0.jpg)](https://www.youtube.com/watch?v=gPiPkYLUqqU)

Click on image to play video

