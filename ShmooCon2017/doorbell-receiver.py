#!/usr/bin/env python2

'''
  Copyright (C) 2017 Bastille Networks

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

#
# 2017-01-13
# @marcnewlin
#
# HeathZenith SL-7762 doorbell receiver, as seen at ShmooCon
#

from gnuradio import blocks, filter, gr, uhd
from gnuradio.filter import firdes
import numpy, logging


# Top Block
class top_block(gr.top_block):

  def __init__(self):
    gr.top_block.__init__(self, name="Doorbell Top Block")

    # RF Config
    self.threshold_min = -60
    self.threshold_max = -50
    self.samp_rate = samp_rate = 100e3
    self.gain = gain = 30
    self.freq = freq = 315e6
    self.decimation = 10

    # USRP
    self.usrp = uhd.usrp_source("", uhd.stream_args("fc32"))
    self.usrp.set_samp_rate(samp_rate)
    self.usrp.set_center_freq(freq, 0)
    self.usrp.set_gain(gain, 0)
    self.usrp.set_antenna("TX/RX", 0)

    # Low Pass Filter
    self.lpf = filter.fir_filter_ccf(self.decimation,
      firdes.low_pass(1, samp_rate, 50e3, 10e3, firdes.WIN_HAMMING, 6.76))

    # Complex to Power (dB)
    self._10log10 = blocks.nlog10_ff(10, 1, 0)
    self.complex_to_mag_squared = blocks.complex_to_mag_squared(1)

    # Threshold
    self.threshold = blocks.threshold_ff(self.threshold_min, self.threshold_max, 0)

    # Framer
    self.framer = doorbell_framer()

    # Connect the blocks
    self.connect((self.usrp, 0), (self.lpf, 0))
    self.connect((self.lpf, 0), (self.complex_to_mag_squared, 0))
    self.connect((self.complex_to_mag_squared, 0), (self._10log10, 0))
    self.connect((self._10log10, 0), (self.threshold, 0))
    self.connect((self.threshold, 0), (self.framer, 0))


# Doorbell Framer
class doorbell_framer(gr.sync_block):

  def __init__(self, ):
    gr.sync_block.__init__(self, name="Doorbell Framer", in_sig=[numpy.float32], out_sig=None)
    self.last_state = 0
    self.last_change = 0
    self.bits = []

  def work(self, input_items, output_items):

    # Step through the bits
    data = input_items[0]
    for x in range(len(data)):
      state = data[x]
      if state != self.last_state:

        # Compute the number of elapsed samples
        # since the last state transition
        offset = self.nitems_read(0) + x
        elapsed = offset - self.last_change
        self.last_change = offset
        self.last_state = state
        if elapsed > 50: self.bits = []

        # If we transitioned low, determine
        # if the encoded bit was a 1 or 0
        if state == 0:

          # Get the encoded bit
          if elapsed <= 4: bit = 1
          else: bit = 0
          self.bits.append(bit)

          # If we have 13 bits, it's a frame! hooray!
          if len(self.bits) == 13:

            # Build the button ID
            button_id = 0
            for b in range(8):
              button_id >>= 1
              button_id |= ((self.bits[b+1] & 1) << 7)

            # Build the tone number
            tone = 0
            for b in range(4):
              tone >>= 1
              tone |= ((self.bits[b+9] & 1) << 3)

            # Record the button press
            logging.info("Button %i, Tone %i" % (button_id, tone))

  # Return the consumed byte count
  return len(data)


# Program entry point
if __name__ == '__main__':

  # Setup logging
  logging.basicConfig(level=logging.INFO, format='[%(asctime)s.%(msecs)03d]  %(message)s', datefmt="%Y-%m-%d %H:%M:%S")

  # Start the flowgraph
  tb = top_block()
  tb.start()
  tb.wait()
