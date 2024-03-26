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
from adef import ActorStringsEntry
from textures import TextureListEntry, AnimatedTexturesEntry
from lp2 import LightsEntry, SplineListEntry, AIMapListEntry, ActorInfoListEntry, Models, LevelModelInstance, LevelMaterialsEntry, GeometrySection, RenderSection, load_adef
from tristripper import TriangleStripper, PrimitiveType, triangle_from_strip_to_triangle_list

try:
    from decompress import *
    has_decompress = True
except ImportError:
    has_decompress = False


def extract_blender_collision(collOb):
  try: collMesh = collOb.to_mesh()
  except RuntimeError: return []
  bm = bmesh.new()
  bm.from_mesh(collMesh)
  collOb.to_mesh_clear()
  
  vertex_groups = collOb.vertex_groups
  deforms = bm.verts.layers.deform.values()
  
  #bbox_corners = [Vector(corner) for corner in collOb.bound_box]
  #bbox_transpose = [[cor[co] for cor in bbox_corners] for co in range(3)]
  #minVec = Vector([min(co) for co in bbox_transpose])
  #maxVec = Vector([max(co) for co in bbox_transpose])
  minX = sys.maxsize
  minY = sys.maxsize
  minZ = sys.maxsize
  maxX = sys.maxsize - 1
  maxY = sys.maxsize - 1
  maxZ = sys.maxsize - 1
  
  sub_sections = {}
  for vert in bm.verts:
    groupIndex = -1
    for g, deform in enumerate(deforms):
      try:
        dv = vert[deform]
        groupIndex = g
      except: pass
    
    if groupIndex != -1:
      groupName = vertex_groups[groupIndex].name
    elif len(vertex_groups) == 0: groupName = "sub0"
    else: continue
    
    if not "verts" in sub_sections:
      sub_sections["verts"] = {}
    if not vert.index in sub_sections["verts"]:
      sub_sections["verts"][vert.index] = groupName
    if not groupName in sub_sections:
      sub_sections[groupName] = {}
    if not "verts" in sub_sections[groupName]:
      sub_sections[groupName]["verts"] = []
    sub_sections[groupName]["verts"].append(list(vert.co[:]) + [1.0])
    minX = min(vert.co[:][0], minX)
    minY = min(vert.co[:][1], minY)
    minZ = min(vert.co[:][2], minZ)
    maxX = max(vert.co[:][0], maxX)
    maxY = max(vert.co[:][1], maxY)
    maxZ = max(vert.co[:][2], maxZ)
  minVec = Vector([minX, minY, minZ])
  maxVec = Vector([maxX, maxY, maxZ])
  
  for face in bm.faces:
    indices = []
    for vert in face.verts:
      groupName = sub_sections["verts"][vert.index]
      indices.append(vert.index)
    edge_indices = []
    for edge in face.edges:
      edge_indices.append(edge.index)
    if not groupName in sub_sections:
      sub_sections[groupName] = {}
    if not "faces" in sub_sections[groupName]:
      sub_sections[groupName]["faces"] = []
    sub_sections[groupName]["faces"].append((indices, edge_indices, list(face.normal[:]) + [-face.normal.dot(face.calc_center_median())]))
    
  for edge in bm.edges:
    indices = []
    for vert in edge.verts:
      groupName = sub_sections["verts"][vert.index]
      indices.append(vert.index)
    if not groupName in sub_sections:
      sub_sections[groupName] = {}
    if not "edges" in sub_sections[groupName]:
      sub_sections[groupName]["edges"] = []
    sub_sections[groupName]["edges"].append(indices)
    
  return minVec, maxVec, sub_sections

def extract_blender_render(rendOb):
  try: rendMesh = rendOb.to_mesh()
  except RuntimeError: return []
  bm = bmesh.new()
  bm.from_mesh(rendMesh)
  rendOb.to_mesh_clear()
  
  vertex_groups = rendOb.vertex_groups
  deforms = bm.verts.layers.deform.values()
  vertex_colors = rendOb.data.vertex_colors
  col_lays = bm.loops.layers.color.keys()
  col_lays = vertex_colors.keys()
  materials = rendOb.data.materials
  uv_lays = bm.loops.layers.uv.keys()
  
  minX = sys.maxsize
  minY = sys.maxsize
  minZ = sys.maxsize
  maxX = sys.maxsize - 1
  maxY = sys.maxsize - 1
  maxZ = sys.maxsize - 1
  
  mesh_sections = {}
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
    
    materialName = materials[face.material_index].name
    if not materialName in mesh_sections:
      mesh_sections[materialName] = []
    mesh_sections[materialName].append(face)
  
  for mat in mesh_sections.keys():
    materialGroup = mesh_sections[mat]
    indices = [vert.index for face in materialGroup for vert in face.verts]
    indexDict = {vert.index: vert for face in materialGroup for vert in face.verts}
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
    for primStrip in primStrips:
      strip = []
      for v, vindex in enumerate(primStrip):
        skipDraw = 0 if v > 1 else 1
        flag = skipDraw << 0xf
        vert = indexDict[vindex]
        stripTri = triangle_from_strip_to_triangle_list(v, primStrip)
        
        colDict = {}
        uvDict = {}
        for loop in vert.link_loops:
          for col_lay in col_lays:
            layer = bm.loops.layers.color[col_lay]
            col = loop[layer][:]#.color[:]
            if not col_lay in colDict: colDict[col_lay] = {}
            if not col in colDict[col_lay]: colDict[col_lay][col] = []
            colDict[col_lay][col].append(loop)
          
          for uv_lay in uv_lays:
            layer = bm.loops.layers.uv[uv_lay]
            uv = loop[layer].uv[:]
            if not uv_lay in uvDict: uvDict[uv_lay] = {}
            if not uv in uvDict[uv_lay]: uvDict[uv_lay][uv] = []
            uvDict[uv_lay][uv].append(loop)
        
        outColors = {}
        for col_lay in col_lays:
          bestScore = 0
          chosenCol = list(colDict[col_lay].keys())[0]
          for col in colDict[col_lay].keys():
            for loop in colDict[col_lay][col]:
              score = len([fvert.index for fvert in loop.face.verts if fvert.index in stripTri])
              if score > bestScore:
                chosenCol = col
                bestScore = score
              if score == 3: break
            if bestScore == 3: break
          outColors[col_lay] = chosenCol
        
        outUVs = {}
        for uv_lay in uv_lays:
          bestScore = 0
          chosenUV = list(uvDict[uv_lay].keys())[0]
          for uv in uvDict[uv_lay].keys():
            for loop in uvDict[uv_lay][uv]:
              score = len([fvert.index for fvert in loop.face.verts if fvert.index in stripTri])
              if score > bestScore:
                chosenUV = uv
                bestScore = score
              if score == 3: break
            if bestScore == 3: break
          outUVs[uv_lay] = chosenUV
        
        minX = min(vert.co[:][0], minX)
        minY = min(vert.co[:][1], minY)
        minZ = min(vert.co[:][2], minZ)
        maxX = max(vert.co[:][0], maxX)
        maxY = max(vert.co[:][1], maxY)
        maxZ = max(vert.co[:][2], maxZ)
        strip.append((vert.co[:], vert.normal[:], outUVs, outColors, flag))
      strips.append(strip)
    mesh_sections[mat] = strips
  
  mesh_data = {}
  for mat_name in mesh_sections.keys():
    mat_index = int(mat_name.split(" ")[-1])
    og_strips = mesh_sections[mat_name]
    new_strips = []
    for strip in og_strips:
      verts = []
      normals = []
      uvs = []
      colors = []
      for v_pos, v_nor, v_uvs, v_cols, strip_flag in strip:
        verts.append((v_pos, strip_flag))
        normals.append(v_nor)
        for uv_index, v_uv in enumerate(v_uvs.keys()):
          if "." in v_uv: uv_index = int(v_uv.split(".")[-1])
          if uv_index >= len(uvs): uvs.append([])
          uvs[uv_index].append(v_uvs[v_uv])
        for col_index, v_col in enumerate(v_cols.keys()):
          if "." in v_col: col_index = int(v_col.split(".")[-1])
          if col_index >= len(colors): colors.append([])
          colors[col_index].append(v_cols[v_col])
      new_strips.append((verts, normals, uvs, colors))
    if mat_index in mesh_data: mesh_data[mat_index].extend(new_strips)
    else: mesh_data[mat_index] = new_strips
  minVec = Vector([minX, minY, minZ])
  maxVec = Vector([maxX, maxY, maxZ])
  return minVec, maxVec, mesh_data, len(col_lays)

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

def save(context, filepath="", save_mesh_changes=False, save_actor_changes=True, save_dynamic_instance_changes=True, save_spline_changes=True, save_aimap_changes=False, use_selection=False):
  #adef_data = None
  adef_path = os.path.join(current_dir.absolute(), "tp_utils")
  adef = load_adef(adef_path)
  #adef_path = os.path.join(adef_path, "adef.sama")
  #with open (adef_path, "rb") as f:
  #  adef_data = BytesIO(f.read())
  #  adef_data.seek(0)
  #adef = Adef(adef_data)
  
  lp2data = None
  if os.path.isfile(filepath):
    with open(filepath, 'rb') as f:
      lp2data = BytesIO(f.read())
      magic = try_read_str(lp2data, 0, 4)
      lp2data.seek(0)
      if magic is not None:
        if magic.startswith("PK2") and has_decompress:
          d = Decompressor(BytesIO(lp2data.read()))
          d.decompressed.seek(0)
          lp2data = BytesIO(d.decompressed.read())
        #load_lp2(lp2data, os.path.splitext(os.path.basename(f.name))[0])
  blocks = {}
  if lp2data != None:
    find_blocks(lp2data, blocks)
    print(blocks)
  
  lp2_version = 4
  texture_data = None
  anim_data = None
  material_data = None
  materials = None
  geometry = None
  node_data = None
  pvs_data = None
  aimap_data = None
  aimaps = AIMapListEntry()
  grid_data = None
  spline_data = None
  splines = SplineListEntry()
  light_data = None
  
  
  
  actors = ActorInfoListEntry(None, adef.classes, adef.enums, adef.strings, ActorStringsEntry(), ActorStringsEntry(), aimaps, splines, None)
  
  for key in blocks.keys():
    block = blocks[key]
    if key == "INFO":
      lp2_version = sread_u32(lp2data, block + 0x4)
    elif key == "TEX ":
      lp2data.seek(block)
      texture_block_size = sread_u32(lp2data, lp2data.tell())
      lp2data.seek(block - 0x4)
      texture_data = BytesIO(lp2data.read(texture_block_size + 0x8))
    elif key == "MAT ":
      lp2data.seek(block)
      material_block_size = sread_u32(lp2data, lp2data.tell())
      lp2data.seek(block - 0x4)
      material_data = BytesIO(lp2data.read(material_block_size + 0x8))
      lp2data.seek(block)
      materials = LevelMaterialsEntry(lp2data)
    elif key == "SECT":
      lp2data.seek(block)
      geometry = GeometrySection(lp2data, lp2_version, materials.materials)
    elif key == "AIMP":
      lp2data.seek(block)
      aimp_block_size = sread_u32(lp2data, lp2data.tell())
      lp2data.seek(block - 0x4)
      aimap_data = BytesIO(lp2data.read(aimp_block_size + 0x8))
    elif key == "NODE":
      lp2data.seek(block)
      node_block_size = sread_u32(lp2data, lp2data.tell())
      lp2data.seek(block - 0x4)
      node_data = BytesIO(lp2data.read(node_block_size + 0x8))
    elif key == "PVS ":
      lp2data.seek(block)
      pvs_block_size = sread_u32(lp2data, lp2data.tell())
      lp2data.seek(block - 0x4)
      pvs_data = BytesIO(lp2data.read(pvs_block_size + 0x8))
    elif key == "GRID":
      lp2data.seek(block)
      grid_block_size = sread_u32(lp2data, lp2data.tell())
      lp2data.seek(block - 0x4)
      grid_data = BytesIO(lp2data.read(grid_block_size + 0x8))
    elif key == "LITE":
      lp2data.seek(block)
      light_block_size = sread_u32(lp2data, lp2data.tell())
      lp2data.seek(block - 0x4)
      light_data = BytesIO(lp2data.read(light_block_size + 0x8))
    elif key == "ANIM":
      lp2data.seek(block)
      anim_block_size = sread_u32(lp2data, lp2data.tell())
      lp2data.seek(block - 0x4)
      anim_data = BytesIO(lp2data.read(anim_block_size + 0x8))
    elif key == "ACTR":
      lp2data.seek(block)
      actr_block_size = sread_u32(lp2data, lp2data.tell())
      lp2data.seek(block - 0x4)
      actor_data = BytesIO(lp2data.read(actr_block_size + 0x8))
    elif key == "SPLN":
      lp2data.seek(block)
      spln_block_size = sread_u32(lp2data, lp2data.tell())
      lp2data.seek(block - 0x4)
      spline_data = BytesIO(lp2data.read(spln_block_size + 0x8))
      
  
  if bpy.ops.object.mode_set.poll(): bpy.ops.object.mode_set(mode='OBJECT')
  if use_selection: obs = context.selected_objects
  else: obs = context.scene.objects
  
  collMeshes = {}
  rendMeshes = {}
  dynamicInstanceObjects = []
  splineObjects = []
  aimapObjects = []
  actorObjects = []
  for ob in obs:
    ob_eval = ob
    lp2_type = None
    if "_lp2_type" in ob_eval: lp2_type = ob_eval["_lp2_type"]
    if ob_eval.data != None:
      ob_type = str(type(ob_eval.data))
      if "types.Mesh" in ob_type:
        for collection in ob_eval.users_collection:
            if "Level Models" in collection.name:
              if len(ob_eval.data.materials.keys()) > 0 or len(ob_eval.data.uv_layers.keys()) > 0 or len(ob_eval.data.vertex_colors.keys()) > 0:
                if not ob_eval.data.name in rendMeshes: rendMeshes[ob_eval.data.name] = (ob_eval, int(ob_eval.data.name.replace("Render Mesh ", "")))
              elif not ob_eval.data.name in collMeshes: collMeshes[ob_eval.data.name] = (ob_eval, int(ob_eval.data.name.replace("Collision Mesh ", "")))
              break
      if lp2_type == None:
        if "types.Curve" in ob_type: lp2_type = "Spline"
        elif "types.SunLight" in ob_type: lp2_type = "SunLight"
        elif "types.SpotLight" in ob_type: lp2_type = "SpotLight"
        elif "types.PointLight" in ob_type: lp2_type = "PointLight"
        elif "types.Mesh" in ob_type and "Face Blocks" in ob_eval.data.attributes: lp2_type = "AIMap"
    elif ob_eval.data == None:
      if lp2_type == None:
        if "Actor Name" in ob_eval: lp2_type = "Actor"
        else:
          for collection in ob_eval.users_collection:
            if "Level Models" in collection.name:
              if "Dynamic" in collection.name: lp2_type = "Dynamic Instance"
              else: lp2_type = "Static Instance"
              break
    if lp2_type == None: continue
    
    if lp2_type == "Spline":
      splineObjects.append(ob_eval)
    elif lp2_type == "AIMap":
      aimapObjects.append(ob_eval)
    elif lp2_type == "Actor":
      actorObjects.append(ob_eval)
    elif lp2_type == "Dynamic Instance":
      dynamicInstanceObjects.append(ob_eval)
    elif lp2_type == "Static Instance":
      lp2_type = lp2_type
    elif lp2_type.endswith("Light"):
      lp2_type = lp2_type
    elif ob_eval.data == None:
      print(ob_eval.users_collection)
  
  #for instance in geometry.model_instances:
  #  for rend_inst in instance.render_instances:
  #    rend_inst.sect_index
      
  
  dynamicInstances = []
  dynamicInstanceNames = [dynamic.name for dynamic in dynamicInstanceObjects]
  dynamicCollMeshes = {}
  dynamicRendMeshes = {}
  for ob_eval in dynamicInstanceObjects:
    levelInst = LevelModelInstance(None, lp2_version)
    dynamicInstances.append(levelInst)
    levelInst.transform = Euler((math.radians(-90), 0, 0)).to_matrix().to_4x4() @ ob_eval.matrix_world
    levelInst.inv_transform = levelInst.transform.inverted_safe()
    levelInst.vertex_color_index = 0 if not "Vertex Color Index" in ob_eval else ob_eval["Vertex Color Index"]
    levelInst.effects = 0 if not "Effects" in ob_eval else ob_eval["Effects"]
    for child in ob_eval.children:
      bbox_corners = [Vector(corner) for corner in child.bound_box]
      bbox_transpose = [[cor[co] for cor in bbox_corners] for co in range(3)]
      minVec = Vector([min(co) for co in bbox_transpose])
      maxVec = Vector([max(co) for co in bbox_transpose])
      inst_index = 0xFFFFFFFF
      geoInst = levelInst.GeometryInstance(inst_index, 0, minVec, maxVec)
      if child.data.name in collMeshes:
        geoInst.sect_index = collMeshes[child.data.name][1]
        if not geoInst.sect_index in dynamicCollMeshes:
          dynamicCollMeshes[geoInst.sect_index] = extract_blender_collision(collMeshes[child.data.name][0])
        levelInst.collision_instances.append(geoInst)
      elif child.data.name in rendMeshes:
        geoInst.sect_index = rendMeshes[child.data.name][1]
        if not geoInst.sect_index in dynamicRendMeshes:
          dynamicRendMeshes[geoInst.sect_index] = extract_blender_render(rendMeshes[child.data.name][0])
        levelInst.render_instances.append(geoInst)
    levelInst.coll_inst_count = len(levelInst.collision_instances)
    levelInst.rend_inst_count = len(levelInst.render_instances)
  
  for collName in collMeshes.keys():
    collOb, collIndex = collMeshes[collName]
    if not collIndex in dynamicCollMeshes: continue
    
    minVec, maxVec, collSection = dynamicCollMeshes[collIndex]
    for groupName in collSection.keys():
      if groupName == "verts": continue
      group = collSection[groupName]
      #print(group["verts"])
      #print(group["edges"])
      #print(group["faces"])
  
  if save_mesh_changes:
    for rendName in rendMeshes.keys():
      rendOb, rendIndex = rendMeshes[rendName]
      if not rendIndex in dynamicRendMeshes: continue
      minVec, maxVec, mesh_data, n_color_layers = dynamicRendMeshes[rendIndex]
      while rendIndex >= len(geometry.render_sections):
        geometry.render_sections.append(RenderSection())
        geometry.render_sections[-1].save_changes()
      geometry.render_sections[rendIndex].inject_changes(mesh_data, n_color_layers, minVec, maxVec, materials.materials)
      geometry.render_sections[rendIndex].save_changes()
  
  aimapNames = [aimap.name for aimap in aimapObjects]
  for ob_eval in aimapObjects:
    output_transform = Euler((math.radians(-90), 0, 0)).to_matrix().to_4x4() @ ob_eval.matrix_world
    bm = bmesh.new()
    try: me = ob_eval.to_mesh()
    except RuntimeError: continue
    me.transform(output_transform)
    bm.from_mesh(me)
    ob_eval.to_mesh_clear()
    out_verts = []#list(vert.co[:]) + [1.0] for vert in bm.verts]
    out_faces = []
    out_vert_map = {}
    out_vert_id = 0
    face_blocks = bm.faces.layers.float.get("Face Blocks")
    #edge_blocks = [bm.edges.layers.int.get("Edge Blocks 1"), bm.edges.layers.int.get("Edge Blocks 2")]
    corner_blocks = [bm.loops.layers.float.get("Corner Blocks 1"), bm.loops.layers.float.get("Corner Blocks 2")]
    #print(face_blocks)
    orderedFaces = bm.faces#.copy()
    orderedFaces.sort(key=lambda x: x.index)
    for face in orderedFaces:
      out_edge = []
      out_faces.append((int(face[face_blocks]), out_edge))
      edge_blocks = {}
      for loop in face.loops:
        edge_blocks[loop.edge.index] = int(loop[corner_blocks[0]])
      for edge in face.edges:
        oevs = []
        oewvs = []
        edge_neighbor = 0xffff
        neighbor = face
        for f in edge.link_faces:
          if f.index != face.index:
            neighbor = f
            edge_neighbor = f.index
        
        #edge_block = 0
        #for eblock in edge_blocks:
        #  if (edge[eblock] >> 2) == face.index: edge_block = edge[eblock] & 3
        edge_block = 0 if not edge.index in edge_blocks else edge_blocks[edge.index]
        
        out_edge.append((oevs, edge_block, oewvs, edge_neighbor))
        
        #vs = [list(v.co[:]) + [1.0] for v in edge.verts]
        #fvs = [list(v.co[:]) + [1.0] for v in face.verts]
        evs = [v for v in edge.verts]
        fvs = [v for v in neighbor.verts if not v in evs]
        vs = evs + fvs
        vs = [Vector(list(v.co[:])) for v in vs]
        
        #oevs.extend([v.index for v in edge.verts])
        for v in edge.verts:
          if (_id := out_vert_map.get(v)) is not None:
            oevs.append(_id)
            continue
          out_verts.append(list(v.co[:]) + [1.0])
          out_vert_map[v] = out_vert_id
          oevs.append(out_vert_id)
          out_vert_id += 1
        #edge_pos = Vector(vs[0]).xyz
        #edge_dir = Vector(vs[1]).xyz - edge_pos
        #edge_dir = edge_dir * Vector([1.,0.,1.])
        #edge_pos = edge_pos * Vector([1.,0.,1.]) + edge_dir * 0.5
        #half_len = edge_dir.length * 0.5
        #edge_dir.normalize()
        #edge_dir = Vector([edge_dir[2], edge_dir[1], -edge_dir[0]])#, edge_dir[3]])
        #if bmesh.geometry.intersect_face_point(face, edge_pos + edge_dir * half_len):
        #  edge_dir = -edge_dir
        #edge_plane = [edge_dir[0], edge_dir[1], edge_dir[2], -edge_dir.dot(edge_pos)]
        v1 = vs[0]# * Vector([1., 0., 1.])
        v2 = vs[1]# * Vector([1., 0., 1.])
        v3 = vs[2]# * Vector([1., 0., 1.])
        edge1 = v3 - v1
        edge2 = v2 - v1
        #mid = (v1 + v2 + v3) / 3.0
        #mid = v1 + edge1 * 0.5
        edge_dir = edge1.cross(edge2)
        edge_dir = edge_dir * Vector([1.,0.,1.])
        edge_dir.normalize()
        #edge_dir = Vector([edge_dir[0], edge_dir[1], -edge_dir[2]])
        edge_plane = [edge_dir[0], 0.0, edge_dir[2], -edge_dir.dot(v3 * Vector([1.,0.,1.]))]
        oewvs.extend(edge_plane)
    aimaps.add_map(out_verts, out_faces)
  
  splineNames = [spline.name for spline in splineObjects]
  for ob_eval in splineObjects:
    output_transform = Euler((math.radians(-90), 0, 0)).to_matrix().to_4x4() @ ob_eval.matrix_world
    for spline in ob_eval.data.splines:
      splines.add_spline([point.co[0:3] for point in spline.points], output_transform, spline.use_cyclic_u)
  
  actorNames = [actor.name for actor in actorObjects]
  for ob_eval in actorObjects:
    output_transform = Euler((math.radians(-90), 0, 0)).to_matrix().to_4x4() @ ob_eval.matrix_world
    actors.create_new_actor(output_transform, ob_eval["Actor Name"])
  for a, ob_eval in enumerate(actorObjects):
    for prop_name in ob_eval.keys():
      prop_val = ob_eval[prop_name]
      if not ':' in prop_name: continue
      
      param_lookup = prop_name.split(':')
      if '' in param_lookup: param_lookup.remove('')
      param_lookup = int(param_lookup[0])
      param = actors.actors[a].add_parameter(param_lookup)
      if param == None: continue
      
      if param.type == 0:
        low_name = param.string.lower()
        if "time" in low_name and not "secs" in low_name:
          prop_val *= 60.0
        param.value = prop_val
        param.loaded_value = float_to_u32(param.value)
      elif param.type == 2:
        param.value = bool(prop_val)
        param.loaded_value = 1 if param.value else 0
      elif param.type == 3:
        param.value = prop_val
        if prop_val not in param.actor.actorList.PStringEntry.table:
          param.loaded_value = len(param.actor.actorList.PStringEntry.table)
          param.actor.actorList.PStringEntry.table.append(prop_val)
        else: param.loaded_value = param.actor.actorList.PStringEntry.table.index(prop_val)
      elif param.type == 4:
        param.value = prop_val
        if prop_val not in param.actor.actorList.AStringEntry.table:
          param.loaded_value = len(param.actor.actorList.AStringEntry.table)
          param.actor.actorList.AStringEntry.table.append(prop_val)
        else: param.loaded_value = param.actor.actorList.AStringEntry.table.index(prop_val)
      elif param.type == 5:
        param.loaded_value = 0xFFFFFFFF
        if prop_val != None and prop_val != "":
          if "types.Object" in str(type(prop_val)) and prop_val in actorObjects:
            param.value = prop_val.name
            param.loaded_value = actorObjects.index(prop_val)
          elif prop_val in actorNames:
            param.value = prop_val
            param.loaded_value = actorNames.index(prop_val)
      elif param.type == 8:
        param.loaded_value = 0xFFFFFFFF
        if prop_val != None and prop_val != "":
          if "types.Object" in str(type(prop_val)) and prop_val in splineObjects:
            param.value = prop_val.name
            param.loaded_value = splineObjects.index(prop_val)
          elif prop_val in splineNames:
            param.value = prop_val
            param.loaded_value = splineNames.index(prop_val)
      elif param.type == 9:
        param.loaded_value = 0xFFFFFFFF
        if prop_val != None and prop_val != "":
          if "types.Object" in str(type(prop_val)) and prop_val in dynamicInstanceObjects:
            param.value = prop_val.name
            param.loaded_value = dynamicInstanceObjects.index(prop_val)
          elif prop_val in dynamicInstanceNames:
            param.value = prop_val
            param.loaded_value = dynamicInstanceNames.index(prop_val)
      elif param.type == 10:
        param.loaded_value = 0xFFFFFFFF
        if prop_val != None and prop_val != "":
          if "types.Object" in str(type(prop_val)) and prop_val in aimapObjects:
            param.value = prop_val.name
            param.loaded_value = aimapObjects.index(prop_val)
          elif prop_val in aimapNames:
            param.value = prop_val
            param.loaded_value = aimapNames.index(prop_val)
      elif param.type == 6:
        param.loaded_value = 0xFFFFFFFF
        if "IDPropertyArray" in str(type(prop_val)):
          children_ = [child_param for child_param in actors.actors[a].params if child_param.parent_param == param]
          children = [child_param for child_param in children_ if child_param.type == 0]
          if len(children) < 2 or len(children) != len(children_): continue
          #print(param.string)
          #print([child_param.string for child_param in children])
          for c, child_param in enumerate(children):
            if child_param.string not in actors.AStringEntry.table:
              child_param.a_string_index = len(actors.AStringEntry.table)
              actors.AStringEntry.table.append(child_param.string)
            else: child_param.a_string_index = actors.AStringEntry.table.index(child_param.string)
            child_param.overwritten = True
            #print(list(prop_val))
            if ("Color" in param.string or "Colour" in param.string):
              child_param.value = prop_val[c] * 255.0
            else: child_param.value = prop_val[c]
            child_param.loaded_value = float_to_u32(child_param.value)
            param.loaded_param_count += 1
      else: param.value = param.loaded_value = prop_val
    
  print(actors.AStringEntry.table)
  print(actors.PStringEntry.table)
  
  gmesh_data = BytesIO()
  write_magic_str(gmesh_data, 0x0, "GMSH", 4)
  write_u32(gmesh_data, 0x4, 0)
  if texture_data != None: write_bytes(gmesh_data, gmesh_data.tell(), texture_data.read())
  if anim_data != None: write_bytes(gmesh_data, gmesh_data.tell(), anim_data.read())
  if material_data != None: write_bytes(gmesh_data, gmesh_data.tell(), material_data.read())
  geometry_data = None
  if geometry != None:
    if save_dynamic_instance_changes:
      geometry.dynamic_model_instances = dynamicInstances.copy()
    geometry_data = geometry.save_injected_changes(lp2_version)
  if geometry_data != None: write_bytes(gmesh_data, gmesh_data.tell(), geometry_data.read())
  if node_data != None: write_bytes(gmesh_data, gmesh_data.tell(), node_data.read())
  if pvs_data != None: write_bytes(gmesh_data, gmesh_data.tell(), pvs_data.read())
  if save_aimap_changes:
    aimap_data = aimaps.save_changes()
  if aimap_data != None: write_bytes(gmesh_data, gmesh_data.tell(), aimap_data.read())
  if grid_data != None: write_bytes(gmesh_data, gmesh_data.tell(), grid_data.read())
  write_magic_str(gmesh_data, gmesh_data.tell(), "END ", 4)
  write_u32(gmesh_data, gmesh_data.tell(), 0)
  gmesh_data.seek(0)
  write_u32(gmesh_data, 0x4, swap32(data_len(gmesh_data) - 8))
  gmesh_data.seek(0)
  
  if save_spline_changes:
    spline_data = splines.save_changes()
  
  if save_actor_changes:
    actor_data = BytesIO()
    write_magic_str(actor_data, 0x0, "ACTR", 4)
    write_u32(actor_data, 0x4, 0)
    astring_data = actors.AStringEntry.save_changes("ASTR")
    write_bytes(actor_data, actor_data.tell(), astring_data.read())
    pstring_data = actors.PStringEntry.save_changes("PSTR")
    write_bytes(actor_data, actor_data.tell(), pstring_data.read())
    write_bytes(actor_data, actor_data.tell(), actors.save_changes().read())
    write_magic_str(actor_data, actor_data.tell(), "END ", 4)
    write_u32(actor_data, actor_data.tell(), 0)
    actor_data.seek(0)
    write_u32(actor_data, 0x4, swap32(data_len(actor_data) - 8))
    actor_data.seek(0)
  
  lp2_data = BytesIO()
  write_magic_str(lp2_data, 0x0, "LEVL", 4)
  write_u32(lp2_data, 0x4, 0)
  write_magic_str(lp2_data, lp2_data.tell(), "INFO", 4)
  write_u32(lp2_data, lp2_data.tell(), swap32(4))
  write_u32(lp2_data, lp2_data.tell(), swap32(lp2_version))
  write_bytes(lp2_data, lp2_data.tell(), gmesh_data.read())
  write_bytes(lp2_data, lp2_data.tell(), spline_data.read())
  if light_data != None: write_bytes(lp2_data, lp2_data.tell(), light_data.read())
  write_bytes(lp2_data, lp2_data.tell(), actor_data.read())
  write_magic_str(lp2_data, lp2_data.tell(), "END ", 4)
  write_u32(lp2_data, lp2_data.tell(), 0)
  lp2_data.seek(0)
  write_u32(lp2_data, 0x4, swap32(data_len(lp2_data) - 8))
  lp2_data.seek(0)
  
  with open(filepath, "wb") as f:
    f.write(lp2_data.read())
