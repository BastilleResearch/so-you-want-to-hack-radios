#!/usr/bin/env python

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
# @mknight
#
# Z-Wave decoder, prepared for Shmoocon
#

import argparse
import collections
import signal, sys, os, fcntl
import socket
import matplotlib.pyplot as plt
import time

PREAMBLE = 8*[1, 1, 0, 0]
SFD      = 4*[1, 0] + 4*[0, 1]

MTU        = 170  # MTU == maximum MAC frame length (in octets)
MTU_MARGIN = 40   # extra margin for the preamble (in octets)


def manchester_decode(frame):
  packet = []

  for i in range(len(frame)//2):
    if frame[2*i] == 0 and frame[2*i+1] == 1:
      packet += [0]
    elif frame[2*i] == 1 and frame[2*i+1] == 0:
      packet += [1]
    else:
      packet += [-1]

  return packet


def zwave_crc(frame, length):
  crc = 0xFF

  for b in frame[:length-1]:
    crc = (crc ^ b) & 0xFF

  return crc


# NB This only parses the Z-Wave Node Information Frame
def parse_zwave(packet):
  frame = []
  for i in range(len(packet)//8):
    frame += [int(''.join(map(str, packet[8*i:8*i+8])), 2)]

  fields = None
  if len(packet) > 88:
    fields = {}
    fields['homeid']    = int(''.join(map(str, packet[:32])), 2)
    fields['srcid']     = int(''.join(map(str, packet[32:40])), 2)
    fields['fctl']      = int(''.join(map(str, packet[40:56])), 2)
    fields['length']    = int(''.join(map(str, packet[56:64])), 2)
    fields['destid']    = int(''.join(map(str, packet[64:72])), 2)
    fields['cmdclass']  = int(''.join(map(str, packet[72:80])), 2)
    fields['cmd']       = int(''.join(map(str, packet[80:88])), 2)
    fields['payload']   = []

    payload = packet[88:]
    for i in range(len(payload)//8):
      fields['payload'] += [int(''.join(map(str, payload[8*i:8*i+8])), 2)]

    fields['crc']    = zwave_crc(frame, fields['length'])
    fields['crc_ok'] = True if fields['crc'] == frame[-1] else False

  return fields


def print_packet(meta):
  print "Z-Wave Decoder: Received Packet:"
  print "                Length           ", meta['length']
  print "                Home/Network ID  ", hex(meta['homeid'])
  print "                Source ID        ", hex(meta['srcid'])
  print "                Destination ID   ", hex(meta['destid'])
  print "                Frame Control    ", hex((meta['fctl'] >> 8) & 0xFF)
  print "                Sequence Number  ", meta['fctl'] & 0xFF
  print "                Command Class    ", meta['cmdclass']
  print "                Subcommand       ", meta['cmd']
  print "                Payload          ", meta['payload']
  print "                CRC OK?          ", meta['crc_ok']


def plot_binary(y):
  fig = plt.figure()
  ax = fig.add_subplot(111)
  x = range(len(y))
  ax.plot(x, y)
  ax.set_ylim([-1, 2])
  plt.show()

  return 0


def interrupt_handler(signal, frame):
  print "\nZ-Wave Decoder: exiting..."
  sys.exit(0)


def main():
  signal.signal(signal.SIGINT, interrupt_handler)

  parser = argparse.ArgumentParser(description="Z-Wave Decoder")
  parser.add_argument('--filename', type=str, help='input file')
  parser.add_argument('--port', type=int, help='port')
  parser.add_argument('--plot', action='store_true', help='plot received bits')

  args = parser.parse_args()

  buf = collections.deque()

  if args.filename is not None:
    mode = "file"

    ifile = open(args.filename, 'r')
    data = ifile.readline()

    for d in data:
      buf.append(ord(d))

    if args.plot:
      plot_binary(list(data))

  elif args.port is not None:
    mode = "udp"

    s_symbols = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s_symbols.bind(("127.0.0.1", args.port))
    fcntl.fcntl(s_symbols, fcntl.F_SETFL, os.O_NONBLOCK)

  else:
    print "Z-Wave Decoder: illegal combination of arguments. exiting..."
    sys.exit(0)

  last_update = time.time()
  update_interval = 3.0

  state = "PREAMBLE"

  while True:  # Packet parsing state machine
    if mode == "udp":
      udp_in = None
      try:
        udp_in = s_symbols.recv(1500)
      except:
        pass

      if udp_in is not None:
        for s in udp_in:
          buf.append(ord(s))

    if state == "PREAMBLE":
      if len(buf) >= 8*(MTU + MTU_MARGIN):           # Deref check
        if list(buf)[0:len(PREAMBLE)] == PREAMBLE:   # look for preamble
          #print "Z-Wave Decoder: Preamble found"

          sfd_count = 0
          state = "SFD"

    elif state == "SFD":
      if sfd_count > 1000:	# MAGIC
        #print "Z-Wave Decoder: Bailing from SFD search"
        state = "PREAMBLE"

      if list(buf)[0:len(SFD)] == SFD:
        #print "Z-Wave Decoder: SFD found"

        frame = manchester_decode(list(buf)[0:8*(MTU + MTU_MARGIN)])
        packet = frame[:frame.index(-1)]
        meta = parse_zwave(packet[8:])

        if meta is not None:
          print_packet(meta)
        else:
          print "Z-Wave Decoder: Decoding error"

        for i in range(len(frame)):
          buf.popleft()

        state = "PREAMBLE"

    if len(buf) >= 8*(MTU + MTU_MARGIN):
      buf.popleft()

  return 0


if __name__ == "__main__":
  main()
