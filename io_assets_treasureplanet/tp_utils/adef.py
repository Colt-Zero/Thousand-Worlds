import os
import sys
import math
from io import BytesIO, StringIO
from enum import Enum
from pathlib import Path

current_dir = Path(os.path.dirname(__file__))

from fs_helpers import *

def find_blocks(data, blocks, offset=0):
  magic = try_read_str(data, offset, 4)
  if magic is not None:
    if magic == "ADEF":
      block_size = sread_u32(data, data.tell())
      blocks[magic] = offset + 0x4
      find_blocks(data, blocks, data.tell())
    elif magic == "INFO" or magic == "STR " or magic == "ENUM" or magic == "CLAS":
      block_size = sread_u32(data, data.tell())
      blocks[magic] = offset + 0x4
      find_blocks(data, blocks, data.tell() + block_size)
    elif magic.startswith("END"):
      current_pos = data.tell()
      data.seek(0)
      if data_len(data) - current_pos > 0x4:
        data.seek(current_pos)
        find_blocks(data, blocks, data.tell() + 0x4)
      else:
        return

class Adef:
  def __init__(self, data):
    self.name = "Adef"
    self.version = 0
    self.strings = None
    self.enums = None
    self.classes = None
    
    blocks = {}
    find_blocks(data, blocks)
    for key in blocks.keys():
      block = blocks[key]
      if key == "INFO":
        self.version = sread_u32(data, block + 0x4)
      elif key == "STR ":
        data.seek(block)
        self.strings = ActorStringsEntry(data)
      elif key == "ENUM":
        data.seek(block)
        self.enums = ActorEnumsEntry(data, self.strings.table)
      elif key == "CLAS":
        data.seek(block)
        self.classes = ActorClassesEntry(data, self.strings.table)

class ActorClassesEntry:
  def __init__(self, data, string_table):
    self.data = data
    self.entry_offset = self.data.tell()
    self.block_size = sread_s32(self.data, self.data.tell())
    self.count = sread_s32(self.data, self.data.tell())
    self.classes = []
    for i in range(self.count):
      actor_class = ActorClassEntry(self.data)
      #print("Class name: " + string_table[actor_class.string_index])
      #for p in range(actor_class.properties_count1):
      #  print("Type1 Property name: " + string_table[actor_class.properties_type1[p].string_index])
      #for p in range(actor_class.properties_count2):
      #  print("Type2 name: " + string_table[actor_class.properties_type2[p].string_index])
      self.classes.append(actor_class)

class ActorClassEntry:
  def __init__(self, data):
    self.data = data
    self.entry_offset = self.data.tell()
    self.string_index = sread_u16(self.data, self.data.tell())
    self.par_index = sread_u16(self.data, self.data.tell())
    #self.par_index = 0 if self.par_index == 0xffff else self.par_index
    
    self.properties_count1 = sread_s32(self.data, self.data.tell())
    self.properties_type1 = []
    for i in range(self.properties_count1):
      p_str_index = sread_u16(self.data, self.data.tell())
      p_type = sread_u16(self.data, self.data.tell())
      p_class_ref = sread_u32(self.data, self.data.tell())
      p_value = sread_u32(self.data, self.data.tell())#read_bytes(self.data, self.data.tell(), 0x4)
      self.properties_type1.append(ActorClassPropertyEntry(p_str_index, p_type, p_class_ref, p_value))
      
    self.properties_count2 = sread_s32(self.data, self.data.tell())
    self.properties_type2 = []
    for i in range(self.properties_count2):
      p_str_index = sread_u16(self.data, self.data.tell())
      p_type = sread_u16(self.data, self.data.tell())
      p_class_ref = sread_u32(self.data, self.data.tell())
      p_value = sread_u32(self.data, self.data.tell())
      self.properties_type2.append(ActorClassPropertyEntry(p_str_index, p_type, p_class_ref, p_value))

class ActorClassPropertyEntry:
  def __init__(self, string_index, _type, class_ref, _val):
    self.string_index = string_index
    self.type = _type
    self.class_ref = class_ref
    self.value = _val

class ActorEnumsEntry:
  def __init__(self, data, string_table):
    self.data = data
    self.entry_offset = self.data.tell()
    self.block_size = sread_s32(self.data, self.data.tell())
    self.count = sread_s32(self.data, self.data.tell())
    self.enums = []
    for i in range(self.count):
      enum = ActorEnumEntry(self.data)
      #print("Enum name: " + string_table[enum.string_index])
      #for j in range(enum.count):
      #  print("Enum val: " + string_table[enum.val_string_indexes[j]])
      self.enums.append(enum)

class ActorEnumEntry:
  def __init__(self, data):
    self.data = data
    self.entry_offset = self.data.tell()
    self.string_index = sread_u16(self.data, self.data.tell())
    self.count = sread_u16(self.data, self.data.tell())
    self.val_string_indexes = []
    for i in range(self.count):
      self.val_string_indexes.append(sread_u16(self.data, self.data.tell()))

class ActorStringsEntry:
  def __init__(self, data=None):
    self.data = data
    self.entry_offset = 0
    self.block_size = 0
    self.string_sect_size = 0
    self.count = 0
    self.str_indexes = []
    self.table = []
    if self.data == None: return
    
    self.entry_offset = self.data.tell()
    self.block_size = sread_s32(self.data, self.data.tell())
    self.string_sect_size = sread_s32(self.data, self.data.tell())
    string_data = BytesIO(read_bytes(self.data, self.data.tell(), self.string_sect_size))
    self.count = sread_s32(self.data, self.data.tell())
    
    for i in range(self.count):
      str_index = sread_s32(self.data, self.data.tell())
      self.str_indexes.append(str_index)
      actor_string = read_str_until_null_character(string_data, str_index)
      self.table.append(actor_string)
      #print(actor_string)
  
  def save_changes(self, magic_string="STR "):
    string_data = BytesIO()
    index_data = BytesIO()
    string_index = 0
    self.str_indexes.clear()
    for i in range(len(self.table)):
      string = self.table[i]
      string_index = string_data.tell()
      write_str_with_null_byte(string_data, string_index, string)
      write_u32(index_data, i * 0x4, swap32(string_index))
      self.str_indexes.append(string_index)
    index_data.seek(0)
    self.count = len(self.table)
    string_data.seek(0)
    align_data_to_nearest(string_data, 0x4)
    string_data.seek(0)
    self.string_sect_size = data_len(string_data)
    string_data.seek(0)
    
    final_data = BytesIO()
    write_magic_str(final_data, 0x0, magic_string, 4)
    write_u32(final_data, 0x4, 0x0)
    write_u32(final_data, final_data.tell(), swap32(self.string_sect_size))
    write_bytes(final_data, final_data.tell(), string_data.read())
    write_u32(final_data, final_data.tell(), swap32(self.count))
    write_bytes(final_data, final_data.tell(), index_data.read())
    final_data.seek(0)
    self.block_size = data_len(final_data) - 0x8
    write_u32(final_data, 0x4, swap32(self.block_size))
    final_data.seek(0)
    return final_data
