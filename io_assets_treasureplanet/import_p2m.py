from io import BytesIO
import os
import sys
import math
from pathlib import Path

current_dir = Path(os.path.dirname(__file__))
#print(str(current_dir))
sys.path.insert(1, os.path.join(current_dir.absolute(), "tp_utils"))

from fs_helpers import *

try:
    from decompress import *
    has_decompress = True
except ImportError:
    has_decompress = False

import bpy
from bpy_extras.io_utils import unpack_list
from mathutils import Vector

from textures import TextureListEntry
from p2m import ModelBounds, ModlMaterialsEntry, ModelEntry

def find_blocks(data, blocks, offset=0):
  magic = try_read_str(data, offset, 4)
  if magic is not None:
    if magic.startswith("P2M"):
      block_size = sread_u32(data, data.tell())
      blocks[magic] = offset + 0x4
      find_blocks(data, blocks, data.tell())
    elif magic == "INFO" or magic == "SETT" or magic == "TEXT" or magic == "MATL" or magic.startswith("MODL"):
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

def load_p2m(data, name):
  root_magic = try_read_str(data, 0, 4)
  blocks = {}
  find_blocks(data, blocks)
  
  from . import import_tp2
  textures = []
  P2MBounds = None
  P2MMaterial = None
  p2m_version = 0
  models = []
  for key in blocks.keys():
    block = blocks[key]
    if key == "INFO":
      p2m_version = sread_u32(data, block + 0x4)
    elif key == "SETT":
      data.seek(block)
      P2MBounds = ModelBounds(data)
    elif key == "TEXT":
      TP2Textures = TextureListEntry(block, data, name)
      for texture in TP2Textures.textures:
        textures.append(import_tp2.load_tp2(texture.read(), texture.name))
    elif key == "MATL":
      data.seek(block)
      P2MMaterial = ModlMaterialsEntry(data)
    elif key == "MODL":
      data.seek(block)
      P2MModel = ModelEntry(data, name)
      if True:
        bpy_materials = {}
        for i in range(max(P2MModel.lod_counts)):
          mesh_vertices, mesh_normals, mesh_faces, material_uvs, vertex_groups, lod_radii = P2MModel.get_model_geometry(i)
          mesh = bpy.data.meshes.new(name="%s_lod%d" % (name, i))
          mesh.from_pydata(mesh_vertices, [], mesh_faces)
          per_mesh_materials = {}
          #mesh.vertices.foreach_set("normal", [n for nv in mesh_normals for n in nv])
          
          uv_layer = mesh.uv_layers.new()
          for mat_index in material_uvs.keys():
            face_offset, offset, face_len, mat_uvs = material_uvs[mat_index]
            for u, mat_uv in enumerate(mat_uvs): uv_layer.data[offset+u].uv = mat_uv
            if P2MMaterial == None: continue
            p2m_material = P2MMaterial.materials[mat_index]
            if p2m_material.properties[0].texture_index < 0xff:
              if not mat_index in bpy_materials:
                image = textures[p2m_material.properties[0].texture_index]
                bpy_material = bpy.data.materials.new(name="%s_mat_%d" % (name, mat_index))
                bpy_material.use_nodes = True
                matnodes = bpy_material.node_tree.nodes
                texture = matnodes.new("ShaderNodeTexImage")
                texture.image = image
                matnodes["Principled BSDF"].inputs[7].default_value = 0.1
                matnodes["Principled BSDF"].inputs[9].default_value = 0.75
                
                #diff = matnodes['Material Output'].inputs[0]
                #bpy_material.node_tree.links.new(diff, texture.outputs[0])
                
                bpy_material.node_tree.links.new(texture.outputs[0], matnodes["Principled BSDF"].inputs[0])
                bpy_material.node_tree.links.new(matnodes["Principled BSDF"].outputs[0], matnodes['Material Output'].inputs[0])
                
                bpy_materials[mat_index] = bpy_material
              else: bpy_material = bpy_materials[mat_index]
              
              bpy_material["type"] = p2m_material.type
              for prop, mat_property in enumerate(p2m_material.properties):
                if mat_property.texture_index < 0xff: bpy_material["prop_%d_texture"%prop] = textures[mat_property.texture_index].name
                bpy_material["prop_%d"%prop] = Vector([mat_property.texture_index, mat_property.type, mat_property.col_sel, mat_property.flags])
              
              if not mat_index in per_mesh_materials:
                bpy_index = len(mesh.materials)
                per_mesh_materials[mat_index] = bpy_index
              else: bpy_index = per_mesh_materials[mat_index]
              
              faces = [f for f in mesh.polygons if f.index >= face_offset and f.index < face_offset + face_len]
              for face in faces: face.material_index = bpy_index
              mesh.materials.append(bpy_material)
          
          mesh.update()
          mesh.validate()
          
          obj = bpy.data.objects.new("%s_lod%d" % (name, i), mesh)
          for v, gindices in enumerate(vertex_groups):
            vgroup = obj.vertex_groups.new(name="sub%d" % v)
            vgroup.add(gindices, 1.0, 'REPLACE')
          
          for r, lod_radius in enumerate(lod_radii):
            obj.data["sub%d_lod_radius"%r] = lod_radius
          
          bpy.context.collection.objects.link(obj)
          #bpy.context.view_layer.objects.active = obj
          obj.data["P2M-Version"] = p2m_version
          obj.rotation_euler = [math.radians(90), 0, 0]
          models.append(obj)
          
  print(blocks)
  return models

def try_decompress_p2m(filepath):
  model = None
  with open(filepath, 'rb') as f:
    filedata = BytesIO(f.read())
    magic = try_read_str(filedata, 0, 4)
    filedata.seek(0)
    if magic is not None:
      if magic.startswith("PK2") and has_decompress:
        d = Decompressor(BytesIO(filedata.read()))
        d.decompressed.seek(0)
        filedata = BytesIO(d.decompressed.read())
      model = load_p2m(filedata, os.path.splitext(os.path.basename(f.name))[0])
  return model

def load(operator, context, filepath=""):
  filedata = None
  model = try_decompress_p2m(filepath)
  if model == None: return {'CANCELLED'}
  return {'FINISHED'}
