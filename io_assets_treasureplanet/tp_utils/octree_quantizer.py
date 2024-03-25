import os
import sys
try:
  from PIL import Image
  has_pillow = True
except:
  has_pillow = False

class Color(object):
    """
    Color class
    """

    def __init__(self, red=0, green=0, blue=0, alpha=0):
        """
        Initialize color
        """
        self.red = red
        self.green = green
        self.blue = blue
        self.alpha = alpha


class OctreeNode(object):
    """
    Octree Node class for color quantization
    """

    def __init__(self, level, parent):
        """
        Init new Octree Node
        """
        self.color = Color(0, 0, 0, 0)
        self.pixel_count = 0
        self.palette_index = 0
        self.children = [None for _ in range(16)]#8)]
        # add node to current level
        if level < OctreeQuantizer.MAX_DEPTH - 1:
            parent.add_level_node(level, self)

    def is_leaf(self):
        """
        Check that node is leaf
        """
        return self.pixel_count > 0

    def get_leaf_nodes(self):
        """
        Get all leaf nodes
        """
        leaf_nodes = []
        for i in range(16):#8):
            node = self.children[i]
            if node:
                if node.is_leaf():
                    leaf_nodes.append(node)
                else:
                    leaf_nodes.extend(node.get_leaf_nodes())
        return leaf_nodes

    def get_nodes_pixel_count(self):
        """
        Get a sum of pixel count for node and its children
        """
        sum_count = self.pixel_count
        for i in range(16):#8):
            node = self.children[i]
            if node:
                sum_count += node.pixel_count
        return sum_count

    def add_color(self, color, level, parent):
        """
        Add `color` to the tree
        """
        if level >= OctreeQuantizer.MAX_DEPTH:
            self.color.red += color.red
            self.color.green += color.green
            self.color.blue += color.blue
            self.color.alpha += color.alpha
            self.pixel_count += 1
            return
        index = self.get_color_index_for_level(color, level)
        if not self.children[index]:
            self.children[index] = OctreeNode(level, parent)
        self.children[index].add_color(color, level + 1, parent)

    def get_palette_index(self, color, level):
        """
        Get palette index for `color`
        Uses `level` to go one level deeper if the node is not a leaf
        """
        if self.is_leaf():
            return self.palette_index
        index = self.get_color_index_for_level(color, level)
        if self.children[index]:
            return self.children[index].get_palette_index(color, level + 1)
        else:
            # get palette index for a first found child node
            for i in range(16):#8):
                if self.children[i]:
                    return self.children[i].get_palette_index(color, level + 1)

    def remove_leaves(self):
        """
        Add all children pixels count and color channels to parent node 
        Return the number of removed leaves
        """
        result = 0
        for i in range(16):#8):
            node = self.children[i]
            if node:
                self.color.red += node.color.red
                self.color.green += node.color.green
                self.color.blue += node.color.blue
                self.color.alpha += node.color.alpha
                self.pixel_count += node.pixel_count
                result += 1
        return result - 1

    def get_color_index_for_level(self, color, level):
        """
        Get index of `color` for next `level`
        """
        index = 0
        #mask = 0x80 >> level
        mask = 0x100 >> level
        if color.red & mask:
            index |= 8#4
        if color.green & mask:
            index |= 4#2
        if color.blue & mask:
            index |= 2#1
        if color.alpha & mask:
          index |= 1
        return index

    def get_color(self):
        """
        Get average color
        """
        return Color(
            int(self.color.red / self.pixel_count),
            int(self.color.green / self.pixel_count),
            int(self.color.blue / self.pixel_count),
            int(self.color.alpha / self.pixel_count))


class OctreeQuantizer(object):
    """
    Octree Quantizer class for image color quantization
    Use MAX_DEPTH to limit a number of levels
    """

    MAX_DEPTH = 8

    def __init__(self):
        """
        Init Octree Quantizer
        """
        self.levels = {i: [] for i in range(OctreeQuantizer.MAX_DEPTH)}
        self.root = OctreeNode(0, self)

    def get_leaves(self):
        """
        Get all leaves
        """
        return [node for node in self.root.get_leaf_nodes()]

    def add_level_node(self, level, node):
        """
        Add `node` to the nodes at `level`
        """
        self.levels[level].append(node)

    def add_color(self, color):
        """
        Add `color` to the Octree
        """
        # passes self value as `parent` to save nodes to levels dict
        self.root.add_color(color, 0, self)
    
    def add_color(self, red=0, green=0, blue=0, alpha=0):
      self.root.add_color(Color(red, green, blue, alpha), 0, self)

    def make_palette(self, color_count):
        """
        Make color palette with `color_count` colors maximum
        """
        palette = []
        palette_index = 0
        leaf_count = len(self.get_leaves())
        # reduce nodes
        # up to 8 leaves can be reduced here and the palette will have
        # only 248 colors (in worst case) instead of expected 256 colors
        for level in range(OctreeQuantizer.MAX_DEPTH - 1, -1, -1):
            if self.levels[level]:
                for node in self.levels[level]:
                    leaf_count -= node.remove_leaves()
                    if leaf_count <= color_count:
                        break
                if leaf_count <= color_count:
                    break
                self.levels[level] = []
        # build palette
        for node in self.get_leaves():
            if palette_index >= color_count:
                break
            if node.is_leaf():
                palette.append(node.get_color())
            node.palette_index = palette_index
            palette_index += 1
        return palette

    def get_palette_index(self, color):
        """
        Get palette index for `color`
        """
        return self.root.get_palette_index(color, 0)
    
    def get_palette_index(self, red=0, green=0, blue=0, alpha=0):
        """
        Get palette index for `color`
        """
        return self.root.get_palette_index(Color(red, green, blue, alpha), 0)

def main(path):
    image = Image.open(path)
    no_ext = os.path.splitext(path)[0]
    pixels = image.load()
    width, height = image.size

    octree = OctreeQuantizer()

    # add colors to the octree
    for j in range(height):
        for i in range(width):
            octree.add_color(Color(*pixels[i, j]))

    # 256 colors for 8 bits per pixel output image
    palette = octree.make_palette(256)

    # create palette for 256 color max and save to file
    palette_image = Image.new('RGBA', (16, 16))
    palette_pixels = palette_image.load()
    for i, color in enumerate(palette):
        palette_pixels[int(i % 16), int(i / 16)] = (color.red, color.green, color.blue, color.alpha)
    palette_image.save(no_ext + '_palette.png')

    # save output image
    out_image = Image.new('RGBA', (width, height))
    out_pixels = out_image.load()
    for j in range(height):
        for i in range(width):
            index = octree.get_palette_index(Color(*pixels[i, j]))
            color = palette[index]
            out_pixels[i, j] = (color.red, color.green, color.blue, color.alpha)
    out_image.save(no_ext + '_out.png')

if __name__ == '__main__':
  if len(sys.argv) >= 2:
    if os.path.isfile(sys.argv[1]) and has_pillow:
      main(sys.argv[1])
