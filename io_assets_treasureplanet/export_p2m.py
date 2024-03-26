from io import BytesIO
import os
import sys
import math
from pathlib import Path

current_dir = Path(os.path.dirname(__file__))
sys.path.insert(1, os.path.join(current_dir.absolute(), "tp_utils"))

import bpy
import bmesh
from mathutils import Vector, Matrix, Quaternion, Euler

from fs_helpers import *
from textures import TextureListEntry
from p2m import ModelBounds, ModlMaterialsEntry, ModelEntry, ModlMaterialEntry
from tristripper import TriangleStripper, PrimitiveType, triangle_from_strip_to_triangle_list
from tp2 import reduce_colors

try:
    from decompress import *
    has_decompress = True
except ImportError:
    has_decompress = False

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

def save(context, filepath="", use_selection=False):
  p2mdata = None
  magic = None
  if os.path.exists(filepath):
    with open(filepath, 'rb') as f:
      p2mdata = BytesIO(f.read())
      magic = try_read_str(p2mdata, 0, 4)
      p2mdata.seek(0)
      if magic is not None:
        if magic.startswith("PK2") and has_decompress:
          d = Decompressor(BytesIO(p2mdata.read()))
          d.decompressed.seek(0)
          p2mdata = BytesIO(d.decompressed.read())
  
  blocks = {}
  if p2mdata != None:
    find_blocks(p2mdata, blocks)
    print(blocks)
  
  TP2Textures = None
  P2MBounds = None
  P2MMaterial = None
  P2MModel = None
  P2MVersion = 5
  P2MName = os.path.splitext(os.path.basename(filepath))[0]
  for key in blocks.keys():
    block = blocks[key]
    if key == "INFO":
      P2MVersion = sread_u32(p2mdata, block + 0x4)
    elif key == "SETT":
      p2mdata.seek(block)
      P2MBounds = ModelBounds(p2mdata)
    elif key == "TEXT":
      TP2Textures = TextureListEntry(block, p2mdata, P2MName)
    elif key == "MATL":
      p2mdata.seek(block)
      P2MMaterial = ModlMaterialsEntry(p2mdata)
    elif key == "MODL":
      p2mdata.seek(block)
      P2MModel = ModelEntry(p2mdata, P2MName)
  
  if bpy.ops.object.mode_set.poll(): bpy.ops.object.mode_set(mode='OBJECT')
  if use_selection: obs = context.selected_objects
  else: obs = context.scene.objects
  for ob in context.selected_objects: ob.select_set(False)
  
  meshObs = [ob for ob in obs if ob.data != None and "types.Mesh" in str(type(ob.data))]
  mesh_sections = {}
  output_materials = []
  for meshOb in meshObs:
    bm = bmesh.new()
    try: me = meshOb.to_mesh()
    except RuntimeError: continue
    bm.from_mesh(me)
    meshOb.to_mesh_clear()
    
    #meshOb.select_set(True)
    #bpy.context.view_layer.objects.active = meshOb
    #bpy.ops.object.mode_set(mode='EDIT')
    #obj = bpy.context.edit_object
    #me = obj.data
    #bm = bmesh.from_edit_mesh(me)
    
    vertex_groups = meshOb.vertex_groups
    materials = meshOb.data.materials
    output_materials.extend(materials)
    uv_lay = bm.loops.layers.uv.active
    deforms = bm.verts.layers.deform.values()
    #for group in vertex_groups:
    
    lod_sections = {}
    for face in bm.faces:
      groupIndex = -1
      for vert in face.verts:
        for g, deform in enumerate(deforms):
          try:
            dv = vert[deform]
            groupIndex = g
          except: pass
      if groupIndex != -1:
        groupName = vertex_groups[groupIndex].name
      elif len(vertex_groups) == 0: groupName = "sub0"
      else: continue
      if not groupName in lod_sections:
        lod_sections[groupName] = {}
      materialName = materials[face.material_index].name
      if not materialName in lod_sections[groupName]:
        lod_sections[groupName][materialName] = []
      lod_sections[groupName][materialName].append(face)#extend[vert.index for vert in face.verts])
    
    for sm in lod_sections.keys():
      submesh = lod_sections[sm]
      for mat in submesh.keys():
        materialGroup = submesh[mat]
        indices = [vert.index for face in materialGroup for vert in face.verts]
        stripper = TriangleStripper(indices)
        stripOutput = stripper.Strip()
        
        primStrips = []
        for primGroup in stripOutput:
          stripIndices = primGroup.indices
          if primGroup.type == PrimitiveType.TRIANGLES:
            stripIndices = [stripIndices[p:p+3] for p in range(0, len(stripIndices), 3)]
          else: stripIndices = [stripIndices]
          primStrips.extend(stripIndices)
        
        strips = []
        indexDict = {vert.index: vert for face in materialGroup for vert in face.verts}
        for primStrip in primStrips:
          strip = []
          for v, vindex in enumerate(primStrip):
            skipDraw = 0 if v > 1 else 1
            flag = skipDraw << 0xf
            vert = indexDict[vindex]
            uvDict = {}
            for loop in vert.link_loops:
              uv = loop[uv_lay].uv[:]
              if not uv in uvDict: uvDict[uv] = []
              uvDict[uv].append(loop)
            
            chosenUV = list(uvDict.keys())[0]
            if len(uvDict) != 1:
              stripTri = triangle_from_strip_to_triangle_list(v, primStrip)
              bestScore = 0
              for uv in uvDict.keys():
                for loop in uvDict[uv]:
                  score = len([fvert.index for fvert in loop.face.verts if fvert.index in stripTri])
                  if score > bestScore:
                    chosenUV = uv
                    bestScore = score
                  if score == 3: break
                if bestScore == 3: break
            
            strip.append((vert.co[:], vert.normal[:], chosenUV, flag))
          strips.append(strip)
        submesh[mat] = strips
    
    for subkey in lod_sections.keys():
      lod_section = lod_sections[subkey]
      if not subkey in mesh_sections: mesh_sections[subkey] = {}
      mesh_sections[subkey][meshOb.name] = (lod_section, meshOb.data.get("%s_lod_radius"%subkey, -1.0))
  
  output_materials = list(set(output_materials))
  material_textures = list(set([n.image for m in output_materials for n in m.node_tree.nodes if n.type == 'TEX_IMAGE']))
  
  bounds_data = P2MBounds.save_changes()
  
  texture_data = BytesIO()
  write_magic_str(texture_data, 0x0, "TEXT", 4)
  write_u32(texture_data, 0x4, 0)
  write_u32(texture_data, 0x8, swap32(len(material_textures)))
  text_block_size = 4
  texture_index = {}
  for t, img in enumerate(material_textures):
    imgw, imgh = img.size
    imgdata = list(img.pixels)
    imgpixels = [[int(imgdata[pxc + ipx] * 255) for pxc in range(img.channels)] for ipx in range(0, len(imgdata), img.channels)]
    tp2_data = reduce_colors(imgpixels, imgw, imgh, img.name)
    texture_index[img.name] = t
    texture_data.write(tp2_data.read())
    text_block_size += data_len(tp2_data)
  write_u32(texture_data, 0x4, swap32(text_block_size))
  texture_data.seek(0)
  
  P2MMaterial = ModlMaterialsEntry()
  material_index = {}
  for m, mat in enumerate(output_materials):
    material_index[mat.name] = m
    output_material = ModlMaterialEntry()
    output_material.type = 0x0
    for n in mat.node_tree.nodes:
      if n.type != 'TEX_IMAGE': continue
      output_material.addProperty(texture_index[n.image.name], 0x1, 0x0, 0x0)
    P2MMaterial.materials.append(output_material)
  material_data = P2MMaterial.save_changes()
  
  model_data = BytesIO()
  write_magic_str(model_data, 0x0, "MODL", 4)
  write_u32(model_data, model_data.tell(), 0)
  write_u32(model_data, model_data.tell(), swap32(len(mesh_sections)))
  for sm in mesh_sections.keys():
    submesh = mesh_sections[sm]
    write_u32(model_data, model_data.tell(), swap32(len(submesh)))
    for lm in submesh.keys():
      lodmesh = submesh[lm]
      write_float(model_data, model_data.tell(), swapfloat(lodmesh[1]))
      write_u32(model_data, model_data.tell(), swap32(len(lodmesh[0])))
      lod_strip_count = 0
      for mm in lodmesh[0].keys():
        matmesh = lodmesh[0][mm]
        lod_strip_count += len(matmesh)
        #write_u32(model_data, model_data.tell(), swap32(int(mm.split("_mat_")[1])))
        write_u32(model_data, model_data.tell(), swap32(material_index[mm]))
        write_u32(model_data, model_data.tell(), swap32(len(matmesh)))
        for strip in matmesh:
          write_u32(model_data, model_data.tell(), swap32(len(strip)))
          for vert, norm, uv, flag in strip:
            for co in vert: write_float(model_data, model_data.tell(), swapfloat(co))
            for co in norm: write_float(model_data, model_data.tell(), swapfloat(co))
            for co in uv: write_float(model_data, model_data.tell(), swapfloat(co))
            write_u32(model_data, model_data.tell(), swap32(flag))
      print("Strip count: %d" % lod_strip_count)
  write_u32(model_data, 0x4, swap32(data_len(model_data)-0x8))
  model_data.seek(0)
  
  output_data = BytesIO()
  write_magic_str(output_data, 0x0, "P2M ", 4)
  write_u32(output_data, 0x4, 0)
  write_magic_str(output_data, output_data.tell(), "INFO", 4)
  write_u32(output_data, output_data.tell(), swap32(4))
  write_u32(output_data, output_data.tell(), swap32(P2MVersion))
  output_data.write(bounds_data.read())
  output_data.write(texture_data.read())
  output_data.write(material_data.read())
  output_data.write(model_data.read())
  write_magic_str(output_data, output_data.tell(), "END ", 4)
  write_u32(output_data, output_data.tell(), 0)
  write_u32(output_data, 0x4, swap32(data_len(output_data)-8))
  output_data.seek(0)
  
  with open(filepath, "wb") as f:
    f.write(output_data.read())
  #print(mesh_sections)
