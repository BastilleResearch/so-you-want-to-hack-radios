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
# HeathZenith SL-7762 doorbell transmitter, as seen at ShmooCon
#

from gnuradio import analog
from gnuradio import blocks
from gnuradio import gr
from gnuradio import uhd
from gnuradio.filter import firdes
import sys
import time
import argparse


class top_block(gr.top_block):

  def __init__(self, button_id=124, tone=1):
    gr.top_block.__init__(self, "Top Block")

    # RF Config
    samp_rate = 1e6
    gain = 50
    freq = 315e6

    # USRP
    self.usrp = uhd.usrp_sink("", uhd.stream_args("fc32"))
    self.usrp.set_samp_rate(samp_rate)
    self.usrp.set_center_freq(freq, 0)
    self.usrp.set_gain(gain, 0)
    self.usrp.set_antenna("TX/RX", 0)

    # Signal source
    self.tone = analog.sig_source_c(samp_rate, analog.GR_COS_WAVE, 1000, 1, 0)

    # Generate the bit 1 and bit 0 masks
    b0 = [0]*int(0.00028 * samp_rate) + [1]*int(0.00072 * samp_rate)
    b1 = [0]*int(0.00068 * samp_rate) + [1]*int(0.00032 * samp_rate)

    # Generate the packet mask
    id_bits = "{0:b}".format(button_id).zfill(8)[:8][::-1]
    tone_bits = "{0:b}".format(tone).zfill(4)[:4][::-1]
    packet_bits = '1' + id_bits + tone_bits
    mask = []
    for b in packet_bits:
      if b == '1':
        mask += b1
      else:
        mask += b0

    # Add some 0's to the end of the mask, because
    # the doorbell waits for a transmission to
    # finish before playing the tone
    mask += [0]*15000

    # Vector source w/ packet mask
    self.packet_mask = blocks.vector_source_c(mask, True, 1, [])

    # Multiply (mask * signal)
    self.multiply = blocks.multiply_vcc(1)

    # Connect the blocks
    self.connect((self.tone, 0), (self.multiply, 0))
    self.connect((self.packet_mask, 0), (self.multiply, 1))
    self.connect((self.multiply, 0), (self.usrp, 0))


if __name__ == '__main__':

  parser = argparse.ArgumentParser()
  parser.add_argument('--button', type=int, default=249)
  parser.add_argument('--tone', type=int, default=0)
  args = parser.parse_args()

  tb = top_block(args.button, args.tone)
  tb.start()
  tb.wait()
