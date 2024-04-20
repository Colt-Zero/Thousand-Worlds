from io import BytesIO
import os
from fs_helpers import *
from adef import Adef, ActorStringsEntry
from bsptree import BSPTree
import math
from mathutils import Vector, Matrix, Euler

def load_adef(path):
  adef_data = None
  adef_path = os.path.join(path, "adef.sama")
  with open (adef_path, "rb") as f:
    adef_data = BytesIO(f.read())
    adef_data.seek(0)
  adef = Adef(adef_data)
  return adef

class LevelMaterialsEntry:
  def __init__(self, data = None):
    self.data = data
    self.entry_offset = 0
    self.block_size = 0
    self.count = 0
    self.materials = []
    if self.data == None: return

    self.entry_offset = self.data.tell()
    self.block_size = sread_u32(self.data, self.data.tell())
    self.count = sread_u32(self.data, self.data.tell())
    #print("Mat section beginning: %08x" % self.entry_offset)
    for i in range(self.count):
      self.materials.append(LevelMaterialEntry(mat_data=self.data))
    
    self.data.seek(self.block_size + 0x4 + self.entry_offset)
  
  def save_changes(self):
    output = BytesIO()
    write_magic_str(output, output.tell(), "MAT ", 4)
    write_u32(output, output.tell(), 0)
    write_u32(output, output.tell(), swap32(len(self.materials)))
    for material in self.materials:
      output.write(material.save_changes().read())
    self.block_size = data_len(output) - 0x8
    write_u32(output, 0x4, swap32(self.block_size))
    output.seek(0)
    return output

class LevelMaterialEntry:
  class LevelMaterialDataEntry:
    def __init__(self, texture_index, flags = 0, type = 0, uv_ind = 0):
      self.texture_index = texture_index
      self.flags = flags
      #0x20: Default
      #0x28: Alpha clip?
      #0x30: 
      #0x60: 
      #0x71: 
      #local_c0[1]
      #boolean impact:
      #local_c0[0] 0 or 1
      #local_b0 flags & 0x8 == 0: 0 else 1 -> 0x5000c else 0x5000d
      #local_ac 0 or 1
      #local_a8 flags & 0x10 == 0: 0 else 5
      self.type = type
      #0: Regular texture
      #1: Glow type 1?
      #2: Red Environment map?
      #3: Glass Type?
      #4: Glow type 2?
      #5: Regular Environment map?
      #local_c0[2]
      #boolean impact:
      #local_c0[0] 0 or 0x400
      #local_c0[3] 0 or 1 
      #local_b0 0 or 1 -> 0x5000c or 0x5000d
      #local_ac 0 or 1
      #local_a4 type == 0: 0 else 0x40 -> 0x238 else 0x278
      self.uv = uv_ind
  
  def __init__(self, flags = 0, uv_maps = 0, normals = 0, mat_data = None):
    self.data = mat_data
    self.lod_flags = flags
    self.mat_properties = 0
    self.uv_maps = uv_maps
    self.normals = normals
    self.properties = []
    if self.data == None: return

    self.lod_flags = sread_u32(self.data, self.data.tell())
    #0: Render
    #1: Render when mid?
    #3: Render when close?
    #4: Fade out when close
    #6: Fade out when mid
    if (self.lod_flags & 0x7) == 0x7:
      print("Why the fuck are the LOD flags for this section set to no render")
      #self.lod_flags = 0
    #self.lod_flags = self.lod_flags & 0x7fffffff
    
    self.mat_properties = sread_u16(self.data, self.data.tell())
    self.uv_maps = sread_u16(self.data, self.data.tell())
    self.normals = sread_u16(self.data, self.data.tell())
    #print("Mat properties len: " + str(self.mat_properties))
    for i in range(self.mat_properties):
      #print("Mat property entry: %08x" % self.data.tell())
      prop_data = self.LevelMaterialDataEntry(sread_u16(self.data, self.data.tell()), read_u8(self.data, self.data.tell()), read_u8(self.data, self.data.tell()), read_u8(self.data, self.data.tell()))
      #print("Material Property - Texture: " + textures[prop_data.texture_index].name + " Prop Bytes: " + hex(prop_data.flags) + " " + hex(prop_data.type) + " " + hex(prop_data.uv))
      self.properties.append(prop_data)
    if self.mat_properties != 0:
      if self.properties[0].type != 0:
        self.lod_flags = self.lod_flags# | 0x80000000
    #print("Material Lod Flags: " + hex(self.lod_flags))
  
  def add_property(self, texture_index = 0xffff, b1 = 0, b2 = 0, b3 = 0):
    prop = self.LevelMaterialDataEntry(texture_index, b1, b2, b3)
    self.properties.append(prop)
    self.mat_properties = len(self.properties)
  
  def save_changes(self):
    output = BytesIO()
    write_u32(output, output.tell(), swap32(self.lod_flags))
    write_u16(output, output.tell(), swap16(self.mat_properties))
    write_u16(output, output.tell(), swap16(self.uv_maps))
    write_u16(output, output.tell(), swap16(self.normals))
    for prop in self.properties:
      write_u16(output, output.tell(), swap16(prop.texture_index))
      write_u8(output, output.tell(), prop.flags)
      write_u8(output, output.tell(), prop.type)
      write_u8(output, output.tell(), prop.uv)
    output.seek(0)
    return output

  def printInfo(self, textures):
    print("Material properties: %d UV Maps: %d Normals: %d" % (self.mat_properties, self.uv_maps, self.normals))
    for i in range(self.mat_properties):
      prop_data = self.properties[i]
      textureName = "None"
      if prop_data.texture_index != 0xFFFF:
        textureName = textures[prop_data.texture_index].name
      print("Material Property - Texture: " + textureName + " Prop Bytes: " + hex(prop_data.flags) + " " + hex(prop_data.type) + " " + hex(prop_data.uv))

class GeometrySection:
  def __init__(self, data, versionNo, materials):
    self.data = data
    self.entry_offset = self.data.tell()
    self.block_size = sread_u32(self.data, self.data.tell())
    
    self.render_section_start = self.data.tell()
    self.render_section_count = sread_u32(self.data, self.data.tell())
    print("Render Section Count: " + str(self.render_section_count))
    self.render_sections = []
    for i in range(self.render_section_count):
      self.render_sections.append(RenderSection(self.data, materials))
    
    self.collision_section_start = self.data.tell()
    self.collision_section_count = sread_u32(self.data, self.data.tell())
    print("Collision Section Count: " + str(self.collision_section_count))
    self.collision_sections = []
    for i in range(self.collision_section_count):
      self.collision_sections.append(CollisionSection(self.data))
    
    
    self.render_section_instance_count = -1
    if versionNo > 3: self.render_section_instance_count = sread_u32(self.data, self.data.tell())
    
    self.static_section_start = self.data.tell()
    print("Instance Section Start: " + hex(self.static_section_start))
    
    render_instance_count = 0
    collision_instance_count = 0
    
    self.model_instance_count = sread_u32(self.data, self.data.tell())
    print("Model Instance Count: " + str(self.model_instance_count))
    self.model_instances = []
    for i in range(self.model_instance_count):
      self.model_instances.append(LevelModelInstance(self.data, versionNo, render_instance_count, collision_instance_count))
      render_instance_count += self.model_instances[-1].rend_inst_count
      collision_instance_count += self.model_instances[-1].coll_inst_count
    
    print("Stored Render Section Instance Count: " + str(self.render_section_instance_count))
    if versionNo > 3: self.render_section_instance_count = render_instance_count
    print("Static Render Section Instance Count: " + str(render_instance_count))
    print("Static Collision Section Instance Count: " + str(collision_instance_count))
    
    render_instance_count = 0
    collision_instance_count = 0
    
    self.dynamic_section_start = self.data.tell()
    print("Dynamic Instance Section Start: " + hex(self.dynamic_section_start))
    self.dynamic_model_instance_count = sread_u32(self.data, self.data.tell())
    print("Dynamic Model Instance Count: " + str(self.dynamic_model_instance_count))
    self.dynamic_model_instances = []
    for i in range(self.dynamic_model_instance_count):
      self.dynamic_model_instances.append(LevelModelInstance(self.data, versionNo, render_instance_count, collision_instance_count))
      render_instance_count += self.dynamic_model_instances[-1].rend_inst_count
      collision_instance_count += self.dynamic_model_instances[-1].coll_inst_count
    
    print("Dynamic Render Section Instance Count: " + str(render_instance_count))
    print("Dynamic Collision Section Instance Count: " + str(collision_instance_count))
    
    self.data.seek(self.block_size + 0x4 + self.entry_offset) # Shouldn't be needed anymore
  
  def save_injected_changes(self, versionNo):
    out_data = BytesIO()
    write_magic_str(out_data, 0x0, "SECT", 4)
    write_u32(out_data, 0x4, 0)
    
    #self.data.seek(self.render_section_start)
    #write_bytes(out_data, out_data.tell(), self.data.read(self.collision_section_start - self.render_section_start))
    write_u32(out_data, out_data.tell(), swap32(len(self.render_sections)))
    for rend_sect in self.render_sections:
      rend_sect.data.seek(rend_sect.entry_offset)
      write_bytes(out_data, out_data.tell(), rend_sect.data.read(rend_sect.data_size))
    
    #self.data.seek(self.collision_section_start)
    #write_bytes(out_data, out_data.tell(), self.data.read(self.static_section_start - self.collision_section_start))
    write_u32(out_data, out_data.tell(), swap32(len(self.collision_sections)))
    for coll_sect in self.collision_sections:
      coll_sect.data.seek(coll_sect.entry_offset)
      write_bytes(out_data, out_data.tell(), coll_sect.data.read(coll_sect.data_size))
    
    
    if versionNo > 3: write_u32(out_data, out_data.tell(), swap32(self.render_section_instance_count))
    #self.data.seek(self.static_section_start)
    #write_bytes(out_data, out_data.tell(), self.data.read(self.dynamic_section_start - self.static_section_start))
    write_u32(out_data, out_data.tell(), swap32(len(self.model_instances)))
    for instance in self.model_instances:
      instance.data.seek(instance.entry_offset)
      write_bytes(out_data, out_data.tell(), instance.data.read(instance.data_size))
    
    #self.data.seek(self.dynamic_section_start)
    #write_bytes(out_data, out_data.tell(), self.data.read((self.block_size + 0x4 + self.entry_offset) - self.dynamic_section_start))
    
    write_u32(out_data, out_data.tell(), swap32(len(self.dynamic_model_instances)))
    for instance in self.dynamic_model_instances:
      write_bytes(out_data, out_data.tell(), instance.save_changes(versionNo).read())
    
    out_data.seek(0)
    self.block_size = data_len(out_data) - 0x8
    write_u32(out_data, 0x4, swap32(self.block_size))
    out_data.seek(0)
    return out_data

class CollisionSection:
  def __init__(self, data = None):
    self.data = data
    self.entry_offset = 0
    self.data_size = 0
    self.bounding_floats = [0.0]*6
    self.coll_geom_count = 0
    self.collision_geometry = []
    if self.data == None: return

    self.entry_offset = self.data.tell()
    #Local space section bounds: x,x y,y z,z
    self.bounding_floats = [sread_float(self.data, self.data.tell()) for _ in range(6)]
    #print(self.bounding_floats)
    #for i in range(6): self.bounding_floats = self.bounding_floats + [sread_float(self.data, self.data.tell())]
    
    #print("")
    self.coll_geom_count = sread_u32(self.data, self.data.tell())
    for i in range(self.coll_geom_count):
      self.collision_geometry.append(CollisionGeometry(self.data))
    self.data_size = self.data.tell() - self.entry_offset
  
  def inject_changes(self, mesh_data, minVec, maxVec):
    self.bounding_floats = list(minVec[:]) + list(maxVec[:])
    original_geometry = self.collision_geometry
    self.collision_geometry = []
    for groupIndex in mesh_data.keys():
      #og = original_geometry[groupIndex]
      #mesh_data[groupIndex]["layer"] = og.layer_mask
      #mesh_data[groupIndex]["verts"] = og.vertices
      #mesh_data[groupIndex]["edges"] = og.edges
      #mesh_data[groupIndex]["faces"] = [(og.tri_vert_indices[i], og.tri_edge_indices[i], og.tri_normals[i]) for i in range(len(og.tri_vert_indices))]

      group = CollisionGeometry()
      group.inject_changes(mesh_data[groupIndex])
      self.collision_geometry.append(group)
    self.coll_geom_count = len(self.collision_geometry)

  def save_changes(self):
    output = BytesIO()
    for f in range(6): write_float(output, output.tell(), swapfloat(self.bounding_floats[f]))
    write_u32(output, output.tell(), swap32(self.coll_geom_count))
    for geom in self.collision_geometry:
      output.write(geom.save_changes().read())
    self.entry_offset = 0
    self.data = output
    self.data_size = data_len(self.data)
    self.data.seek(0)

  def get_geometry_per_section(self):
    added_offset = 0
    vertex_groups = []
    for i in range(self.coll_geom_count):
      geom = self.collision_geometry[i]
      adjusted_indices_flat = [ind + added_offset for face in geom.tri_vert_indices for ind in face]
      adjusted_indices = [adjusted_indices_flat[f:f+3] for f in range(0, len(adjusted_indices_flat), 3)]
      #print("Vertices...")
      #print(geom.vertices)
      #print("Normals...")
      #print(geom.tri_normals)
      adjusted_vertices = [v[0:3] for v in geom.vertices]
      adjusted_normals = [n[0:3] for n in geom.tri_normals]
      added_offset += geom.vertex_count
      if i == 0:
        section_vertices = adjusted_vertices
        section_triNormals = adjusted_normals
        section_indices = adjusted_indices
      else:
        section_vertices.extend(adjusted_vertices)
        section_triNormals.extend(adjusted_normals)
        section_indices.extend(adjusted_indices)
      vertex_groups.append(adjusted_indices_flat)
    return section_vertices, section_indices, section_triNormals, vertex_groups, [geo.layer_mask for geo in self.collision_geometry]

class CollisionGeometry:
  def __init__(self, data = None):
    self.data = data
    self.entry_offset = 0
    self.layer_mask = 0x003e00
    self.vertex_count = 0
    self.vertices = []
    self.edge_count = 0
    self.edges = []
    self.triangle_count = 0
    self.tri_vert_indices = []
    self.tri_edge_indices = []
    self.tri_normals = []
    self.bsp_count = 0
    self.bsp_root = None
    if self.data == None: return

    self.entry_offset = self.data.tell()
    
    self.layer_mask = sread_u32(self.data, self.data.tell())
    #breakpoint at 00224654 and check s3+0x1C
    #print(f"%08x" % self.layer_mask)
    
    #Vertex Section
    self.vertex_count = sread_u16(self.data, self.data.tell())
    _v = []
    for v in range(self.vertex_count):
      for vf in range(4):
        _v.append(sread_float(self.data, self.data.tell()))
    self.vertices = [_v[i:i+4] for i in range(0, len(_v), 4)]
    
    #Edge Section
    self.edge_count = sread_u16(self.data, self.data.tell())
    _edges = []
    for e in range(self.edge_count * 2):
      _edges.append(sread_u16(self.data, self.data.tell()))
    self.edges = [_edges[i:i+2] for i in range(0, len(_edges), 2)]
    
    #Triangle Section
    self.triangle_count = sread_u16(self.data, self.data.tell())
    _tri_vert_indices = []
    _tri_edge_indices = []
    _tri_normals = []
    for t in range(self.triangle_count):
      for tv in range(3):
        _tri_vert_indices.append(sread_u16(self.data, self.data.tell()))
      for te in range(3):
        _tri_edge_indices.append(sread_u16(self.data, self.data.tell()))
      for tn in range(4):
        _tri_normals.append(sread_float(self.data, self.data.tell()))
    self.tri_vert_indices = [_tri_vert_indices[i:i+3] for i in range(0, len(_tri_vert_indices), 3)]
    self.tri_edge_indices = [_tri_edge_indices[i:i+3] for i in range(0, len(_tri_edge_indices), 3)]
    self.tri_normals = [_tri_normals[i:i+4] for i in range(0, len(_tri_normals), 4)]
    
    
    #BSP Section
    #print("--LOADED--")
    tri_list = []
    self.bsp_root = self.load_collision_bsp(1, tri_list)
    #print(tri_list)
    #print("Collision Section: " + str(s) + " Part: " + str(g) + " Vertex Count: " + str(self.vertex_count) + " Triangle Count: " + str(self.triangle_count) + " Edge Count: " + str(self.edge_count) + " BSP Count: " + str(self.bsp_count))
  
  class CollisionBSPNode:
    def __init__(self, bsp_tri_count, bsp_tris, nodeA=None, nodeB=None):
      self.triangle_count = bsp_tri_count
      self.triangles = bsp_tris
      self.nodeA = nodeA
      self.nodeB = nodeB
  
  def load_collision_bsp(self, count=1, tri_list = []):
    if self.bsp_count < count:
      self.bsp_count = count
    nodeA = None
    nodeB = None
    
    bsp_triangle_count = sread_u32(self.data, self.data.tell())
    _bsp_tris = []
    for i in range(bsp_triangle_count):
      _bsp_tris.append(sread_u16(self.data, self.data.tell()))
    bsp_tris = _bsp_tris
    
    tri_list.append(bsp_tris)
    
    unk_1_cond = sread_u32(self.data, self.data.tell())
    unk_2_cond = sread_u32(self.data, self.data.tell())
    if unk_1_cond != 0:
      nodeA = self.load_collision_bsp(count + 1, tri_list)
    if unk_2_cond != 0:
      nodeB = self.load_collision_bsp(count + 1, tri_list)
    return self.CollisionBSPNode(bsp_triangle_count, bsp_tris, nodeA, nodeB)
  
  def construct_collision_bsp(self, node, count=1, tri_list = []):
    if not node: return None
    if (not node['front']) and (not node['back']) and (not node['triangles_on_plane']): return None
    if self.bsp_count < count: self.bsp_count = count
    bsp_tris = []
    if node['triangles_on_plane']:
      bsp_tris = [tri.index for tri in node['triangles_on_plane']]
    tri_list.append(bsp_tris)
    bsp_triangle_count = len(bsp_tris)
    nodeA = None
    nodeB = None
    if node['front']:
      nodeA = self.construct_collision_bsp(node['front'], count + 1, tri_list)
    if node['back']:
      nodeB = self.construct_collision_bsp(node['back'], count + 1, tri_list)
    return self.CollisionBSPNode(bsp_triangle_count, bsp_tris, nodeA, nodeB)
  
  def save_bsp(self, node, output):
    write_u32(output, output.tell(), swap32(node.triangle_count))
    for index in node.triangles: write_u16(output, output.tell(), swap16(index))
    write_u32(output, output.tell(), swap32(int(node.nodeA != None)))
    write_u32(output, output.tell(), swap32(int(node.nodeB != None)))
    if node.nodeA != None:
      self.save_bsp(node.nodeA, output)
    if node.nodeB != None:
      self.save_bsp(node.nodeB, output)
  
  def save_changes(self):
    output = BytesIO()
    write_u32(output, output.tell(), swap32(self.layer_mask))

    write_u16(output, output.tell(), swap16(self.vertex_count))
    for vert in self.vertices:
      for vf in range(4): write_float(output, output.tell(), swapfloat(vert[vf]))
    
    write_u16(output, output.tell(), swap16(self.edge_count))
    for edge in self.edges:
      for index in edge: write_u16(output, output.tell(), swap16(index))
    
    write_u16(output, output.tell(), swap16(self.triangle_count))
    for t in range(self.triangle_count):
      for index in self.tri_vert_indices[t]: write_u16(output, output.tell(), swap16(index))
      for index in self.tri_edge_indices[t]: write_u16(output, output.tell(), swap16(index))
      for vf in range(4): write_float(output, output.tell(), swapfloat(self.tri_normals[t][vf]))
    
    self.save_bsp(self.bsp_root, output)
    output.seek(0)
    return output

  def inject_changes(self, mesh_data):
    self.layer_mask = mesh_data["layer"]
    self.vertices = mesh_data["verts"]
    self.vertex_count = len(self.vertices)
    self.edges = mesh_data["edges"]
    self.edge_count = len(self.edges)
    for vert_indices, edge_indices, tri_norm in mesh_data["faces"]:
      self.tri_vert_indices.append(vert_indices)
      self.tri_edge_indices.append(edge_indices)
      self.tri_normals.append(tri_norm)
    self.triangle_count = len(self.tri_vert_indices)

    tris = [[list(self.vertices[ind][0:3]) for ind in ind_tri] for ind_tri in self.tri_vert_indices]
    #tris = [tris[i:i+3] for i in range(0, len(tris), 3)]
    self.bsp_count = 0
    print("--CONSTRUCTED--")
    tri_list = []
    self.bsp_root = self.construct_collision_bsp(BSPTree(tris).root, 1, tri_list)
    print(tri_list)

class RenderSection:
  def __init__(self, data=None, materials=None):
    self.data = data
    self.color_maps = 0
    self.bounding_floats = [0.0]*6
    self.sub_mesh_count = 0
    self.submeshes = []
    self.data_size = 0
    if data == None: return
    
    self.entry_offset = self.data.tell()
    
    self.color_maps = sread_u32(self.data, self.data.tell())
    #Local space section bounds: x,x y,y z,z
    self.bounding_floats = [sread_float(self.data, self.data.tell()) for _ in range(6)]
    #for i in range(6): self.bounding_floats = self.bounding_floats + [sread_float(self.data, self.data.tell())]
    self.sub_mesh_count = sread_u32(self.data, self.data.tell())
    self.submeshes = []
    for i in range(self.sub_mesh_count):
      geom = RenderedGeometry(materials, self.color_maps, self.data)
      self.submeshes.append(geom)
    self.data_size = self.data.tell() - self.entry_offset
  
  def inject_changes(self, mesh_data, color_channels, minVec, maxVec, materials):
    self.color_maps = color_channels
    self.bounding_floats = list(minVec[:]) + list(maxVec[:])
    self.sub_mesh_count = len(mesh_data)
    self.submeshes = []
    for mat_index in mesh_data:
      geom = RenderedGeometry()
      geom.inject_changes(mat_index, mesh_data[mat_index], materials, self.color_maps)
      self.submeshes.append(geom)
  
  def save_changes(self):
    output = BytesIO()
    write_u32(output, output.tell(), swap32(self.color_maps))
    for f in range(6): write_float(output, output.tell(), swapfloat(self.bounding_floats[f]))
    write_u32(output, output.tell(), swap32(self.sub_mesh_count))
    for submesh in self.submeshes: output.write(submesh.save_changes().read())
    self.entry_offset = 0
    self.data = output
    self.data_size = data_len(self.data)
    self.data.seek(0)
  
  def get_section_geometry(self):
    material_uvs = {}
    section_colors = None
    if self.color_maps > 0:
      section_colors = [] #[[] for _ in range(self.color_maps)]
    added_offset = 0
    uv_offset = 0
    face_offset = 0
    vertex_groups = []
    for submesh_vertices, submesh_normals, submesh_uvs, submesh_colors, submesh_faces, submesh_material_index, submesh_groups in self.get_submesh_geometry():
      if not submesh_material_index in material_uvs: material_uvs[submesh_material_index] = (face_offset, uv_offset, len(submesh_faces), submesh_uvs)
      adjusted_indices_flat = [ind + added_offset for face in submesh_faces for ind in face]
      submesh_groups = [[ind + added_offset for ind in group] for group in submesh_groups]
      vertex_groups.extend(submesh_groups)
      adjusted_indices = [adjusted_indices_flat[f:f+3] for f in range(0, len(adjusted_indices_flat), 3)]
      if added_offset == 0:
        section_vertices = submesh_vertices.copy()
        section_normals = submesh_normals.copy()
        section_faces = adjusted_indices
        for sc, submesh_color in enumerate(submesh_colors):
          while sc >= len(section_colors): section_colors.append([])
          section_colors[sc].extend(submesh_color)
      else:
        section_vertices.extend(submesh_vertices)
        section_normals.extend(submesh_normals)
        section_faces.extend(adjusted_indices)
        for sc, submesh_color in enumerate(submesh_colors):
          while sc >= len(section_colors): section_colors.append([])
          section_colors[sc].extend(submesh_color)
      #vertex_groups.append(adjusted_indices_flat)
      added_offset += len(submesh_vertices)
      face_offset += len(submesh_faces)
      if len(submesh_uvs) > 0: uv_offset += len(submesh_uvs[0])
    return section_vertices, section_normals, section_faces, section_colors, material_uvs, vertex_groups
  
  def get_submesh_geometry(self):
    output = []
    for i, submesh in enumerate(self.submeshes):
      submesh_vertices, submesh_normals, submesh_uvs, submesh_colors, submesh_faces, vertex_groups, submesh_offset = submesh.get_geometry_per_submesh()
      output.append((submesh_vertices, submesh_normals, submesh_uvs, submesh_colors, submesh_faces, submesh.material_index, vertex_groups))
    return output

class RenderedGeometry:
  class GeomEntry:
    def __init__(self, data=None, material=None, color_maps=0):
      self.data = data
      self.vertex_count = 0
      self.vertices = []
      self.faces = []
      self.normals = None
      self.uvs = None
      self.uv_maps = None
      self.colors = []
      self.color_maps = []
      self.face_data = []
      if data == None: return
      
      self.vertex_count = sread_u32(self.data, self.data.tell())
      #if self.vertex_count == 0: print("Vertex count ERROR AT: " + hex(self.data.tell()))
      
      _v = []
      for v in range(self.vertex_count):
        for vf in range(3): _v.append(sread_float(self.data, self.data.tell()))
        self.face_data.append(sread_u32(self.data, self.data.tell()))
      self.vertices = [_v[i:i+3] for i in range(0, len(_v), 3)]
      
      flip = True
      for f in range(2, len(self.face_data)):
        flip = self.add_face(self.faces, f, self.face_data[f], flip)
        #flip = self.reset_winding(self.face_data[f], flip)
      
      _n = None
      if material.normals:
        _n = []
        for v in range(self.vertex_count):
          for vf in range(3):
            _n.append(sread_float(self.data, self.data.tell()))
      if _n != None:
        self.normals = [_n[i:i+3] for i in range(0, len(_n), 3)]
      else:
        self.normals = [0,1,0]*self.vertex_count
        self.normals = [self.normals[i:i+3] for i in range(0, len(self.normals), 3)]
      
      self.colors = [[] for _ in range(color_maps)]
      self.color_maps = [[] for _ in range(color_maps)]
      for m in range(material.mat_properties):
        for vc in range(color_maps):
          for v in range(self.vertex_count):
            self.colors[vc].append([read_u8(self.data, self.data.tell()) for c in range(3)] +
                                   [read_u8(self.data, self.data.tell())])# << 1])
      for c, colors in enumerate(self.colors):
        if len(colors) < 1: break
        self.color_maps[c] = []
        for face in self.faces: self.color_maps[c].extend([list((Vector(colors[face[0]]) / 255.0)[:]),
                                                           list((Vector(colors[face[1]]) / 255.0)[:]),
                                                           list((Vector(colors[face[2]]) / 255.0)[:])])
      
      self.uv_maps = None
      if material.uv_maps > 0:
        self.uv_maps = []
        self.uvs = []
        for m in range(material.uv_maps):
          _uv_map = []
          for v in range(self.vertex_count):
            _uv_map.append([sread_float(self.data, self.data.tell()), sread_float(self.data, self.data.tell())])
          self.uvs.append(_uv_map)
          uv_map = []
          for face in self.faces:
            uv_map.append(_uv_map[face[0]])
            uv_map.append(_uv_map[face[1]])
            uv_map.append(_uv_map[face[2]])
          self.uv_maps.append(uv_map)
    
    def inject_changes(self, mesh_data, material):
      v_data, n_data, uv_data, col_data = mesh_data
      
      self.vertex_count = len(v_data)
      self.face_data = []
      self.vertices = []
      for v in range(self.vertex_count):
        self.vertices.extend(list(v_data[v][0][:]))
        self.face_data.append(v_data[v][1])
      self.vertices = [self.vertices[i:i+3] for i in range(0, len(self.vertices), 3)]
      
      flip = True
      self.faces = []
      for f in range(2, len(self.face_data)):
        flip = self.add_face(self.faces, f, self.face_data[f], flip)
      
      if material.normals:
        _n = []
        for v in range(self.vertex_count):
          _n.extend(list(n_data[v][:]))
        self.normals = [_n[i:i+3] for i in range(0, len(_n), 3)]
      
      self.colors = [[] for _ in range(len(col_data))]
      self.color_maps = [[] for _ in range(len(col_data))]
      for m in range(material.mat_properties):
        for vc, col_chan in enumerate(col_data):
          for v in range(self.vertex_count):
            self.colors[vc].append([int(c * 255) for c in col_chan[v]])
      for c, colors in enumerate(self.colors):
        if len(colors) < 1: break
        self.color_maps[c] = []
        for face in self.faces: self.color_maps[c].extend([list((Vector(colors[face[0]]) / 255.0)[:]),
                                                           list((Vector(colors[face[1]]) / 255.0)[:]),
                                                           list((Vector(colors[face[2]]) / 255.0)[:])])
      
      self.uv_maps = None
      if material.uv_maps > 0:
        self.uv_maps = []
        self.uvs = []
        for m in range(material.uv_maps):
          _uv_map = []
          for v in range(self.vertex_count):
            _uv_map.append(list(uv_data[m][v][:]))
          self.uvs.append(_uv_map)
          uv_map = []
          for face in self.faces:
            uv_map.append(_uv_map[face[0]])
            uv_map.append(_uv_map[face[1]])
            uv_map.append(_uv_map[face[2]])
          self.uv_maps.append(uv_map)
    
    def save_changes(self):
      output = BytesIO()
      
      write_u32(output, output.tell(), swap32(self.vertex_count))
      for v in range(self.vertex_count):
        for vf in range(3): write_float(output, output.tell(), swapfloat(self.vertices[v][vf]))
        write_u32(output, output.tell(), swap32(self.face_data[v]))
      
      if self.normals != None:
        for norm in self.normals:
          for nf in range(3): write_float(output, output.tell(), swapfloat(norm[nf]))
      
      for color_map in self.colors:
        for color in color_map:
          for c8 in color[0:3]: write_u8(output, output.tell(), c8)
          write_u8(output, output.tell(), color[3])# >> 1)
      
      if self.uvs != None:
        for uv_map in self.uvs:
          for uv in uv_map:
            for uf in range(2): write_float(output, output.tell(), swapfloat(uv[uf]))
      
      output.seek(0)
      return output
    
    def add_face(self, faces, fc, face_data, flip):
      if (face_data & 0x8000): return True#flip
      fa = max(0, fc - 2)
      fb = max(0, fc - 1)
      flip = (fc % 2) != 0
      if fc >= 2:
        if not flip: faces.append([fa, fb, fc])
        else: faces.append([fb, fa, fc])#([fa, fc, fb])
      return not flip
    
    def reset_winding(self, face_data, flip):
      if (face_data & 0x8000): return True
      return flip
  
  def __init__(self, materials=None, color_maps=None, data=None):
    self.data = data
    self.color_maps = color_maps
    self.material_index = 0
    self.material = None
    self.unk_1 = 0
    self.geom_count = 0
    self.geometry = []
    if data == None: return
    
    self.material_index = sread_u16(self.data, self.data.tell())
    material = materials[self.material_index]
    self.material = material
    self.unk_1 = sread_u16(self.data, self.data.tell())
    if self.unk_1 != 0:
      #print("Weird LOD related section at: " + hex(self.data.tell()))
      if (material.lod_flags & 0x80000000) != 0:
        unk_vals = [sread_float(self.data, self.data.tell()) for c in range(8)]
        #self.data.seek(self.data.tell() + (0x8 * 0x4)) #TODO: Actually read data here
      else:
        unk_vals = [sread_float(self.data, self.data.tell()) for c in range(8)]
        #self.data.seek(self.data.tell() + 0x20) # But apparently don't read data here
      print(unk_vals)
    
    self.geom_count = sread_u32(self.data, self.data.tell())
    self.geometry = []
    for g in range(self.geom_count):
      geom = self.GeomEntry(self.data, material, color_maps)
      self.geometry.append(geom)
  
  def inject_changes(self, mat_index, mesh_data, materials=None, color_maps=0):
    self.color_maps = color_maps
    self.material_index = mat_index
    self.material = materials[self.material_index]
    self.geom_count = len(mesh_data)
    self.geometry = []
    for group_index in mesh_data.keys():
      group_data = mesh_data[group_index]
      verts = []
      norms = []
      uvs = []
      cols = []
      for v_data, n_data, uv_data, col_data in group_data:
        vert_len = len(verts) + len(v_data)
        if vert_len > 64 or len(verts) == 64:
          strip_data = (verts, norms, uvs, cols)
          geom = self.GeomEntry()
          geom.inject_changes(strip_data, self.material)
          self.geometry.append(geom)
          verts = []
          norms = []
          uvs = []
          cols = []
        verts.extend(v_data)
        norms.extend(n_data)
        for uv_chan, uv in enumerate(uv_data):
          while uv_chan >= len(uvs): uvs.append([])
          uvs[uv_chan].extend(uv)
        for col_chan, col in enumerate(col_data):
          while col_chan >= len(cols): cols.append([])
          cols[col_chan].extend(col)
      strip_data = (verts, norms, uvs, cols)
      #for strip_data in group_data:
      geom = self.GeomEntry()
      geom.inject_changes(strip_data, self.material)
      self.geometry.append(geom)
    self.geom_count = len(self.geometry)
  
  def save_changes(self):
    output = BytesIO()
    write_u16(output, output.tell(), swap16(self.material_index))
    write_u16(output, output.tell(), 0)
    write_u32(output, output.tell(), swap32(self.geom_count))
    for geom in self.geometry: output.write(geom.save_changes().read())
    output.seek(0)
    return output
  
  def get_geometry_per_submesh(self, index_offset = 0):
    added_offset = 0
    submesh_uvs = []
    if self.color_maps > 0:
      #submesh_colors = [[] for _ in range(self.color_maps)]
      submesh_colors = []
    else: submesh_colors = []
    vertex_groups = []
    for i, geom in enumerate(self.geometry):
      adjusted_indices_flat = [ind + index_offset + added_offset for face in geom.faces for ind in face]
      vertex_groups.append(adjusted_indices_flat)
      adjusted_indices = [adjusted_indices_flat[f:f+3] for f in range(0, len(adjusted_indices_flat), 3)]
      added_offset += geom.vertex_count
      if i == 0:
        submesh_vertices = geom.vertices.copy()
        submesh_normals = geom.normals.copy()
        submesh_indices = adjusted_indices
        for c, col in enumerate(geom.color_maps):
          while c >= len(submesh_colors): submesh_colors.append([])
          submesh_colors[c].extend(col)
        if geom.uv_maps != None:
          for m in range(len(geom.uv_maps)):#self.material.mat_properties):
            uv_index = m
            uv_index = self.material.properties[m].uv - 1 # These could be wrong
            if uv_index < 0: continue
            submesh_uvs.append(geom.uv_maps[uv_index].copy())
      else:
        submesh_vertices.extend(geom.vertices)
        submesh_normals.extend(geom.normals)
        submesh_indices.extend(adjusted_indices)
        for c, col in enumerate(geom.color_maps):
          while c >= len(submesh_colors): submesh_colors.append([])
          submesh_colors[c].extend(col)
        if geom.uv_maps != None:
          for m in range(len(geom.uv_maps)):#self.material.mat_properties):
            uv_index = m
            uv_index = self.material.properties[m].uv - 1 # These could be wrong
            if uv_index < 0: continue
            submesh_uvs[m].extend(geom.uv_maps[uv_index]) # TODO: Make sure indexing via material property byte 3 is correct
    
    return submesh_vertices, submesh_normals, submesh_uvs, submesh_colors, submesh_indices, vertex_groups, added_offset

class LevelModelInstance:
  class GeometryInstance:
    def __init__(self, inst_index, sect_index, _min, _max):#, _min = np.array([0,0,0,0]), _max = np.array([0,0,0,0])):
      self.index = inst_index
      self.sect_index = sect_index
      self.min = _min
      self.max = _max
  
  def __init__(self, data, versionNo, render_instance_count = 0, collision_instance_count = 0):
    self.data = data
    self.object_type = "GeometryInstance"
    self.effects = 0
    self.vertex_color_index = 0
    self.rend_inst_count = 0
    self.render_instances = []
    self.coll_inst_count = 0
    self.collision_instances = []
    self.transform = Matrix()
    self.inv_transform = self.transform.inverted_safe()
    if data == None: return
    
    self.entry_offset = self.data.tell()
    _m = [sread_float(self.data, self.data.tell()) for _ in range(4 * 4)]
    _m = [_m[i:i+4] for i in range(0, len(_m), 4)]
    self.transform = Matrix(_m).transposed()
    self.inv_transform = self.transform.inverted_safe()
    
    self.vertex_color_index = sread_u32(self.data, self.data.tell())
    if versionNo >= 3:
      self.effects = sread_u32(self.data, self.data.tell()) # So far only zero
      #if self.effects != 0: print("Model Instance Effects " + hex(self.effects))
    
    self.rend_inst_count = sread_u32(self.data, self.data.tell())
    for i in range(self.rend_inst_count):
      if versionNo < 4: rend_inst_index = render_instance_count + i
      else: rend_inst_index = sread_u32(self.data, self.data.tell()) # Apparently not used for dynamic instances?
      rend_sect_index = sread_u32(self.data, self.data.tell())
      vec1 = Vector([sread_float(self.data, self.data.tell()) for _ in range(3)])
      vec2 = Vector([sread_float(self.data, self.data.tell()) for _ in range(3)])
      #vec1 = self.inv_transform @ vec1
      #vec2 = self.inv_transform @ vec2
      vlist = vec1[:] + vec2[:]
      minVec = Vector([min([vlist[e], vlist[e+3]]) for e in range(3)])#vec1
      maxVec = Vector([max([vlist[e], vlist[e+3]]) for e in range(3)])#vec2
      self.render_instances.append(self.GeometryInstance(rend_inst_index, rend_sect_index, minVec, maxVec))
    
    self.coll_inst_count = sread_u32(self.data, self.data.tell())
    for i in range(self.coll_inst_count):
      coll_inst_index = collision_instance_count + i
      coll_sect_index = sread_u32(self.data, self.data.tell())
      vec1 = Vector([sread_float(self.data, self.data.tell()) for _ in range(3)])
      vec2 = Vector([sread_float(self.data, self.data.tell()) for _ in range(3)])
      #vec1 = self.inv_transform @ vec1
      #vec2 = self.inv_transform @ vec2
      vlist = vec1[:] + vec2[:]
      minVec = Vector([min([vlist[e], vlist[e+3]]) for e in range(3)])#vec1
      maxVec = Vector([max([vlist[e], vlist[e+3]]) for e in range(3)])#vec2
      
      #minVec = np.minimum(vec1, vec2)
      #maxVec = np.maximum(vec1, vec2)
      #diffVec = (minVec + maxVec) * 0.5 - minVec
      #minRt = np.sqrt(diffVec[0] * diffVec[0] + diffVec[1] * diffVec[1] + diffVec[2] * diffVec[2])
      #maxRt = np.sqrt(diffVec[0] * diffVec[0] + diffVec[2] * diffVec[2])
      #minVec = np.array(minVec.tolist() + [minRt])
      #maxVec = np.array(maxVec.tolist() + [maxRt])
      #World space instance bounds x,y,z x,y,z
      #print("Collision Instance Bounds Center: " + str((vec1 + vec2) * 0.5))
      #print("Collision Instance Transform: " + str(self.transform[3][0:3]))
      #print("")
      self.collision_instances.append(self.GeometryInstance(coll_inst_index, coll_sect_index, minVec, maxVec))
    
    self.data_size = self.data.tell() - self.entry_offset
  
  def save_changes(self, versionNo):
    inst_data = BytesIO()
    
    transform = self.transform.transposed()
    _m = [transform[i][j] for i in range(4) for j in range(4)]
    for f in _m: write_float(inst_data, inst_data.tell(), swapfloat(f))
    
    write_u32(inst_data, inst_data.tell(), swap32(self.vertex_color_index))
    if versionNo >= 3: write_u32(inst_data, inst_data.tell(), swap32(self.effects))
    
    write_u32(inst_data, inst_data.tell(), swap32(len(self.render_instances)))
    for render_instance in self.render_instances:
      if versionNo >= 4: write_u32(inst_data, inst_data.tell(), swap32(render_instance.index))
      write_u32(inst_data, inst_data.tell(), swap32(render_instance.sect_index))
      for f in render_instance.min[:]: write_float(inst_data, inst_data.tell(), swapfloat(f))
      for f in render_instance.max[:]: write_float(inst_data, inst_data.tell(), swapfloat(f))
    write_u32(inst_data, inst_data.tell(), swap32(len(self.collision_instances)))
    for collision_instance in self.collision_instances:
      write_u32(inst_data, inst_data.tell(), swap32(collision_instance.sect_index))
      for f in collision_instance.min[:]: write_float(inst_data, inst_data.tell(), swapfloat(f))
      for f in collision_instance.max[:]: write_float(inst_data, inst_data.tell(), swapfloat(f))
    
    inst_data.seek(0)
    return inst_data

class PVS:
  def __init__(self, geometrySection, versionNo, data=None):
    self.data = data
    self.entry_offset = 0
    self.block_size = 0
    self.vertex_count = 0
    self.portal_cells_count = 0
    self.vertices = []
    self.portal_cells = []
    self.transform = Matrix()
    if data == None: return
    
    self.entry_offset = self.data.tell()
    self.block_size = sread_u32(self.data, self.data.tell())
    
    self.vertex_count = sread_u32(self.data, self.data.tell())
    for i in range(self.vertex_count * 4):
      self.vertices.append(sread_float(self.data, self.data.tell()))
    self.vertices = [self.vertices[i:i+4] for i in range(0, len(self.vertices), 4)]
    
    if len(self.vertices) > 0:
      self.setup_transform()
    
    self.portal_cells_count = sread_u32(self.data, self.data.tell())
    for i in range(self.portal_cells_count):
      self.portal_cells.append(PortalCell(geometrySection, versionNo, self.data))
  
  def setup_transform(self):
    avgVertex = Vector([0.0, 0.0, 0.0])
    for vertex in self.vertices: avgVertex += Vector(vertex[0:3])
    avgVertex /= len(self.vertices)
    self.transform[3] = Vector([avgVertex.x, avgVertex.y, avgVertex.z, 1.0])
    self.transform = self.transform.transposed()
    invtransform = self.transform.inverted_safe()
    
    self.vertices = [list((invtransform @ Vector(vertex[0:3]))[:]) for vertex in self.vertices]
  
  def save_changes(self):
    pvs_data = BytesIO()
    write_u32(pvs_data, 0x0, swap32(len(self.vertices)))
    saved_vertices = [list((self.transform @ Vector(vertex))[:]) for vertex in self.vertices]
    for vertex in saved_vertices:
      for j in range(4): write_float(pvs_data, pvs_data.tell(), swapfloat(vertex[j]))
    write_u32(pvs_data, pvs_data.tell(), swap32(len(self.portal_cells)))
    for cell in self.portal_cells:
      write_u32(pvs_data, pvs_data.tell(), swap32(cell.flags))
      write_u32(pvs_data, pvs_data.tell(), swap32(cell.edge_count))
      for e in range(cell.edge_count):
        for j in range(2): write_u32(pvs_data, pvs_data.tell(), swap32(cell.edge_indices[e][j]))
        for j in range(4): write_float(pvs_data, pvs_data.tell(), swapfloat(cell.edge_planes[e][j]))
        write_u32(pvs_data, pvs_data.tell(), swap32(cell.edge_neighbors[e]))
    pvs_data.seek(0)
    return pvs_data
  
  def validate(self):
    self.portal_cells_count = len(self.portal_cells)
    if self.portal_cells_count == 0: return
    
    for cell in self.portal_cells:
      if cell.edge_count < 1: continue
      for j in range(cell.edge_count-1):
        v1 = self.vertices[cell.edge_indices[j][0]]
        v2 = self.vertices[cell.edge_indices[j][1]]
        v3 = self.vertices[cell.edge_indices[j+1][0]]
        zdiff1 = v2[2] - v1[2]
        zdiff2 = v3[2] - v1[2]
        ydiff1 = v2[1] - v1[1]
        ydiff2 = v3[1] - v1[1]
        xdiff = v3[0] - v1[0]
        val = zdiff1 * xdiff - zdiff2 * (ydiff1 * zdiff2 - ydiff2 * zdiff1)
        if val <= 0.0: cell.flags = 0xff
        if val == 0.0: cell.flags = 0x8f
  
  def from_py(self, vertices, faces, geometrySection, versionNo):
    self.vertex_count = len(vertices)
    self.vertices = vertices
    self.portal_cells_count = len(faces)
    for face in faces:
      cell = PortalCell(geometrySection, versionNo)
      cell.from_py(face, geometrySection)
      self.map_cells.append(cell)
  
  def get_bpymesh(self):
    from collections import deque
    
    map_edges = []
    face_map = {}
    for c, cell in enumerate(self.portal_cells):
      cell_indices = [i for e in cell.edge_indices for i in e]
      cell_indices = list(set(cell_indices))
      if len(cell_indices) < 3: continue
      
      to_visit = deque()
      to_visit.append(cell.edge_indices[0])
      cell_indices = [cell.edge_indices[0]]
      while to_visit:
        edge = to_visit.popleft()
        next = [p for p in cell.edge_indices if edge[1] in p and not (p in cell_indices or list(reversed(p)) in cell_indices)]
        if len(next) > 0:
          next = next[0]
          if next.index(edge[1]) != 0: next = list(reversed(next))
          to_visit.append(next)
          cell_indices.append(next)
      edge_indices = cell_indices
      cell_indices = [ce[0] for ce in cell_indices]
      
      key = str(list(sorted(cell_indices)))
      if not key in face_map: face_map[key] = [cell_indices, self.portal_cells[c].flags]
      elif not self.portal_cells[c].flags in face_map[key]: face_map[key].append(self.portal_cells[c].flags)
      
      map_edges.extend(edge_indices)
    
    map_edges = [sorted(indices) for indices in map_edges if len(set(indices)) == 2]
    map_cell_flags = [face_map[face_indices][1:] for face_indices in face_map.keys()]
    map_faces = [face_map[face_indices][0] for face_indices in face_map.keys()]
    return self.vertices, map_faces, map_edges, map_cell_flags, self.transform

class PortalCell:
  def __init__(self, geometrySection, versionNo, data=None):
    self.data = data
    self.flags = 0
    self.edge_count = 0
    self.sections_count = 0
    self.node_id_count = 0
    self.grid_cell_id_count = 0
    self.edge_planes = []
    self.edge_indices = []
    self.edge_neighbors = []
    self.sections = []
    self.node_ids = []
    self.grid_cell_ids = []
    if self.data == None: return
    
    self.flags = sread_u32(self.data, self.data.tell())
    if 0xff < self.flags:
      print("portal cell 'flags' out of range!")
    
    self.edge_count = sread_u32(self.data, self.data.tell())
    if 0xff < self.edge_count:
      print("portal cell 'no_edges' out of range!")
    
    for i in range(self.edge_count):
      for j in range(2):
        self.edge_indices.append(sread_u32(self.data, self.data.tell())) # Edge vertex indices
      for j in range(4):
        self.edge_planes.append(sread_float(self.data, self.data.tell())) # Edge plane (tangent direction xyz and world placement w)
      self.edge_neighbors.append(sread_u32(self.data, self.data.tell())) # Cell neighbor along edge
    self.edge_planes = [self.edge_planes[i:i+4] for i in range(0, len(self.edge_planes), 4)]
    self.edge_indices = [self.edge_indices[i:i+2] for i in range(0, len(self.edge_indices), 2)]
    
    self.sections_count = sread_u32(self.data, self.data.tell())
    if 0xffff < self.sections_count:
      print("portal cell 'no_sections' out of range!")
    
    for i in range(self.sections_count):
      rend_model_index = sread_u16(self.data, self.data.tell())
      rend_inst_index = sread_u16(self.data, self.data.tell())
      global_inst_index = geometrySection.model_instances[rend_model_index].render_instances[rend_inst_index].index
      self.sections = self.sections + [rend_model_index, rend_inst_index, global_inst_index]
    self.sections = [self.sections[i:i+3] for i in range(0, len(self.sections), 3)]
    
    if versionNo < 4:
      self.node_id_count = 0
      #TODO: BuildNodeList
    else:
      self.node_id_count = sread_u32(self.data, self.data.tell())
      if 0xffff < self.node_id_count:
        print("portal cell 'node_id_count' out of range!")
      if self.node_id_count != 0:
        self.node_ids = []
        for i in range(self.node_id_count):
          self.node_ids.append(sread_u16(self.data, self.data.tell()))
       
    if versionNo < 4:
      self.grid_cell_id_count = 0
    else:
      self.grid_cell_id_count = sread_u32(self.data, self.data.tell())
      if self.grid_cell_id_count != 0:
        self.grid_cell_ids = []
        for i in range(self.grid_cell_id_count):
          self.grid_cell_ids.append(sread_u16(self.data, self.data.tell()))
  
  def add_nodes(self, node_buffer, node_count):
    self.node_id_count = node_count
    self.node_ids = []
    for i in range(node_count):
      self.node_ids.append(node_buffer[i])
    #print(f"portal cell node_id_count: %d" % node_count)
  
  def build_node_list(self, node):
    node_count = 0
    node_buffer = [0]*1024
    if self.sections_count == 0:
      self.add_nodes(node_buffer, node_count)
      return
    for i, section in enumerate(self.sections):
      section = self.sections[i]
      if node == None: continue
      foundNode, node_count = self.find_nodes_for_section(node, section, node_buffer, node_count)
    self.add_nodes(node_buffer, node_count)
  
  def find_nodes_for_section(self, node, section, node_buffer, node_count):
    foundNode = False
    if node == None: return foundNode, node_count
    if node.get_section() == section: foundNode = True
    else:
      foundNode, node_count = self.find_nodes_for_section(node.child_node_b, section, node_buffer, node_count)
    if foundNode:
      if node_count != 0:
        for i in range(node_count):
          if node_buffer[i] == node.node_index: foundNode = False
          if not foundNode: break
      if foundNode:
        node_buffer[node_count] = node.node_index
        node_count += 1
    if not foundNode:
      foundNode, node_count = self.find_nodes_for_section(node.child_node_a, section, node_buffer, node_count)
      if not foundNode: return False, node_count
    return foundNode, node_count
  
  def from_py(self, face, geometrySection):
    flags, edges, sections = face
    self.flags = flags
    
    self.edge_count = len(edges)
    for indices, planes, neighbors in edges:
      self.edge_indices.append(indices)
      self.edge_planes.append(planes)
      self.edge_neighbors.append(neighbors)
    
    self.sections_count = len(sections)
    for rend_model_index, rend_inst_index in sections:
      global_inst_index = geometrySection.model_instances[rend_model_index].render_instances[rend_inst_index].index
      self.sections = self.sections + [[rend_model_index, rend_inst_index, global_inst_index]]
    
    #TODO: Nodes and Grid Cells

class NodeTree:
  class NodeEntry:
    def __init__(self, vector, node_index, model_index, model_inst_index, global_inst_index, rnode_a, rnode_b):
      self.vector = vector #TODO: Figure out what these floats are for
      #print(self.vector)
      self.node_index = node_index
      self.model_index = model_index
      self.model_inst_index = model_inst_index
      self.global_inst_index = global_inst_index
      self.child_node_a = rnode_a
      self.child_node_b = rnode_b
    
    def get_section(self):
      return [self.model_index, self.model_inst_index, self.global_inst_index]
  
  def __init__(self, geometrySection, versionNo, data=None):
    self.data = data
    self.entry_offset = 0
    self.block_size = 0
    self.node_count = 0
    self.branch_count = 0
    self.leaf_count = 0
    self.root_node = None
    if self.data == None: return
    
    self.entry_offset = self.data.tell()
    self.block_size = sread_u32(self.data, self.data.tell())
    if versionNo > 3:
      self.node_count = sread_u32(self.data, self.data.tell())
    self.root_node = self.load_nodes(versionNo, geometrySection)
  
  def load_nodes(self, versionNo, geometrySection):
    node = None
    valid_node = sread_u32(self.data, self.data.tell())
    if valid_node == 0: return node
    
    if versionNo < 4:
      node_index = self.node_count
      self.node_count += 1
    else:
      node_index = sread_u16(self.data, self.data.tell())
    
    vector = [sread_float(self.data, self.data.tell()) for i in range(4)]
    #print(vector)
    rend_model_index = sread_u32(self.data, self.data.tell())
    rend_inst_index = sread_u32(self.data, self.data.tell())
    
    if rend_model_index == 0xffffffff or rend_inst_index == 0xffffffff:
      self.branch_count += 1
      global_inst_index = 0xffff
    else:
      self.leaf_count += 1
      global_inst_index = geometrySection.model_instances[rend_model_index].render_instances[rend_inst_index].index
    
    recurse_node_a = self.load_nodes(versionNo, geometrySection)
    recurse_node_b = self.load_nodes(versionNo, geometrySection)
    node = self.NodeEntry(vector, node_index, rend_model_index, rend_inst_index, global_inst_index, recurse_node_a, recurse_node_b)
    return node

class Grid:
  def __init__(self, data=None):
    self.data = data
    self.entry_offset = 0
    self.block_size = 0
    self.width = 0
    self.depth = 0
    self.scale = 1.0
    self.unk_f1 = 0.0
    self.unk_f2 = 0.0
    self.cells = []
    if self.data == None: return
    
    self.entry_offset = self.data.tell()
    self.block_size = sread_u32(self.data, self.data.tell())
    self.width = sread_u32(self.data, self.data.tell())
    self.depth = sread_u32(self.data, self.data.tell())
    self.scale = sread_float(self.data, self.data.tell())
    self.unk_f1 = sread_float(self.data, self.data.tell())
    self.unk_f2 = sread_float(self.data, self.data.tell())
    
    for i in range(self.depth):
      row = []
      for j in range(self.width):
        cell_size = sread_u32(self.data, self.data.tell())
        sects = []
        for c in range(cell_size):
          cell_short_1 = sread_u16(self.data, self.data.tell())
          cell_short_2 = sread_u16(self.data, self.data.tell())
          sects.append((cell_short_1, cell_short_2))
        
        cell_size_b = sread_u32(self.data, self.data.tell())
        ints = []
        for c in range(cell_size_b):
          cell_int = sread_u32(self.data, self.data.tell())
          ints.append(cell_int)
        row.append((sects, ints))
      self.cells.append(row)
    self.cells = [cell for row in reversed(self.cells) for cell in row]
  
  def get_bpymesh(self):
    return self.width, self.width, self.scale, self.unk_f1, self.unk_f2, [int(len(sects) > 0) + int(len(ints) > 0)*2 for sects, ints in self.cells]

def pj(s1, s2):
  return os.path.join(s1, s2)

class Models:
  def __init__(self, asset_root):
    self.p2m_path = os.path.join(asset_root, "MODELS")
    self.p2s_path = os.path.join(asset_root, "SKELS")
    self.p2m_directory = {}
    self.populate_directory()
  
  def populate_directory(self): #GetMesh__9MESH_LISTPc
    self.p2m_directory["MeshActor"] = []
    self.p2m_directory["LevelExit"] = [(pj("PICKUPS", "EXIT"),)] # Notably also adds a light
    self.p2m_directory["LevelExitPorts"] = [(pj("SKYS", "THRUPORT"),), (pj("SKYS", "ENDPORT"),)] # Branch type (if level id is 19 (0x13))
    self.p2m_directory["Health"] = [(pj("PICKUPS", "HEALTH"),)]
    self.p2m_directory["Treasure_A"] = [(pj("PICKUPS", "TREASH_A"),)]
    self.p2m_directory["BeaconEnergy"] = [(pj("PICKUPS", "BENERGY"),), (pj("PICKUPS", "BENERGY2"),), (pj("PICKUPS", "BENERGY3"),)]
    self.p2m_directory["Barrel"] = [(pj("CRATES", "T_BARREL"), "Spawn"), (pj("CRATES", "BARREL"), "Spawn")] # Branch type
    self.p2m_directory["BarrelDebris"] = [(pj("CRATES", "BARRELB1"),), (pj("CRATES", "BARRELB2"),), (pj("CRATES", "BARRELB3"),), (pj("CRATES", "BARRELID"),)]
    self.p2m_directory["SteelBarrel"] = [(pj("CRATES", "STEEL_T"), "Spawn"), (pj("CRATES", "BARSTEEL"), "Spawn")] # Branch type
    self.p2m_directory["SteelBarrelDebris"] = [(pj("CRATES", "STEEL_B1"),), (pj("CRATES", "STEEL_B2"),), (pj("CRATES", "STEEL_B3"),), (pj("CRATES", "STEEL_LD"),)]
    self.p2m_directory["TntBarrel"] = [(pj("CRATES", "TNT_NEW"),)]
    self.p2m_directory["TntBarrelDebris"] = [(pj("CRATES", "TNTNEWB1"),), (pj("CRATES", "TNTNEWB2"),), (pj("CRATES", "TNTNEWB3"),), (pj("CRATES", "TNTNEWLD"),)]
    self.p2m_directory["CrateSmash"] = [(pj("CRATES", "SMASH"),)]
    self.p2m_directory["CrateSmashDebris"] = [(pj("CRATES", "SMABIT1"),), (pj("CRATES", "SMABIT2"),), (pj("CRATES", "SMABIT3"),), (pj("CRATES", "SMABIT4"),)]
    self.p2m_directory["MorphButton"] = [(pj("MORPH", "SWITCHBS"),), (pj("MORPH", "SWITCHHN"),)]
    self.p2m_directory["JumpPad"] = [(pj("MORPH", "MORPHPAD"),)]
    self.pad_dict = { "PowerGauntlets" : 1, "Hyper" : 2, "HighJump" : 3, "Switch" : 4, "Glider" : 5 }
    self.p2m_directory["MorphTriggerPad"] = [(pj("MORPH", "MORPHPAD"),), (pj("MORPH", "POWRGLVL"), "Ability"), (pj("MORPH", "SHOE_L"), "Ability"), (pj("MORPH", "JETPACK"), "Ability"), (pj("MORPH", "HAND"), "Ability"), (pj("MORPH", "GLIDER"), "Ability")] # Branch type
    self.p2m_directory["MorphCapstainSwitch"] = [(pj("MORPH", "CAP_BS"),), (pj("MORPH", "CAP_TOP"),)]
    self.p2m_directory["PoundButton"] = [(pj("MORPH", "HBUTBASE"),), (pj("MORPH", "HBUT_TOP"),)]
    self.p2m_directory["SplineFlintsShip"] = [(pj("EFFECTS", "FLINTHUL"),)]
    self.p2m_directory["SplineLongBoat"] = [(pj("EFFECTS", "LONGBOAT"),)]
    self.p2m_directory["SplineLongBoatDebris"] = [(pj("EFFECTS", "LONGBIT1"),), (pj("EFFECTS", "LONGBIT2"),), (pj("EFFECTS", "LONGBIT3"),), (pj("EFFECTS", "LONGBIT4"),)]
    self.p2m_directory["CollectPuzzle"] = [(pj("CRATES", "LANTERN"),)]
    self.p2m_directory["TrickCounter"] = [(pj("PICKUPS", "STUNKPIK"),)]
    self.p2m_directory["FlyingRingShort"] = [(pj("EFFECTS", "RING_1"),)]
    self.p2m_directory["SolarSurferDebris"] = [(pj("SURFER", "SURFMID"),), (pj("SURFER", "SURFNOSE"),), (pj("SURFER", "SURFSBOT"),), (pj("SURFER", "SURFSTOP"),), (pj("SURFER", "SURFTAIL"),)]
    self.p2m_directory["SurferLantern"] = [(pj("CRATES", "LAMPON"),), (pj("CRATES", "LAMP"),)] # Branch type, Notably also adds a light
    self.p2m_directory["SurferZipper"] = [(pj("SURFER", "ZIPPER"),)]
    #self.p2m_directory["SplineMeteor"] = [(pj("EFFECTS", "FIREBALL"),)]
    #self.p2m_directory["AutoGun"] = [(pj("EFFECTS", "FIREBALL"),)]
    #self.p2m_directory["LavaBubbler"] = [(pj("EFFECTS", "FIREBALL"),)]
    #self.p2m_directory["StaticMeltDown"] = [(pj("EFFECTS", "FIREBALL"),)]
    #self.p2m_directory["RoamingMeltDown"] = [(pj("EFFECTS", "FIREBALL"),)]
    self.p2m_directory["StaticSporePod"] = [(pj("EFFECTS", "SPOR_CLS"),), (pj("EFFECTS", "SPOR_OPN"),)] # Branch type
    self.p2m_directory["RoamingElectroBotDebris"] = [(pj("EFFECTS", "BOT_BOD"),), (pj("EFFECTS", "BOT_HEAD"),), (pj("EFFECTS", "BOT_LEG"),), (pj("EFFECTS", "BOT_LEG"),), (pj("EFFECTS", "COG1"),), (pj("EFFECTS", "COG2"),), (pj("EFFECTS", "SPRING1"),), (pj("EFFECTS", "SPRING2"),)]
    #self.p2m_directory["RoamingRobocop"] = [(pj("BADGUY", "ROBTRACK"),)]
    #self.p2m_directory["RoamingRoboStealth"] = [(pj("BADGUY", "ROBTRACK"),)]
    self.p2m_directory["RoamingLongSword"] = [(pj("BADGUY", "LSWORD"),)]
    #self.p2m_directory["Scroop"] = [(pj("SURFER", "ZIPPER"),)]
    #self.p2m_directory["SilverBoss"] = [(pj("SILVER","FLAME"),), (pj("SILVER","CANNON"),), (pj("SILVER","BUZZSAW"),), (pj("SILVER","BUZBLADE"),), (pj("SILVER","SWORD"),), (pj("SILVER","GRENADE"),), (pj("SILVER","COPTER"),), (pj("SILVER","BUZZARM"),)] # Branch type
    
    # Extra (inaccurate model assignments)
    self.p2m_directory["CutsceneShot"] = [(pj("PICKUPS", "CHECKCAM"),)]

class ActorInfoListEntry:
  def __init__(self, data, class_entry, enums_entry, cstring_entry, astring_entry, pstring_entry, ai_maps, splines, models):
    self.ClassesEntry = class_entry
    self.EnumsEntry = enums_entry
    self.AStringEntry = astring_entry
    self.CStringEntry = cstring_entry
    self.PStringEntry = pstring_entry
    self.data = data
    self.entry_offset = 0
    self.block_size = 0
    self.count = 0
    self.ai_maps = ai_maps
    self.splines = splines
    self.models = models
    self.actors = []
    
    self.enums = {}
    for enum in self.EnumsEntry.enums:
      enumString = self.CStringEntry.table[enum.string_index]
      if not enumString in self.enums:
        self.enums[enumString] = []
      for eVal in enum.val_string_indexes:
        self.enums[enumString].append(self.CStringEntry.table[eVal])
    
    if self.data == None: return
    
    self.entry_offset = self.data.tell()
    self.block_size = sread_s32(self.data, self.data.tell())
    self.count = sread_s32(self.data, self.data.tell())
    if self.count > 0:
      for i in range(self.count):
        self.actors.append(ActorInfoEntry(self, self.data))
      for i in range(self.count): self.actors[i].populateParamValues(self.enums) # Separated from actor creation on purpose
    self.data.seek(self.entry_offset + 0x4 + self.block_size)
  
  def save_changes(self):
    out_data = BytesIO()
    write_magic_str(out_data, 0x0, "AINF", 4)
    write_u32(out_data, 0x4, 0)
    write_u32(out_data, 0x8, swap32(len(self.actors)))
    for actor in self.actors: write_bytes(out_data, out_data.tell(), actor.save_changes())
    out_data.seek(0)
    self.block_size = data_len(out_data) - 0x8
    write_u32(out_data, 0x4, swap32(self.block_size))
    out_data.seek(0)
    return out_data
  
  def create_new_actor(self, transform, class_name):
    actor = ActorInfoEntry(self)
    actor.transform = transform
    actor.change_class(class_name)
    self.actors.append(actor)
    return actor
  
  def getParamDict(self, actor, force_func_params=False, classNames=None):
    paramsToAdd = []
    for param in actor.params:
      if param.parent_param == None and not (param.overwritten or param.added) and (param.type != 6 or (param.type == 6 and param.next_count > 0)):
        paramsToAdd.append(param.string)
    #params = {"Actor Name" : {"value" : classNames[classNames.index(actor.name)]}}
    params = {"Actor Name" : {"hierarchy" : "Actor Name", "actor_value" : actor.name}}
    params["Actor Unused Parameters"] = {"hierarchy" : "Actor Unused Parameters", "actor_value" : paramsToAdd}
    current_parent = None
    current_parent_count = actor.param_count
    current_funcbox = None
    previous_funcbox = None
    current_funcbox_children = None
    previous_parent_count = 0
    for p, param in enumerate(actor.params):
      hierarchy = []
      parent_loop = param
      while parent_loop != None:
        hierarchy = [parent_loop.string] + hierarchy
        parent_loop = parent_loop.parent_param
      hierarchy = ":".join(hierarchy)
      if not ":" in hierarchy: hierarchy = ":" + hierarchy
      
      if current_parent_count >= previous_parent_count:
        if param.type != 6:
          if param.overwritten or param.added:
            if param.type == 2:
              if current_funcbox_children != None: current_funcbox_children[hierarchy] = {"hierarchy" : hierarchy, "value" : param.value}
              else: params[hierarchy] = {"hierarchy" : hierarchy, "value" : param.value}
              if current_funcbox != None: current_funcbox[param.string] = (1, param.type)
            elif param.type == 0:
              if current_funcbox_children != None: current_funcbox_children[hierarchy] = {"hierarchy" : hierarchy, "value" : param.value}
              else: params[hierarchy] = {"hierarchy" : hierarchy, "value" : param.value}
              if current_funcbox != None: current_funcbox[param.string] = (1, param.type)
            elif param.type == 3:
              if current_funcbox_children != None: current_funcbox_children[hierarchy] = {"hierarchy" : hierarchy, "value" : param.value}
              else: params[hierarchy] = {"hierarchy" : hierarchy, "value" : param.value}
              if current_funcbox != None: current_funcbox[param.string] = (1, param.type)
            elif param.type == 4:
              enum_index = 0
              enumbox = {}
              enumbox["hierarchy"] = hierarchy
              enumbox["list"] = []
              if param.string in self.enums:
                for e, enumVal in enumerate(self.enums[param.string]):
                  enumbox["list"].append(enumVal)
                  if param.value == enumVal: enum_index = e
              enumbox["value"] = enum_index
              if current_funcbox_children != None: current_funcbox_children[hierarchy] = enumbox
              else: params[hierarchy] = enumbox
              if current_funcbox != None: current_funcbox[param.string] = (1, param.type)
            elif param.type == 5:
              sel = 0
              if param.loaded_value != 0xFFFFFFFF: sel = param.loaded_value + 1
              actorbox = {"hierarchy" : hierarchy, "rlist" : 3, "value" : sel}
              if current_funcbox_children != None: current_funcbox_children[hierarchy] = actorbox
              else: params[hierarchy] = actorbox
              if current_funcbox != None: current_funcbox[param.string] = (1, param.type)
            elif param.type == 8:
              splinebox = {"hierarchy" : hierarchy, "rlist" : 0, "value" : param.loaded_value}
              if current_funcbox_children != None: current_funcbox_children[hierarchy] = splinebox
              else: params[hierarchy] = splinebox
              if current_funcbox != None: current_funcbox[param.string] = (1, param.type)
            elif param.type == 9:
              geombox = {"hierarchy" : hierarchy, "rlist" : 1, "value" : param.loaded_value}
              if current_funcbox_children != None: current_funcbox_children[hierarchy] = geombox
              else: params[hierarchy] = geombox
              if current_funcbox != None: current_funcbox[param.string] = (1, param.type)
            elif param.type == 10:
              aimapbox = {"hierarchy" : hierarchy, "rlist" : 2, "value" : param.loaded_value}
              if current_funcbox_children != None: current_funcbox_children[hierarchy] = aimapbox
              else: params[hierarchy] = aimapbox
              if current_funcbox != None: current_funcbox[param.string] = (1, param.type)
            else:
              if current_funcbox_children != None: current_funcbox_children[hierarchy] = {"hierarchy" : hierarchy, "value" : param.value}
              else: params[hierarchy] = {"hierarchy" : hierarchy, "value" : param.value}
              if current_funcbox != None: current_funcbox[param.string] = (1, param.type)
          elif current_funcbox != None and param.parent_param == current_parent:
            current_funcbox[param.string] = (0, param.type)
        elif current_funcbox != None and param.parent_param == current_parent and param.next_count > 0:
          cost = 0
          if (param.overwritten or param.added): cost = param.loaded_param_count
          current_funcbox[param.string] = (cost, param.type)
          
      if param.type == 6 and (param.overwritten or param.added):# or force_func_params):
        current_parent = param
        #preserve old param
        previous_parent_count = current_parent_count
        previous_funcbox = current_funcbox
        previous_funcbox_children = current_funcbox_children
        if current_parent.loaded_param_count > 0 or force_func_params:
          if not force_func_params:
            current_parent_count += current_parent.loaded_param_count
          else: current_parent_count += current_parent.next_count
          current_funcbox = {}
          current_funcbox_children = {}
          #current_funcbox[param.string] = "Add Parameter..."#.append(param.string + " Add Parameter...")
          params[hierarchy] = {"hierarchy" : hierarchy, "value": current_funcbox}#.append(current_funcbox)
          params[hierarchy + "_Children"] = current_funcbox_children#.append(current_funcbox_children)
      
      if current_parent_count == previous_parent_count and current_parent != None:# and current_parent.parent_param != None:
        #restore old param
        current_parent = current_parent.parent_param
        current_funcbox = previous_funcbox
        current_funcbox_children = previous_funcbox_children
      
      current_parent_count -= 1
      if current_parent_count < 0:
        current_parent_count = 0
      if current_parent_count < previous_parent_count:
        previous_parent_count = current_parent_count
    return params

class ActorInfoEntry:
  def __init__(self, actorList, data=None):
    self.actorList = actorList
    self.data = data
    self.entry_offset = -1
    self.object_type = "Actor"
    
    if data == None:
      self.a_string_index = 0
      self.class_index = 0xffff
      self.name = ""
      self.transform = Matrix()
      self.param_count = 0
      self.params = []
      return
    
    self.entry_offset = self.data.tell()
    self.a_string_index = sread_u16(self.data, self.data.tell())
    self.name = self.actorList.AStringEntry.table[self.a_string_index]
    self.class_index = self.getPropertyIndex(self.actorList.ClassesEntry.classes, self.name)
    if self.class_index == 0xffff:
      self.class_index = self.getPropertyIndex(self.actorList.ClassesEntry.classes, self.name + "Actor")
    
    _m = [sread_float(self.data, self.data.tell()) for _ in range(4 * 4)]
    _m = [_m[i:i+4] for i in range(0, len(_m), 4)]
    self.transform = Matrix(_m).transposed()
    
    self.param_count = sread_u16(self.data, self.data.tell())
    self.params = []
    # END OF CLASS SECTION: The first 68(0x44) bytes of each Actor's info
    
    # vvv BEGINNING PARAMETERS SECTION vvv
    if self.class_index == 0xffff: self.loadParams(False, False, self.param_count, 0)
    else:
      self.params = self.defaultParams(self.class_index)
      self.loadParams(self.params != None, self.params != None, self.param_count, self.class_index)
  
  def save_changes(self):
    out_data = BytesIO()
    write_u16(out_data, out_data.tell(), swap16(self.a_string_index))
    transform = self.transform.transposed()
    _m = [transform[i][j] for i in range(4) for j in range(4)]
    for f in _m: write_float(out_data, out_data.tell(), swapfloat(f))
    write_u16(out_data, out_data.tell(), swap16(self.param_count))
    if len(self.params) > 0:
      saved_params, full_count = self.save_params(0, self.param_count)
      for saved_param in saved_params:
        write_u16(out_data, out_data.tell(), swap16(saved_param[0]))
        write_u8(out_data, out_data.tell(), saved_param[1])
        write_u8(out_data, out_data.tell(), saved_param[2])
        write_u32(out_data, out_data.tell(), swap32(saved_param[3]))
    out_data.seek(0)
    return out_data.read()
  
  def change_class(self, newClassName):
    self.name = newClassName
    self.class_index = self.getPropertyIndex(self.actorList.ClassesEntry.classes, self.name)
    if self.class_index == 0xffff:
      self.name = self.name + "Actor"
      self.class_index = self.getPropertyIndex(self.actorList.ClassesEntry.classes, self.name)
    if self.class_index == 0xffff:
      print(self.name)
      return
    if self.name not in self.actorList.AStringEntry.table:
      self.a_string_index = len(self.actorList.AStringEntry.table)
      self.actorList.AStringEntry.table.append(self.name)
    else: self.a_string_index = self.actorList.AStringEntry.table.index(self.name)
    self.param_count = 0
    self.params.clear()
    self.params = self.defaultParams(self.class_index)
    self.populateParamValues(self.actorList.enums)
  
  def add_parameter(self, lookup):
    out_param = None
    matching_param = None
    if type(lookup) == int:
      matching_param = self.params[lookup]
    else:
      hierarchy = lookup
      for param in self.params:
        h = len(hierarchy)-1
        parent_loop = param
        matching_nest = True
        while parent_loop != None and h >= 0:
          if parent_loop.string != hierarchy[h]:
            matching_nest = False
            break
          parent_loop = parent_loop.parent_param
          h -= 1
        if matching_nest:
          matching_param = param
          break
    if matching_param != None and (matching_param.type != 6 or (matching_param.type == 6 and matching_param.next_count > 0)):
      if not (matching_param.overwritten or matching_param.added):
        parent_loop = matching_param
        child_new = False
        while parent_loop != None:
          if not (parent_loop.overwritten or parent_loop.added):
            parent_loop.overwritten = True
            if parent_loop.string not in self.actorList.AStringEntry.table:
              parent_loop.a_string_index = len(self.actorList.AStringEntry.table)
              self.actorList.AStringEntry.table.append(parent_loop.string)
            else: parent_loop.a_string_index = self.actorList.AStringEntry.table.index(parent_loop.string)
            child_new = True
          else: child_new = False
          if child_new:
            if parent_loop.parent_param != None:
              parent_loop.parent_param.loaded_param_count += 1
            else: self.param_count += 1
          parent_loop = parent_loop.parent_param
        out_param = matching_param
    return out_param
  
  def find_param(self, par_name):
    out_param = None
    for param in self.params:
      if (param.parent_param == None or (param.parent_param != None and param.parent_param.string == par_name)) and param.string == par_name:
        out_param = param
        break
    return out_param
  
  def save_params(self, param_index, param_count):
    saved_data = []
    i = 0
    p = 0
    while i < param_count:
      param = self.params[param_index + p]
      p += 1
      if not (param.overwritten or param.added): continue
      i += 1
      saved_data = saved_data + [[param.a_string_index, param.type, param.loaded_param_count, param.loaded_value]]
      if param.type == 6 and param.loaded_param_count == 0: continue
      function_saved_data, count = self.save_params(param_index + p, param.loaded_param_count)
      saved_data = saved_data + function_saved_data
      p += count
    return saved_data, p
  
  def get_models(self):
    name = self.name
    models = []
    
    if not name in self.actorList.models.p2m_directory: return models
    if not os.path.isdir(self.actorList.models.p2m_path): return models
    
    directory = self.actorList.models.p2m_directory[name]
    for param in self.params:
      if param.type == 3:
        if "MeshFilename" in param.string:
          file_path = str(param.value).upper().split('\\')
          if len(file_path) == 1:
            file_path = file_path[0].split('/')
          models.append(pj(self.actorList.models.p2m_path, pj(file_path[0], file_path[1])))
    if len(directory) > 1:
      for i, model_file in enumerate(directory):
        ind = i
        model_param = None
        if len(model_file) > 1:
          for param in self.params:
            if param.string == model_file[1]:
              model_param = param
              break
        if model_param:
          if model_param.type == 4:
            enum_ind = self.actorList.enums[model_param.string].index(model_param.value)
            if model_param.string == "Spawn": ind = 1 - int(enum_ind - 2 < 2)
            if model_param.string == "Ability" and model_param.value in self.actorList.models.pad_dict: ind = self.actorList.models.pad_dict[model_param.value]
        if ind == i:
          models.append(pj(self.actorList.models.p2m_path, model_file[0] + ".P2M"))
    elif len(directory) > 0:
      models.append(pj(self.actorList.models.p2m_path, directory[0][0] + ".P2M"))
    return models
  
  def loadParams(self, has_params_1, has_params_2, param_count, class_index, parent_param = None):
    if param_count == 0:
      return
    
    for i in range(param_count):
      param_string_index = sread_u16(self.data, self.data.tell())
      param_type = read_u8(self.data, self.data.tell())
      next_param_count = read_u8(self.data, self.data.tell())
      param_value = sread_u32(self.data, self.data.tell())
      
      param = ActorParameterEntry(self, self.actorList.AStringEntry, class_index, param_string_index, param_type, next_param_count, param_value, parent_param)
      param.a_string_index = param_string_index
      if has_params_1 or has_params_2:
        param_string = self.actorList.AStringEntry.table[param_string_index]
        prop_index, inherit_type = self.getParam(param_string, class_index)
        param.loadClassProperty(prop_index, inherit_type)
      
      found_matching = False
      for d_param in self.params:
        w_param1 = d_param
        w_param2 = param
        matching_nest = True
        while not (w_param1.parent_param == None or w_param2.parent_param == None):
          w_param1 = w_param1.parent_param
          w_param2 = w_param2.parent_param
          if w_param1.string != w_param2.string:
            matching_nest = False
            break
        
        if matching_nest and d_param.string == param.string and d_param.type == param.type and (d_param.parent_param == None or d_param.parent_param.overwritten):# and d_param.next_count >= param.next_count:
          d_param.a_string_index = param.a_string_index
          d_param.loaded_value = param.loaded_value
          d_param.overwritten = True
          found_matching = True
          if d_param.type == 0x6:
            d_param.loaded_param_count = next_param_count
          break
      if not found_matching:
        param.added = True
        self.params.append(param)
      
      if not (has_params_1 or has_params_2) and next_param_count:
        self.loadParams(False, False, next_param_count, 0, param)
      elif (has_params_1 or has_params_2) and next_param_count:
        if param.type == 6:
          next_class_index = class_index
          #next_class_index = param.property_class_ref if param.property_class_ref != 0xffff else class_index
          self.loadParams(has_params_1, has_params_2, next_param_count, next_class_index, param)
        else:
          self.loadParams(False, False, next_param_count, 0, param)
  
  def defaultParams(self, class_index, parent_param=None):
    input_class = self.actorList.ClassesEntry.classes[class_index]
    parent_class = None
    par_class_prop_count = 0
    if input_class.par_index != 0xffff:
      parent_class = self.actorList.ClassesEntry.classes[input_class.par_index]
      par_class_prop_count = parent_class.properties_count1
    
    prop_1 = []
    if input_class.par_index != 0xffff:
      properties = parent_class.properties_type1
      for i in range(par_class_prop_count):
        if (properties[i].type == 0x5 or properties[i].type == 0x4) and properties[i].value == 0:
          properties[i].value = 0xffff
        if properties[i].type == 0x6:
          param_class_count = self.actorList.ClassesEntry.classes[properties[i].class_ref].properties_count1 + self.actorList.ClassesEntry.classes[properties[i].class_ref].properties_count2
          def_param = ActorParameterEntry(self, self.actorList.CStringEntry, input_class.par_index, properties[i].string_index, properties[i].type, param_class_count, properties[i].value, parent_param)
          prop_1 = prop_1 + [def_param]
          r_prop_1 = self.defaultParams(properties[i].class_ref, def_param)
          prop_1 = prop_1 + r_prop_1
        else:
          param_class_count = self.actorList.ClassesEntry.classes[properties[i].class_ref].properties_count1 + self.actorList.ClassesEntry.classes[properties[i].class_ref].properties_count2
          def_param = ActorParameterEntry(self, self.actorList.CStringEntry, input_class.par_index, properties[i].string_index, properties[i].type, param_class_count, properties[i].value, parent_param)
          prop_1 = prop_1 + [def_param]
      
      properties = parent_class.properties_type2
      for i in range(parent_class.properties_count2):
        if (properties[i].type == 0x5 or properties[i].type == 0x4) and properties[i].value == 0:
          properties[i].value = 0xffff
        if properties[i].type == 0x6:
          param_class_count = self.actorList.ClassesEntry.classes[properties[i].class_ref].properties_count1 + self.actorList.ClassesEntry.classes[properties[i].class_ref].properties_count2
          def_param = ActorParameterEntry(self, self.actorList.CStringEntry, input_class.par_index, properties[i].string_index, properties[i].type, param_class_count, properties[i].value, parent_param)
          prop_1 = prop_1 + [def_param]
          r_prop_1 = self.defaultParams(properties[i].class_ref, def_param)
          prop_1 = prop_1 + r_prop_1
        else:
          param_class_count = self.actorList.ClassesEntry.classes[properties[i].class_ref].properties_count1 + self.actorList.ClassesEntry.classes[properties[i].class_ref].properties_count2
          def_param = ActorParameterEntry(self, self.actorList.CStringEntry, input_class.par_index, properties[i].string_index, properties[i].type, param_class_count, properties[i].value, parent_param)
          prop_1 = prop_1 + [def_param]
    
    properties = input_class.properties_type1
    for i in range(input_class.properties_count1):
      if (properties[i].type == 0x5 or properties[i].type == 0x4) and properties[i].value == 0:
          properties[i].value = 0xffff
      if properties[i].type == 0x6:
        param_class_count = self.actorList.ClassesEntry.classes[properties[i].class_ref].properties_count1 + self.actorList.ClassesEntry.classes[properties[i].class_ref].properties_count2
        def_param = ActorParameterEntry(self, self.actorList.CStringEntry, class_index, properties[i].string_index, properties[i].type, param_class_count, properties[i].value, parent_param)
        prop_1 = prop_1 + [def_param]
        r_prop_1 = self.defaultParams(properties[i].class_ref, def_param)
        prop_1 = prop_1 + r_prop_1
      else:
        param_class_count = self.actorList.ClassesEntry.classes[properties[i].class_ref].properties_count1 + self.actorList.ClassesEntry.classes[properties[i].class_ref].properties_count2
        def_param = ActorParameterEntry(self, self.actorList.CStringEntry, class_index, properties[i].string_index, properties[i].type, param_class_count, properties[i].value, parent_param)
        prop_1 = prop_1 + [def_param]
    
    properties = input_class.properties_type2
    for i in range(input_class.properties_count2):
      if (properties[i].type == 0x5 or properties[i].type == 0x4) and properties[i].value == 0:
          properties[i].value = 0xffff
      if properties[i].type == 0x6:
        param_class_count = self.actorList.ClassesEntry.classes[properties[i].class_ref].properties_count1 + self.actorList.ClassesEntry.classes[properties[i].class_ref].properties_count2
        def_param = ActorParameterEntry(self, self.actorList.CStringEntry, class_index, properties[i].string_index, properties[i].type, param_class_count, properties[i].value, parent_param)
        prop_1 = prop_1 + [def_param]
        r_prop_1 = self.defaultParams(properties[i].class_ref, def_param)
        prop_1 = prop_1 + r_prop_1
      else:
        param_class_count = self.actorList.ClassesEntry.classes[properties[i].class_ref].properties_count1 + self.actorList.ClassesEntry.classes[properties[i].class_ref].properties_count2
        def_param = ActorParameterEntry(self, self.actorList.CStringEntry, class_index, properties[i].string_index, properties[i].type, param_class_count, properties[i].value, parent_param)
        prop_1 = prop_1 + [def_param]
    return prop_1
  
  def getParam(self, _param_string, class_index):
    param_string = _param_string
    while True:
      base_class = self.actorList.ClassesEntry.classes[class_index]
      parent_class = self.actorList.ClassesEntry.classes[base_class.par_index]
      if base_class.par_index != 0xffff and parent_class.properties_count1 > 0:
        prop_index = self.getPropertyIndex(parent_class.properties_type1, param_string)
        if prop_index != 0xffff:
          return prop_index, 0
      
      if base_class.properties_count1 > 0:
        prop_index = self.getPropertyIndex(base_class.properties_type1, param_string)
        if prop_index != 0xffff:
          return prop_index, 1
      
      set_flag_skip = False
      if base_class.par_index != 0xffff and parent_class.properties_count2 > 0:
        prop_index = self.getPropertyIndex(parent_class.properties_type2, param_string)
        if prop_index != 0xffff:
          return prop_index, 2
          #set_flag_skip = True
      
      if set_flag_skip == False:
        if base_class.properties_count2 < 1:
          return -1, 0
        prop_index = self.getPropertyIndex(base_class.properties_type2, param_string)
        if prop_index == 0xffff:
          return -1, 1
        else:
          return prop_index, 3
      param_string = "Flags"  
  
  def populateParamValues(self, enumDict):
    for param in self.params:
      param.value = self.paramTypeSwitch(param.type, param.loaded_value, param.property_value, param.next_count)
      if param.type != 4: continue
      
      if param.string not in enumDict:
        enumDict[param.string] = []
      if not param.value in enumDict[param.string]:
        enumDict[param.string].append(param.value)
  
  def getPropertyIndex(self, properties, string):
    for p in range(len(properties)):
      prop_string = self.actorList.CStringEntry.table[properties[p].string_index]
      if prop_string == string:
        return p
    return 0xffff
  
  def paramTypeSwitch(self, param_type, param_value, property_value, param_count=0):
    result = 0xffff
    if param_type == 0:
      result = u32_to_float(param_value)#"{:.3f}".format(u32_to_float(param_value)).replace("-0.000", "0.000").rstrip("0").rstrip(".")
    elif param_type == 8:
      result = param_value
    elif param_type == 3:
      if param_value < len(self.actorList.PStringEntry.table):
        result = self.actorList.PStringEntry.table[param_value]
      else: result = ""
    elif param_type == 2:
      result = param_value == 1
    elif param_type == 4:
      if param_value < 0xffff:
        param_val_string = self.actorList.AStringEntry.table[param_value & 0xffff]
        result = param_val_string
      else:
        result = "NULL"
      #enum = self.actorList.EnumsEntry.enums[property_value]
      #enum_vals = enum.val_string_indexes
      #r_enum_index = 0
      #for e in range(enum.count):
      #  enum_val_string = self.actorList.CStringEntry.table[enum_vals[e]]
      #  if param_val_string == enum_val_string:
      #    r_enum_index = e
      #    break
      
    elif param_type == 5:
      if param_value < 0xffff:
        result = self.actorList.actors[param_value].name + " (" + str(param_value) + ")"
      else:
        result = "NULL"
    elif param_type == 9:
      result = param_value# | 0x8000000)
    elif param_type == 10:
      result = param_value
    elif param_type == 7:
      result = "Unsupported Param Type"
    elif param_type == 6:
      result = "Default Param Count: " + str(param_count)
    else:
      result = hex(param_value)
    return result

class ActorParameterEntry:
  def __init__(self, actor, StringEntry, class_index, string_index, _type, next_param_count, loaded_val, parent_param):
    self.actor = actor
    self.class_index = class_index
    self.parent_index = 0xffff
    self.base_class = None
    self.parent_class = None
    self.parent_param = parent_param
    self.base_class = self.actor.actorList.ClassesEntry.classes[self.class_index]
    self.parent_index = self.base_class.par_index
    if self.parent_index != 0xffff:
      self.parent_class = self.actor.actorList.ClassesEntry.classes[self.parent_index]
    
    self.string_index = string_index
    self.string = StringEntry.table[self.string_index]
    self.type = _type
    self.next_count = next_param_count
    self.loaded_value = loaded_val
    self.value = self.loaded_value
    
    self.overwritten = False
    self.added = False
    self.loaded_param_count = 0
    
    self.property_index = 0xffff
    self.inherit_type = 0xffff
    self.property_type = 0x7
    self.property_value = 0xffffffff
    self.property_class_ref = 0xffff
  
  def copy(self):
    out = ActorParameterEntry(self.actor, self.actor.actorList.AStringEntry, self.class_index, self.a_string_index, self.type, self.next_count, self.loaded_value, self.parent_param)
    out.a_string_index = self.a_string_index
    out.string_index = self.string_index
    out.value = self.value
    out.overwritten = self.overwritten
    out.added = self.added
    out.loaded_param_count = self.loaded_param_count
    out.property_index = self.property_index
    out.inherit_type = self.inherit_type
    out.property_type = self.property_type
    out.property_value = self.property_value
    out.property_class_ref = self.property_class_ref
    return out
  
  def add_parameter(self, new_name):
    out_param = None
    for param in self.actor.params:
      if param.string != new_name or param.parent_param != self: continue
      out_param = param
      if (param.overwritten or param.added): continue
      param.parent_param.loaded_param_count += 1
      if param.string not in self.actor.actorList.AStringEntry.table:
        param.a_string_index = len(self.actor.actorList.AStringEntry.table)
        self.actor.actorList.AStringEntry.table.append(param.string)
      else: param.a_string_index = self.actor.actorList.AStringEntry.table.index(param.string)
      param.overwritten = True
    return out_param
  
  def loadClassProperty(self, property_index, inherit_type):
    self.property_index = property_index & 0xffff
    self.inherit_type = inherit_type
    c_property = None
    
    if self.parent_index != 0xffff and self.inherit_type == 0:
      if self.property_index < self.parent_class.properties_count1:
        c_property = self.parent_class.properties_type1[self.property_index]
    if self.inherit_type == 1:
      if self.property_index < self.base_class.properties_count1:
        c_property = self.base_class.properties_type1[self.property_index]
    if self.parent_index != 0xffff and self.inherit_type == 2:
      if self.property_index < self.parent_class.properties_count2:
        c_property = self.parent_class.properties_type2[self.property_index]
    if self.inherit_type == 3:
      if self.property_index < self.base_class.properties_count2:
        c_property = self.base_class.properties_type2[self.property_index]
    
    if c_property != None:
      self.property_type = c_property.type
      self.property_value = c_property.value
      self.property_class_ref = c_property.class_ref

class AIMapListEntry:
  def __init__(self, data = None):
    self.data = data
    self.block_size = 0
    self.type = 0
    self.count = 0
    self.maps = []
    if self.data == None: return
    
    self.entry_offset = self.data.tell()
    self.block_size = sread_s32(self.data, self.data.tell())
    self.type = sread_u32(self.data, self.data.tell()) # Probably don't have to store, since the existence of any blocked edges would imply what type it is
    self.count = sread_u32(self.data, self.data.tell())
    for i in range(self.count): self.maps.append(AIMapEntry(self.data, self.type))
    self.data.seek(self.entry_offset + 0x4 + self.block_size)
  
  def save_changes(self):
    out_data = BytesIO()
    write_magic_str(out_data, 0x0, "AIMP", 4)
    write_u32(out_data, 0x4, 0x0)
    write_u32(out_data, 0x8, swap32(self.type))
    write_u32(out_data, 0xC, swap32(len(self.maps)))
    for _map in self.maps: write_bytes(out_data, out_data.tell(), _map.save_changes())
    out_data.seek(0)
    self.block_size = data_len(out_data) - 0x8
    write_u32(out_data, 0x4, swap32(self.block_size))
    out_data.seek(0)
    return out_data
  
  def add_map(self, vertices, faces):
    self.type = 2
    aimap = AIMapEntry(None, self.type)
    aimap.from_py(vertices, faces)
    self.maps.append(aimap)
    self.count = len(self.maps)
  
  def get_edgeplanes(self):
    planes = []
    for m in self.maps:
      planes.append(m.get_edgeplanes())
    return planes
  
  def get_bpymaps(self):
    maps = []
    for m in self.maps:
      maps.append(m.get_bpymesh())
    return maps

class AIMapEntry: #TODO Potentially make it possible to create AIMaps based on the collision geometry, within user specified regions
  class AIMapCell: #TODO Make operators for toggling the blocked state of cells(faces) and edges
    def __init__(self, data = None, _type = 0):
      self.type = _type
      self.object_type = "AIMap Cell"
      self.data = data
      self.cell_flags = 0
      self.edge_count = 0
      self.edge_planes = []
      self.edge_indices = []
      self.edge_neighbors = []
      self.edge_flags = []
      if self.data == None: return
      
      self.cell_flags = sread_u32(self.data, self.data.tell()) # Cell blocked flag (Store as face attribute)
      self.edge_count = sread_u32(self.data, self.data.tell())
      for i in range(self.edge_count):
        # Edge vertex indices
        for j in range(2): self.edge_indices.append(sread_u32(self.data, self.data.tell())) 
        # Edge blocked flag (Store as 2 separate edge attributes to account for cell sharedness)
        if (self.type & 2) != 0: self.edge_flags.append(sread_u32(self.data, self.data.tell()))
        #if self.edge_flags[-1] != 0: print("Edge flag: " + str(self.edge_flags[-1]))
        # Edge plane (tangent direction xyz and world placement w)
        for j in range(4): self.edge_planes.append(sread_float(self.data, self.data.tell()))
        self.edge_neighbors.append(sread_u32(self.data, self.data.tell())) # Cell neighbor along edge
      self.edge_planes = [self.edge_planes[i:i+4] for i in range(0, len(self.edge_planes), 4)]
      self.edge_indices = [self.edge_indices[i:i+2] for i in range(0, len(self.edge_indices), 2)]
    
    def from_py(self, face):
      flags, edges = face
      self.cell_flags = flags
      self.edge_count = len(edges)
      for indices, flags, planes, neighbors in edges:
        self.edge_indices.append(indices)
        self.edge_flags.append(flags)
        self.edge_planes.append(planes)
        self.edge_neighbors.append(neighbors)
  
  def __init__(self, data = None, _type = 0):
    self.object_type = "AIMap"
    self.type = _type
    self.data = data
    self.vertex_count = 0
    self.vertices = []
    self.cell_count = 0
    self.map_cells = []
    self.transform = Matrix()
    if self.data == None: return
    
    self.vertex_count = sread_u32(self.data, self.data.tell())
    vertex_array = [sread_float(self.data, self.data.tell()) for _ in range(self.vertex_count * 4)]
    self.vertices = [vertex_array[i:i+4] for i in range(0, len(vertex_array), 4)]
    
    self.setup_transform()
    
    self.cell_count = sread_u32(self.data, self.data.tell())
    for i in range(self.cell_count): self.map_cells.append(self.AIMapCell(self.data, self.type))
    #print(str([cell.edge_count for cell in self.map_cells]))
  
  def setup_transform(self):
    avgVertex = Vector([0.0, 0.0, 0.0])
    for vertex in self.vertices: avgVertex += Vector(vertex[0:3])
    avgVertex /= len(self.vertices)
    self.transform[3] = Vector([avgVertex.x, avgVertex.y, avgVertex.z, 1.0])
    self.transform = self.transform.transposed()
    invtransform = self.transform.inverted_safe()
    
    self.vertices = [list((invtransform @ Vector(vertex[0:3]))[:]) for vertex in self.vertices]
  
  def save_changes(self):
    map_data = BytesIO()
    write_u32(map_data, 0x0, swap32(len(self.vertices)))
    saved_vertices = [list((self.transform @ Vector(vertex))[:]) for vertex in self.vertices]
    for vertex in saved_vertices:
      for j in range(4): write_float(map_data, map_data.tell(), swapfloat(vertex[j]))
    write_u32(map_data, map_data.tell(), swap32(len(self.map_cells)))
    for cell in self.map_cells:
      write_u32(map_data, map_data.tell(), swap32(cell.cell_flags))
      write_u32(map_data, map_data.tell(), swap32(cell.edge_count))
      for e in range(cell.edge_count):
        for j in range(2): write_u32(map_data, map_data.tell(), swap32(cell.edge_indices[e][j]))
        write_u32(map_data, map_data.tell(), swap32(cell.edge_flags[e]))
        for j in range(4): write_float(map_data, map_data.tell(), swapfloat(cell.edge_planes[e][j]))
        write_u32(map_data, map_data.tell(), swap32(cell.edge_neighbors[e]))
    map_data.seek(0)
    return map_data.read()
  
  def from_py(self, vertices, faces):
    self.vertex_count = len(vertices)
    self.vertices = vertices
    #self.setup_transform()
    self.cell_count = len(faces)
    for face in faces:
      cell = self.AIMapCell(None, self.type)
      cell.from_py(face)
      self.map_cells.append(cell)
  
  def get_edgeplanes(self):
    output = []
    #vertices = [self.transform @ Vector(vertex) for vertex in self.vertices]
    vertices = [Vector(vertex) for vertex in self.vertices]
    for c, cell in enumerate(self.map_cells):
      for e, edge in enumerate(cell.edge_indices):
        edge_center = vertices[edge[0]]#(vertices[edge[0]] + vertices[edge[1]]) / 2.0
        edge_planedir = Vector(cell.edge_planes[e][0:3])
        transform = Matrix()
        transform[3] = Vector(list(edge_center[:]) + [1.0])
        transform = transform.transposed()
        transform = transform @ Euler((math.radians(90), 0, 0)).to_matrix().to_4x4() @ edge_planedir.to_track_quat('X', 'Y').to_matrix().transposed().to_4x4()
        output.append(transform)
    return output
  
  def get_bpymesh(self):
    from collections import deque
    
    map_edges = []
    #map_faces = []
    map_corners = []
    face_map = {}
    edges_blocked = []
    f = 0
    for c, cell in enumerate(self.map_cells):
      cell_indices = [i for e in cell.edge_indices for i in e]
      cell_indices = list(set(cell_indices))
      if len(cell_indices) < 3: continue
      
      to_visit = deque()
      to_visit.append(cell.edge_indices[0])
      cell_indices = [cell.edge_indices[0]]
      edge_blocks = [cell.edge_flags[0]]
      while to_visit:
        edge = to_visit.popleft()
        next = [(p, cell.edge_flags[b]) for b, p in enumerate(cell.edge_indices) if edge[1] in p and not (p in cell_indices or list(reversed(p)) in cell_indices)]
        if len(next) > 0:
          next, next_block = next[0]
          if next.index(edge[1]) != 0: next = list(reversed(next))
          to_visit.append(next)
          cell_indices.append(next)
          edge_blocks.append(next_block)
      edge_indices = cell_indices
      cell_indices = [ce[0] for ce in cell_indices]
      
      corner_map = {}
      for e, ei in enumerate(edge_indices):
        for i, iv in enumerate(ei):
          eb = [0, 0] if not iv in corner_map else corner_map[iv]
          if eb[i] == 0: eb[i] = edge_blocks[e]
          corner_map[iv] = eb# + [edge_blocks[e]]
      cell_corners = [corner_map[ckey] for ckey in corner_map.keys()]#cell_indices]
      map_corners.extend(cell_corners)
      
      key = str(list(sorted(cell_indices)))
      if not key in face_map: face_map[key] = [cell_indices, self.map_cells[c].cell_flags]
      elif not self.map_cells[c].cell_flags in face_map[key]: face_map[key].append(self.map_cells[c].cell_flags)
      
      map_edges.extend(edge_indices)
      edges_blocked.extend([((f << 2) | eb) for eb in edge_blocks])
      f += 1
    
    index_map = {}
    for i, edge_indices in enumerate(map_edges):
      if len(set(edge_indices)) < 2: continue
      edge_indices = sorted(edge_indices)
      edge_index = (edge_indices[0] << 0x10) | edge_indices[1]
      eb = edges_blocked[i]
      if not edge_index in index_map: index_map[edge_index] = [eb]
      elif not eb in index_map[edge_index]: index_map[edge_index].append(eb)
    
    map_edges = [[edge_indices >> 0x10, edge_indices & 0xFFFF] for edge_indices in index_map.keys()]
    map_edge_blocks = [index_map[edge_indices] for edge_indices in index_map.keys()]
    map_cell_blocks = [face_map[face_indices][1:] for face_indices in face_map.keys()]
    map_faces = [face_map[face_indices][0] for face_indices in face_map.keys()]
    return self.vertices, map_faces, map_edges, map_edge_blocks, map_cell_blocks, map_corners, self.transform

class SplineListEntry:
  def __init__(self, data=None):
    self.data = data
    self.entry_offset = 0
    self.block_size = 0
    self.spline_count = 0
    self.splines = []
    if self.data == None: return
    
    self.entry_offset = self.data.tell()
    self.block_size = sread_s32(self.data, self.data.tell())
    self.spline_count = sread_s32(self.data, self.data.tell())
    for i in range(self.spline_count): self.splines.append(SplineEntry(self.data))
    self.data.seek(self.entry_offset + 0x4 + self.block_size)
  
  def save_changes(self):
    out_data = BytesIO()
    write_magic_str(out_data, 0x0, "SPLN", 4)
    write_u32(out_data, 0x4, 0x0)
    write_u32(out_data, 0x8, swap32(len(self.splines)))
    for spline in self.splines: write_bytes(out_data, out_data.tell(), spline.save_changes())
    out_data.seek(0)
    self.block_size = data_len(out_data) - 0x8
    write_u32(out_data, 0x4, swap32(self.block_size))
    out_data.seek(0)
    return out_data
  
  def add_spline(self, points, transform, cyclic=False):
    spline = SplineEntry()
    spline.loop_flag = cyclic
    spline.transform = transform
    spline.point_count = len(points)
    spline.points = points
    self.splines.append(spline)
    self.spline_count = len(self.splines)
  
  def get_bpypaths(self):
    return [spline.get_bpypath() for spline in self.splines]

class SplineEntry:
  def __init__(self, data=None):
    self.data = data
    self.loop_flag = False
    self.point_count = 0
    self.points = []
    self.object_type = "Spline"
    self.transform = Matrix()
    if self.data == None: return
    
    self.loop_flag = sread_s32(self.data, self.data.tell()) != 0 #Something to do with count during spline creation
    self.point_count = sread_s32(self.data, self.data.tell())
    
    for i in range(self.point_count):
      for j in range(3): self.points.append(sread_float(self.data, self.data.tell()))
    self.points = [self.points[i:i+3] for i in range(0, len(self.points), 3)]
    
    avgVertex = Vector([0.0, 0.0, 0.0])
    for vertex in self.points: avgVertex += Vector(vertex)
    avgVertex /= len(self.points)
    self.transform[3] = Vector([avgVertex.x, avgVertex.y, avgVertex.z, 1.0])
    self.transform = self.transform.transposed()
    
    invtransform = self.transform.inverted_safe()
    self.points = [list((invtransform @ Vector(vertex))[:]) for vertex in self.points]
  
  def save_changes(self):
    spline_data = BytesIO()
    write_u32(spline_data, 0x0, swap32(int(self.loop_flag)))
    write_u32(spline_data, 0x4, swap32(len(self.points)))
    saved_points = [list((self.transform @ Vector(vertex))[:]) for vertex in self.points]
    for point in saved_points:
      for j in range(3): write_float(spline_data, spline_data.tell(), swapfloat(point[j]))
    spline_data.seek(0)
    return spline_data.read()
  
  def get_bpypath(self):
    return self.loop_flag, self.points, self.transform

class LightsEntry:
  def __init__(self, data=None, name=None):
    self.name = name
    self.data = data
    self.entry_offset = 0
    self.block_size = 0
    self.count = 0
    self.lights = []
    if self.data == None: return
    self.entry_offset = self.data.tell()
    self.block_size = sread_u32(self.data, self.data.tell())
    self.count = sread_u32(self.data, self.data.tell())
    print(self.name + " has " + str(self.count) + " lights")
    for i in range(self.count):
      self.lights.append(LightEntry(self.data))
    self.data.seek(self.entry_offset + 0x4 + self.block_size)
  
  def save_changes(self):
    output = BytesIO()
    write_magic_str(output, output.tell(), "LITE", 4)
    write_u32(output, output.tell(), 0)
    self.count = len(self.lights)
    write_u32(output, output.tell(), swap32(self.count))
    for light in self.lights: write_bytes(output, output.tell(), light.save_changes().read())
    self.block_size = data_len(output) - 0x8
    write_u32(output, 0x4, swap32(self.block_size))
    output.seek(0)
    return output

class LightEntry: #GetMeshLights__10LIGHT_LISTR11MESH_LIGHTSP5CVec4
  TYPES = ["Ambient", "Point", "Spot", "Sun"]
  
  def __init__(self, data=None):
    self.data = data
    self.flag = 0x1F
    self.type = 1
    self.color = ([0.0, 0.0, 0.0])
    self.transform = Matrix()
    self.radfall = tuple([0.0, 0.0])
    self.spot = tuple([0.0, 0.0])
    if self.data == None: return
    self.object_type = "Light"
    
    self.flag = sread_u32(self.data, self.data.tell())
    if (self.flag & 0x1) != 0:
      self.type = sread_u32(self.data, self.data.tell())
      if self.type == 4: self.type = 3
    
    if (self.flag & 0x2) != 0:
      _v = [sread_float(self.data, self.data.tell()) for _ in range(4)]
      self.color = tuple(reversed(_v[0:3]))
    
    if (self.flag & 0x4) != 0:
      _m = [sread_float(self.data, self.data.tell()) for _ in range(4 * 4)]
      _m = [_m[i:i+4] for i in range(0, len(_m), 4)]
      self.transform = Matrix(_m).transposed()
      #R = self.transform.to_3x3().normalized().to_4x4()
      #T = Matrix.Translation(self.transform.to_translation())
      #S = Matrix.Diagonal(self.transform.to_scale().to_4d())
      #self.transform = T @ R# @ S
    
    if (self.flag & 0x8) != 0:
      # Radius, Falloff
      self.radfall = tuple([sread_float(self.data, self.data.tell()), sread_float(self.data, self.data.tell())])
    if (self.flag & 0x10) != 0:
      self.spot = tuple([sread_float(self.data, self.data.tell()), sread_float(self.data, self.data.tell())])
  
  def get_bpylight(self):
    return self.TYPES[self.type], self.color, self.radfall, self.spot, self.transform
  
  def save_changes(self):
    output = BytesIO()
    write_u32(output, output.tell(), swap32(self.flag))
    if (self.flag & 0x1) != 0: write_u32(output, output.tell(), swap32(self.type))
    if (self.flag & 0x2) != 0:
      _c = list(reversed(self.color)) + [1.0]
      for i in range(4): write_float(output, output.tell(), swapfloat(_c[i]))
    if (self.flag & 0x4) != 0:
      transform = self.transform.transposed()
      _m = [transform[i][j] for i in range(4) for j in range(4)]
      for f in _m: write_float(output, output.tell(), swapfloat(f))
    if (self.flag & 0x8) != 0:
      for val in list(self.radfall): write_float(output, output.tell(), swapfloat(val))
    if (self.flag & 0x10) != 0:
      for val in list(self.spot): write_float(output, output.tell(), swapfloat(val))
    output.seek(0)
    return output

  def inject_changes(self, color, type=0, transform=Matrix(), energy=0, soft_radius=0, spot_size=0, spot_blend=0):
    self.flag = 0x1F
    self.type = type
    self.color = tuple(color)
    self.transform = transform

    self.radfall = (soft_radius, (energy * 2) - soft_radius)
    if (self.radfall[0] + self.radfall[1]) == 0 or spot_size == 0: return
    spot_val = spot_size * spot_size
    spot_val -= energy * energy
    spot_val = math.sqrt(spot_val)
    spot_val /= (self.radfall[0] + self.radfall[1])
    spot_val *= 0.5
    self.spot = (spot_val - (spot_val * spot_blend), spot_val + (spot_val * spot_blend))
