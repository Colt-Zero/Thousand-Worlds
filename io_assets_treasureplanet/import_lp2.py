from io import BytesIO
import os
import sys
import math
from pathlib import Path


current_dir = Path(os.path.dirname(__file__))
print(str(current_dir))
#sys.path.insert(1, os.path.join(current_dir.absolute(), "tp_utils"))

from tp_utils.fs_helpers import *

try:
    from tp_utils.decompress import *
    has_decompress = True
except ImportError:
    has_decompress = False

import bpy
from mathutils import Vector, Matrix, Quaternion, Euler

from tp_utils.adef import ActorStringsEntry
from tp_utils.textures import TextureListEntry, AnimatedTexturesEntry

from tp_utils.lp2 import LightsEntry, SplineListEntry, AIMapListEntry, ActorInfoListEntry, Models, GeometrySection, LevelMaterialsEntry, load_adef, PVS, Grid, NodeTree

import json

def adef_loader():
  path = os.path.join(current_dir.parent.absolute(), "tp_utils")
  return load_adef(path)

def create_actor(adef, class_name, asset_root = None, transform=Matrix()):
  models = None
  if asset_root != None: models = Models(asset_root)
  actors = ActorInfoListEntry(None, adef.classes, adef.enums, adef.strings, ActorStringsEntry(), ActorStringsEntry(), None, None, models)
  actor = actors.create_new_actor(transform, class_name)
  return (actor, actors)

def find_blocks(data, blocks, offset=0):
  magic = try_read_str(data, offset, 4)
  if magic is not None:
    if magic == "LEVL" or magic == "GMSH" or magic == "ACTR":
      block_size = sread_u32(data, data.tell())
      blocks[magic] = offset + 0x4
      find_blocks(data, blocks, data.tell())
    elif magic == "INFO" or magic.startswith("TEX") or magic == "ANIM" or magic == "MAT " or magic == "SECT" or magic == "NODE" or magic == "PVS " or magic == "AIMP" or magic == "GRID" or magic == "SPLN" or magic == "LITE" or magic == "ASTR" or magic == "PSTR" or magic == "AINF":
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

def load_lp2(data, name, adef, asset_root):
  for ob in bpy.context.selected_objects: ob.select_set(False)
  
  ModelDirectory = None
  world_asset_root = bpy.data.worlds['World']['Asset Root'] if "Asset Root" in bpy.data.worlds['World'] else None
  if world_asset_root != None: ModelDirectory = Models(world_asset_root)
  if ModelDirectory == None or (ModelDirectory != None and not os.path.isdir(ModelDirectory.p2m_path)):
    bpy.data.worlds['World']['Asset Root'] = asset_root
    ModelDirectory = Models(asset_root)
  
  root_magic = try_read_str(data, 0, 4)
  
  blocks = {}
  find_blocks(data, blocks)
  print(blocks)
  
  from . import import_tp2
  from . import import_p2m
  
  lp2_version = 4
  textures = []
  materials = None
  animated_textures = None
  lights = None
  stringlists = {}
  splines = None
  aimaps = None
  geometry = None
  nodetree = None
  collisionMeshes = []
  
  actorMeshes = {}
  
  for key in blocks.keys():
    block = blocks[key]
    if key == "INFO":
      lp2_version = sread_u32(data, block + 0x4)
    elif key == "TEX ":
      TP2Textures = TextureListEntry(block, data, name)
      for texture in TP2Textures.textures:
        textures.append(import_tp2.load_tp2(texture.read(), texture.name))
    elif key == "ANIM":
      data.seek(block)
      animated_textures = AnimatedTexturesEntry(data, textures)
    elif key == "LITE":
      data.seek(block)
      lights = LightsEntry(data, name)
      light_collection = bpy.data.collections.new("Lights")
      bpy.context.collection.children.link(light_collection)
      for light in lights.lights:
        _type, color, atten, area, matrix = light.get_bpylight()
        if _type == "Ambient":
          world = bpy.data.worlds['World']
          bg = world.node_tree.nodes['Background']
          bg.inputs[0].default_value[:3] = color
          bg.inputs[1].default_value = 1.0
          continue
        bpylight = bpy.data.lights.new('%sLight' % _type, _type.upper())
        bpylight.color = color
        bpylight.energy = 2.0
        if _type == "Point":
          bpylight.energy = (atten[0] + atten[1]) * 0.5
          bpylight.energy = bpylight.energy * 12500
          bpylight.shadow_soft_size = 5
        elif _type == "Spot":
          bpylight.energy = (atten[0] + atten[1]) * 0.5
          bpylight.energy = bpylight.energy * 100000
          bpylight.spot_size = (area[0] + area[1]) * 0.5
          bpylight.show_cone = True
        bpyob = bpy.data.objects.new(bpylight.name, bpylight)
        light_collection.objects.link(bpyob)
        bpyob.matrix_world = Euler((math.radians(90), 0, 0)).to_matrix().to_4x4() @ matrix
        bpyob["_lp2_type"] = '%sLight' % _type
    elif key == "SPLN":
      data.seek(block)
      splines = SplineListEntry(data)
      spline_collection = bpy.data.collections.new("Splines")
      bpy.context.collection.children.link(spline_collection)
      for s, (looping, points, transform) in enumerate(splines.get_bpypaths()):
        curveData = bpy.data.curves.new('Spline %d' % s, type='CURVE')
        curveData.dimensions = '3D'
        curveData.resolution_u = 8
        curveData.use_path = True
        curveData.path_duration = 300
        polyline = curveData.splines.new('NURBS')
        polyline.points.add(len(points)-1)
        for i, point in enumerate(points): polyline.points[i].co = tuple(point + [1])
        polyline.use_cyclic_u = looping
        curveOB = bpy.data.objects.new('Spline %d' % s, curveData)
        curveData.bevel_depth = 0.4
        spline_collection.objects.link(curveOB)
        curveOB.matrix_world = Euler((math.radians(90), 0, 0)).to_matrix().to_4x4() @ transform
        curveOB["_lp2_type"] = "Spline"
    elif key == "ASTR" or key == "PSTR":
      data.seek(block)
      stringlists[key] = ActorStringsEntry(data)
    elif key == "GRID":
      data.seek(block)
      grid = Grid(data)
      if not "Potentially Visible Set" in bpy.data.collections:
        pvs_collection = bpy.data.collections.new("Potentially Visible Set")
        bpy.context.collection.children.link(pvs_collection)
      else: pvs_collection = bpy.data.collections["Potentially Visible Set"]
      
      gWidth, gDepth, gScale, gX, gZ, grid_cell_flags = grid.get_bpymesh()
      #gSize = (gWidth + gDepth) // 2
      gSize = max(gWidth, gDepth)
      bpy.ops.mesh.primitive_grid_add(x_subdivisions=gWidth, y_subdivisions=gDepth, size=gSize*gScale, enter_editmode=False, align='WORLD', location=(gX-(gWidth*gScale*0.5)+(float(gWidth) / gSize)*(gScale*2), gZ-(gDepth*gScale*0.5)+(float(gDepth) / gSize)*(gScale*2), 0), scale=(1,1,1))
      obj = bpy.data.objects["Grid"]
      #obj.scale.xy = float(gWidth) / gSize, float(gDepth) / gSize
      #obj.dimensions = (gWidth*gScale, gDepth*gScale, 0)
      bpy.context.collection.objects.unlink(obj)
      pvs_collection.objects.link(obj)
      
      grid_material = bpy.data.materials.new(name="Grid Material")
      grid_material.use_nodes = True
      matnodes = grid_material.node_tree.nodes
      
      attribute_node = matnodes.new("ShaderNodeAttribute")
      attribute_node.attribute_name = "Face Flags"
      face_div = matnodes.new("ShaderNodeMath")
      face_div.operation = 'DIVIDE'
      face_div.inputs[1].default_value = 2
      face_sub = matnodes.new("ShaderNodeMath")
      face_sub.operation = 'SUBTRACT'
      face_sub.inputs[1].default_value = 1
      face_col = matnodes.new("ShaderNodeMixRGB")
      face_col.inputs[1].default_value = (0, 0.124355*0.25, 0.147233*0.25, 1)
      face_mix_col = matnodes.new("ShaderNodeMixRGB")
      face_mix_col.inputs[1].default_value = (0, 0.5, 0.452407, 1)
      face_mix_col.inputs[2].default_value = (0.5, 0.323793, 0, 1)
      
      grid_material.node_tree.links.new(attribute_node.outputs[2], face_div.inputs[0])
      grid_material.node_tree.links.new(face_div.outputs[0], face_col.inputs[0])
      grid_material.node_tree.links.new(attribute_node.outputs[2], face_sub.inputs[0])
      grid_material.node_tree.links.new(face_sub.outputs[0], face_mix_col.inputs[0])
      grid_material.node_tree.links.new(face_mix_col.outputs[0], face_col.inputs[2])
      grid_material.node_tree.links.new(face_col.outputs[0], matnodes["Principled BSDF"].inputs[0])
      grid_material.node_tree.links.new(matnodes["Principled BSDF"].outputs[0], matnodes['Material Output'].inputs[0])
      
      bpy.context.view_layer.objects.active = obj
      bpy.ops.object.mode_set(mode='OBJECT')
      obj.data.materials.append(grid_material)
      obj.data.attributes.new(name="Face Flags", type='FLOAT', domain='FACE')
      #for cf, cell_flag in enumerate(grid_cell_flags): obj.data.attributes["Face Flags"].data[cf].value = cell_flag
      obj.select_set(False)
    elif key == "NODE":
      data.seek(block)
      nodetree = NodeTree(geometry, lp2_version, data)
    elif key == "PVS ":
      data.seek(block)
      pvs = PVS(geometry, lp2_version, data)
      
      for cell in pvs.portal_cells:
        node_id_set = list(set(sorted(cell.node_ids)))
        cell.build_node_list(nodetree.root_node)
        node_id_set2 = list(set(sorted(cell.node_ids)))
        if node_id_set2 != node_id_set:
          print("Node list mismatch!")
          print(node_id_set)
          print(node_id_set2)
      
      if not "Potentially Visible Set" in bpy.data.collections:
        pvs_collection = bpy.data.collections.new("Potentially Visible Set")
        bpy.context.collection.children.link(pvs_collection)
      else: pvs_collection = bpy.data.collections["Potentially Visible Set"]
      
      pvs_material = bpy.data.materials.new(name="PVS Material")
      pvs_material.use_nodes = True
      matnodes = pvs_material.node_tree.nodes
      
      attribute_node = matnodes.new("ShaderNodeAttribute")
      attribute_node.attribute_name = "Face Flags"
      face_div = matnodes.new("ShaderNodeMath")
      face_div.operation = 'DIVIDE'
      face_div.inputs[1].default_value = 2
      face_sub = matnodes.new("ShaderNodeMath")
      face_sub.operation = 'SUBTRACT'
      face_sub.inputs[1].default_value = 1
      face_col = matnodes.new("ShaderNodeMixRGB")
      face_col.inputs[1].default_value = (0, 0.124355, 0.147233, 1)
      face_mix_col = matnodes.new("ShaderNodeMixRGB")
      face_mix_col.inputs[1].default_value = (0, 0.5, 0.452407, 1)
      face_mix_col.inputs[2].default_value = (0.5, 0.323793, 0, 1)
      
      pvs_material.node_tree.links.new(attribute_node.outputs[2], face_div.inputs[0])
      pvs_material.node_tree.links.new(face_div.outputs[0], face_col.inputs[0])
      pvs_material.node_tree.links.new(attribute_node.outputs[2], face_sub.inputs[0])
      pvs_material.node_tree.links.new(face_sub.outputs[0], face_mix_col.inputs[0])
      pvs_material.node_tree.links.new(face_mix_col.outputs[0], face_col.inputs[2])
      pvs_material.node_tree.links.new(face_col.outputs[0], matnodes["Principled BSDF"].inputs[0])
      pvs_material.node_tree.links.new(matnodes["Principled BSDF"].outputs[0], matnodes['Material Output'].inputs[0])
      
      pvs_vertices, pvs_faces, pvs_edges, pvs_cell_flags, transform = pvs.get_bpymesh()
      mesh = bpy.data.meshes.new(name="PVS Mesh")
      mesh.from_pydata(pvs_vertices, pvs_edges, pvs_faces)
      mesh.update()
      mesh.validate()
      
      obj = bpy.data.objects.new("Potentially Visible Set", mesh)
      obj["_lp2_type"] = "PVS"
      pvs_collection.objects.link(obj)
      
      bpy.context.view_layer.objects.active = obj
      bpy.ops.object.mode_set(mode='OBJECT')
      mesh.materials.append(pvs_material)
      mesh.attributes.new(name="Face Flags", type='FLOAT', domain='FACE')
      for cf, cell_flag in enumerate(pvs_cell_flags): mesh.attributes["Face Flags"].data[cf].value = cell_flag[0]
      obj.matrix_world = Euler((math.radians(90), 0, 0)).to_matrix().to_4x4() @ transform
      obj.select_set(False)
    elif key == "AIMP":
      data.seek(block)
      aimaps = AIMapListEntry(data)
      aimap_collection = bpy.data.collections.new("AI Maps")
      bpy.context.collection.children.link(aimap_collection)
      bpy_material = bpy.data.materials.new(name="AIMap Material")
      bpy_material.use_nodes = True
      matnodes = bpy_material.node_tree.nodes
      
      wire_node = matnodes.new("ShaderNodeWireframe")
      wire_node.use_pixel_size = True
      wire_node.inputs[0].default_value = 4
      wire_mix = matnodes.new("ShaderNodeMath")
      wire_mix.operation = 'SMOOTH_MAX'
      wire_mix.inputs[2].default_value = 10
      wire_mul = matnodes.new("ShaderNodeMath")
      wire_mul.operation = 'MULTIPLY'
      
      attribute_node = matnodes.new("ShaderNodeAttribute")
      attribute_node.attribute_name = "Face Blocks"
      face_div = matnodes.new("ShaderNodeMath")
      face_div.operation = 'DIVIDE'
      face_div.inputs[1].default_value = 2
      face_sub = matnodes.new("ShaderNodeMath")
      face_sub.operation = 'SUBTRACT'
      face_sub.inputs[1].default_value = 1
      
      corner_node_1 = matnodes.new("ShaderNodeAttribute")
      corner_node_1.attribute_name = "Corner Blocks 1"
      corner_node_2 = matnodes.new("ShaderNodeAttribute")
      corner_node_2.attribute_name = "Corner Blocks 2"
      
      corn_1_div = matnodes.new("ShaderNodeMath")
      corn_1_div.operation = 'DIVIDE'
      corn_1_div.inputs[1].default_value = 2
      edge_1_sub = matnodes.new("ShaderNodeMath")
      edge_1_sub.operation = 'SUBTRACT'
      edge_1_sub.inputs[1].default_value = 1
      
      corn_2_div = matnodes.new("ShaderNodeMath")
      corn_2_div.operation = 'DIVIDE'
      corn_2_div.inputs[1].default_value = 2
      edge_2_sub = matnodes.new("ShaderNodeMath")
      edge_2_sub.operation = 'SUBTRACT'
      edge_2_sub.inputs[1].default_value = 1
      
      face_col = matnodes.new("ShaderNodeMixRGB")
      face_col.inputs[1].default_value = (0, 0.124355, 0.147233, 1)
      
      face_mix_col = matnodes.new("ShaderNodeMixRGB")
      face_mix_col.inputs[1].default_value = (0, 0.5, 0.452407, 1)
      face_mix_col.inputs[2].default_value = (0.5, 0.323793, 0, 1)
      
      corn_col_1 = matnodes.new("ShaderNodeMixRGB")
      edge_mix_col_1 = matnodes.new("ShaderNodeMixRGB")
      edge_mix_col_1.inputs[1].default_value = (0.0696048, 0.5, 0.000703388, 1)
      edge_mix_col_1.inputs[2].default_value = (0.439657, 0.502886, 0, 1)
      
      corn_col_2 = matnodes.new("ShaderNodeMixRGB")
      edge_mix_col_2 = matnodes.new("ShaderNodeMixRGB")
      edge_mix_col_2.inputs[1].default_value = (0.0696048, 0.5, 0.000703388, 1)
      edge_mix_col_2.inputs[2].default_value = (0.439657, 0.502886, 0, 1)
      
      final_edge_mix = matnodes.new("ShaderNodeMixRGB")
      mix_col = matnodes.new("ShaderNodeMixRGB")
      
      bpy_material.node_tree.links.new(attribute_node.outputs[2], face_div.inputs[0])
      bpy_material.node_tree.links.new(face_div.outputs[0], face_col.inputs[0])
      
      bpy_material.node_tree.links.new(corner_node_1.outputs[2], corn_1_div.inputs[0])
      bpy_material.node_tree.links.new(corn_1_div.outputs[0], corn_col_1.inputs[0])
      bpy_material.node_tree.links.new(corner_node_1.outputs[2], edge_1_sub.inputs[0])
      bpy_material.node_tree.links.new(edge_1_sub.outputs[0], edge_mix_col_1.inputs[0])
      bpy_material.node_tree.links.new(edge_mix_col_1.outputs[0], corn_col_1.inputs[2])
      
      bpy_material.node_tree.links.new(corner_node_2.outputs[2], corn_2_div.inputs[0])
      bpy_material.node_tree.links.new(corn_2_div.outputs[0], corn_col_2.inputs[0])
      bpy_material.node_tree.links.new(corner_node_2.outputs[2], edge_2_sub.inputs[0])
      bpy_material.node_tree.links.new(edge_2_sub.outputs[0], edge_mix_col_2.inputs[0])
      bpy_material.node_tree.links.new(edge_mix_col_2.outputs[0], corn_col_2.inputs[2])
      
      bpy_material.node_tree.links.new(attribute_node.outputs[2], face_sub.inputs[0])
      bpy_material.node_tree.links.new(face_sub.outputs[0], face_mix_col.inputs[0])
      bpy_material.node_tree.links.new(face_mix_col.outputs[0], face_col.inputs[2])
      
      bpy_material.node_tree.links.new(corn_1_div.outputs[0], wire_mix.inputs[0])
      bpy_material.node_tree.links.new(corn_2_div.outputs[0], wire_mix.inputs[1])
      bpy_material.node_tree.links.new(wire_node.outputs[0], wire_mul.inputs[0])
      bpy_material.node_tree.links.new(wire_mix.outputs[0], wire_mul.inputs[1])
      
      bpy_material.node_tree.links.new(wire_mul.outputs[0], mix_col.inputs[0])
      bpy_material.node_tree.links.new(face_col.outputs[0], mix_col.inputs[1])
      bpy_material.node_tree.links.new(face_col.outputs[0], corn_col_1.inputs[1])
      bpy_material.node_tree.links.new(face_col.outputs[0], corn_col_2.inputs[1])
      bpy_material.node_tree.links.new(corn_col_1.outputs[0], final_edge_mix.inputs[1])
      bpy_material.node_tree.links.new(corn_col_2.outputs[0], final_edge_mix.inputs[2])
      bpy_material.node_tree.links.new(final_edge_mix.outputs[0], mix_col.inputs[2])
      
      bpy_material.node_tree.links.new(mix_col.outputs[0], matnodes["Principled BSDF"].inputs[0])
      bpy_material.node_tree.links.new(matnodes["Principled BSDF"].outputs[0], matnodes['Material Output'].inputs[0])
      
      for a, (mesh_vertices, mesh_faces, mesh_edges, edge_blocks, cell_blocks, cell_corners, transform) in enumerate(aimaps.get_bpymaps()):
        mesh = bpy.data.meshes.new(name="AIMap %d" % (a))
        mesh.from_pydata(mesh_vertices, mesh_edges, mesh_faces)
        mesh.update()
        mesh.validate()
        obj = bpy.data.objects.new("AIMap %d" % (a), mesh)
        obj["_lp2_type"] = "AIMap"
        aimap_collection.objects.link(obj)
        
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='OBJECT')
        mesh.materials.append(bpy_material)
        mesh.attributes.new(name="Face Blocks", type='FLOAT', domain='FACE')
        mesh.attributes.new(name="Edge Blocks 1", type='INT', domain='EDGE')
        mesh.attributes.new(name="Edge Blocks 2", type='INT', domain='EDGE')
        mesh.attributes.new(name="Corner Blocks 1", type='FLOAT', domain='CORNER')
        mesh.attributes.new(name="Corner Blocks 2", type='FLOAT', domain='CORNER')
        for cc, cell_corner in enumerate(cell_corners):
          mesh.attributes["Corner Blocks 1"].data[cc].value = cell_corner[0]
          mesh.attributes["Corner Blocks 2"].data[cc].value = cell_corner[-1]
        for cb, cell_block in enumerate(cell_blocks): mesh.attributes["Face Blocks"].data[cb].value = cell_block[0]
        for eb, edge_block in enumerate(edge_blocks):
          mesh.attributes["Edge Blocks 1"].data[eb].value = edge_block[0]
          mesh.attributes["Edge Blocks 2"].data[eb].value = edge_block[-1]
        obj.matrix_world = Euler((math.radians(90), 0, 0)).to_matrix().to_4x4() @ transform
        obj.select_set(False)
    elif key == "AINF":
      data.seek(block)
      actorList = ActorInfoListEntry(data, adef.classes, adef.enums, adef.strings, stringlists["ASTR"], stringlists["PSTR"], aimaps, splines, ModelDirectory)
      
      enum_path = os.path.join(current_dir.parent.absolute(), "tp_utils")
      enum_path = os.path.join(enum_path,'enums.json')
      if os.path.exists(enum_path):
        with open(enum_path, "r") as fp:
          loaded_enums = json.load(fp)
          for enum_key in loaded_enums.keys():
            if enum_key not in actorList.enums:
              actorList.enums[enum_key] = []
            for enum_val in loaded_enums[enum_key]:
              if not enum_val in actorList.enums[enum_key]:
                actorList.enums[enum_key].append(enum_val)
      #with open(enum_path, 'w') as fp:
      #  json.dump(actorList.enums, fp)
      
      if splines == None: spline_namelist = None
      else: spline_namelist = [None] + [bpy.data.objects['Spline %d' % s] for s in range(len(actorList.splines.splines))]
      if aimaps == None: aimap_namelist = None
      else: aimap_namelist = [None] + [bpy.data.objects["AIMap %d" % a] for a in range(len(actorList.ai_maps.maps))]
      if geometry == None: geom_namelist = None
      else: geom_namelist = [None] + [bpy.data.objects["Dynamic Model %d" % g] for g in range(len(geometry.dynamic_model_instances))]
      
      orderedClasses = adef.classes.classes.copy()
      orderedClasses.sort(key=lambda x: x.properties_count1 + x.properties_count2, reverse=True)
      classNames = [adef.strings.table[cls.string_index] for cls in orderedClasses]
      actor_collection = bpy.data.collections.new("Actors")
      bpy.context.collection.children.link(actor_collection)
      for a, actor in enumerate(actorList.actors):
        obj = bpy.data.objects.new("%s %d" % (actor.name, a), None)
        obj.empty_display_type = 'SPHERE'
        obj["_lp2_type"] = "Actor"
        obj["Actor Name"] = actor.name
        actor_collection.objects.link(obj)
        #bpy.context.view_layer.objects.active = obj
        obj.matrix_world = Euler((math.radians(90), 0, 0)).to_matrix().to_4x4() @ actor.transform
        
        model_paths = actor.get_models()
        
        for filepath in model_paths:
          loaded_models = []
          modelname = os.path.splitext(os.path.basename(filepath))[0]
          if not modelname in actorMeshes:
            loaded_models = import_p2m.try_decompress_p2m(filepath)
            for loaded_model in loaded_models:
              bpy.context.collection.objects.unlink(loaded_model)
              actor_collection.objects.link(loaded_model)
            actorMeshes[modelname] = [loaded_model.data for loaded_model in loaded_models]
          if modelname in actorMeshes:
            loaded_meshes = actorMeshes[modelname]
            if len(loaded_models) < len(loaded_meshes):
              for mesh in loaded_meshes:
                aobj = bpy.data.objects.new(mesh.name, mesh)
                actor_collection.objects.link(aobj)
                #bpy.context.view_layer.objects.active = aobj
                loaded_models.append(aobj)
                #aobj["P2M-Version"] = p2m_version
            for aobj in loaded_models:
              if not "_lod0" in aobj.name: aobj.hide_set(not aobj.hide_get())
              aobj.rotation_euler = [0, 0, 0]#[math.radians(90), 0, 0]
              aobj.parent = obj
      
      actor_namelist = [None] + [bpy.data.objects["%s %d" % (actorList.actors[a].name, a)] for a in range(len(actorList.actors))]
      namelists = [spline_namelist, geom_namelist, aimap_namelist, actor_namelist]
      for a, actor in enumerate(actorList.actors):
        obj = bpy.data.objects["%s %d" % (actor.name, a)]
        
        parent_children_connections = {}
        for param in actor.params:
          if param.parent_param == None: continue
          if not param.parent_param in parent_children_connections:
            parent_children_connections[param.parent_param] = []
          parent_children_connections[param.parent_param].append(param)
        
        for p, param in enumerate(actor.params):
          if not (param.overwritten or param.added): continue
          param_id = "%02d:%s" % (actor.params.index(param), param.string)
          
          if param.type == 0:
            if param.parent_param != None and param.parent_param in parent_children_connections:
              children = parent_children_connections[param.parent_param]
              if len(children) > 1:
                float_children = [float_child for float_child in children if float_child.type == 0]
                if len(float_children) == len(children): continue
            obj[param_id] = param.value
            if "SplineVehicle" in actor.name and "FollowOffset" == param.string and "Follow Path" in obj.constraints:
              obj.constraints["Follow Path"].offset = param.value
            ui = obj.id_properties_ui(param_id)
            par_name = param.string.lower()
            if "radius" in par_name or "distance" in par_name:
              ui.update(subtype="DISTANCE")
              if "radius" in par_name:
                obj.empty_display_size = param.value
            elif "time" in par_name or "delay" in par_name:
              if not "secs" in par_name: obj[param_id] = param.value / 60.0
              ui.update(subtype="TIME_ABSOLUTE")
          elif param.type == 2:
            obj[param_id] = param.value
            ui = obj.id_properties_ui(param_id)
            ui.update(min=0, max=1, soft_min=0, soft_max=1)
          elif param.type == 3:
            obj[param_id] = param.value
          elif param.type == 4:
            enum_index = 0
            enum_list = []
            if param.string in actorList.enums:
              for e, enumVal in enumerate(actorList.enums[param.string]):
                enum_list.append(enumVal)
                if param.value == enumVal: enum_index = e
            obj[param_id.replace(':', '-')] = enum_list
            obj[param_id] = enum_list[enum_index]
          elif param.type == 5 or param.type == 8 or param.type == 9 or param.type == 10:
            sel = 0
            #if param.type > 5: sel = param.loaded_value
            #el
            if param.loaded_value != 0xFFFFFFFF: sel = param.loaded_value + 1
            rlist_val = namelists[abs(param.type - 8)]
            if rlist_val != None: rlist_val = rlist_val[sel]
            if rlist_val != None:
              #if param.type == 5 and param.string == "Follow":
              #  bpy.context.view_layer.objects.active = obj
              #  bpy.ops.object.constraint_add(type='COPY_ROTATION')
              #  obj.constraints["Copy Rotation"].target = rlist_val
              #  #obj.constraints["Copy Rotation"].mix_mode = 'AFTER'
              #  #obj.constraints["Copy Rotation"].invert_x = True
              #  #obj.constraints["Copy Rotation"].invert_y = True
              #  #obj.constraints["Copy Rotation"].invert_z = True
              #  #bpy.ops.object.constraint_add(type='DAMPED_TRACK')
              #  #obj.constraints["Damped Track"].target = rlist_val
              #  bpy.ops.object.constraint_add(type='LIMIT_DISTANCE')
              #  obj.constraints["Limit Distance"].target = rlist_val
              #  obj.select_set(False)
              #if param.type == 9:
              #  bpy.context.view_layer.objects.active = rlist_val
              #  #bpy.ops.object.constraint_add(type='COPY_TRANSFORMS')
              #  #rlist_val.constraints["Copy Transforms"].target = obj
              #  bpy.ops.object.constraint_add(type='COPY_ROTATION')
              #  rlist_val.constraints["Copy Rotation"].target = obj
              #  #rlist_val.constraints["Copy Rotation"].use_y = False
              #  #rlist_val.constraints["Copy Rotation"].mix_mode = 'AFTER'
              #  #rlist_val.constraints["Copy Rotation"].invert_x = True
              #  #rlist_val.constraints["Copy Rotation"].invert_y = True
              #  #rlist_val.constraints["Copy Rotation"].invert_z = True
              #  bpy.ops.object.constraint_add(type='LIMIT_DISTANCE')
              #  rlist_val.constraints["Limit Distance"].target = obj
              #  rlist_val.constraints["Limit Distance"].distance = 1e-05
              #  rlist_val.select_set(False)
              #if "SplineVehicle" in actor.name:
              #  spline_param = param
              #  spline_obj = rlist_val
              #  if param.type == 5:
              #    vehicle_actor = actorList.actors[int(rlist_val.name.split(' ')[-1])]
              #    for vp in vehicle_actor.params:
              #      if vp.type == 8:
              #        spline_param = vp
              #        sel = vp.loaded_value
              #        spline_obj = namelists[abs(vp.type - 8)]
              #        if spline_obj != None: spline_obj = spline_obj[sel]
              #        break
              #  if spline_param.type == 8 and spline_obj != None:
              #    if "Empty" not in bpy.data.objects: bpy.data.objects.new("Empty", None)
              #    bpy.context.view_layer.objects.active = obj
              #    bpy.ops.object.constraint_add(type='COPY_LOCATION')
              #    obj.constraints["Copy Location"].target = bpy.data.objects["Empty"]
              #    bpy.ops.object.constraint_add(type='FOLLOW_PATH')
              #    obj.constraints["Follow Path"].use_curve_follow = True
              #    obj.constraints["Follow Path"].target = spline_obj
              #    bpy.ops.constraint.followpath_path_animate(constraint="Follow Path", owner='OBJECT')
              #    obj.select_set(False)
              rlist_val = rlist_val.name
            if rlist_val == None: rlist_val = ""
            obj[param_id] = rlist_val
          elif param.type == 6:
            if param in parent_children_connections and param.loaded_param_count > 0:
              children = parent_children_connections[param]
              if len(children) > 1:
                float_children = { float_child : float_child.value if (float_child.overwritten or float_child.added) else 0.0 for float_child in children if float_child.type == 0 }
                if len(float_children) == len(children):
                  float_names = [float_child.string for float_child in float_children.keys()]
                  obj[param_id] = Vector(list(float_children.values()))
                  if "Size" in param.string:
                    ui = obj.id_properties_ui(param_id)
                    ui.update(subtype="XYZ_LENGTH")
                  elif ("X" in float_names[0] and "Y" in float_names[1]):
                    ui = obj.id_properties_ui(param_id)
                    ui.update(subtype="XYZ")
                  elif ("Color" in param.string or "Colour" in param.string):
                    obj[param_id] = Vector(list(float_children.values())) / 255.0
                    ui = obj.id_properties_ui(param_id)
                    ui.update(min=0.0, soft_min=0.0)
                    ui.update(soft_max=1.0)
                    ui.update(subtype="COLOR")
                  continue
              obj[param_id] = []#[child.string for child in children]
          else: obj[param_id] = param.value
    elif key == "MAT ":
      data.seek(block)
      materials = LevelMaterialsEntry(data)
    elif key == "SECT":
      data.seek(block)
      geometry = GeometrySection(data, lp2_version, materials.materials)
      models_collection = bpy.data.collections.new("Level Models")
      bpy.context.collection.children.link(models_collection)
      dynamic_models_collection = bpy.data.collections.new("Dynamic Level Models")
      bpy.context.collection.children.link(dynamic_models_collection)
      
      collisionMeshes = []
      for c, collSect in enumerate(geometry.collision_sections):
        section_vertices, section_indices, section_triNormals, vertex_groups = collSect.get_geometry_per_section()
        mesh = bpy.data.meshes.new(name="Collision Mesh %d" % (c))
        mesh.from_pydata(section_vertices, [], section_indices)
        mesh.update()
        mesh.validate()
        collisionMeshes.append((mesh, vertex_groups))
      
      bpy_materials = {}
      renderMeshes = []
      for r, rendSect in enumerate(geometry.render_sections):
        section_vertices, section_normals, section_faces, section_colors, material_uvs, vertex_groups = rendSect.get_section_geometry()
        mesh = bpy.data.meshes.new(name="Render Mesh %d" % r)
        mesh.from_pydata(section_vertices, [], section_faces)
        per_mesh_materials = {}
        
        #mesh.vertices.foreach_set("normal", [n for nv in section_normals for n in nv])
        
        uv_layers = []
        for mat_index in material_uvs.keys():
          face_offset, offset, face_len, mat_uvs = material_uvs[mat_index]
          for lay, uv_map in enumerate(mat_uvs):
            if lay == len(uv_layers): uv_layers.append(mesh.uv_layers.new())
            for u, mat_uv in enumerate(uv_map): uv_layers[lay].data[offset+u].uv = mat_uv
          
          lp2_material = materials.materials[mat_index]
          if lp2_material.properties[0].texture_index < 0xff:
            if not mat_index in bpy_materials:
              image = textures[lp2_material.properties[0].texture_index]
              bpy_material = bpy.data.materials.new(name="LP2 Material %03d" % mat_index)#image.name)
              bpy_material.use_nodes = True
              matnodes = bpy_material.node_tree.nodes
              texture = matnodes.new("ShaderNodeTexImage")
              texture.image = image
              matnodes["Principled BSDF"].inputs[7].default_value = 0.1
              matnodes["Principled BSDF"].inputs[9].default_value = 0.75
              if image.channels == 4:
                bpy_material.node_tree.links.new(texture.outputs[1], matnodes["Principled BSDF"].inputs[21])
                #bpy_material.blend_method = 'BLEND'
                #bpy_material.alpha_threshold = 0
              #TODO: Implement vertex color OSL shader node
              bpy_material.node_tree.links.new(texture.outputs[0], matnodes["Principled BSDF"].inputs[0])
              bpy_material.node_tree.links.new(matnodes["Principled BSDF"].outputs[0], matnodes['Material Output'].inputs[0])
              bpy_materials[mat_index] = bpy_material
            else: bpy_material = bpy_materials[mat_index]
            
            if not mat_index in per_mesh_materials:
              bpy_index = len(mesh.materials)
              per_mesh_materials[mat_index] = bpy_index
            else: bpy_index = per_mesh_materials[mat_index]
            
            faces = [f for f in mesh.polygons if f.index >= face_offset and f.index < face_offset + face_len]
            for face in faces: face.material_index = bpy_index
            mesh.materials.append(bpy_material)
        
        if rendSect.color_maps > 0:
          for section_color in section_colors:
            vcol_lay = mesh.vertex_colors.new()
            for sc, col in enumerate(vcol_lay.data):
              col.color = list(reversed(section_color[sc][0:3])) + [section_color[sc][3]]
        mesh.color_attributes.active_color_index = 0
        mesh.update()
        mesh.validate()
        renderMeshes.append((mesh, vertex_groups))
      
      renderMeshObjects = {}
      
      for i, inst in enumerate(geometry.model_instances):
        iobj = bpy.data.objects.new("Model %d" % i, None)
        models_collection.objects.link(iobj)
        #bpy.context.view_layer.objects.active = iobj
        transform = Euler((math.radians(90), 0, 0)).to_matrix().to_4x4() @ inst.transform
        iobj.matrix_world = transform
        iobj["Vertex Color Index"] = inst.vertex_color_index
        iobj["Effects"] = inst.effects
        iobj["_lp2_type"] = "Static Instance"
        
        for r, render_instance in enumerate(inst.render_instances):
          rend_sect_index = render_instance.sect_index
          mesh, vertex_groups = renderMeshes[rend_sect_index]
          obj = bpy.data.objects.new("Model %d Render %d" % (i, r), mesh)
          for v, gindices in enumerate(vertex_groups):
            if ("sub%d" % v) in obj.vertex_groups.keys(): continue
            vgroup = obj.vertex_groups.new(name="sub%d" % v)
            vgroup.add(gindices, 1.0, 'REPLACE')
          if not mesh.name in renderMeshObjects: renderMeshObjects[mesh.name] = obj
          obj["bounds"] = render_instance.max - render_instance.min
          models_collection.objects.link(obj)
          obj.parent = iobj
          if renderMeshObjects[mesh.name] != obj  and inst.vertex_color_index > 0:
            bpy.context.view_layer.objects.active = obj
            
            #TODO: Setup proper geometry node implentation for vertex colors, replacing the data transfer modifier
            #vcol_selection = "Col"
            #if inst.vertex_color_index > 0: vcol_selection = "%s.%03d" % (vcol_selection, inst.vertex_color_index) 
            #if "Geometry Nodes %s" % vcol_selection in bpy.data.node_groups:
            #  bpy.ops.object.modifier_add(type='NODES')
            #  node_group = bpy.data.node_groups["Geometry Nodes %s" % vcol_selection]
            #else:
            #  bpy.ops.node.new_geometry_nodes_modifier()
            #  ng = bpy.context.object.modifiers["GeometryNodes"].node_group
            #  node_group = ng
            #  node_group.name = "Geometry Nodes %s" % vcol_selection
            #  nodes = node_group.nodes
            #  group_output = nodes["Group Output"]
            # #group_output.inputs.new(type='CUSTOM', name='Attribute')
            #  string_input = nodes.new(type='FunctionNodeInputString')
            #  string_input.string = vcol_selection
            #  color_input = nodes.new(type='GeometryNodeInputNamedAttribute')
            #  color_input.data_type = 'FLOAT_COLOR'
            #  
            #  links = node_group.links
            #  links.new(string_input.outputs[0], color_input.inputs[0])
            #  links.new(color_input.outputs["Attribute"], nodes["Group Output"].inputs[1])
            #bpy.context.object.modifiers["GeometryNodes"].node_group = node_group
            #bpy.context.object.modifiers["GeometryNodes"]["Output_2_attribute_name"] = "Col"
            
            #bpy.ops.object.modifier_add(type='DATA_TRANSFER')
            #bpy.context.object.modifiers["DataTransfer"].object = bpy.data.objects[renderMeshObjects[mesh.name].name]
            #bpy.context.object.modifiers["DataTransfer"].use_loop_data = True
            #bpy.context.object.modifiers["DataTransfer"].data_types_loops = {'VCOL'}
            #bpy.context.object.modifiers["DataTransfer"].loop_mapping = 'TOPOLOGY'
            #vcol_selection = "Col"
            #if inst.vertex_color_index > 0: vcol_selection = "%s.%03d" % (vcol_selection, inst.vertex_color_index) 
            #bpy.context.object.modifiers["DataTransfer"].layers_vcol_loop_select_src = vcol_selection
            #bpy.context.object.modifiers["DataTransfer"].layers_vcol_loop_select_dst = "Col"
            
            obj.select_set(False)
          #obj.matrix_world = transform
        
        for c, coll_instance in enumerate(inst.collision_instances):
          coll_sect_index = coll_instance.sect_index
          mesh, vertex_groups = collisionMeshes[coll_sect_index]
          obj = bpy.data.objects.new("Model %d Collision %d" % (i, c), mesh)
          for v, gindices in enumerate(vertex_groups):
            if ("sub%d" % v) in obj.vertex_groups.keys(): continue
            vgroup = obj.vertex_groups.new(name="sub%d" % v)
            vgroup.add(gindices, 1.0, 'REPLACE')
          
          obj["bounds"] = coll_instance.max - coll_instance.min
          models_collection.objects.link(obj)
          obj.parent = iobj
          obj.hide_set(not obj.hide_get())
          #obj.matrix_world = transform
      
      for i, inst in enumerate(geometry.dynamic_model_instances):
        iobj = bpy.data.objects.new("Dynamic Model %d" % i, None)
        dynamic_models_collection.objects.link(iobj)
        #bpy.context.view_layer.objects.active = iobj
        transform = Euler((math.radians(90), 0, 0)).to_matrix().to_4x4() @ inst.transform
        iobj.matrix_world = transform
        iobj["Vertex Color Index"] = inst.vertex_color_index
        iobj["Effects"] = inst.effects
        iobj["_lp2_type"] = "Dynamic Instance"
        for r, render_instance in enumerate(inst.render_instances):
          rend_sect_index = render_instance.sect_index
          mesh, vertex_groups = renderMeshes[rend_sect_index]
          obj = bpy.data.objects.new("Dynamic Model %d Render %d" % (i, r), mesh)
          for v, gindices in enumerate(vertex_groups):
            if ("sub%d" % v) in obj.vertex_groups.keys(): continue
            vgroup = obj.vertex_groups.new(name="sub%d" % v)
            vgroup.add(gindices, 1.0, 'REPLACE')
          if not mesh.name in renderMeshObjects: renderMeshObjects[mesh.name] = obj
          obj["bounds"] = render_instance.max - render_instance.min
          dynamic_models_collection.objects.link(obj)
          obj.parent = iobj
          if renderMeshObjects[mesh.name] != obj and inst.vertex_color_index > 0:
            bpy.context.view_layer.objects.active = obj
            
            #TODO: Setup proper geometry node implentation for vertex colors, replacing the data transfer modifier
            #vcol_selection = "Col"
            #if inst.vertex_color_index > 0: vcol_selection = "%s.%03d" % (vcol_selection, inst.vertex_color_index) 
            #if "Geometry Nodes %s" % vcol_selection in bpy.data.node_groups:
            #  bpy.ops.object.modifier_add(type='NODES')
            #  node_group = bpy.data.node_groups["Geometry Nodes %s" % vcol_selection]
            #else:
            #  bpy.ops.node.new_geometry_nodes_modifier()
            #  ng = bpy.context.object.modifiers["GeometryNodes"].node_group
            #  node_group = ng
            #  node_group.name = "Geometry Nodes %s" % vcol_selection
            #  nodes = node_group.nodes
            #  group_output = nodes["Group Output"]
            # #group_output.inputs.new(type='CUSTOM', name='Attribute')
            #  string_input = nodes.new(type='FunctionNodeInputString')
            #  string_input.string = vcol_selection
            #  color_input = nodes.new(type='GeometryNodeInputNamedAttribute')
            #  color_input.data_type = 'FLOAT_COLOR'
            #  
            #  links = node_group.links
            #  links.new(string_input.outputs[0], color_input.inputs[0])
            #  links.new(color_input.outputs["Attribute"], nodes["Group Output"].inputs[1])
            #bpy.context.object.modifiers["GeometryNodes"].node_group = node_group
            #bpy.context.object.modifiers["GeometryNodes"]["Output_2_attribute_name"] = "Col"
            
            #bpy.ops.object.modifier_add(type='DATA_TRANSFER')
            #bpy.context.object.modifiers["DataTransfer"].object = bpy.data.objects[renderMeshObjects[mesh.name].name]
            #bpy.context.object.modifiers["DataTransfer"].use_loop_data = True
            #bpy.context.object.modifiers["DataTransfer"].data_types_loops = {'VCOL'}
            #bpy.context.object.modifiers["DataTransfer"].loop_mapping = 'TOPOLOGY'
            #vcol_selection = "Col"
            #if inst.vertex_color_index > 0: vcol_selection = "%s.%03d" % (vcol_selection, inst.vertex_color_index) 
            #bpy.context.object.modifiers["DataTransfer"].layers_vcol_loop_select_src = vcol_selection
            #bpy.context.object.modifiers["DataTransfer"].layers_vcol_loop_select_dst = "Col"
            
            obj.select_set(False)
          #obj.matrix_world = transform
          
        for c, coll_instance in enumerate(inst.collision_instances):
          coll_sect_index = coll_instance.sect_index
          mesh, vertex_groups = collisionMeshes[coll_sect_index]
          obj = bpy.data.objects.new("Dynamic Model %d Collision %d" % (i, c), mesh)
          for v, gindices in enumerate(vertex_groups):
            if ("sub%d" % v) in obj.vertex_groups.keys(): continue
            vgroup = obj.vertex_groups.new(name="sub%d" % v)
            vgroup.add(gindices, 1.0, 'REPLACE')
          obj["bounds"] = coll_instance.max - coll_instance.min
          dynamic_models_collection.objects.link(obj)
          obj.parent = iobj
          obj.hide_set(not obj.hide_get())
          #obj.matrix_world = transform

def load(operator, context, filepath=""):
  filedata = None
  
  #adef_data = None
  adef_path = os.path.join(current_dir.parent.absolute(), "tp_utils")
  adef = load_adef(adef_path)
  #adef_path = os.path.join(adef_path, "adef.sama")
  #with open (adef_path, "rb") as f:
  #  adef_data = BytesIO(f.read())
  #  adef_data.seek(0)
  #adef = Adef(adef_data)
      
  with open(filepath, 'rb') as f:
    filedata = BytesIO(f.read())
    magic = try_read_str(filedata, 0, 4)
    filedata.seek(0)
    if magic is not None:
      if magic.startswith("PK2") and has_decompress:
        d = Decompressor(BytesIO(filedata.read()))
        d.decompressed.seek(0)
        filedata = BytesIO(d.decompressed.read())
      load_lp2(filedata, os.path.splitext(os.path.basename(f.name))[0], adef, filepath.split("LEVELS")[0])
  if filedata == None: return {'CANCELLED'}
  return {'FINISHED'}
