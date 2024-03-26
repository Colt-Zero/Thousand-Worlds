from io import BytesIO
import os
import sys
import math
from pathlib import Path

current_dir = Path(os.path.dirname(__file__))
#print(str(current_dir))
sys.path.insert(1, os.path.join(current_dir.absolute(), "tp_utils"))

try:
    from decompress import *
    has_decompress = True
except ImportError:
    has_decompress = False

import bpy
from fs_helpers import *
from textures import TextureListEntry

class SkelMaterialsEntry:
  def __init__(self, data):
    self.data = data
    self.entry_offset = self.data.tell()
    self.block_size = sread_s32(self.data, self.data.tell())
    self.count = sread_s32(self.data, self.data.tell())
    self.materials = []
    for i in range(self.count):
      mat_entry_offset = self.data.tell()
      mat = SkelMaterialEntry(self.data, mat_entry_offset)
      self.materials.append(mat)

class SkelMaterialEntry:
  class SkelMaterialDataEntry:
    def __init__(self, texture_index, unk_b1, unk_b2, unk_b3):
      self.texture_index = texture_index
      self.unk_b1 = unk_b1
      self.unk_b2 = unk_b2
      self.unk_b3 = unk_b3
  
  def __init__(self, data, entry_offset):
    self.data = data
    self.entry_offset = entry_offset
    self.type = sread_u32(self.data, self.data.tell())
    self.property_count = sread_u32(self.data, self.data.tell())
    self.properties = []
    for i in range(self.property_count):
      mat_data = self.SkelMaterialDataEntry(read_u8(self.data, self.data.tell()), read_u8(self.data, self.data.tell()), read_u8(self.data, self.data.tell()), read_u8(self.data, self.data.tell()))
      self.properties.append(mat_data)
  
  def printInfo(self, textures):
    for mat_data in self.properties:
      textureName = "None"
      if mat_data.texture_index != 0xFF: textureName = textures[mat_data.texture_index].name
      print("Property - Texture: " + textureName + " Unk_Bytes: " + hex(mat_data.unk_b1) + " " + hex(mat_data.unk_b2) + " " + hex(mat_data.unk_b3))

class SkelModelEntry:
  def __init__(self, data):
    self.data = data
    self.entry_offset = self.data.tell()
    self.block_size = sread_u32(self.data, self.entry_offset)
    self.lod_flag = sread_u32(self.data, self.data.tell())
    self.mesh_count = sread_u32(self.data, self.data.tell())
    self.meshes = []
    for m in range(self.mesh_count):
      self.meshes.append(SkelModelLodEntry(self.data, "_l"+str(m), self.lod_flag))
    self.data.seek(self.entry_offset + self.block_size + 0x4)

class SkelModelLodEntry:
  def __init__(self, data, name, lod_flag):
    self.name = name
    self.data = data
    if (lod_flag & 1) != 0:
      self.lod_radius = sread_float(self.data, self.data.tell())
    else: self.lod_radius = 0.0
    self.submesh_count = sread_u32(self.data, self.data.tell())
    
    #print("Place %08x" % self.data.tell())
    print("Lod Radius: %f" % self.lod_radius)
    print("Submesh Count: %d" % self.submesh_count)
    self.submeshes = []
    for s in range(self.submesh_count):
      #print("Place %08x" % self.data.tell())
      self.submeshes.append(SkelModelSubmeshEntry(self.data, s))
    #print("Place %08x" % self.data.tell())
    #submesh_count > geom_count > strip_count > substrip_count * 8
    for submesh in self.submeshes:
      val = sread_u32(self.data, self.data.tell())
      for geom in submesh.geometry:
        for sc in geom.strip_counts:
          self.data.seek(self.data.tell() + (sc * 0x4 * 2)) # Likely uvs
    #print("Place %08x" % self.data.tell())

class SkelModelSubmeshEntry:
  class SkelModelGeometry:
    def __init__(self, data, g):
      self.data = data
      self.joint_count = sread_u32(self.data, self.data.tell())
      self.vertex_count = sread_u32(self.data, self.data.tell())
      self.strip_count = sread_u32(self.data, self.data.tell())
      self.strip_counts = []
      print("Geometry %d Vertex Count: %d Joint Count: %d Strip Count: %d" % (g, self.vertex_count, self.joint_count, self.strip_count))
      for j in range(self.joint_count):
        self.data.seek(self.data.tell() + 0x2 * 2) # 2 byte unk index (index * 0x4), 2 byte unk
      
      _v = []
      _n = []
      for v in range(self.vertex_count):
        for p in range(3): _v.append(sread_float(self.data, self.data.tell()))
        self.data.seek(self.data.tell() + 0x4)
        for n in range(3): _n.append(sread_float(self.data, self.data.tell()))
        self.data.seek(self.data.tell() + 0x2 * 2)
      self.vertices = [_v[i:i+3] for i in range(0, len(_v), 3)]
      self.normals = [_n[i:i+3] for i in range(0, len(_n), 3)]
      
      _f = []
      for s in range(self.strip_count):
        sub_strip = sread_u32(self.data, self.data.tell())
        self.strip_counts.append(sub_strip)
        #print("Substrip count: %d" % sub_strip)
        for ss in range(sub_strip):
          _f.append(read_u16(self.data, self.data.tell()) >> 0x5)
          _f.append(read_u16(self.data, self.data.tell()))
          #self.data.seek(self.data.tell() + 0x2 * 2) # 2 byte vertex index (index * 0x20), 2 byte winding indicator
      self.face_data = [_f[i:i+2] for i in range(0, len(_f), 2)]
      self.faces = []
      flip = True
      for f in range(len(self.face_data)):
        flip = self.add_face(self.faces, self.face_data[f][0], self.face_data[f][1], flip)
        flip = self.reset_winding(self.face_data[f][1], flip)
      #print(self.faces)
    
    def add_face(self, faces, fc, face_data, flip):
      if (face_data & 0x8000): return flip
      fa = 0 if fc < 3 else fc - 2
      fb = 0 if fc < 2 else fc - 1
      if not flip: faces.append([fa, fb, fc])
      else: faces.append([fa, fc, fb])
      return not flip
    
    def reset_winding(self, face_data, flip):
      if (face_data & 0x8000): return True
      return flip
  
  def __init__(self, data, index):
    self.data = data
    self.geom_count = sread_u32(self.data, self.data.tell())
    print("Submesh %d Geom Count: %d" % (index, self.geom_count))
    self.geometry = []
    for g in range(self.geom_count):
      self.geometry.append(self.SkelModelGeometry(self.data, g))

def find_blocks(data, blocks, offset=0):
  magic = try_read_str(data, offset, 4)
  if magic is not None:
    if magic.startswith("P2S"):
      block_size = sread_u32(data, data.tell())
      blocks[magic] = offset + 0x4
      find_blocks(data, blocks, data.tell())
    elif magic == "INFO" or magic == "SETT" or magic == "TEXT" or magic == "MATL" or magic == "SKEL" or magic == "CYCL" or magic == "JNTL" or magic == "MODL":
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

def load_p2s(data, name):
  blocks = {}
  find_blocks(data, blocks)
  
  from . import import_tp2
  textures = []
  P2SMaterials = None
  p2s_version = 0
  for key in blocks.keys():
    block = blocks[key]
    if key == "INFO":
      p2s_version = sread_u32(data, block + 0x4)
    elif key == "TEXT":
      TP2Textures = TextureListEntry(block, data, name)
      for texture in TP2Textures.textures:
        textures.append(import_tp2.load_tp2(texture.read(), texture.name))
    elif key == "MATL":
      data.seek(block)
      P2SMaterials = SkelMaterialsEntry(data)
      for i, mat in enumerate(P2SMaterials.materials):
        print("%s Material %d" % (name, i))
        mat.printInfo(textures)
    elif key == "MODL":
      data.seek(block)
      P2SModel = SkelModelEntry(data)
  
  print(blocks)

def load(operator, context, filepath=""):
  filedata = None
      
  with open(filepath, 'rb') as f:
    filedata = BytesIO(f.read())
    magic = try_read_str(filedata, 0, 4)
    filedata.seek(0)
    if magic is not None:
      if magic.startswith("PK2") and has_decompress:
        d = Decompressor(BytesIO(filedata.read()))
        d.decompressed.seek(0)
        filedata = BytesIO(d.decompressed.read())
      model = load_p2s(filedata, os.path.splitext(os.path.basename(f.name))[0])
  if filedata == None: return {'CANCELLED'}
  return {'FINISHED'}
