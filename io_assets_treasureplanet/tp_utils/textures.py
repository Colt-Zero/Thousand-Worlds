from io import BytesIO
import os

from fs_helpers import *

class AnimatedTexturesEntry:
  def __init__(self, data, textures):
    self.data = data
    self.entry_offset = self.data.tell()
    self.block_size = sread_u32(self.data, self.data.tell())
    if self.block_size > 0x4:
      texture_index = sread_u16(self.data, self.data.tell())
      animated_texture_count = 0
      while texture_index != 0xffff:
        frame_count = sread_u16(self.data, self.data.tell())
        print(textures[texture_index].name + " Frames: " + str(frame_count))
        if frame_count > 0:
          while frame_count > 0:
            frame_count -= 1
            frame_texture_a = sread_u16(self.data, self.data.tell())
            frame_texture_b = sread_u16(self.data, self.data.tell())
            #print(textures[frame_texture_a].name)
            #print(textures[frame_texture_b].name)
        texture_index = sread_u16(self.data, self.data.tell())
        animated_texture_count += 1
      print("Level has " + str(animated_texture_count) + " animated textures")
    else:
      print("Level does not have animated textures")
    self.data.seek(self.block_size + 0x4 + self.entry_offset)

class TextureListEntry:
  def __init__(self, entry_offset, data, name):
    self.entry_offset = entry_offset
    self.data = data
    self.data.seek(self.entry_offset)
    self.block_size = sread_u32(self.data, self.data.tell())
    self.texture_count = sread_u32(self.data, self.data.tell())
    self.textures = []
    for i in range(self.texture_count):
      magic = try_read_str(self.data, self.data.tell(), 4)
      if magic.startswith("TP2"):
        tex_name = name + ("_%d" % i)
        texture_start = self.data.tell() - 4
        header_size = sread_u32(self.data, texture_start + 0x8)
        if header_size == 0x44:
          tex_name = read_str_until_null_character(self.data, texture_start + 0x10)
        texture_size = sread_u32(self.data, texture_start + 0xC)
        texture = TextureEntry(tex_name, self.entry_offset, texture_start, self.data, texture_size)
        self.textures.append(texture)
        self.data.seek(texture_start + texture_size)
    self.data.seek(self.entry_offset + 0x4 + self.block_size)

class TextureEntry:
  def __init__(self, name, texture_block, entry_offset, data, data_size):
    self.texture_block = texture_block
    self.entry_offset = entry_offset
    self.data = data
    self.data_size = data_size
    self.name = name
  
  def read(self):
    old_pos = self.data.tell()
    self.data.seek(self.entry_offset)
    bytes = BytesIO(self.data.read(self.data_size))
    self.data.seek(old_pos)
    return bytes
