import numpy as np
import sys

class Triangle:
    def __init__(self, vertices, index):
        self.index = index
        self.vertices = vertices  # List of 3 vertices, each a (x, y, z) tuple

class Plane:
    def __init__(self, normal, distance):
        self.normal = normal        # Plane normal vector (unit vector)
        self.distance = distance    # Distance from the origin along the normal vector

class BSPTree:
    def __init__(self, triangles):
        triangles = [Triangle(verts, ind) for ind, verts in enumerate(triangles)]
        #tri_list = []
        self.root = self.build_tree(triangles)#, tri_list)
        #print(tri_list)
    
    def build_tree(self, triangles, tri_list = []):
        if not triangles:
            return None
        
        # Select a splitting plane (e.g., median plane, random plane, etc.)
        plane = self.choose_splitting_plane(triangles)

        # Classify triangles based on the plane
        triangles_on_plane = []
        triangles_front = []
        triangles_back = []
        
        for triangle in triangles:
            side = self.classify_triangle(triangle, plane)
            if side == 0:
                triangles_on_plane.append(triangle)
            elif side == 1:
                triangles_front.append(triangle)
            else:
                triangles_back.append(triangle)
        
        #if len(triangles_on_plane) > 0:
        #    tri_list.append([tri.index for tri in triangles_on_plane])

        # Create current node
        node = {
            'plane': plane,
            'triangles_on_plane': triangles_on_plane,
            'front': self.build_tree(triangles_front, tri_list),
            'back': self.build_tree(triangles_back, tri_list)
        }
        
        return node
    
    def distance_to_plane(self, point, plane):
        # Calculate the signed distance from a point to a plane
        #return np.dot(point, plane.normal) + plane.distance
        return sum([p * n for p, n in zip(point, plane.normal)]) - plane.distance

    def classify_triangle(self, triangle, plane):
        # Classify triangle relative to the plane
        on_plane = 0
        front = 1
        back = 2
        
        # Compute distance from each vertex of triangle to the plane
        distances = [self.distance_to_plane(vertex, plane) for vertex in triangle.vertices]
        
        if all(d == 0 for d in distances):
            return on_plane
        elif all(d >= 0 for d in distances):
            return front
        elif all(d <= 0 for d in distances):
            return back
        else:
            return on_plane  # Triangle intersects the plane (handle as on-plane)
    
    def classify_point(self, point, plane):
        on_plane = 0
        front = 1
        back = 2
        distance = self.distance_to_plane(point, plane)

        if distance == 0: return on_plane
        elif distance >= 0: return front
        elif distance <= 0: return back
        return on_plane

    def choose_splitting_plane(self, triangles):
        # For simplicity, choose a plane perpendicular to one of the coordinate axes
        # For example, a plane perpendicular to the x-axis passing through the median x-value
        # This can be more sophisticated based on scene complexity (e.g., using a heuristic)
        # Here's a simple example:
        
        # Calculate median x-value of triangle centroids
        centroids = [self.calculate_centroid(triangle) for triangle in triangles]
        median_x = sorted(centroids, key=lambda x: x[0])[len(centroids) // 2][0]
        plane = Plane(normal=(1, 0, 0), distance=median_x)

        #plane = self.select_optimal_plane(triangles)

        # Compute centroids of triangles
        #centroids = np.array([np.mean(triangle.vertices, axis=0) for triangle in triangles])
        # Fit a plane to centroids using Principal Component Analysis (PCA)
        #_, _, v = np.linalg.svd(centroids - np.mean(centroids, axis=0))
        #plane_normal = v[0]  # Use the first principal component as the plane normal
        # Choose splitting plane parameters
        #plane_distance = -np.dot(plane_normal, np.mean(centroids, axis=0))
        #plane = Plane(normal=plane_normal, distance=plane_distance)
        
        # Splitting plane perpendicular to x-axis passing through median_x
        return plane
    
    def calculate_centroid(self, triangle):
        # Compute the centroid of a triangle
        return (
            (triangle.vertices[0][0] + triangle.vertices[1][0] + triangle.vertices[2][0]) / 3,
            (triangle.vertices[0][1] + triangle.vertices[1][1] + triangle.vertices[2][1]) / 3,
            (triangle.vertices[0][2] + triangle.vertices[1][2] + triangle.vertices[2][2]) / 3
        )
    
    def select_optimal_plane(self, triangles):
        best_plane = None
        best_cost = sys.maxsize
        
        # Evaluate cost for each candidate plane
        for plane in self.generate_candidate_planes(triangles):
            cost = self.evaluate_split_cost(triangles, plane)
            if cost < best_cost:
                best_cost = cost
                best_plane = plane
        
        return best_plane
    
    def generate_candidate_planes(self, triangles):
        # Example: Generate candidate planes (e.g., axis-aligned planes)
        # Here, we generate planes parallel to x, y, and z axes
        
        min_x = min_y = min_z = sys.maxsize
        max_x = max_y = max_z = -sys.maxsize - 1
        for triangle in triangles:
          for vert in triangle.vertices:
            min_x = min(vert[0], min_x)
            max_x = max(vert[0], max_x)
            min_y = min(vert[1], min_y)
            max_y = max(vert[1], max_y)
            min_z = min(vert[2], min_z)
            max_z = max(vert[2], max_z)
        
        mid_x = 0.5 * (min_x + max_x)
        mid_y = 0.5 * (min_y + max_y)
        mid_z = 0.5 * (min_z + max_z)
        
        # Generate candidate planes (axis-aligned)
        planes = [
            Plane(normal=(1, 0, 0), distance=mid_x),  # Split along x-axis
            Plane(normal=(0, 1, 0), distance=mid_y),  # Split along y-axis
            Plane(normal=(0, 0, 1), distance=mid_z)   # Split along z-axis
        ]
        
        return planes
    
    def evaluate_split_cost(self, triangles, plane):
        # Example: Evaluate split cost using SAH (surface area heuristic)
        triangles_front = []
        triangles_back = []
        
        for triangle in triangles:
            side = self.classify_triangle(triangle, plane)
            if side == 1:
                triangles_front.append(triangle)
            elif side == 2:
                triangles_back.append(triangle)
        
        area_front = self.calculate_bounding_volume_area(triangles_front)
        area_back = self.calculate_bounding_volume_area(triangles_back)
        
        # SAH cost (e.g., sum of areas)
        cost = area_front + area_back
        return cost
    
    def calculate_bounding_volume_area(self, triangles):
        # Example: Calculate bounding volume area (e.g., AABB surface area)
        # Here, we use the bounding box area as a simple approximation
        
        min_x = min_y = min_z = sys.maxsize
        max_x = max_y = max_z = -sys.maxsize - 1
        for triangle in triangles:
          for vert in triangle.vertices:
            min_x = min(vert[0], min_x)
            max_x = max(vert[0], max_x)
            min_y = min(vert[1], min_y)
            max_y = max(vert[1], max_y)
            min_z = min(vert[2], min_z)
            max_z = max(vert[2], max_z)
        extents = np.array([max_x, max_y, max_z]) - np.array([min_x, min_y, min_z])

        surface_area = 2 * (extents[0] * extents[1] + extents[1] * extents[2] + extents[2] * extents[0])
        return surface_area