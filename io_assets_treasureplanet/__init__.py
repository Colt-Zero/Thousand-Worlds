bl_info = {
  "name": "Thousand Worlds: Treasure Planet (PS2) Asset editor",
  "author": "Colt Zero",
  "version": (1, 0),
  "blender": (3, 3, 3),
  "location": "File > Import/Export",
  "description": "Import and export files in the Bizarre Creations Treasure Planet asset formats",
  "category": "Import-Export"
}

if "bpy" in locals():
  import importlib
  if "import_lp2" in locals():
    importlib.reload(import_lp2)
  if "export_lp2" in locals():
    importlib.reload(export_lp2)
  if "import_p2m" in locals():
    importlib.reload(import_p2m)
  if "export_p2m" in locals():
    importlib.reload(export_p2m)
  if "import_p2s" in locals():
    importlib.reload(import_p2s)
  if "export_tp2" in locals():
    importlib.reload(export_tp2)
  if "import_tp2" in locals():
    importlib.reload(import_tp2)

import bpy
from bpy.props import (
  CollectionProperty,
  StringProperty,
  BoolProperty,
  FloatProperty,
)
from bpy_extras.io_utils import (
  ImportHelper,
  ExportHelper,
)

#import bpy
#coll = bpy.context.view_layer.active_layer_collection.collection
#for ob in bpy.context.scene.objects:
#  if not coll in ob.users_collection: continue
#  ob.hide_set(not ob.hide_get())

class LP2Importer(bpy.types.Operator, ImportHelper):
  """Import LP2 Level"""
  bl_idname = "import_mesh.lp2"
  bl_label = "Import LP2 Level"
  bl_options = {'REGISTER', 'UNDO'}
  
  files: CollectionProperty(
    name="File Path",
    description="File path used for importing the LP2 file",
    type=bpy.types.OperatorFileListElement,
  )
  
  directory: StringProperty()
  
  filename_ext = ".LP2"
  filter_glob: StringProperty(default="*.LP2", options={'HIDDEN'})
  
  def execute(self, context):
    import os
    from . import import_lp2
    
    context.window.cursor_set('WAIT')
    
    paths = [
      os.path.join(self.directory, name.name)
      for name in self.files
    ]
    
    if not paths:
      paths.append(self.filepath)
    
    for path in paths:
      import_lp2.load(self, context, path)
    
    context.window.cursor_set('DEFAULT')
    
    return {'FINISHED'}

class LP2Exporter(bpy.types.Operator, ExportHelper):
  """Export LP2 Level"""
  bl_idname = "export_mesh.lp2"
  bl_label = "Export LP2 Level"
  bl_options = {'REGISTER', 'UNDO'}
  
  filename_ext = ".LP2"
  filter_glob: StringProperty(default="*.LP2", options={'HIDDEN'})
  
  save_mesh_changes: BoolProperty(name="Save Level Meshes", description="Save Changes to Level Meshes", default=False)
  save_collision_changes: BoolProperty(name="Save Collision Meshes", description="Save Changes to Collision Meshes", default=False)
  save_actor_changes: BoolProperty(name="Save Actors", description="Save Changes to Actors", default=True)
  save_dynamic_instance_changes: BoolProperty(name="Save Dynamic Instances", description="Save Changes to Dynamic Instances", default=True)
  save_spline_changes: BoolProperty(name="Save Splines", description="Save Changes to Splines", default=True)
  save_light_changes: BoolProperty(name="Save Lights", description="Save changes to Lights", default=True)
  save_aimap_changes: BoolProperty(name="Save AI Maps", description="Save Changes to AI Maps", default=False)
  use_selection: BoolProperty(name="Selection Only", description="Export selected objects only", default=False)
  
  def invoke(self, context, event):
    return super().invoke(context, event)
  
  def execute(self, context):
    from . import export_lp2
    context.window.cursor_set('WAIT')
    
    #props = self.properties
    #filepath = self.filepath
    #filepath = bpy.path.ensure_ext(filepath, self.filename_ext)
    #export_lp2.save(context, filepath, props)
    
    keywords = self.as_keywords(ignore=("check_existing", "filter_glob",))
    export_lp2.save(context, **keywords)
    
    context.window.cursor_set('DEFAULT')
    return {'FINISHED'}
  
  def draw(self, context):
    pass
    #layout = self.layout
    #layout.use_property_split = True
    #layout.use_property_decorate = False
    #sfile = context.space_data
    #operator = sfile.active_operator

class LP2_PT_export_options(bpy.types.Panel):
  bl_space_type = 'FILE_BROWSER'
  bl_region_type = 'TOOL_PROPS'
  bl_label = "Options"
  bl_parent_id = "FILE_PT_operator"
  
  @classmethod
  def poll(cls, context):
    sfile = context.space_data
    operator = sfile.active_operator
    return operator.bl_idname == "EXPORT_MESH_OT_lp2"
  
  def draw(self, context):
    layout = self.layout
    layout.use_property_split = True
    layout.use_property_decorate = False  # No animation.
    
    sfile = context.space_data
    operator = sfile.active_operator
    
    layout.prop(operator, "save_mesh_changes")
    layout.prop(operator, "save_collision_changes")
    layout.prop(operator, "save_actor_changes")
    layout.prop(operator, "save_dynamic_instance_changes")
    layout.prop(operator, "save_spline_changes")
    layout.prop(operator, "save_light_changes")
    layout.prop(operator, "save_aimap_changes")
    layout.prop(operator, "use_selection")

class P2MImporter(bpy.types.Operator, ImportHelper):
  """Import P2M model"""
  bl_idname = "import_mesh.p2m"
  bl_label = "Import P2M Model"
  bl_options = {'REGISTER', 'UNDO'}
  
  files: CollectionProperty(
    name="File Path",
    description="File path used for importing the P2M file",
    type=bpy.types.OperatorFileListElement,
  )
  
  directory: StringProperty()
  
  filename_ext = ".P2M"
  filter_glob: StringProperty(default="*.P2M", options={'HIDDEN'})
  
  def execute(self, context):
    import os
    from . import import_p2m
    
    context.window.cursor_set('WAIT')
    
    paths = [
      os.path.join(self.directory, name.name)
      for name in self.files
    ]
    
    if not paths:
      paths.append(self.filepath)
    
    for path in paths:
      import_p2m.load(self, context, path)
    
    context.window.cursor_set('DEFAULT')
    
    return {'FINISHED'}

class P2MExporter(bpy.types.Operator, ExportHelper):
  """Export P2M Model"""
  bl_idname = "export_mesh.p2m"
  bl_label = "Export P2M Model"
  bl_options = {'REGISTER', 'UNDO'}
  
  filename_ext = ".P2M"
  filter_glob: StringProperty(default="*.P2M", options={'HIDDEN'})
  
  use_selection: BoolProperty(name="Selection Only", description="Export selected objects only", default=False)
  
  def invoke(self, context, event):
    return super().invoke(context, event)
  
  def execute(self, context):
    from . import export_p2m
    context.window.cursor_set('WAIT')
    
    keywords = self.as_keywords(ignore=("check_existing", "filter_glob",))
    export_p2m.save(context, **keywords)
    
    context.window.cursor_set('DEFAULT')
    return {'FINISHED'}
  
  def draw(self, context):
    pass

class P2M_PT_export_options(bpy.types.Panel):
  bl_space_type = 'FILE_BROWSER'
  bl_region_type = 'TOOL_PROPS'
  bl_label = "Options"
  bl_parent_id = "FILE_PT_operator"
  
  @classmethod
  def poll(cls, context):
    sfile = context.space_data
    operator = sfile.active_operator
    return operator.bl_idname == "EXPORT_MESH_OT_p2m"
  
  def draw(self, context):
    layout = self.layout
    layout.use_property_split = True
    layout.use_property_decorate = False  # No animation.
    
    sfile = context.space_data
    operator = sfile.active_operator
    
    layout.prop(operator, "use_selection")

class P2SImporter(bpy.types.Operator, ImportHelper):
  """Import P2S model"""
  bl_idname = "import_mesh.p2s"
  bl_label = "Import P2S Model"
  bl_options = {'REGISTER', 'UNDO'}
  
  files: CollectionProperty(
    name="File Path",
    description="File path used for importing the P2S file",
    type=bpy.types.OperatorFileListElement,
  )
  
  directory: StringProperty()
  
  filename_ext = ".P2S"
  filter_glob: StringProperty(default="*.P2S", options={'HIDDEN'})
  
  def execute(self, context):
    import os
    from . import import_p2s
    
    context.window.cursor_set('WAIT')
    
    paths = [
      os.path.join(self.directory, name.name)
      for name in self.files
    ]
    
    if not paths:
      paths.append(self.filepath)
    
    for path in paths:
      import_p2s.load(self, context, path)
    
    context.window.cursor_set('DEFAULT')
    
    return {'FINISHED'}

class TP2Importer(bpy.types.Operator, ImportHelper):
  """Import TP2 image"""
  bl_idname = "image.tp2_import"
  bl_label = "Import TP2 Image"
  bl_options = {'REGISTER', 'UNDO'}
  
  files: CollectionProperty(
    name="File Path",
    description="File path used for importing the TP2 file",
    type=bpy.types.OperatorFileListElement,
  )
  
  directory: StringProperty()
  
  filename_ext = ".TP2"
  filter_glob: StringProperty(default="*.TP2", options={'HIDDEN'})
  
  def execute(self, context):
    import os
    from . import import_tp2
    
    context.window.cursor_set('WAIT')
    
    paths = [
      os.path.join(self.directory, name.name)
      for name in self.files
    ]
    
    if not paths:
      paths.append(self.filepath)
    
    for path in paths:
      import_tp2.load(self, context, path)
    
    context.window.cursor_set('DEFAULT')
    
    return {'FINISHED'}

class TP2Exporter(bpy.types.Operator, ExportHelper):
  """Export TP2 image"""
  bl_idname = "image.tp2_export"
  bl_label = "Export TP2 Image"
  bl_options = {'REGISTER', 'UNDO'}
  
  filename_ext = ".TP2"
  filter_glob: StringProperty(default="*.TP2", options={'HIDDEN'})
  
  def execute(self, context):
    
    return {'FINISHED'}

adef = None
actor_enums = None

def get_classes(self, context):
  global adef
  from . import import_lp2
  if adef == None:
    adef = import_lp2.adef_loader()
    adef.class_names = None
  if adef.class_names == None:
    orderedClasses = adef.classes.classes.copy()
    orderedClasses.sort(key=lambda x: x.properties_count1 + x.properties_count2, reverse=True)
    classNames = [adef.strings.table[cls.string_index] for cls in orderedClasses]
    adef.class_names = classNames
  else: classNames = adef.class_names
  return [(className, className, "") for className in classNames]

class AddActor(bpy.types.Operator):
  bl_idname = "object.add_actor"
  bl_label = "Add LP2 Actor"
  bl_options = {'REGISTER', 'UNDO'}
  bl_property = "class_name"
  
  class_name: bpy.props.EnumProperty(items=get_classes, name="Actor Class")
  
  def execute(self, context):
    global adef
    from . import import_lp2
    from . import import_p2m
    import os
    import math
    from mathutils import Vector, Matrix, Euler
    
    message = "Created Actor %s" % self.class_name
    
    if not "Actors" in bpy.data.collections:
      actor_collection = bpy.data.collections.new("Actors")
      bpy.context.collection.children.link(actor_collection)
    else: actor_collection = bpy.data.collections["Actors"]
    
    if adef == None:
      adef = import_lp2.adef_loader()
      adef.class_names = None
    
    transform = Euler((math.radians(90), 0, 0)).to_matrix().to_4x4()
    transform = Matrix.Translation(bpy.context.scene.cursor.location) @ transform
    asset_root = bpy.data.worlds['World']['Asset Root'] if "Asset Root" in bpy.data.worlds['World'] else None 
    actor, actorList = import_lp2.create_actor(adef, self.class_name, asset_root, Euler((math.radians(-90), 0, 0)).to_matrix().to_4x4() @ transform)
    
    obj = bpy.data.objects.new(actor.name, None)
    obj.empty_display_type = 'SPHERE'
    obj["Actor Name"] = actor.name
    obj["_lp2_type"] = "Actor"
    obj.matrix_world = transform
    actor_collection.objects.link(obj)
    
    model_paths = None
    if actorList.models != None:
      model_paths = actor.get_models()
    if model_paths != None and len(model_paths) > 0:
      actorMeshes = {}
      for robj in context.scene.objects:
        if robj.parent == None: continue
        if robj.data == None: continue
        if robj.parent.data != None: continue
        if not "Actor Name" in robj.parent: continue
        robj_name = robj.data.name
        if robj_name in bpy.data.meshes:
          robj_name = robj_name.split("_lod")[0]
          if not robj_name in actorMeshes: actorMeshes[robj_name] = [robj.data]
          elif not robj.data in actorMeshes[robj_name]: actorMeshes[robj_name].extend([robj.data])
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
              loaded_models.append(aobj)
              #aobj["P2M-Version"] = p2m_version
          for aobj in loaded_models:
            if not "_lod0" in aobj.name: aobj.hide_set(not aobj.hide_get())
            aobj.rotation_euler = [0, 0, 0]
            aobj.parent = obj
    
    self.report({'INFO'}, message)
    return {'FINISHED'}
  
  def invoke(self, context, event):
    context.window_manager.invoke_search_popup(self)
    return {'RUNNING_MODAL'}

def get_params(self, context, actor, obj):
    for prop_name in obj.keys():
      if not ':' in prop_name: continue
      prop_val = obj[prop_name]
      param_lookup = prop_name.split(':')
      if '' in param_lookup: param_lookup.remove('')
      param_lookup = int(param_lookup[0])
      param = actor.add_parameter(param_lookup)
    
    output_params = []
    for p, param in enumerate(actor.params):
      if (param.overwritten or param.added) and (param.type == 0 or param.type == 3 or param.type == 6): continue
      if param.parent_param != None and not (param.parent_param.overwritten or param.parent_param.added): continue
      if param.parent_param != None:
        parent_lookup = "%02d:%s" % (actor.params.index(param.parent_param), param.parent_param.string)
        if parent_lookup in obj and "IDPropertyArray" in str(type(obj[parent_lookup])):
          parent_prop_floats = [f for f in obj[parent_lookup] if type(f) == float]
          if len(parent_prop_floats) > 1 and len(parent_prop_floats) == len(obj[parent_lookup]):
            continue
      
      lookup = secondary = "%02d:%s" % (p, param.string)
      if param.overwritten or param.added:
        secondary = "Modify %s" % secondary
      else: secondary = "Add %s" % secondary
      output_params.append((lookup, secondary))
    output_params = [(out, out2, "") for out, out2 in output_params]
    return output_params

def get_param_values(self, context, actor, obj):
    global actor_enums
    import os
    import json
    from pathlib import Path
    
    param_lookup = self.selected_name.split(':')
    if '' in param_lookup: param_lookup.remove('')
    param_lookup = int(param_lookup[0])
    param = actor.add_parameter(param_lookup)
    
    if param.type == 2: return [("0", "False", ""), ("1", "True", "")]
    
    if param.type == 4:
      if actor_enums == None:
        current_dir = Path(os.path.dirname(__file__))
        enum_path = os.path.join(current_dir.absolute(), "tp_utils")
        enum_path = os.path.join(enum_path,'enums.json')
        if os.path.exists(enum_path):
          with open(enum_path, "r") as fp:
            actor_enums = json.load(fp)
      return [(enum_val, enum_val, "") for enum_val in actor_enums[param.string]]
    
    if param.type == 5:
      objectNames = ["None"] + [robj.name for robj in context.scene.objects if robj.data == None and "Actor Name" in robj]
    elif param.type == 8:
      objectNames = ["None"] + [robj.name for robj in context.scene.objects if robj.data != None and "types.Curve" in str(type(robj.data))]
    elif param.type == 9:
      #dynam = [robj for robj in context.scene.objects if robj.data == None and not "Actor Name" in robj]
      #dynam = [robj.name for robj in dynam if (("_lp2_type" in robj and robj["_lp2_type"] == "Dynamic Instance") or len([uc for uc in robj.users_collection if "Dynamic Level Models" == uc.name]) > 0)]
      objectNames = ["None"] + [robj.name for robj in bpy.data.collections['Dynamic Level Models'].all_objects if robj.data == None]
    elif param.type == 10:
      objectNames = ["None"] + [robj.name for robj in context.scene.objects if robj.data != None and "types.Mesh" in str(type(robj.data)) and ("Face Blocks" in robj.data.attributes or "Corner Blocks 1" in robj.data.attributes or "Corner Blocks 2" in robj.data.attributes)]
    if param.type == 5 or param.type == 8 or param.type == 9 or param.type == 10:
      return [(objectName if objectName != "None" else "      ", objectName, "") for objectName in objectNames]
    return []

def get_parameters(self, context):
  global adef
  from . import import_lp2
  
  obj = bpy.context.view_layer.objects.active
  if obj == None: return []
  if obj.data != None: return []
  if not "Actor Name" in obj: return []
  if self.stage == 1:
    if self.selected_name == "": return []
  
  if adef == None:
    adef = import_lp2.adef_loader()
    adef.class_names = None
  actor, actorList = import_lp2.create_actor(adef, obj["Actor Name"])
  
  if self.stage == 1:
    return get_param_values(self, context, actor, obj)
  else: return get_params(self, context, actor, obj)

class AddActorParameter(bpy.types.Operator):
  bl_idname = "object.add_actor_parameter"
  bl_label = "Add/Modify Actor Parameters"
  bl_options = {'REGISTER', 'UNDO'}
  bl_property = "parameter"
  
  selected_name: bpy.props.StringProperty()
  parameter: bpy.props.EnumProperty(items=get_parameters, name="Parameter")
  stage: bpy.props.IntProperty()
  
  def execute(self, context):
    global adef
    global actor_enums
    import os
    import json
    from pathlib import Path
    from . import import_lp2
    from mathutils import Vector
    obj = bpy.context.view_layer.objects.active
    if obj == None: return {'CANCELLED'} 
    if obj.data != None: return {'CANCELLED'}
    if not "Actor Name" in obj: return {'CANCELLED'}
    
    if self.stage == 0:
      self.selected_name = self.parameter
    parameter_value = ""
    if self.stage == 1:
      parameter_value = self.parameter
    
    if not ':' in self.selected_name: return {'CANCELLED'}
    if not self.selected_name in obj:
      message = "Add Parameter %s" % self.selected_name
    else: message = "Mod Parameter %s" % self.selected_name
    
    if adef == None:
      adef = import_lp2.adef_loader()
      adef.class_names = None
    actor, actorList = import_lp2.create_actor(adef, obj["Actor Name"])
    
    param_lookup = self.selected_name.split(':')
    if '' in param_lookup: param_lookup.remove('')
    param_lookup = int(param_lookup[0])
    param = actor.add_parameter(param_lookup)
    
    if param.type == 4:
      if actor_enums == None:
        current_dir = Path(os.path.dirname(__file__))
        enum_path = os.path.join(current_dir.absolute(), "tp_utils")
        enum_path = os.path.join(enum_path,'enums.json')
        if os.path.exists(enum_path):
          with open(enum_path, "r") as fp:
            actor_enums = json.load(fp)
      enumlist = []
      enum_index = 0
      index_assigned = False
      if param.string in actor_enums:
        for e, enumVal in enumerate(actor_enums[param.string]):
          enumlist.append(enumVal)
          if not index_assigned and (param.value == enumVal or parameter_value == enumVal):
            enum_index = e
            if parameter_value == enumVal: index_assigned = True
      if enumlist[enum_index] == parameter_value or not self.selected_name in obj:
        #obj[self.selected_name.replace(':', '-')] = enumlist
        obj[self.selected_name] = enumlist[enum_index]
    elif param.type == 5 or param.type == 8 or param.type == 9 or param.type == 10:
      if not parameter_value in context.scene.objects and not self.selected_name in obj: obj[self.selected_name] = ""
      elif parameter_value in context.scene.objects: obj[self.selected_name] = parameter_value
      else: obj[self.selected_name] = ""
    elif param.type == 6:
      if param.next_count > 0 and not self.selected_name in obj:
        children = [child_param for child_param in actor.params if child_param.parent_param == param]
        float_children = []
        if len(children) > 1:
          float_children = [child_param.value for child_param in children if child_param.type == 0]
        if len(float_children) == len(children):
          obj[self.selected_name] = Vector(float_children)
          if "Color" in param.string or "Colour" in param.string:
            ui = obj.id_properties_ui(self.selected_name)
            ui.update(min=0.0, soft_min=0.0)
            ui.update(soft_max=1.0)
            ui.update(subtype="COLOR")
          elif "Size" in param.string:
            ui = obj.id_properties_ui(self.selected_name)
            ui.update(subtype="XYZ_LENGTH")
          elif ("X" in children[0].string and "Y" in children[1].string):# and (len(children) > 2 and "Z" in children[2].string):
            ui = obj.id_properties_ui(self.selected_name)
            ui.update(subtype="XYZ")
        else:
          obj[self.selected_name] = []#[child_param.string for child_param in children]
    elif param.type == 0 or param.type == 2 or param.type == 3:
      if param.type == 0 and not self.selected_name in obj:
        obj[self.selected_name] = param.value
        par_name = param.string.lower()
        if "radius" in par_name or "distance" in par_name or "time" in par_name or "delay" in par_name:
          ui = obj.id_properties_ui(self.selected_name)
          if "radius" in par_name or "distance" in par_name:
            ui.update(subtype="DISTANCE")
          elif "time" in par_name or "delay" in par_name:
            if not "secs" in par_name:
              obj[self.selected_name] = obj[self.selected_name] / 60.0
            ui.update(subtype="TIME_ABSOLUTE")
      elif param.type == 2:
        if not self.selected_name in obj:
          obj[self.selected_name] = param.value
        obj[self.selected_name] = 0 if parameter_value == "" else int(parameter_value)
        ui = obj.id_properties_ui(self.selected_name)
        ui.update(min=0, max=1, soft_min=0, soft_max=1)
      elif not self.selected_name in obj:
        obj[self.selected_name] = param.value
    elif not self.selected_name in obj: obj[self.selected_name] = param.value
    
    self.report({'INFO'}, message)
    if self.stage == 0 and not (param.type == 0 or param.type == 3 or param.type == 6):
      self.stage = 1
      context.window_manager.invoke_search_popup(self)
      return {'RUNNING_MODAL'}
    return {'FINISHED'}
  
  def invoke(self, context, event):
    self.stage = 0
    context.window_manager.invoke_search_popup(self)
    return {'RUNNING_MODAL'}

class ActorSelectReferences(bpy.types.Operator):
  bl_idname = "object.actor_select_references"
  bl_label = "Actor Select References"
  bl_options = {'REGISTER', 'UNDO'}
  
  def execute(self, context):
    obj = bpy.context.view_layer.objects.active
    if obj.data != None: return {'CANCELLED'}
    if not "Actor Name" in obj: return {'CANCELLED'}
    
    for prop_name in obj.keys():
      if not ':' in prop_name: continue
      prop_val = obj[prop_name]
      if type(prop_val) == str and prop_val in bpy.data.objects:
        bpy.data.objects[prop_val].select_set(True)
    return {'FINISHED'}

class ActorSelectReferencers(bpy.types.Operator):
  bl_idname = "object.actor_select_referencers"
  bl_label = "Actor Select References"
  bl_options = {'REGISTER', 'UNDO'}
  
  def execute(self, context):
    obj = bpy.context.view_layer.objects.active
    
    for robj in context.scene.objects:
      if robj.data != None: continue
      if not "Actor Name" in robj: continue
      for prop_name in robj.keys():
        prop_val = robj[prop_name]
        if type(prop_val) != str: continue
        if not ':' in prop_name: continue
        if prop_val != obj.name: continue
        robj.select_set(True)
        break
    return {'FINISHED'}

class AIMapFaceBlocker(bpy.types.Operator):
  bl_idname = "lp2.block_faces"
  bl_label = "AIMap Face Block Operator"
  bl_options = {'REGISTER', 'UNDO'}
  
  def execute(self, context):
    obj = bpy.context.view_layer.objects.active
    ob_type = None if obj.data == None else str(type(obj.data))
    if ob_type == None or not "types.Mesh" in ob_type: return {'CANCELLED'}
    if obj.data.total_face_sel < 1: return {'CANCELLED'}
    mesh = obj.data
    selected_faces = [f for f in mesh.polygons if f.select]
    
    bpy.ops.object.mode_set(mode='OBJECT')
    if not "Face Blocks" in mesh.attributes:
      mesh.attributes.new(name="Face Blocks", type='FLOAT', domain='FACE')
    for face in selected_faces:
      mesh.attributes["Face Blocks"].data[face.index].value = int(mesh.attributes["Face Blocks"].data[face.index].value + 1) % 3
    bpy.ops.object.mode_set(mode='EDIT')
    return {'FINISHED'}

class AIMapEdgeBlocker(bpy.types.Operator):
  bl_idname = "lp2.block_edge"
  bl_label = "AIMap Edge Block Operator"
  bl_options = {'REGISTER', 'UNDO'}
  
  def execute(self, context):
    import bmesh
    
    obj = bpy.context.view_layer.objects.active
    ob_type = None if obj.data == None else str(type(obj.data))
    if ob_type == None or not "types.Mesh" in ob_type: return {'CANCELLED'}
    if obj.data.total_face_sel < 1 or obj.data.total_edge_sel < 1: return {'CANCELLED'}
    
    mesh = obj.data
    bmeh = bmesh.from_edit_mesh(mesh)
    history = [e for e in bmeh.select_history if type(e) is bmesh.types.BMEdge]
    edge = None
    if len(history) > 0: edge = history[-1]
    if edge == None: return {'CANCELLED'}
    
    faces = [f for f in edge.link_faces if f.select]
    if len(faces) > 1: faces = [f for f in faces if f.index == mesh.polygons.active]
    if len(faces) != 1: return {'CANCELLED'}
    
    edge_faces = [[f.index for f in e.link_faces] for e in bmeh.edges]
    face = faces[0]
    link_index = [elf for elf in edge.link_faces].index(face)
    edge_index = edge.index
    face_index = face.index
    loops = [(l.index, l.edge.index) for l in face.loops if l.vert in edge.verts]
    
    bpy.ops.object.mode_set(mode='OBJECT')
    layer = "Edge Blocks %d" % (link_index + 1)
    if not layer in mesh.attributes:
      mesh.attributes.new(name=layer, type='INT', domain='EDGE')
      #for e, e_face in enumerate(edge_faces): mesh.attributes[layer].data[e].value = e_face[link_index] << 2
    mesh.attributes[layer].data[edge_index].value = (face_index << 2) | (((mesh.attributes[layer].data[edge_index].value & 3) + 1) % 3)
    for i in range(2):
      clayer = "Corner Blocks %d" % (int(loops[i][1] != edge_index) + 1)
      if not clayer in mesh.attributes: mesh.attributes.new(name=clayer, type='FLOAT', domain='CORNER')
      #mesh.attributes[clayer].data[loops[i][0]].value = mesh.attributes[layer].data[edge_index].value & 3
      mesh.attributes[clayer].data[loops[i][0]].value = (mesh.attributes[clayer].data[loops[i][0]].value + 1) % 3
    bpy.ops.object.mode_set(mode='EDIT')
    return {'FINISHED'}

def menu_lp2_import(self, context):
  self.layout.operator(LP2Importer.bl_idname, text="Bizarre Creations Level (.LP2)")

def menu_lp2_export(self, context):
  self.layout.operator(LP2Exporter.bl_idname, text="Bizarre Creations Level (.LP2)")

def menu_p2m_import(self, context):
  self.layout.operator(P2MImporter.bl_idname, text="Bizarre Creations Model (.P2M)")

def menu_p2m_export(self, context):
  self.layout.operator(P2MExporter.bl_idname, text="Bizarre Creations Model (.P2M)")

def menu_p2s_import(self, context):
  self.layout.operator(P2SImporter.bl_idname, text="Bizarre Creations Animated Model (.P2S)")

def menu_tp2_import(self, context):
  self.layout.operator(TP2Importer.bl_idname, text="Bizarre Creations Image (.TP2)")

def menu_tp2_export(self, context):
  self.layout.operator(TP2Exporter.bl_idname, text="Bizarre Creations Image (.TP2)")

def aimap_block_faces(self, context):
  self.layout.operator(AIMapFaceBlocker.bl_idname, text="AIMap Block Faces")

def aimap_block_edge(self, context):
  self.layout.operator(AIMapEdgeBlocker.bl_idname, text="AIMap Block Edge")

def add_actor(self, context):
  self.layout.operator(AddActor.bl_idname, text="Add Actor")
  
def add_actor_parameter(self, context):
  self.layout.operator(AddActorParameter.bl_idname, text="Add/Modify Actor Parameters")

def actor_select_references(self, context):
  self.layout.operator(ActorSelectReferences.bl_idname, text="Select Objects Referenced by Actor")
  
def select_actor_referencers(self, context):
  self.layout.operator(ActorSelectReferencers.bl_idname, text="Select Actors that Reference this Object")

classes = (
  LP2Importer,
  LP2Exporter,
  P2MImporter,
  P2MExporter,
  P2SImporter,
  TP2Importer,
  TP2Exporter,
  LP2_PT_export_options,
  P2M_PT_export_options,
  AIMapFaceBlocker,
  AIMapEdgeBlocker,
  AddActor,
  AddActorParameter,
  ActorSelectReferences,
  ActorSelectReferencers,
)

def register():
  for cls in classes:
    bpy.utils.register_class(cls)
  
  #bpy.types.IMAGE_OT_OPEN.append(menu_tp2_import)
  #bpy.types.IMAGE_OT_SAVE.append(menu_tp2_export)
  bpy.types.TOPBAR_MT_file_import.append(menu_lp2_import)
  bpy.types.TOPBAR_MT_file_export.append(menu_lp2_export)
  bpy.types.TOPBAR_MT_file_import.append(menu_p2m_import)
  bpy.types.TOPBAR_MT_file_export.append(menu_p2m_export)
  bpy.types.TOPBAR_MT_file_import.append(menu_p2s_import)
  bpy.types.TOPBAR_MT_file_import.append(menu_tp2_import)
  bpy.types.VIEW3D_MT_image_add.append(menu_tp2_import)
  bpy.types.VIEW3D_MT_view.append(aimap_block_faces)
  bpy.types.VIEW3D_MT_view.append(aimap_block_edge)
  bpy.types.VIEW3D_MT_object.append(add_actor)
  bpy.types.VIEW3D_MT_object.append(add_actor_parameter)
  bpy.types.VIEW3D_MT_object.append(actor_select_references)
  bpy.types.VIEW3D_MT_object.append(select_actor_referencers)

def unregister():
  for cls in classes:
    bpy.utils.unregister_class(cls)
  
  #bpy.types.IMAGE_OT_OPEN.remove(menu_tp2_import)
  #bpy.types.IMAGE_OT_SAVE.remove(menu_tp2_export)
  bpy.types.TOPBAR_MT_file_import.remove(menu_lp2_import)
  bpy.types.TOPBAR_MT_file_export.remove(menu_lp2_export)
  bpy.types.TOPBAR_MT_file_import.remove(menu_p2m_import)
  bpy.types.TOPBAR_MT_file_export.remove(menu_p2m_export)
  bpy.types.TOPBAR_MT_file_import.remove(menu_p2s_import)
  bpy.types.TOPBAR_MT_file_import.remove(menu_tp2_import)
  bpy.types.VIEW3D_MT_image_add.remove(menu_tp2_import)
  bpy.types.VIEW3D_MT_view.remove(aimap_block_faces)
  bpy.types.VIEW3D_MT_view.remove(aimap_block_edge)
  bpy.types.VIEW3D_MT_object.remove(add_actor)
  bpy.types.VIEW3D_MT_object.remove(add_actor_parameter)
  bpy.types.VIEW3D_MT_object.remove(actor_select_references)
  bpy.types.VIEW3D_MT_object.remove(select_actor_referencers)

if __name__ == "__main__":
  register()
