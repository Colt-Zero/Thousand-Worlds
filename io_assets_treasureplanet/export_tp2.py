from io import BytesIO
import os
import sys
from pathlib import Path

current_dir = Path(os.path.dirname(__file__))
print(str(current_dir))
sys.path.insert(1, os.path.join(current_dir.absolute(), "tp_utils"))

from tp_utils.fs_helpers import *
from tp_utils.tp2 import reduce_colors

try:
    from decompress import *
    has_decompress = True
except ImportError:
    has_decompress = False

def save(context, filepath="", use_selection=False):
  filedata = None
  magic = None
  if os.path.exists(filepath):
    with open(filepath, 'rb') as f:
      filedata = BytesIO(f.read())
      magic = try_read_str(filedata, 0, 4)
      filedata.seek(0)
      if magic is not None:
        if magic.startswith("PK2") and has_decompress:
          d = Decompressor(BytesIO(filedata.read()))
          d.decompressed.seek(0)
          filedata = BytesIO(d.decompressed.read())
  
  
