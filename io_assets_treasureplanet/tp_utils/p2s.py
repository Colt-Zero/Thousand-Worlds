from io import BytesIO
import os
import sys
import math

from fs_helpers import *
from mathutils import Vector, Matrix

class SkelMaterialsEntry:
  def __init__(self, data):
    self.data = data
    self.entry_offset = self.data.tell()
    self.block_size = sread_u32(self.data, self.data.tell())
    self.count = sread_u32(self.data, self.data.tell())
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
  
  def get_model_geometry(self, lod_no=0):
    if lod_no >= self.mesh_count: return
    geometry = []
    lod_radii = []
    for lod_mesh in self.meshes:
      if not lod_mesh.name.endswith("_l%d"%lod_no): continue
      lod_radii.append(lod_mesh.lod_radius)
      geometry.extend(lod_mesh.get_submesh_geometry())
      #geometry.append((lod_mesh.get_submesh_geometry(), int(lod_mesh.name.rsplit("_l")[1])))
    
    added_offset = 0
    #for g, lod_geometry in enumerate(geometry):
    for submesh_vertices, submesh_normals, submesh_faces, submesh_offset in geometry:
      adjusted_indices = submesh_faces.copy()
      #adjusted_indices_flat = [ind + added_offset for face in submesh_faces for ind in face]
      #adjusted_indices = [adjusted_indices_flat[f:f+3] for f in range(0, len(adjusted_indices_flat), 3)]
      if added_offset == 0:
        mesh_vertices = submesh_vertices.copy()
        mesh_normals = submesh_normals.copy()
        mesh_faces = adjusted_indices
      else:
        mesh_vertices.extend(submesh_vertices)
        mesh_normals.extend(submesh_normals)
        mesh_faces.extend(adjusted_indices)
      added_offset += len(submesh_vertices)
    #return geometry, lod_radii
    return [(mesh_vertices, mesh_normals, mesh_faces)], lod_radii

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
      submesh.material_index = sread_u32(self.data, self.data.tell())
      for geom in submesh.geometry:
        for sc in geom.strip_counts:
          self.data.seek(self.data.tell() + (sc * 0x4 * 2)) # Likely uvs
    #print("Place %08x" % self.data.tell())
  
  def get_submesh_geometry(self):
    output = []
    for i, submesh in enumerate(self.submeshes):
      submesh_vertices, submesh_normals, submesh_faces, submesh_offset = submesh.get_geometry_per_submesh()
      output.append((submesh_vertices, submesh_normals, submesh_faces, submesh_offset))
    return output

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
      self.faces = []
      self.vert_skips = []
      for v in range(self.vertex_count):
        #print("Vertex %d offset: %08x" % (v, self.data.tell()))
        for p in range(3): _v.append(sread_float(self.data, self.data.tell()))
        face_data = sread_u32(self.data, self.data.tell()) # question mark
        for n in range(3): _n.append(sread_float(self.data, self.data.tell()))
        self.data.seek(self.data.tell() + 0x2 * 2) # skeleton related I believe
        self.vert_skips.append(face_data)
        #if v >= 2:
        #  self.add_face(self.faces, v, face_data)
      self.vertices = [_v[i:i+3] for i in range(0, len(_v), 3)]
      self.normals = [_n[i:i+3] for i in range(0, len(_n), 3)]
      
      _f = []
      for s in range(self.strip_count):
        strip_len = sread_u32(self.data, self.data.tell())
        self.strip_counts.append(strip_len)
        #print("Substrip count: %d" % strip_len)
        for ss in range(strip_len):
          _f.append(sread_u16(self.data, self.data.tell()) >> 4)
          _f.append(sread_u16(self.data, self.data.tell()))
          #self.data.seek(self.data.tell() + 0x2 * 2) # 2 byte vertex index (index * 0x20), 2 byte winding indicator
      self.face_data = [_f[i:i+2] for i in range(0, len(_f), 2)]
      _v = []
      _n = []
      for f in range(len(self.face_data)):
        self.add_face(self.faces, self.face_data[f][0], self.face_data[f][1])
      #print(self.faces)
    
    def add_face(self, faces, fc, face_data):
      if (face_data & 0x8000): return
      fa = max(0, fc - 2)
      fb = max(0, fc - 1)
      flip = (fc % 2) != 0
      if fc >= 2:
        if not flip: faces.append([fa, fb, fc])
        else: faces.append([fb, fa, fc])#([fa, fc, fb])
      return
    
    #def add_face(self, faces, fc, face_data, flip):
    #  if (face_data & 0x8000): return flip
    #  fa = 0 if fc < 3 else fc - 2
    #  fb = 0 if fc < 2 else fc - 1
    #  if not flip: faces.append([fa, fb, fc])
    #  else: faces.append([fa, fc, fb])
    #  return not flip
    
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
  
  def get_geometry_per_submesh(self, start_offset = 0):
    added_offset = 0
    for i in range(self.geom_count):
      geom = self.geometry[i]
      adjusted_indices = geom.faces.copy()
      #for j in range(len(adjusted_indices)):
      #  for k in range(3): adjusted_indices[j][k] += start_offset + added_offset
      added_offset += geom.vertex_count
      if i == 0:
        submesh_vertices = geom.vertices.copy()
        submesh_normals = geom.normals.copy()
        submesh_faces = adjusted_indices
      else:
        submesh_vertices.extend(geom.vertices.copy())
        submesh_normals.extend(geom.normals.copy())
        submesh_faces.extend(adjusted_indices)
    return submesh_vertices, submesh_normals, submesh_faces, added_offset

class JointListEntry:
  def __init__(self, data, name):
    self.name = name
    self.data = data
    self.entry_offset = self.data.tell()
    self.block_size = sread_u32(self.data, self.data.tell())
    self.count = sread_u32(self.data, self.data.tell())
    self.joints = []
    for i in range(self.count):
      joint_entry_offset = self.data.tell()
      joint = JointEntry(self.name, self.data, self.entry_offset, joint_entry_offset)
      self.joints.append(joint)

class JointEntry:
  def __init__(self, root_name, data, joint_block, entry_offset):
    self.joint_block = joint_block
    self.data = data
    self.entry_offset = entry_offset
    self.name = try_read_str(self.data, self.entry_offset, 0x10)
    self.count = sread_u32(self.data, self.data.tell())
    self.indexes = []
    index_offset = self.data.tell()
    for i in range(self.count):
      self.indexes.append(sread_u32(self.data, index_offset + i * 0x4))
    print(root_name + " Joint: " + self.name)
    print(self.indexes)

class SkeletonEntry:
  def __init__(self, data, name):
    self.name = name
    self.data = data
    self.entry_offset = self.data.tell()
    self.block_size = sread_u32(self.data, self.data.tell())
    self.bone_count = sread_u32(self.data, self.data.tell())
    self.bones = [None]*self.bone_count
    self.root = BoneEntry(self.data, self.bones)
    #for i in range(self.bone_count):
    #  bone = BoneEntry(self.data)
    #  self.bones.append(bone)

class BoneEntry:
  def __init__(self, data, bones, parent=None):
    self.data = data
    self.entry_offset = self.data.tell()

    self.bone_index = sread_u32(self.data, self.entry_offset)
    if self.bone_index == 0xFFFFFFFF: return
    #print(self.bone_index)
    bones[self.bone_index] = self

    _m = [sread_float(self.data, self.data.tell()) for _ in range(4 * 4)]
    _m = [_m[i:i+4] for i in range(0, len(_m), 4)]
    self.transform = Matrix(_m).transposed()
    
    self.floats = []
    for i in range(3):
      self.floats.append(sread_float(self.data, self.data.tell()))
    
    sread_u32(self.data, self.data.tell())
    
    self.parent = parent
    self.child_2 = BoneEntry(data, bones, self)
    self.child_1 = BoneEntry(data, bones, self)
  
  #def __init__(self, skeleton_name, data, skeleton_block, entry_offset):
  #  self.skeleton_block = skeleton_block
  #  self.data = data
  #  self.entry_offset = entry_offset
  #  self.bone_index = sread_u32(self.data, self.entry_offset)
  #  
  #  _m = [sread_float(self.data, self.data.tell()) for _ in range(4 * 4)]
  #  _m = [_m[i:i+4] for i in range(0, len(_m), 4)]
  #  self.transform = Matrix(_m).transposed()
  # 
  #  self.floats = []
  # for i in range(3):
  #   self.floats.append(sread_float(self.data, self.data.tell()))
  #
  #  self.unknown = sread_u32(self.data, self.entry_offset + 20 * 0x4)
  #  print(skeleton_name + " Bone #" + str(self.bone_index) + " Unk: " + str(self.unknown))
  #  #print(self.transform)
  #  #print(self.floats)
  # 
  #  #Handle padding
  #  padding_check = sread_s32(self.data, self.data.tell())
  # while padding_check == -1:
  #   padding_check = sread_s32(self.data, self.data.tell())
  # self.data.seek(self.data.tell() - 0x4)

class CyclesEntry:
  def __init__(self, data, name, bone_count):
    self.name = name
    self.data = data
    self.entry_offset = self.data.tell()
    self.block_size = sread_u32(self.data, self.data.tell())
    self.flags = sread_u32(self.data, self.data.tell())
    self.cycles_count = sread_u32(self.data, self.data.tell())
    
    self.cycles = []
    if self.cycles_count != 0:
      for c in range(self.cycles_count):
        cycle_offset = self.data.tell()
        cycle = CycleEntry(self.name, self.data, self.entry_offset, self.flags, cycle_offset, bone_count)
        self.cycles.append(cycle)
        print(self.name + " Anim #" + str(c + 1) + " : " + cycle.name + " Frame Count: " + str(int(len(cycle.frames[1]) / 5)))
        """
        stri = "[ "
        for i in range(int(len(cycle.frames[0]) / 5)):
          stri += "Frame #" + str(i + 1) + ": ["
          for j in range(len(cycle.frames)):
            stri += "["
            for k in range(5):
              stri += "{:.3f}".format(cycle.frames[j][i * 5 + k]).rstrip("0").rstrip(".") + ", "
            stri += "] "
          stri += "]\n"
        print(stri + "]")
        """
    self.data.seek(self.entry_offset + self.block_size + 0x4)

class CycleEntry:
  def __init__(self, root_name, data, cycles_block, flags, entry_offset, bone_count):
    self.cycles_block = cycles_block
    self.data = data
    self.entry_offset = entry_offset
    self.flags = flags
    
    self.name = ""
    self.unk_1 = 0
    self.unk_2 = 0
    self.unk_3 = 0
    self.unk_4 = []
    self.unk_5 = 0
    self.unk_6 = []
    self.unk_7 = 0xffffffff
    self.unk_f1 = 1.0
    self.unk_f2 = 20.0
    self.bunk = []
    self.frames = []
    if (self.flags & 0x1) != 0:
      self.name = try_read_str(self.data, self.data.tell(), 0x10)
    if (self.flags & 0x2) != 0:
      self.unk_1 = sread_s32(self.data, self.data.tell())
    if (self.flags & 0x4) != 0:
      self.unk_2 = sread_s32(self.data, self.data.tell())
    if (self.flags & 0x8) != 0:
      self.unk_f1 = sread_float(self.data, self.data.tell())
    if (self.flags & 0x10) != 0:
      self.unk_f2 = sread_float(self.data, self.data.tell())
    if (self.flags & 0x20) != 0:
      self.unk_3 = sread_s32(self.data, self.data.tell())
      if self.unk_3 != 0:
        for i in range(self.unk_3):
          self.unk_4.append(sread_s32(self.data, self.data.tell()))
    if (self.flags & 0x40) != 0:
      self.unk_5 = sread_s32(self.data, self.data.tell())
      if self.unk_5 != 0:
        for i in range(self.unk_5):
          self.unk_6.append(self.data.read(1))
          self.unk_6.append(self.data.read(1))
          self.unk_6.append(self.data.read(1))
          self.unk_6.append(self.data.read(1))
    if (self.flags & 0x80) != 0:
      self.unk_7 = sread_s32(self.data, self.data.tell())
    
    self.bunk.append(1)
    if bone_count != 0:
      bone_frames = []
      for b in range(bone_count):
        bunk = sread_s32(self.data, self.data.tell())
        self.bunk.append(bunk)
        self.bunk.append(bunk << 2)
        self.bunk.append(bunk << 4)
        self.LoadKeyframe(bone_frames)
        bunk = sread_s32(self.data, self.data.tell())
        self.bunk.append(bunk)
        self.bunk.append(bunk << 2)
        self.bunk.append(bunk << 4)
        self.LoadKeyframe(bone_frames)
        bunk = sread_s32(self.data, self.data.tell())
        self.bunk.append(bunk)
        self.bunk.append(bunk << 2)
        self.bunk.append(bunk << 4)
        self.LoadKeyframe(bone_frames)
        self.frames.append(bone_frames)
        
  def LoadKeyframe(self, bone_frames):
    check = sread_s32(self.data, self.data.tell())
    if check != -1:
      self.LoadKeyframe(bone_frames)
      for i in range(5):
        v = sread_float(self.data, self.data.tell())
        bone_frames.append(v)
      self.LoadKeyframe(bone_frames)