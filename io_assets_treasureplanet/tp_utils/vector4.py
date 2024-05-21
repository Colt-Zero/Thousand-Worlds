import numbers

def bit(x, n):  return (x >> n) & 1

class Vector4:
  @property
  def xyzw(self):
    self.dest = (1 << 3) | (1 << 2) | (1 << 1) | 1
    return self
  
  @property
  def xyz(self):
    self.dest = (1 << 3) | (1 << 2) | (1 << 1)
    return self
  @property
  def xyw(self):
    self.dest = (1 << 3) | (1 << 2) | 1
    return self
  @property
  def xzw(self):
    self.dest = (1 << 3) | (1 << 1) | 1
    return self
  @property
  def yzw(self):
    self.dest = (1 << 2) | (1 << 1) | 1
    return self
    
  @property
  def xy(self):
    self.dest = (1 << 3) | (1 << 2)
    return self
  @property
  def xz(self):
    self.dest = (1 << 3) | (1 << 1)
    return self
  @property
  def xw(self):
    self.dest = (1 << 3) | 1
    return self
  @property
  def yz(self):
    self.dest = (1 << 2) | (1 << 1)
    return self
  @property
  def yw(self):
    self.dest = (1 << 2) | 1
    return self
  @property
  def zw(self):
    self.dest = (1 << 1) | 1
    return self
  
  def __getitem__(self, index):
    if index == 3: return self.w
    if index == 2: return self.z
    if index == 1: return self.y
    return self.x
  
  def __setitem__(self, index, value):
    if index == 3: self.w = value
    if index == 2: self.z = value
    if index == 1: self.y = value
    if index == 0: self.x = value
  
  def __repr__(self):
    return f'Vector4({self.x}, {self.y}, {self.z}, {self.w})'
  
  def __init__(self, x = 0.0, y = 0.0, z = 0.0, w = 0.0):
    self.dest = 0xf
    self.x = x
    self.y = y
    self.z = z
    self.w = w
  
  def copy(self, other):
    for i in range(4): self[i] = other[i]
  
  def reset_dest(self):
    self.dest = 0xf
  
  def __add__(self, other):
    new = Vector4()
    for f in range(4):
      if not bit(self.dest, 3 - f): continue
      if isinstance(other, numbers.Number): new[f] = self[f] + other
      elif isinstance(other[f], numbers.Number): new[f] = self[f] + other[f]
    self.reset_dest()
    return new
  
  def __sub__(self, other):
    new = Vector4()
    for f in range(4):
      if not bit(self.dest, 3 - f): continue
      if isinstance(other, numbers.Number): new[f] = self[f] - other
      elif isinstance(other[f], numbers.Number): new[f] = self[f] - other[f]
    self.reset_dest()
    return new
  
  def __mul__(self, other):
    new = Vector4()
    for f in range(4):
      if not bit(self.dest, 3 - f): continue
      if isinstance(other, numbers.Number): new[f] = self[f] * other
      elif isinstance(other[f], numbers.Number): new[f] = self[f] * other[f]
    self.reset_dest()
    return new
  
  def __truediv__(self, other):
    new = Vector4()
    for f in range(4):
      if not bit(self.dest, 3 - f): continue
      if isinstance(other, numbers.Number): new[f] = self[f] / other
      elif isinstance(other[f], numbers.Number): new[f] = self[f] / other[f]
    self.reset_dest()
    return new
  
  def min(self, other):
    new = Vector4()
    for f in range(4):
      if not bit(self.dest, 3 - f): continue
      if isinstance(other, numbers.Number): new[f] = min(self[f], other)
      elif isinstance(other[f], numbers.Number): new[f] = min(self[f], other[f])
    self.reset_dest()
    return new
  
  def max(self, other):
    new = Vector4()
    for f in range(4):
      if not bit(self.dest, 3 - f): continue
      if isinstance(other, numbers.Number): new[f] = max(self[f], other)
      elif isinstance(other[f], numbers.Number): new[f] = max(self[f], other[f])
    self.reset_dest()
    return new