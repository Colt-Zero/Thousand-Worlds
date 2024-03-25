from io import BytesIO
from fs_helpers import *

class ModelBounds:
  def __init__(self, data=None):
    self.data = data
    
    self.flags = 0
    self.scale = 0.0
    self.center = []
    self.size = 5.0
    self.unk = 1.0
    if data == None: return
    
    self.entry_offset = self.data.tell()
    self.block_size = sread_u32(self.data, self.data.tell())
    self.flags = sread_u32(self.data, self.data.tell())
    
    if (self.flags & 1):
      self.scale = sread_float(self.data, self.data.tell())
    
    if (self.flags & 2):
      for i in range(3):
        self.center.append(sread_float(self.data, self.data.tell()))
      self.size = sread_float(self.data, self.data.tell())
  
  def save_changes(self):
    output = BytesIO()
    write_magic_str(output, 0x0, "SETT", 4)
    write_u32(output, 0x4, 0)
    
    if self.scale > 0.0: self.flags |= 1
    if len(self.center) == 3: self.flags |= 2
    
    write_u32(output, output.tell(), swap32(self.flags))
    if (self.flags & 1):
      write_float(output, output.tell(), swapfloat(self.scale))
    if (self.flags & 2):
      for co in self.center:
        write_float(output, output.tell(), swapfloat(co))
      write_float(output, output.tell(), swapfloat(self.size))
    
    output.seek(0)
    self.block_size = data_len(output) - 0x8
    write_u32(output, 0x4, swap32(self.block_size))
    output.seek(0)
    return output
    

class ModlMaterialsEntry:
  def __init__(self, data=None):
    self.data = data
    
    self.block_size = 0
    self.count = 0
    self.materials = []
    if data == None: return
    
    self.entry_offset = self.data.tell()
    self.block_size = sread_u32(self.data, self.data.tell())
    self.count = sread_u32(self.data, self.data.tell())
    for i in range(self.count):
      mat_entry_offset = self.data.tell()
      mat = ModlMaterialEntry(self.data, mat_entry_offset)
      self.materials.append(mat)
  
  def save_changes(self):
    output = BytesIO()
    write_magic_str(output, 0x0, "MATL", 4)
    write_u32(output, 0x4, swap32(self.block_size))
    write_u32(output, 0x8, swap32(len(self.materials)))
    self.block_size = 4
    for mat in self.materials:
      mat_data = mat.save_changes()
      output.write(mat_data.read())
      self.block_size += data_len(mat_data)
    write_u32(output, 0x4, swap32(self.block_size))
    output.seek(0)
    return output

class ModlMaterialEntry:
  class ModlMaterialDataEntry:
    def __init__(self, texture_index, _type, col_sel, flags):
      self.texture_index = texture_index
      self.type = _type
      self.col_sel = col_sel
      self.flags = flags
  
  def __init__(self, data=None, entry_offset=0):
    self.data = data
    self.type = 0
    self.property_count = 0
    self.properties = []
    if self.data == None: return
    
    self.entry_offset = entry_offset
    self.type = sread_u32(self.data, self.data.tell())
    self.property_count = sread_u32(self.data, self.data.tell())
    self.properties = []
    for i in range(self.property_count):
      mat_data = self.ModlMaterialDataEntry(read_u8(self.data, self.data.tell()), read_u8(self.data, self.data.tell()), read_u8(self.data, self.data.tell()), read_u8(self.data, self.data.tell()))
      fog_bitfield = 0
      property_type = mat_data.type
      if (self.type & 0x2) != 0: fog_bitfield = 0x10
      if mat_data.col_sel == 0 or 4 < mat_data.col_sel:
        fog_bitfield |= 1
      if (mat_data.flags & 1) != 0:
        fog_bitfield = fog_bitfield & 0xfffffffe | 2
      if (mat_data.flags & 2) != 0:
        fog_bitfield = fog_bitfield & 0xfffffffe | 2
      if (mat_data.flags & 4) != 0:
        fog_bitfield |= 8
      if (mat_data.flags & 0x10) != 0:
        fog_bitfield |= 4
      unk_shift = 1 if property_type != 0x1 else 0
      x10 = (unk_shift << 6 | 0x23c) << 0x2f | 0x1000000000000008 #0x111E000000000008 0x113E000000000008
      #0x4 0x8 0x14 0x18 0x20 0x24 0x28 0x30*4(0xc0 0xc1 0xc2 0xc3)
      type2_screenVal = 0
      if property_type == 1 or property_type == 4:
        x20 = 0x44
        x24 = 0x0
      elif property_type == 2:
        x20 = 0x48
        x24 = 0x80
        type2_screenVal = 1
      elif property_type == 3:
        x20 = 0x42
        x24 = 0x80
      elif property_type == 5:
        x20 = 0x9
        x24 = 0x0
      elif property_type == 6:
        x20 = 0x58
        x24 = 0x0
      if (fog_bitfield & 4) == 0: x50 = 0x5000c
      else: x50 = 0x5040d
      if property_type == 2 or property_type == 3 or property_type == 5 or property_type == 6:
        fog_bitfield |= 0x20
        x60 = 0
      else: x60 = 1#TODO: Fog color 3 bytes
      x80 = type2_screenVal << 0x20# | screen_x362 << 0x18 | screen_x1c8
      x90 = unk_shift << 6 | 0x23c
      
      
      self.properties.append(mat_data)
  
  def printInfo(self, textures):
    for mat_data in self.properties:
      textureName = "None"
      if mat_data.texture_index != 0xFF: textureName = textures[mat_data.texture_index].name
      print("Material Property - Texture: " + textureName + " Unk_Bytes: " + hex(mat_data.type) + " " + hex(mat_data.col_sel) + " " + hex(mat_data.flags))
  
  def addProperty(self, texture_index, _type, col_sel, _flags):
    mat_data = self.ModlMaterialDataEntry(texture_index, _type, col_sel, _flags)
    self.properties.append(mat_data)
    self.property_count = len(self.properties)
  
  def save_changes(self):
    mat_data = BytesIO()
    write_u32(mat_data, 0x0, swap32(self.type))
    write_u32(mat_data, 0x4, swap32(self.property_count))
    for p in self.properties:
      write_u8(mat_data, mat_data.tell(), p.texture_index)
      write_u8(mat_data, mat_data.tell(), p.type)
      write_u8(mat_data, mat_data.tell(), p.col_sel)
      write_u8(mat_data, mat_data.tell(), p.flags)
    mat_data.seek(0)
    return mat_data


class ModelSubmeshEntry:
  class MeshGeomEntry:
    def __init__(self, data=None):
      self.data = data
      self.vertex_count = 0
      self.vertices = []
      self.normals = []
      self.uvs = []
      self.faces = []
      if self.data == None: return
      
      mesh_geom_offset = self.data.tell()
      self.vertex_count = sread_u32(self.data, mesh_geom_offset)
      self.approx_strip_count = 0
      _uvs = []
      flip = True
      for v in range(self.vertex_count):
        vertex_offset = self.data.tell()
        v_x = sread_float(self.data, vertex_offset + 0x0)
        v_y = sread_float(self.data, vertex_offset + 0x4)
        v_z = sread_float(self.data, vertex_offset + 0x8)
        n_x = sread_float(self.data, vertex_offset + 0xC)
        n_y = sread_float(self.data, vertex_offset + 0x10)
        n_z = sread_float(self.data, vertex_offset + 0x14)
        u_x = sread_float(self.data, vertex_offset + 0x18)
        u_y = sread_float(self.data, vertex_offset + 0x1C)
        face_data = sread_u32(self.data, vertex_offset + 0x20)
        self.vertices.append([v_x, v_y, v_z])
        self.normals.append([n_x, n_y, n_z])
        _uvs.append([u_x, u_y])
        if (face_data & 0x8000): self.approx_strip_count += 1
        if v >= 2:
          flip = self.add_face(self.faces, v, face_data, flip)
          #flip = self.reset_winding(face_data, flip)
      self.approx_strip_count /= 2
      for face in self.faces:
        self.uvs.append(_uvs[face[0]])
        self.uvs.append(_uvs[face[1]])
        self.uvs.append(_uvs[face[2]])
      
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
  
  def __init__(self, data=None):
    self.data = data
    self.material_index = 0
    self.geom_count = 0
    self.geometry = []
    if self.data == None: return
    
    submesh_offset = self.data.tell()
    self.material_index = sread_u32(self.data, submesh_offset)
    self.geom_count = sread_u32(self.data, submesh_offset + 0x4)
    self.approx_strip_count = 0
    for p in range(self.geom_count):
      geom = self.MeshGeomEntry(self.data)
      self.approx_strip_count += geom.approx_strip_count
      self.geometry.append(geom)
  
  def get_geometry_per_submesh(self, start_offset = 0):
    added_offset = 0
    for i in range(self.geom_count):
      geom = self.geometry[i]
      adjusted_indices = geom.faces.copy()
      for j in range(len(adjusted_indices)):
        for k in range(3): adjusted_indices[j][k] += start_offset + added_offset
      added_offset += geom.vertex_count
      if i == 0:
        submesh_vertices = geom.vertices.copy()
        submesh_normals = geom.normals.copy()
        submesh_uvs = geom.uvs.copy()
        submesh_faces = adjusted_indices
      else:
        submesh_vertices.extend(geom.vertices.copy())
        submesh_normals.extend(geom.normals.copy())
        submesh_uvs.extend(geom.uvs.copy())
        submesh_faces.extend(adjusted_indices)
    return submesh_vertices, submesh_normals, submesh_uvs, submesh_faces, added_offset

class ModelLodEntry:
  def __init__(self, data=None, name=None):
    self.name = name
    self.data = data
    self.lod_radius = 0.0
    self.submesh_count = 0
    self.submeshes = []
    if self.data == None: return
    
    lod_offset = self.data.tell()
    self.lod_radius = sread_float(self.data, lod_offset)
    self.submesh_count = sread_u32(self.data, lod_offset + 0x4)
    self.approx_strip_count = 0
    for s in range(self.submesh_count):
      submesh = ModelSubmeshEntry(self.data)
      self.approx_strip_count += submesh.approx_strip_count
      self.submeshes.append(submesh)
    print("Original Strip count: %d" % self.approx_strip_count)
  
  def get_submesh_geometry(self):
    output = []
    for i, submesh in enumerate(self.submeshes):
      submesh_vertices, submesh_normals, submesh_uvs, submesh_faces, submesh_offset = submesh.get_geometry_per_submesh()
      output.append((submesh_vertices, submesh_normals, submesh_uvs, submesh_faces, submesh.material_index, submesh_offset))
    return output

class ModelEntry:
  def __init__(self, data=None, name=None):
    self.name = name
    self.data = data
    self.mesh_count_maybe = 0
    self.lod_meshes = []
    self.lod_counts = []
    if self.data == None: return
    
    self.entry_offset = self.data.tell()
    self.block_size = sread_u32(self.data, self.entry_offset)
    
    self.mesh_count_maybe = sread_u32(self.data, self.entry_offset + 4)
    if self.mesh_count_maybe > 1: print("Mesh Count:%d" % self.mesh_count_maybe)
    self.lod_counts = [0]*self.mesh_count_maybe
    self.populate_meshes()
  
  def populate_meshes(self):
    self.data.seek(self.entry_offset + 0x8)
    for m in range(self.mesh_count_maybe):
      mesh_offset = self.data.tell()
      lod_count = sread_u32(self.data, mesh_offset)
      self.lod_counts[m] = lod_count
      for l in range(lod_count):
        lod_mesh = ModelLodEntry(self.data, self.name+"_m"+str(m)+"_l"+str(l))
        self.lod_meshes.append(lod_mesh)
    self.data.seek(self.entry_offset + self.block_size + 0x4)
  
  def get_model_geometry(self, lod_no=0):
    if lod_no >= max(self.lod_counts): return
    geometry = []
    lod_radii = []
    for lod_mesh in self.lod_meshes:
      if not lod_mesh.name.endswith("_l%d"%lod_no): continue
      lod_radii.append(lod_mesh.lod_radius)
      geometry.append((lod_mesh.get_submesh_geometry(), int(lod_mesh.name.rsplit("_l")[0].rsplit("_m")[1])))
    
    material_uvs = {}
    added_offset = 0
    uv_offset = 0
    face_offset = 0
    vertex_groups = [[]]*self.mesh_count_maybe
    for g, (lod_geometry, group_id) in enumerate(geometry):
      for submesh_vertices, submesh_normals, submesh_uvs, submesh_faces, submesh_material_index, submesh_offset in lod_geometry:
        if not submesh_material_index in material_uvs: material_uvs[submesh_material_index] = (face_offset, uv_offset, len(submesh_faces), submesh_uvs)
        adjusted_indices_flat = [ind + added_offset for face in submesh_faces for ind in face]
        adjusted_indices = [adjusted_indices_flat[f:f+3] for f in range(0, len(adjusted_indices_flat), 3)]
        if added_offset == 0:
          mesh_vertices = submesh_vertices.copy()
          mesh_normals = submesh_normals.copy()
          mesh_faces = adjusted_indices
        else:
          mesh_vertices.extend(submesh_vertices)
          mesh_normals.extend(submesh_normals)
          mesh_faces.extend(adjusted_indices)
        vertex_groups[group_id].extend(adjusted_indices_flat)#(added_offset, len(submesh_vertices)))
        added_offset += len(submesh_vertices)
        face_offset += len(submesh_faces)
        uv_offset += len(submesh_uvs)
    return mesh_vertices, mesh_normals, mesh_faces, material_uvs, vertex_groups, lod_radii
