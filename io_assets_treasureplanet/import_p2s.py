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

from mathutils import Vector, Matrix, Euler

from p2s import SkelMaterialsEntry, SkelModelEntry, JointListEntry, SkeletonEntry, CyclesEntry

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
  P2SModel = None
  P2SSkeleton = None
  P2SJoints = None
  P2SCycles = None
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
    elif key == "JNTL":
      data.seek(block)
      P2SJoints = JointListEntry(data, name)
    elif key == "SKEL":
      data.seek(block)
      P2SSkeleton = SkeletonEntry(data, name)
      for bone in P2SSkeleton.bones:
        obj = bpy.data.objects.new("%s Bone %d" % (name, bone.bone_index), None)
        bpy.context.collection.objects.link(obj)
        obj.empty_display_type = 'SINGLE_ARROW'
        obj.matrix_world =  Euler((math.radians(90), 0, 0)).to_matrix().to_4x4() @ bone.transform #Matrix.Translation(bone.floats)
    elif key == "CYCL":
      data.seek(block)
      P2SCycles = CyclesEntry(data, name, P2SSkeleton.bone_count)
    elif key == "MODL":
      data.seek(block)
      P2SModel = SkelModelEntry(data)
      for i in range(P2SModel.mesh_count):
        geometry, lod_radii = P2SModel.get_model_geometry(i)
        for s, (mesh_vertices, mesh_normals, mesh_faces) in enumerate(geometry):
          mesh = bpy.data.meshes.new(name="%s_lod%d_%d" % (name, i, s))
          mesh.from_pydata(mesh_vertices, [], mesh_faces)
          mesh.update()
          mesh.validate()
          obj = bpy.data.objects.new("%s_lod%d_%d" % (name, i, s), mesh)
          for r, lod_radius in enumerate(lod_radii):
            obj.data["sub%d_lod_radius"%r] = lod_radius
          
          bpy.context.collection.objects.link(obj)
          #bpy.context.view_layer.objects.active = obj
          obj.data["P2S-Version"] = p2s_version
          obj.rotation_euler = [math.radians(90), 0, 0]
          #models.append(obj)
  
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
