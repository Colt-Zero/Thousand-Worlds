import sys
from enum import Enum
from collections import deque
from typing import TypeVar, Generic, List

class Heap:
  class Linker:
    def __init__(self, elem, i):
      self.elem = elem
      self.index = i
  
  def __init__(self, locked=False, lt=False):
    self.locked = locked
    self.finder = []
    self.heap = []
    if not lt: self.compare = lambda a, b: a.elem > b.elem
    else: self.compare = lambda a, b: a.elem < b.elem
  
  def __getitem__(self, index): return self.peek(index)
  
  @property
  def empty(self): return not self.heap
  
  @property
  def size(self): return len(self.heap)
  
  def valid(self, i): return i < len(self.finder)
  
  def removed(self, i):
    assert self.valid(i)
    return self.finder[i] >= self.size
  
  def lock(self):
    assert not self.locked
    self.locked = True
  
  def clear(self):
    self.heap.clear()
    self.finder.clear()
    self.locked = False
  
  def top(self):
    assert not self.empty
    return self.heap[0].elem
  
  def peek(self, i):
    assert not self.removed(i)
    return self.heap[self.finder[i]].elem
  
  def pop(self):
    assert self.locked and not self.empty
    self.swap(0, self.size - 1)
    self.heap.pop()
    if not self.empty: self.adjust(0)
  
  def push(self, elem):
    assert not self.locked
    Id = self.size
    self.finder.append(Id)
    self.heap.append(self.Linker(elem, Id))
    self.adjust(Id)
    return Id
  
  def erase(self, i):
    assert self.locked and not self.removed(i)
    j = self.finder[i]
    self.swap(j, self.size - 1)
    self.heap.pop()
    if j != self.size: self.adjust(j)
  
  def pos(self, i):
    assert self.valid(i)
    return self.heap[i].index
  
  def update(self, i, elem):
    assert self.locked and not self.removed(i)
    j = self.finder[i]
    self.heap[j].elem = elem
    self.adjust(j)
  
  def swap(self, a, b):
    temp = self.heap[b]
    self.heap[b] = self.heap[a]
    self.heap[a] = temp
    self.finder[self.heap[a].index] = a
    self.finder[self.heap[b].index] = b
  
  def adjust(self, i):
    assert i < self.size
    exp = self.compare
    j = i
    while j > 0 and exp(self.heap[(j-1) // 2], self.heap[j]):
      self.swap(j, (j-1) // 2)
      j = (j-1) // 2
    
    i = j
    while 2*i+1 < self.size:
      j = 2*i+1
      if j + 1 < self.size and exp(self.heap[j], self.heap[j+1]):
        j += 1
      if exp(self.heap[j], self.heap[i]): return
      self.swap(i, j)
      i = j
      

T = TypeVar('T')

class Graph(Generic[T]):
  class Arc:
    def __init__(self, term):
      self.term = term
  
  class Node:
    def __init__(self, arcs):
      self.arcs: List[Arc] = arcs
      self.start = sys.maxsize
      self.end = sys.maxsize
      self.marker = False
      self.elem: T = None
    
    @property
    def empty(self): return self.start == self.end
    
    @property
    def size(self): return self.end - self.start
    
    @property
    def marked(self): return self.marker
    
    def mark(self): self.marker = True
    def unmark(self): self.marker = False
  
  def __init__(self, nodes):
    self.arcs: List[self.Arc] = []
    self.nodes: List[self.Node] = [self.Node(self.arcs) for i in range(nodes)]
  
  @property
  def empty(self): return not self.nodes
  
  @property
  def size(self): return len(self.nodes)
  
  @property
  def start(self): return 0
  
  @property
  def end(self): return len(self.nodes)
  
  def __getitem__(self, index):
    assert index <= self.size
    return self.nodes[index]#.elem
  
  def __setitem__(self, index, value):
    self.nodes[index].elem = value
  
  def swap(self, other):
    temp = other.nodes
    other.nodes = self.nodes
    self.nodes = temp
    temp = other.arcs
    other.arcs = self.arcs
    self.arcs = temp
  
  def insert_arc(self, start, end):
    assert start < self.size and end < self.size
    assert start >= self.start and start < self.end
    assert end >= self.start and end < self.end
    
    node = self.nodes[start]
    #print(node)
    if node.empty:
      node.start = len(self.arcs)
      node.end = node.start + 1
    else:
      assert node.end == len(self.arcs)
      node.end += 1
    
    self.arcs.append(self.Arc(end))
    return len(self.arcs)-1

class PrimitiveType(Enum):
  TRIANGLES = 0x4
  TRIANGLE_STRIP = 0x5

class PrimitiveGroup:
  def __init__(self, _type=PrimitiveType.TRIANGLE_STRIP):
    self.type = _type
    self.indices = []

class TriangleOrder(Enum):
  ABC = 0
  BCA = 1
  CAB = 2

class Triangle:
  def __init__(self, A, B, C):
    self.a = A
    self.b = B
    self.c = C
    self.stripID = 0
  
  def reset(self): self.stripID = 0

class TriangleEdge:
  def __init__(self, A, B):
    self.a = A
    self.b = B
  
  def __eq__(self, other):
    return self.a == other.a and self.b == other.b
  
  def __lt__(self, other):
    return self.a < other.a or (self.a == other.a and self.b < other.b)

class TriEdge(TriangleEdge):
  def __init__(self, A, B, triPos):
    super().__init__(A, B)
    self.triPos = triPos

class Strip:
  def __init__(self, start=0, order=TriangleOrder.ABC, size=0):
    self.start = start
    self.order = order
    self.size = size

class Policy:
  def __init__(self, minStripSize, maxStripSize, useCache):
    self.degree = 0
    self.cacheHits = 0
    self.minStripSize = minStripSize
    self.maxStripSize = maxStripSize
    self.useCache = useCache
    self.strip = Strip()
  
  def challenge(self, strip, degree, cacheHits):
    if strip.size < self.minStripSize or strip.size > self.maxStripSize: return
    if not self.useCache:
      if strip.size > self.strip.size:
        self.strip = strip
    else:
      if cacheHits > self.cacheHits:
        self.strip = strip
        self.degree = degree
        self.cacheHits = cacheHits
      elif cacheHits == self.cacheHits:
        if self.strip.size != 0 and degree < self.degree:
          self.strip = strip
          self.degree = degree
        elif strip.size > self.strip.size:
          self.strip = strip
          self.degree = degree

class CacheSimulator:
  def __init__(self, hits=0, pushHits=True, defaultLen=10):
    self.defaultlen = defaultLen
    self.pushCacheHits = pushHits
    self.hitcount = hits
    self.cache = deque(maxlen=self.defaultlen)
    self.reset()
  
  def copy(self):
    from copy import deepcopy
    new = CacheSimulator(self.hits, self.pushCacheHits, self.defaultlen)
    new.cache = deepcopy(self.cache)
    new.hitcount = self.hits
    return new
  
  @property
  def size(self): return len(self.cache)
  
  @property
  def hits(self): return self.hitcount
  
  def pushHits(self, enabled=True): self.pushCacheHits = enabled
  
  def clear(self):
    self.hitcount = 0
    self.cache.clear()
  
  def reset(self):
    self.hitcount = 0
    self.cache.extend([sys.maxsize for i in range(self.cache.maxlen)])
  
  def resize(self, size=10):
    self.cache = deque(self.cache, size)
    self.cache.extend([sys.maxsize for i in range(self.cache.maxlen - len(self.cache))])
  
  def push(self, index, countCacheHit=False):
    if (self.pushCacheHits or countCacheHit) and index in self.cache:
      if countCacheHit: self.hitcount += 1
      if not self.pushCacheHits: return
    self.cache.appendleft(index)
    self.cache.pop()
  
  def merge(self, backward, possibleOverlap):
    overlap = min(possibleOverlap, self.size)
    for i in range(overlap): self.push(backward.cache[i], True)
    self.hitcount += backward.hits

def UnmarkNodes(triangles: Graph[Triangle]):
  for t, triNode in enumerate(triangles): triNode.unmark()

def LinkNeighbours(triangles: Graph[Triangle], edgeMap: List[TriEdge], edge: TriEdge):
  #expr = lambda a, b: a.a < b.a or (a.a == b.a and a.b < b.b)
  for i, e in enumerate(edgeMap):
    if not e < edge: break#expr(e, edge): break
  for e in edgeMap[i:]:
    if edge != e: break
    triangles.insert_arc(edge.triPos, e.triPos)
  
  #while edgeMap[i] != edgeMap[-1] and edge == edgeMap[i]:
  #  triangles.insert_arc(edge.triPos, edgeMap[i].triPos)
  #  i += 1

def MakeConnectivityGraph(triangles: Graph[Triangle], indices: List[int]):
  assert triangles.size == len(indices) // 3
  
  for i in range(triangles.size):
    triangles[i] = Triangle(indices[i*3+0], indices[i*3+1], indices[i*3+2])
  
  edges: List[TriEdge] = []
  for t, triNode in enumerate(triangles):
    triangle = triNode.elem
    edges.extend([TriEdge(triangle.a, triangle.b, t),
                  TriEdge(triangle.b, triangle.c, t),
                  TriEdge(triangle.c, triangle.a, t)])
  
  edges.sort()
  
  for t, triNode in enumerate(triangles):
    triangle = triNode.elem
    LinkNeighbours(triangles, edges, TriEdge(triangle.b, triangle.a, t))
    LinkNeighbours(triangles, edges, TriEdge(triangle.c, triangle.b, t))
    LinkNeighbours(triangles, edges, TriEdge(triangle.a, triangle.c, t))

class TriangleStripper:
  def __init__(self, indices: List[int]):
    self.firstRun = True
    self.stripID = 0
    self.primitives: List[PrimitiveGroup] = []
    self.triHeap = Heap()
    self.candidates: List[int] = []
    self.cache = CacheSimulator(defaultLen=0)
    self.backCache = CacheSimulator(defaultLen=0)
    self.triangles = Graph[Triangle](len(indices) // 3)
    self.SetCacheSize(256)
    self.SetMinStripSize()
    self.SetMaxStripSize()
    self.SetBackwardSearch()
    self.SetCacheHits()
    MakeConnectivityGraph(self.triangles, indices)
  
  @property
  def Cache(self): return self.cache.size != 0
  
  @property
  def CacheSize(self): return self.cache.size
  
  def SetBackwardSearch(self, enabled=False): self.backwardSearch = enabled
  
  def SetCacheHits(self, enabled=True): self.cache.pushHits(enabled)
  
  def SetMinStripSize(self, size=2): self.minStripSize = max(1, size)
  def SetMaxStripSize(self, size=64): self.maxStripSize = size
  
  def SetCacheSize(self, size=10):
    self.cache.resize(size)
    self.backCache.resize(size)
  
  def ResetStripIDs(self):
    for t in range(self.triangles.start, self.triangles.end): self.triangles[t].elem.reset()
  
  def InitTriHeap(self):
    for triNode in self.triangles: self.triHeap.push(triNode.size)
    self.triHeap.lock()
    while not self.triHeap.empty and self.triHeap.top() == 0: self.triHeap.pop()
  
  def CountDegenerateTriangles(self):
    degenerates = 0
    for triNode in self.triangles:
      if len(set([triNode.elem.a, triNode.elem.b, triNode.elem.c])) < 3:
       dengenerates += 1
    return degenerates
  
  def AddLeftTriangles(self):
    primitives = PrimitiveGroup(PrimitiveType.TRIANGLES)
    for triNode in self.triangles:
      if triNode.marked: continue
      primitives.indices.extend([triNode.elem.a, triNode.elem.b, triNode.elem.c])
    if primitives.indices: self.primitives.append(primitives)
  
  def AddIndex(self, index, notSimulation):
    if self.Cache: self.cache.push(index, not notSimulation)
    if notSimulation: self.primitives[-1].indices.append(index)
  
  def BackAddIndex(self, index):
    if self.Cache: self.backCache.push(index, True)
  
  def FirstEdge(self, tri: Triangle, order: TriangleOrder):
    if order == TriangleOrder.ABC: return TriangleEdge(tri.a, tri.b)
    if order == TriangleOrder.BCA: return TriangleEdge(tri.b, tri.c)
    if order == TriangleOrder.CAB: return TriangleEdge(tri.c, tri.a)
    assert False
    return TriangleEdge(0, 0)
  
  def LastEdge(self, tri: Triangle, order: TriangleOrder):
    if order == TriangleOrder.ABC: return TriangleEdge(tri.b, tri.c)
    if order == TriangleOrder.BCA: return TriangleEdge(tri.c, tri.a)
    if order == TriangleOrder.CAB: return TriangleEdge(tri.a, tri.b)
    assert False
    return TriangleEdge(0, 0)
  
  def AddTriangle(self, tri: Triangle, order: TriangleOrder, notSimulation):
    if order == TriangleOrder.ABC:
      self.AddIndex(tri.a, notSimulation)
      self.AddIndex(tri.b, notSimulation)
      self.AddIndex(tri.c, notSimulation)
    elif order == TriangleOrder.BCA:
      self.AddIndex(tri.b, notSimulation)
      self.AddIndex(tri.c, notSimulation)
      self.AddIndex(tri.a, notSimulation)
    elif order == TriangleOrder.CAB:
      self.AddIndex(tri.c, notSimulation)
      self.AddIndex(tri.a, notSimulation)
      self.AddIndex(tri.b, notSimulation)
  
  def BackAddTriangle(self, tri: Triangle, order: TriangleOrder):
    if order == TriangleOrder.ABC:
      self.BackAddIndex(tri.c)
      self.BackAddIndex(tri.b)
      self.BackAddIndex(tri.a)
    elif order == TriangleOrder.BCA:
      self.BackAddIndex(tri.a)
      self.BackAddIndex(tri.c)
      self.BackAddIndex(tri.b)
    elif order == TriangleOrder.CAB:
      self.BackAddIndex(tri.b)
      self.BackAddIndex(tri.a)
      self.BackAddIndex(tri.c)
  
  def MarkTriAsTaken(self, i):
    self.triangles[i].mark()
    if not self.triHeap.removed(i): self.triHeap.erase(i)
    
    for a in range(self.triangles[i].start, self.triangles[i].end):
      j = self.triangles[i].arcs[a].term - self.triangles.start
      if not self.triangles[j].marked and not self.triHeap.removed(j):
        newDegree = self.triHeap.peek(j) - 1
        self.triHeap.update(j, newDegree)
        if self.Cache and newDegree > 0: self.candidates.append(j)
  
  def LinkToNeighbour(self, node, clockWise, order: TriangleOrder, notSimulation):
    edge = self.LastEdge(node.elem, order)
    #for l, arc in node.arcs[node.start:node.end]:
    for l in range(node.start, node.end):
      arc = node.arcs[l]
      triNode = self.triangles[arc.term]
      tri = triNode.elem
      
      if (notSimulation or tri.stripID != self.stripID) and not triNode.marked:
        if edge.b == tri.a and edge.a == tri.b:
          order = TriangleOrder.ABC if clockWise else TriangleOrder.BCA
          self.AddIndex(tri.c, notSimulation)
          return order, l
        elif edge.b == tri.b and edge.a == tri.c:
          order = TriangleOrder.BCA if clockWise else TriangleOrder.CAB
          self.AddIndex(tri.a, notSimulation)
          return order, l
        elif edge.b == tri.c and edge.a == tri.a:
          order = TriangleOrder.CAB if clockWise else TriangleOrder.ABC
          self.AddIndex(tri.b, notSimulation)
          return order, l
    #print(l)
    #print(node.end)
    return order, node.end
  
  def BackLinkToNeighbour(self, node, clockWise, order: TriangleOrder):
    edge = self.FirstEdge(node.elem, order)
    for l in range(node.start, node.end):
      arc = node.arcs[l]
      triNode = self.triangles[arc.term]
      tri = triNode.elem
      
      if tri.stripID != self.stripID and not triNode.marked:
        if edge.b == tri.a and edge.a == tri.b:
          order = TriangleOrder.CAB if clockWise else TriangleOrder.BCA
          self.BackAddIndex(tri.c)
          return order, l
        elif edge.b == tri.b and edge.a == tri.c:
          order = TriangleOrder.ABC if clockWise else TriangleOrder.CAB
          self.BackAddIndex(tri.a)
          return order, l
        elif edge.b == tri.c and edge.a == tri.a:
          order = TriangleOrder.BCA if clockWise else TriangleOrder.ABC
          self.BackAddIndex(tri.b)
          return order, l
    return order, node.end
  
  def ExtendToStrip(self, start, order: TriangleOrder):
    startOrder = order
    triNode = self.triangles[start]
    tri = triNode.elem
    
    
    tri.stripID = self.stripID
    self.stripID += 1
    self.AddTriangle(tri, order, False)
    
    size = 1
    clockWise = False
    
    finalIndex = start
    while (self.triangles.start + finalIndex + 1) != self.triangles.end and ((not self.Cache) or (size + 2) < self.CacheSize):
      o, l = self.LinkToNeighbour(triNode, clockWise, order, False)
      order = o
      if l == triNode.end:
        finalIndex = self.triangles.end-1
        triNode = self.triangles[finalIndex]
        size -= 1
      else:
        link = triNode.arcs[l]
        finalIndex = link.term
        triNode = self.triangles[link.term]
        triNode.elem.stripID = self.stripID
        clockWise = not clockWise
      size += 1
    return Strip(start, startOrder, size)
  
  def BackExtendToStrip(self, start, order: TriangleOrder, clockWise):
    triNode = self.triangles[start]
    tri = triNode.elem
    
    tri.stripID = self.stripID
    self.stripID += 1
    self.BackAddIndex(self.LastEdge(tri, order).b)
    size = 1
    
    finalIndex = start
    while (not self.Cache) or (size + 2) < self.CacheSize:
      o, l = self.BackLinkToNeighbour(triNode, clockWise, order)
      order = o
      if l == triNode.end: break
      else:
        link = triNode.arcs[l]
        triNode = self.triangles[link.term]
        finalIndex = link.term
        triNode.elem.stripID = self.stripID
        clockWise = not clockWise
      size += 1
    
    if clockWise: return Strip()
    if self.Cache:
      self.cache.merge(self.backCache, size)
      self.backCache.reset()
    return Strip(finalIndex - self.triangles.start, order, size)
  
  def BuildStrip(self, strip: Strip):
    clockWise = False
    start = strip.start
    order = strip.order
    
    self.primitives.append(PrimitiveGroup())
    self.AddTriangle(self.triangles[strip.start].elem, order, True)
    self.MarkTriAsTaken(start)
    
    node = self.triangles[start]
    for i in range(1, strip.size):
      o, l = self.LinkToNeighbour(node, clockWise, order, True)
      order = o
      #assert l != node.end
      if l == node.end: break
      link = node.arcs[l]
      node = self.triangles[link.term]
      self.MarkTriAsTaken(link.term)
      clockWise = not clockWise
  
  def FindBestStrip(self):
    cacheBackup = self.cache.copy()
    backupHits = self.cache.hits
    policy = Policy(self.minStripSize, self.maxStripSize, self.Cache)
    
    while self.candidates:
      candidate = self.candidates.pop()
      if self.triangles[candidate].marked or self.triHeap[candidate] == 0: continue
      
      for i in range(3):
        strip = self.ExtendToStrip(candidate, TriangleOrder(i))
        policy.challenge(strip, self.triHeap[strip.start], self.cache.hits)
        self.cache = cacheBackup
        self.cache.hitcount = backupHits
      if self.backwardSearch:
        for i in range(3):
          strip = self.BackExtendToStrip(candidate, TriangleOrder(i), False)
          policy.challenge(strip, self.triHeap[strip.start], self.cache.hits)
          self.cache = cacheBackup
          self.cache.hitcount = backupHits
        for i in range(3):
          strip = self.BackExtendToStrip(candidate, TriangleOrder(i), True)
          policy.challenge(strip, self.triHeap[strip.start], self.cache.hits)
          self.cache = cacheBackup
          self.cache.hitcount = backupHits
    
    return policy.strip
  
  def Stripify(self):
    while not self.triHeap.empty:
      heapTop = self.triHeap.pos(0)
      self.candidates.append(heapTop)
      while self.candidates:
        triStrip = self.FindBestStrip()
        if triStrip.size >= self.minStripSize and triStrip.size < self.maxStripSize:
          self.BuildStrip(triStrip)
        #lse: print(triStrip.start)
      
      if not self.triHeap.removed(heapTop): self.triHeap.erase(heapTop)
      while not self.triHeap.empty and self.triHeap.top() == 0: self.triHeap.pop()
  
  def Strip(self):
    if not self.firstRun:
      UnmarkNodes(self.triangles)
      self.ResetStripIDs()
      self.cache.reset()
      self.triHeap.clear()
      self.candidates.clear()
      self.stripID = 0
    
    self.InitTriHeap()
    self.Stripify()
    self.AddLeftTriangles()
    
    
    sumTriangles = 0
    sumStrips = 0
    stripCount = 0
    for primGroup in self.primitives:
      if primGroup.type == PrimitiveType.TRIANGLES: sumTriangles += len(primGroup.indices) // 3
      else:
        stripCount += 1
        sumStrips += len(primGroup.indices) - 2
      #if primGroup.type == PrimitiveType.TRIANGLES: print(len(primGroup.indices) // 3)
      #else: print(len(primGroup.indices) - 2)
      #print(primGroup.indices)
      #print(primGroup.type)
    
    log = False
    if log:
      degenerates = self.CountDegenerateTriangles()
      if degenerates: print(f"Dengenerate Triangles: {degenerates}")
      print(f"Strip Count: {stripCount}")
      print(f"Triangles: {sumTriangles}")
      print(f"Triangles from Strips: {sumStrips}")
      print(f"Total Triangles: {(self.triangles.end - self.triangles.start)}")
    
    return self.primitives

def triangle_strip_to_triangle_list(strip):
  triangles = []
  for i in range(2, len(strip)):
    triangles.extend(triangle_from_strip_to_triangle_list(i, strip))
    #if i % 2 == 0: # Even index, clockwise order
    #  triangles.extend([strip[i - 2], strip[i - 1], strip[i]])
    #else: # Odd index, counterclockwise order
    #  triangles.extend([strip[i - 1], strip[i - 2], strip[i]])
  return triangles

def triangle_from_strip_to_triangle_list(index, strip):
  if index % 2 == 0: # Even index, clockwise order
    return [strip[index - 2], strip[index - 1], strip[index]]
  # Odd index, counterclockwise order
  return [strip[index - 1], strip[index - 2], strip[index]]

#ChatGPT test obj loader
def load_obj(file_path):
  vertices = []
  faces = []
  with open(file_path, 'r') as file:
    for line in file:
      if line.startswith('v '): vertices.append(list(map(float, line[2:].split())))
      elif line.startswith('f '): faces.append([int(vertex.split('/')[0]) - 1 for vertex in line[2:].split()])
  return vertices, faces

# Example usage
#obj_file_path = "sphere.obj"
#loaded_vertices, loaded_faces = load_obj(obj_file_path)
#indices = [index for face in loaded_faces for index in face]

#stripper = TriangleStripper(indices)
#output = stripper.Strip()
#triangles = []
#for primGroup in output:
#  if primGroup.type == PrimitiveType.TRIANGLES:
#    this = True
#    #triangles.extend(primGroup.indices)
#  else:
#    triangles.extend(triangle_strip_to_triangle_list(primGroup.indices))
#print(len(triangles) // 3)
#
#for i in range(0, len(triangles), 3): print(f"f {triangles[i]+1} {triangles[i+1]+1} {triangles[i+2]+1}")
