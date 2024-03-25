from io import BytesIO
from fs_helpers import *
from octree_quantizer import OctreeQuantizer, Color
import math

def read_tp2(data, name):
  header_size = sread_u32(data, 0x8)
  offset = 0x10
  if header_size == 0x44: offset = 0x30
  width = sread_u16(data, offset + 0x0)
  height = sread_u16(data, offset + 0x2)
  data_size = sread_u32(data, offset + 0x6)
  nr_colors = sread_u16(data, offset + 0xA)
  palette_size = sread_u16(data, offset + 0xE)
  cmbitdepth = int(round(palette_size / nr_colors)) * 8
  alpha = 1 if cmbitdepth == 32 else 0
  #fmt = read_u8(data, 0x10)
  if palette_size > 16 * (3 + alpha): fmt = 0x13
  else: fmt = 0x14
  
  fmt_str = "unk"
  if fmt == 0x00: # rgba8
    fmt_str = "rgba8"
    cmbitdepth = 0
    nr_colors = 0
  elif fmt == 0x01: # rgb8
    fmt_str = "rgb8"
    cmbitdepth = 0
    nr_colors = 0
  elif fmt == 0x13: # pal8
    fmt_str = "pal8"
    #if force_24bit: cmbitdepth = 24
    #nr_colors = 256
  elif fmt == 0x14: # pal4
    fmt_str = "pal4"
    #if force_24bit: cmbitdepth = 24
    #nr_colors = 16
  #print("%s : %d %d format %s" % (name, width, height, fmt_str))
  
  pixels = read_pixels(data, header_size, width, height, data_size, fmt)
  
  palette_bytes = BytesIO()
  if fmt == 0x13 or fmt == 0x14:
    #print ("Palette size: %x" % palette_size)
    alpha = 1 if cmbitdepth == 32 else 0
    palette_bytes = read_palette(data, header_size + data_size, nr_colors * (3 + alpha), alpha) 
    #print ("Output Palette size: %x" % data_len(palette_bytes))
  
  palette = []
  if fmt == 0x13 or fmt == 0x14:
    bitdepth = int(round(palette_size / nr_colors)) * 8
    alpha = 1 if bitdepth == 32 else 0
    for p in range(nr_colors):
      b = read_u8(palette_bytes, p * (3 + alpha) + 0)
      g = read_u8(palette_bytes, p * (3 + alpha) + 1)
      r = read_u8(palette_bytes, p * (3 + alpha) + 2)
      a = 255
      if alpha: a = read_u8(palette_bytes, p * (3 + alpha) + 3)
      palette.append((r / 255, g / 255, b / 255, a / 255))
  
  out_pixels = [None] * (height * width)
  fully_opaque = True
  for i in range(width):
    for j in range(height):
      p_index = j * width + i
      if fmt == 0x13 or fmt == 0x14:
        index = read_u8(pixels, p_index)
        color = palette[index]
      elif fmt == 0x00 or fmt == 0x01:
        bgra = 1 if fmt == 0x00 else 0
        b = read_u8(pixels, p_index * (3 + bgra) + 0x0)
        g = read_u8(pixels, p_index * (3 + bgra) + 0x1)
        r = read_u8(pixels, p_index * (3 + bgra) + 0x2)
        a = 255
        if bgra: a = read_u8(pixels, p_index * (3 + bgra) + 0x3)
        color = [r, g, b, a]
      else:
        color = [0, 0, 0, 0]
      if color[3] != 255: fully_opaque = False
      out_pixels[(j) * width + i] = [color[0], color[1], color[2], color[3]]
      #out_pixels[((height-1)-j) * width + i] = [color[0], color[1], color[2], color[3]]
  if fully_opaque: out_pixels = [px[:-1] for px in out_pixels]
  out_pixels = [chan for px in out_pixels for chan in px]
  return width, height, out_pixels

def reduce_colors(pixels, width, height, name=None, limit=256):
  has_alpha = 1#0
  octree = OctreeQuantizer()
  for j in range(height):
    for i in range(width):
      pix = [c for c in pixels[i + width * j]]#((height-1)-j)]]
      octree.add_color(*pix)
      if pix[3] < 255: has_alpha = 1
  palette = octree.make_palette(limit)
  palette = read_palette_fixed_size_from_list(palette, len(palette), has_alpha)
  palette_size = data_len(palette)
  palette.seek(0)
  
  if palette_size > 16 * (3 + has_alpha): fmt = 0x4
  else: fmt = 0x5
  
  if fmt == 0x5:
    pixel_data = BytesIO(b'\0'*((width*height)>>1))
  else: pixel_data = BytesIO(b'\0'*(width*height))
  for j in range(height):
    for i in range(width):
      place = i + width * j#((height-1)-j)
      index = octree.get_palette_index(*pixels[place])#)*pixels[i, (height - 1) - j])
      if fmt == 0x5:
        placeShifted = place // 2
        val = read_u8(pixel_data, placeShifted)
        write_u8(pixel_data, placeShifted, (val << 4) | index)
      else: write_u8(pixel_data, place, index)
  data_size = data_len(pixel_data)
  pixel_data.seek(0)
  
  output = BytesIO()
  nr_colors = int(palette_size / (3 + has_alpha))
  #cmtype = 1
  #imgtype = 1
  cmbitdepth = 24 + (8 * has_alpha)
  imgbitdepth = (nr_colors-1).bit_length()
  imgbitdepth = 4 * math.ceil(imgbitdepth/4)
  version = 4
  bull = 1
  FFVal = 0xFFD
  offset = 0x10
  header_size = 0x24
  if name != None:
    header_size += 0x20
  if header_size == 0x44:
    offset = 0x30
  write_magic_str(output, 0x0, "TP2", 4)
  write_u16(output, 0x4, swap16(version))
  write_u16(output, 0x6, swap16(FFVal)) #Unknown, seems to always be 0xFFC, 0xFFD, or 0xFFE
  write_u32(output, 0x8, swap32(header_size))
  write_u32(output, 0xC, swap32(palette_size + data_size + header_size))
  if name != None: write_str(output, output.tell(), name, 0x20)
  write_u16(output, offset + 0x0, swap16(width))
  write_u16(output, offset + 0x2, swap16(height))
  write_u8(output, offset + 0x4, fmt)
  write_u8(output, offset + 0x5, imgbitdepth)
  write_u32(output, offset + 0x6, swap32(data_size))
  write_u16(output, offset + 0xA, swap16(nr_colors))
  write_u8(output, offset + 0xC, 0) #Unknown, seems to always be 0
  write_u8(output, offset + 0xD, cmbitdepth) #Uncertain, but fairly sure
  write_u16(output, offset + 0xE, swap16(palette_size))
  write_u32(output, offset + 0x10, swap32(bull)) #Unknown, seems to be either 0 or 1
  output.write(pixel_data.read())
  output.write(palette.read())
  output.seek(0)
  return output

def read_pixels(data, offset, width, height, data_size, fmt):
  if fmt == 0x0:
    return read_pixels_bgra(data, offset, width, height)
  elif fmt == 0x1:
    return read_pixels_bgr(data, offset, width, height)
  elif fmt == 0x13:
    return read_pixels_raw(data, offset, data_size)
  elif fmt == 0x14:
    return read_pixels_exp(data, offset, width, height)

def read_pixels_bgra(data, offset, width, height):
  pixels = BytesIO()
  nr_pixels = width * height
  for p in range(nr_pixels):
    r = read_u8(data, offset + p * 4 + 0)
    g = read_u8(data, offset + p * 4 + 1)
    b = read_u8(data, offset + p * 4 + 2)
    a = read_u8(data, offset + p * 4 + 3)
    write_u8(pixels, p * 4 + 0, b)
    write_u8(pixels, p * 4 + 1, g)
    write_u8(pixels, p * 4 + 2, r)
    write_u8(pixels, p * 4 + 3, a)
  return pixels
  
def read_pixels_bgr(data, offset, width, height):
  pixels = BytesIO()
  nr_pixels = width * height
  for p in range(nr_pixels):
    r = read_u8(data, offset + p * 3 + 0)
    g = read_u8(data, offset + p * 3 + 1)
    b = read_u8(data, offset + p * 3 + 2)
    write_u8(pixels, p * 3 + 0, b)
    write_u8(pixels, p * 3 + 1, g)
    write_u8(pixels, p * 3 + 2, r)
  return pixels
  
def read_pixels_exp(data, offset, width, height):
  pixels = BytesIO()
  nr_pixels = (width * height) >> 1
  for p in range(nr_pixels):
    pix = read_u8(data, offset + p)
    write_u8(pixels, p * 2 + 0, pix & 0xF)
    write_u8(pixels, p * 2 + 1, pix >> 4)
  return pixels

def read_pixels_raw(data, offset, data_size):
  data.seek(offset)
  pixels = BytesIO(data.read(data_size))
  return pixels

def read_palette(data, offset, size, alpha=0):
  palette = BytesIO()
  palette.seek(0)
  data.seek(offset)
  current_size = 0
  for p in range(8):
    read_palette_block(palette, palette.tell(), data, data.tell(), size, alpha)
    read_palette_block(palette, palette.tell(), data, data.tell(), size, alpha)# + 32, size, alpha)
    read_palette_block(palette, palette.tell(), data, data.tell(), size, alpha)# - 64, size, alpha)
    read_palette_block(palette, palette.tell(), data, data.tell(), size, alpha)# + 32, size, alpha)
  return palette

def read_palette_block(palette, palette_offset, data, offset, max_size, alpha=0):
  for pb in range(8):
    if palette_offset + pb * (3 + alpha) < max_size and (offset + pb * 4) < data_len(data):
      b = read_u8(data, offset + pb * 4 + 0)
      g = read_u8(data, offset + pb * 4 + 1)
      r = read_u8(data, offset + pb * 4 + 2)
      a = read_u8(data, offset + pb * 4 + 3)
      write_u8(palette, palette_offset + pb * (3 + alpha) + 0, r)
      write_u8(palette, palette_offset + pb * (3 + alpha) + 1, g)
      write_u8(palette, palette_offset + pb * (3 + alpha) + 2, b)
      if alpha == 1: write_u8(palette, palette_offset + pb * (3 + alpha) + 3, a)

def read_palette_fixed_size_from_list(colors, size, alpha=0):
    palette = BytesIO()
    palette.seek(0)
    for p in range(size):
      b = colors[p].blue
      g = colors[p].green
      r = colors[p].red
      a = colors[p].alpha
      write_u8(palette, p * (3 + alpha) + 0, r)
      write_u8(palette, p * (3 + alpha) + 1, g)
      write_u8(palette, p * (3 + alpha) + 2, b)
      if alpha == 1:
        write_u8(palette, p * (3 + alpha) + 3, a)
    #palette.write(b'\0'*(size * (3 + alpha) - size * (3 + alpha)))
    return palette

