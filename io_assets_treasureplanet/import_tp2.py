from io import BytesIO
import os
import sys
from pathlib import Path

current_dir = Path(os.path.dirname(__file__))
print(str(current_dir))
sys.path.insert(1, os.path.join(current_dir.absolute(), "tp_utils"))

from tp_utils.fs_helpers import *
from tp_utils.tp2 import read_tp2

try:
    from decompress import *
    has_decompress = True
except ImportError:
    has_decompress = False

import bpy

def load_tp2(data, name):
  width, height, out_pixels = read_tp2(data, name)
  image_object = bpy.data.images.new(name, width, height)
  image_object.pixels = out_pixels
  return image_object

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
      image = load_tp2(filedata, os.path.basename(f.name))
  if filedata == None: return {'CANCELLED'}
  return {'FINISHED'}
