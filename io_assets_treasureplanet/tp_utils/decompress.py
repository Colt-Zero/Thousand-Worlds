import os
import sys
import math
from io import BytesIO
from enum import Enum

from fs_helpers import *

class ModularInt(object):
    def __init__(self, bits, signed=True):
        self._value_range = pow(2, bits)
        if(signed):
            self._lower = -pow(2, bits -1)
            self._upper = pow(2, bits -1) -1
        else:
            self._lower = 0
            self._upper = pow(2, bits) -1
    
    @property
    def value(self):
        return self._value
    
    @value.setter
    def value(self,value):
        while value > self._upper:
            value = value - self._value_range
        while value < self._lower:
            value = value + self._value_range
        self._value = value

class Decompressor:
  def __init__(self, original_data):
    decompressed = BytesIO()
    self.decompressed = decompressed
    #stream_size = read_u24(original_data, 0x4)
    stream_size = (read_u8(original_data, 0x6) << 0x10) + (read_u8(original_data, 0x5) << 0x8) + read_u8(original_data, 0x4)
    #print("Stream size: %x" % stream_size)
    check_sum = sread_u32(original_data, 0x8)
    #print("Check-sum: %x" % check_sum)
    
    shift_index = ModularInt(32, False)
    signed_index = ModularInt(32, True)
    while True:
      nested_index = 0
      #shift_index.value = (((read_u8(original_data, original_data.tell()) * 0x100) + read_u8(original_data, original_data.tell())) * 0x100 + read_u8(original_data, original_data.tell())) * 0x100 + read_u8(original_data, original_data.tell())
      shift_index.value = read_u32(original_data, original_data.tell())
      signed_index.value = shift_index.value
      mask = shift_index.value & 3
      while True:
        if signed_index.value < 0:
          #short = ((read_u8(original_data, original_data.tell()) << 0x8) | read_u8(original_data, original_data.tell()))
          short = read_u16(original_data, original_data.tell())
          bytes_to_decompress = ((short >> 0xE - mask & 0x1F)) + 2
          while bytes_to_decompress != -1:
            bytes_to_decompress -= 1
            decompressed_index = decompressed.tell()
            decompressed_byte = read_u8(decompressed, decompressed_index - ((short & (0x3FFF >> mask)) + 1))
            write_u8(decompressed, decompressed_index, decompressed_byte)
        else:
          byte = read_u8(original_data, original_data.tell())
          write_u8(decompressed, decompressed.tell(), byte)
        if stream_size <= decompressed.tell():
          nested_index = 0
          decompressed.seek(0)
          #print("Decompressed size: %x" % data_len(decompressed))
          while stream_size != 0:
            stream_size -= 1
            byte = read_u8(decompressed, stream_size)
            nested_index += byte
          if nested_index != check_sum:
            print("ERROR! %x" % nested_index)
          return
        nested_index += 1
        shift_index.value <<= 1
        signed_index.value = shift_index.value
        if (nested_index >= 0x1E):
          break

if __name__ == '__main__':
  if len(sys.argv) == 2:
    with open(sys.argv[1], "rb") as f:
      #print("x" % sum(f.read()))
      file = Decompressor(BytesIO(f.read()))
      if file != None:
        output_path = os.path.join(os.path.dirname(sys.argv[1]), "out_" + os.path.basename(sys.argv[1]))
        with open(output_path, "wb") as wf:
          file.decompressed.seek(0)
          wf.write(file.decompressed.read())
