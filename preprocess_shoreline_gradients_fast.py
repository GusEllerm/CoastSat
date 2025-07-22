#!/usr/bin/env python3
"""
FAST preprocessing script using spatial partitioning.

This approach:
1. Divides the world into grid cells
2. Groups transects by grid cells
3. Only checks shorelines against nearby transects
4. Should be 100-1000x faster than brute force approach
"""

import json
import math
import sys
from shapely.geometry import LineString, Point
from collections import defaultdict
import time

def load_geojson(filename):
    """Load a GeoJSON file."""
    with open(filename, 'r') as f:
        return json.load(f)

def save_geojson(data, filename):
    """Save data as a GeoJSON file."""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

def trend_to_color(trend, n_points_nonan=None):
    """Convert trend value to RGB color using the same scale as JavaScript."""
    if n_points_nonan is not None and n_points_nonan < 10:
        return 'rgb(186, 186, 186)'
    
    if trend is None:
        return 'rgb(128, 128, 128)'
    
    trend = max(-3, min(3, trend))
    normalized = (trend + 3) / 6
    
    if normalized <= 0.5:
        r = 255
        g = int(255 * (normalized * 2))
        b = 0
    else:
        r = int(255 * (2 - normalized * 2))
        g = int(255 * (2 - normalized * 2))
        b = int(255 * ((normalized - 0.5) * 2))
    
    return f'rgb({r}, {g}, {b})'

def get_bbox(coords):
    """Get bounding box of coordinates."""
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return (min(lons), min(lats), max(lons), max(lats))

def get_grid_cells(bbox, cell_size=0.1):
    """Get grid cell indices that a bounding box overlaps."""
    min_lon, min_lat, max_lon, max_lat = bbox
    
    min_cell_x = int(min_lon / cell_size)
    max_cell_x = int(max_lon / cell_size)
    min_cell_y = int(min_lat / cell_size)
    max_cell_y = int(max_lat / cell_size)
    
    cells = []
    for x in range(min_cell_x, max_cell_x + 1):
        for y in range(min_cell_y, max_cell_y + 1):
            cells.append((x, y))
    
    return cells

def point_on_line_at_distance(line_coords, target_distance):
    """Find a point on a LineString at a specific distance along the line."""
    if not line_coords or len(line_coords) < 2:
        return None
    
    current_distance = 0
    
    for i in range(len(line_coords) - 1):
        x1, y1 = line_coords[i]
        x2, y2 = line_coords[i + 1]
        
        segment_length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        
        if current_distance + segment_length >= target_distance:
            remaining_distance = target_distance - current_distance
            ratio = remaining_distance / segment_length
            
            x = x1 + (x2 - x1) * ratio
            y = y1 + (y2 - y1) * ratio
            return [x, y]
        
        current_distance += segment_length
    
    return None

def calculate_line_length(line_coords):
    """Calculate total length of a LineString."""
    if not line_coords or len(line_coords) < 2:
        return 0
    
    total_length = 0
    for i in range(len(line_coords) - 1):
        x1, y1 = line_coords[i]
        x2, y2 = line_coords[i + 1]
        total_length += math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    return total_length

def find_intersection_distance_fast(shoreline_coords, transect_coords):
    """Fast intersection distance calculation with bounding box check."""
    try:
        # Quick bounding box check
        shore_bbox = get_bbox(shoreline_coords)
        trans_bbox = get_bbox(transect_coords)
        
        # Check if bounding boxes overlap with small buffer
        buffer = 0.001  # About 100m
        if (shore_bbox[2] < trans_bbox[0] - buffer or trans_bbox[2] < shore_bbox[0] - buffer or
            shore_bbox[3] < trans_bbox[1] - buffer or trans_bbox[3] < shore_bbox[1] - buffer):
            return None
        
        shoreline = LineString(shoreline_coords)
        transect = LineString(transect_coords)
        
        intersection = shoreline.intersection(transect)
        
        if intersection.is_empty:
            return None
        
        # Get intersection coordinate
        intersect_coord = None
        try:
            if hasattr(intersection, 'coords'):
                coords_list = list(intersection.coords)
                if len(coords_list) > 0:
                    intersect_coord = coords_list[0]
        except:
            pass
        
        if intersect_coord is None:
            return None
        
        # Calculate distance along shoreline
        distance = 0
        min_dist = float('inf')
        best_distance = None
        
        for i in range(len(shoreline_coords) - 1):
            x1, y1 = shoreline_coords[i]
            x2, y2 = shoreline_coords[i + 1]
            
            segment_length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            
            if segment_length == 0:
                distance += segment_length
                continue
            
            # Point-to-line distance
            t = max(0, min(1, ((intersect_coord[0] - x1) * (x2 - x1) + 
                              (intersect_coord[1] - y1) * (y2 - y1)) / (segment_length**2)))
            
            closest_x = x1 + t * (x2 - x1)
            closest_y = y1 + t * (y2 - y1)
            
            dist = math.sqrt((intersect_coord[0] - closest_x)**2 + 
                           (intersect_coord[1] - closest_y)**2)
            
            if dist < min_dist:
                min_dist = dist
                best_distance = distance + t * segment_length
            
            distance += segment_length
        
        if min_dist < 0.001:
            return best_distance
        
        return None
        
    except Exception:
        return None

def process_shoreline_gradients_fast():
    """Main processing function using spatial partitioning."""
    # Parse command line arguments
    limit = None
    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv[1:]):
            if arg == '--limit' and i + 2 < len(sys.argv):
                try:
                    limit = int(sys.argv[i + 2])
                    print(f"Limiting processing to first {limit} shorelines")
                except ValueError:
                    print("Invalid limit value")
    
    print("Loading GeoJSON files...")
    start_time = time.time()
    
    shorelines = load_geojson('shorelines.geojson')
    transects = load_geojson('transects_extended.geojson')
    
    if limit:
        shorelines['features'] = shorelines['features'][:limit]
    
    print(f"Loaded {len(shorelines['features'])} shorelines")
    print(f"Loaded {len(transects['features'])} transects")
    print(f"Loading took {time.time() - start_time:.1f} seconds")
    
    # Build spatial index for transects
    print("Building spatial index...")
    index_start = time.time()
    
    cell_size = 0.05  # ~5.5km grid cells
    transect_grid = defaultdict(list)
    
    for i, transect in enumerate(transects['features']):
        if i % 10000 == 0:
            print(f"  Indexing transect {i+1}/{len(transects['features'])} ({i/len(transects['features'])*100:.1f}%)")
        
        if transect['geometry']['type'] != 'LineString':
            continue
            
        coords = transect['geometry']['coordinates']
        bbox = get_bbox(coords)
        cells = get_grid_cells(bbox, cell_size)
        
        transect_data = {
            'coords': coords,
            'props': transect.get('properties', {}),
            'index': i
        }
        
        for cell in cells:
            transect_grid[cell].append(transect_data)
    
    print(f"Spatial indexing took {time.time() - index_start:.1f} seconds")
    print(f"Created {len(transect_grid)} grid cells")
    print(f"Average transects per cell: {len(transects['features']) / len(transect_grid):.1f}")
    
    # Process shorelines
    processed_shorelines = []
    total_intersections = 0
    total_checks = 0
    process_start = time.time()
    
    for i, shoreline in enumerate(shorelines['features']):
        shore_start = time.time()
        
        if shoreline['geometry']['type'] != 'LineString':
            continue
        
        shoreline_coords = shoreline['geometry']['coordinates']
        shoreline_length = calculate_line_length(shoreline_coords)
        
        # Find nearby transects using spatial index
        shore_bbox = get_bbox(shoreline_coords)
        candidate_cells = get_grid_cells(shore_bbox, cell_size)
        
        candidate_transects = set()
        for cell in candidate_cells:
            for transect in transect_grid.get(cell, []):
                candidate_transects.add(transect['index'])
        
        candidate_count = len(candidate_transects)
        intersections = []
        
        # Check intersections only with nearby transects
        for transect_idx in candidate_transects:
            transect = transects['features'][transect_idx]
            transect_coords = transect['geometry']['coordinates']
            
            total_checks += 1
            intersection_distance = find_intersection_distance_fast(shoreline_coords, transect_coords)
            
            if intersection_distance is not None:
                props = transect.get('properties', {})
                trend = props.get('trend')
                n_points_nonan = props.get('n_points_nonan', 0)
                color = trend_to_color(trend, n_points_nonan)
                
                intersections.append({
                    'distance': intersection_distance,
                    'color': color,
                    'transect_id': props.get('id', 'unknown'),
                    'trend': trend
                })
        
        intersections.sort(key=lambda x: x['distance'])
        total_intersections += len(intersections)
        
        # Create gradient data
        if len(intersections) > 1:
            gradient_coords = []
            gradient_colors = []
            
            for intersection in intersections:
                coord = point_on_line_at_distance(shoreline_coords, intersection['distance'])
                if coord:
                    gradient_coords.append(coord)
                    gradient_colors.append(intersection['color'])
            
            if len(gradient_coords) > 1:
                # Preserve original shoreline properties
                original_props = shoreline.get('properties', {})
                
                processed_shoreline = {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': gradient_coords
                    },
                    'properties': {
                        **original_props,  # Include all original properties
                        'colors': gradient_colors,
                        'original_length': shoreline_length,
                        'intersection_count': len(intersections),
                        'transect_ids': [i['transect_id'] for i in intersections]
                    }
                }
                processed_shorelines.append(processed_shoreline)
        
        # Progress reporting
        shore_time = time.time() - shore_start
        elapsed = time.time() - process_start
        avg_time = elapsed / (i + 1)
        remaining = avg_time * (len(shorelines['features']) - i - 1)
        
        print(f"Shoreline {i+1}/{len(shorelines['features'])} ({(i+1)/len(shorelines['features'])*100:.1f}%): "
              f"{candidate_count} candidates -> {len(intersections)} intersections "
              f"({shore_time:.1f}s, ETA: {remaining/60:.1f}min)")
    
    # Results
    total_time = time.time() - start_time
    print(f"\nSUMMARY:")
    print(f"Total processing time: {total_time/60:.1f} minutes")
    print(f"Total intersection checks: {total_checks:,}")
    print(f"Speedup vs brute force: {(len(shorelines['features']) * len(transects['features']) / total_checks):.1f}x")
    print(f"Total intersections found: {total_intersections}")
    print(f"Shorelines with gradients: {len(processed_shorelines)}")
    print(f"Average intersections per shoreline: {total_intersections/len(shorelines['features']):.1f}")
    
    # Save result
    output = {
        'type': 'FeatureCollection',
        'features': processed_shorelines
    }
    
    save_geojson(output, 'shorelines_with_gradients.geojson')
    print("Saved shorelines_with_gradients.geojson")

if __name__ == '__main__':
    process_shoreline_gradients_fast()
