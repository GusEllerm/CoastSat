#!/usr/bin/env python3
"""
Narrative Zoning Analysis for Shoreline Transects

This script analyzes shoreline transects to identify narrative zones - contiguous segments
of transects with similar characteristics that tell meaningful stories about coastal behavior.

Usage:
    python narrative_zoning.py <site_id> <transects_geojson_file>

Output:
    JSON containing zones and transect classifications for the specified site.
"""

import json
import sys
import argparse
import math
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import numpy as np

try:
    import geopandas as gpd
    import pandas as pd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False

__all__ = ["run_narrative_zoning"]
def run_narrative_zoning(site_id: str, transects_file: str, min_zone_length: int = 3,  zone_definitions: Optional[Dict[str, Any]] = None, sort_by_priority: bool = False) -> Dict[str, Any]:
    """
    Entry point for programmatic use (e.g., Stencila). Returns JSON-serializable result.
    """
    result = analyze_site(site_id, transects_file, min_zone_length, zone_definitions=zone_definitions, sort_by_priority=sort_by_priority)
    return make_json_serializable(result)


def make_json_serializable(obj) -> Any:
    """
    Convert an object to a JSON-serializable format.
    
    Handles common issues like:
    - NaN values (convert to None/null)
    - Infinity values (convert to large numbers or None)
    - Shapely geometries (convert to coordinate lists)
    - Pandas Series (convert to lists)
    - NumPy types (convert to Python types)
    """
    if obj is None:
        return None
    elif isinstance(obj, (int, str, bool)):
        return obj
    elif isinstance(obj, float):
        if math.isnan(obj):
            return None
        elif math.isinf(obj):
            return 1e308 if obj > 0 else -1e308  # Large but finite numbers
        else:
            return obj
    elif isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_serializable(item) for item in obj]
    elif hasattr(obj, '__geo_interface__'):  # Shapely geometries
        # Convert to simplified coordinate representation
        try:
            geo = obj.__geo_interface__
            if geo['type'] == 'LineString':
                return {
                    'type': 'LineString',
                    'coordinates': geo['coordinates']
                }
            elif geo['type'] == 'Point':
                return {
                    'type': 'Point', 
                    'coordinates': geo['coordinates']
                }
            else:
                return geo
        except:
            return str(obj)
    elif hasattr(obj, 'tolist'):  # NumPy arrays
        return make_json_serializable(obj.tolist())
    elif hasattr(obj, 'to_dict'):  # Pandas Series
        return make_json_serializable(obj.to_dict())
    else:
        # Last resort: convert to string
        return str(obj)


def get_default_zone_definitions() -> Dict[str, Any]:
    """
    Get the default zone definitions used by the system.
    
    Returns:
        Dictionary of zone definitions with priority-based classification rules
    """
    return {
        "no_data": {
            "priority": 1,
            "conditions": [
                {"field": "trend", "operator": "is_null", "value": None}
            ],
            "description_template": "No data zone spanning {length_km:.1f}km where insufficient observations prevent trend analysis."
        },
        "rapid_erosion": {
            "priority": 2,
            "conditions": [
                {"field": "trend", "operator": "<", "value": -0.8}
            ],
            "description_template": "Critical erosion hotspot spanning {length_km:.1f}km with average retreat of {avg_trend_abs:.1f}m/year. This area requires immediate attention and monitoring."
        },
        "moderate_erosion": {
            "priority": 3,
            "conditions": [
                {"field": "trend", "operator": "<", "value": -0.3}
            ],
            "description_template": "Erosion zone extending {length_km:.1f}km showing consistent retreat averaging {avg_trend_abs:.1f}m/year. Ongoing erosion processes are evident."
        },
        "rapid_accretion": {
            "priority": 4,
            "conditions": [
                {"field": "trend", "operator": ">", "value": 0.8}
            ],
            "description_template": "Dynamic accretion zone over {length_km:.1f}km with significant sand accumulation averaging {avg_trend:.1f}m/year. This area shows strong sediment deposition."
        },
        "moderate_accretion": {
            "priority": 5,
            "conditions": [
                {"field": "trend", "operator": ">", "value": 0.3}
            ],
            "description_template": "Stable accretion zone spanning {length_km:.1f}km with gradual beach building averaging {avg_trend:.1f}m/year. Positive sediment balance is maintained."
        },
        "high_uncertainty": {
            "priority": 6,
            "conditions": [
                {"field": "r2_score", "operator": "<", "value": 0.05, "allow_null": True},
                {"field": "rmse", "operator": ">", "value": 30, "allow_null": True}
            ],
            "logic": "OR",  # Either condition can trigger this zone
            "description_template": "Data-limited zone over {length_km:.1f}km where shoreline trends are difficult to determine reliably. Additional monitoring may be needed."
        },
        "steep_beach": {
            "priority": 7,
            "conditions": [
                {"field": "beach_slope", "operator": ">", "value": 0.08}
            ],
            "description_template": "High-energy beach zone over {length_km:.1f}km characterized by steep beach profiles. This area may be vulnerable to storm impacts."
        },
        "low_energy": {
            "priority": 8,
            "conditions": [
                {"field": "beach_slope", "operator": "<", "value": 0.04}
            ],
            "description_template": "Protected shoreline segment spanning {length_km:.1f}km with gentle beach profiles indicating low wave energy conditions."
        },
        "stable": {
            "priority": 9,
            "conditions": [],  # Default catch-all zone
            "description_template": "Stable shoreline segment extending {length_km:.1f}km showing minimal change over time. This area exhibits natural equilibrium."
        }
    }


def evaluate_condition(value: Any, condition: Dict[str, Any]) -> bool:
    """
    Evaluate a single condition against a value.
    
    Args:
        value: The value to test
        condition: Condition dictionary with operator, value, etc.
        
    Returns:
        True if condition is met, False otherwise
    """
    operator = condition["operator"]
    threshold = condition["value"]
    allow_null = condition.get("allow_null", False)
    
    # Handle null values
    if value is None:
        if operator == "is_null":
            return True
        return allow_null
    
    # Handle different operators
    if operator == "<":
        return value < threshold
    elif operator == "<=":
        return value <= threshold
    elif operator == ">":
        return value > threshold
    elif operator == ">=":
        return value >= threshold
    elif operator == "==":
        return value == threshold
    elif operator == "!=":
        return value != threshold
    elif operator == "is_null":
        return False  # value is not None here
    else:
        raise ValueError(f"Unknown operator: {operator}")


def classify_transect_zone_custom(transect: Dict[str, Any], zone_definitions: Dict[str, Any]) -> str:
    """
    Classify a transect using custom zone definitions.
    
    Args:
        transect: Transect feature with properties
        zone_definitions: Dictionary of zone definitions
        
    Returns:
        Zone classification string
    """
    props = transect['properties']
    
    # Sort zones by priority (lower number = higher priority)
    sorted_zones = sorted(zone_definitions.items(), key=lambda x: x[1].get('priority', 999))
    
    for zone_name, zone_def in sorted_zones:
        conditions = zone_def.get('conditions', [])
        
        # If no conditions, this is a catch-all zone
        if not conditions:
            return zone_name
            
        logic = zone_def.get('logic', 'AND')
        
        if logic == 'AND':
            # All conditions must be true
            if all(evaluate_condition(props.get(cond['field']), cond) for cond in conditions):
                return zone_name
        elif logic == 'OR':
            # Any condition can be true
            if any(evaluate_condition(props.get(cond['field']), cond) for cond in conditions):
                return zone_name
    
    # Fallback to stable if no zones match
    return "stable"


def load_transects_for_site(site_id: str, transects_file: str) -> List[Dict[str, Any]]:
    """
    Load and filter transects for a specific site_id.
    
    Args:
        site_id: The site identifier to filter by (e.g., 'aus0001')
        transects_file: Path to the transects GeoJSON file
        
    Returns:
        List of transect features for the specified site
    """
    try:
        with open(transects_file, 'r') as f:
            data = json.load(f)
        
        # Filter features by site_id
        site_transects = [
            feature for feature in data['features'] 
            if feature['properties']['site_id'] == site_id
        ]
        
        # Sort by transect ID to ensure proper ordering
        site_transects.sort(key=lambda x: x['properties']['id'])
        
        return site_transects
        
    except FileNotFoundError:
        print(f"Error: Could not find transects file: {transects_file}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in file: {transects_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error loading transects: {e}", file=sys.stderr)
        sys.exit(1)


def convert_geodataframe_to_transects(gdf, site_id: str) -> List[Dict[str, Any]]:
    """
    Convert a GeoDataFrame to the transect format expected by narrative zoning.
    
    Args:
        gdf: GeoDataFrame containing transect data
        site_id: Site ID to filter for
        
    Returns:
        List of transect dictionaries with required properties
    """
    if not GEOPANDAS_AVAILABLE:
        raise ImportError("geopandas is required for analyze_site_from_geodataframe function")
    
    # Filter for the specific site
    site_transects = gdf[gdf['site_id'] == site_id].copy()
    
    if len(site_transects) == 0:
        return []
    
    # Sort by transect_id to ensure proper ordering
    site_transects = site_transects.sort_values('id')
    
    # Convert to the expected transect format
    transects = []
    for idx, row in site_transects.iterrows():
        # Extract properties from the GeoDataFrame row
        transect = {
            'properties': {
                'transect_id': row.get('id'),  # Use 'id' column, not 'transect_id'
                'site_id': row.get('site_id'),
                'trend': row.get('trend'),
                'beach_slope': row.get('beach_slope'), 
                'r2_score': row.get('r2_score'),
                'rmse': row.get('rmse'),
                'along_dist': row.get('along_dist'),  # Add along_dist for zone calculations
                'id': row.get('id'),  # Also add 'id' for backward compatibility
                # Add any other properties that might be needed
            },
            'geometry': row.get('geometry')  # Include geometry if needed
        }
        transects.append(transect)
    
    return transects


def classify_transect_zone(transect: Dict[str, Any], zone_definitions: Optional[Dict[str, Any]] = None) -> str:
    """
    Classify a single transect into a narrative zone category based on its properties.
    
    Args:
        transect: A single transect feature with properties
        zone_definitions: Optional custom zone definitions. If None, uses defaults.
        
    Returns:
        Zone classification string
    """
    if zone_definitions is None:
        zone_definitions = get_default_zone_definitions()
    
    return classify_transect_zone_custom(transect, zone_definitions)


def identify_narrative_zones(transects: List[Dict[str, Any]], min_zone_length: int = 3, zone_definitions: Optional[Dict[str, Any]] = None, sort_by_priority: bool = False) -> List[Dict[str, Any]]:
    """
    Identify contiguous narrative zones from a sequence of transects.
    
    Args:
        transects: List of transect features sorted by position
        min_zone_length: Minimum number of transects to form a zone
        zone_definitions: Optional custom zone definitions
        sort_by_priority: If True, return zones sorted by zone priority instead of spatial order
        
    Returns:
        List of zone dictionaries with metadata
    """
    if not transects:
        return []

    # Precompute and store classification for each transect to avoid recomputation
    for transect in transects:
        transect['zone_classification'] = classify_transect_zone(transect, zone_definitions)

    zones = []
    current_zone_type = None
    current_zone_start = 0
    current_zone_transects = []
    zone_counter = 1  # Start counting from 1

    for i, transect in enumerate(transects):
        zone_type = transect['zone_classification']

        if zone_type != current_zone_type:
            # End current zone if it meets minimum length
            if current_zone_type is not None and len(current_zone_transects) >= min_zone_length:
                zones.append(create_zone_summary(current_zone_type, current_zone_transects, current_zone_start, zone_definitions, zone_counter))
                zone_counter += 1

            # Start new zone
            current_zone_type = zone_type
            current_zone_start = i
            current_zone_transects = [transect]
        else:
            # Continue current zone
            current_zone_transects.append(transect)

    # Don't forget the last zone
    if current_zone_type is not None and len(current_zone_transects) >= min_zone_length:
        zones.append(create_zone_summary(current_zone_type, current_zone_transects, current_zone_start, zone_definitions, zone_counter))

    # Sort zones by priority if requested
    if sort_by_priority and zone_definitions:
        # Get priority for each zone type, defaulting to 999 for unknown types
        zones.sort(key=lambda zone: zone_definitions.get(zone['zone_type'], {}).get('priority', 999))

    return zones


def create_zone_summary(zone_type: str, transects: List[Dict[str, Any]], start_index: int, zone_definitions: Optional[Dict[str, Any]] = None, zone_index: int = 1) -> Dict[str, Any]:
    """Create a summary of a narrative zone."""
    if not transects:
        return {}
    
    # Calculate zone statistics from transect properties using numpy for aggregates
    trends = np.array([t['properties']['trend'] for t in transects if t['properties']['trend'] is not None])
    slopes = np.array([t['properties']['beach_slope'] for t in transects if t['properties']['beach_slope'] is not None])
    r2s = np.array([t['properties']['r2_score'] for t in transects if t['properties']['r2_score'] is not None])

    rmses = np.array([t['properties']['rmse'] for t in transects if t['properties'].get('rmse') is not None])
    maes = np.array([t['properties']['mae'] for t in transects if t['properties'].get('mae') is not None])
    cils = np.array([t['properties']['cil'] for t in transects if t['properties'].get('cil') is not None])
    cius = np.array([t['properties']['ciu'] for t in transects if t['properties'].get('ciu') is not None])
    orientations = np.array([t['properties']['orientation'] for t in transects if t['properties'].get('orientation') is not None])

    start_dist = transects[0]['properties']['along_dist']
    end_dist = transects[-1]['properties']['along_dist']

    zone_summary = {
        'zone_type': zone_type,
        'transect_count': len(transects),
        'start_index': start_index,
        'end_index': start_index + len(transects) - 1,
        'start_distance': start_dist,
        'end_distance': end_dist,
        'length_meters': abs(end_dist - start_dist),
        'start_transect_id': transects[0]['properties']['id'],
        'end_transect_id': transects[-1]['properties']['id'],

        # Renamed fields
        'mean_trend': trends.mean() if trends.size > 0 else None,
        'avg_beach_slope': slopes.mean() if slopes.size > 0 else None,

        # Existing fields
        'avg_r2': r2s.mean() if r2s.size > 0 else None,
        'max_trend': trends.max() if trends.size > 0 else None,
        'min_trend': trends.min() if trends.size > 0 else None,

        # New aggregate metrics
        'avg_rmse': rmses.mean() if rmses.size > 0 else None,
        'avg_mae': maes.mean() if maes.size > 0 else None,
        'avg_cil': cils.mean() if cils.size > 0 else None,
        'avg_ciu': cius.mean() if cius.size > 0 else None,
        'avg_orientation': orientations.mean() if orientations.size > 0 else None,

        'transect_ids': [t['properties']['id'] for t in transects]
    }
    
    # Generate unique zone name
    site_id = transects[0]['properties'].get('site_id', 'unknown_site')
    zone_summary['zone_name'] = f"{site_id}_{zone_type}_zone_{zone_index:02d}"
    
    # Add narrative description using zone definitions
    zone_summary['narrative_description'] = get_zone_narrative_description_custom(zone_summary, zone_definitions)
    
    return zone_summary


def get_zone_narrative_description_custom(zone: Dict[str, Any], zone_definitions: Optional[Dict[str, Any]] = None) -> str:
    """Generate a narrative description for a zone using custom zone definitions."""
    if zone_definitions is None:
        zone_definitions = get_default_zone_definitions()
    
    zone_type = zone['zone_type']
    zone_def = zone_definitions.get(zone_type, {})
    template = zone_def.get('description_template', f"Unclassified zone spanning {{length_km:.1f}}km.")
    
    # Prepare template variables
    length_km = zone['length_meters'] / 1000
    mean_trend = zone.get('mean_trend', 0) or 0
    avg_trend_abs = abs(mean_trend)  # For backward compatibility with templates
    
    template_vars = {
        'length_km': length_km,
        'mean_trend': mean_trend,
        'avg_trend': mean_trend,  
        'avg_trend_abs': avg_trend_abs,
        'transect_count': zone.get('transect_count', 0),
        'avg_beach_slope': zone.get('avg_beach_slope', 0) or 0,
        'avg_slope': zone.get('avg_beach_slope', 0) or 0,  
        'avg_r2': zone.get('avg_r2', 0) or 0,
        'max_trend': zone.get('max_trend', 0) or 0,
        'min_trend': zone.get('min_trend', 0) or 0,
        # New aggregate metrics
        'avg_rmse': zone.get('avg_rmse', 0) or 0,
        'avg_mae': zone.get('avg_mae', 0) or 0,
        'avg_cil': zone.get('avg_cil', 0) or 0,
        'avg_ciu': zone.get('avg_ciu', 0) or 0,
        'avg_orientation': zone.get('avg_orientation', 0) or 0
    }
    
    try:
        return template.format(**template_vars)
    except (KeyError, ValueError) as e:
        # Fallback if template formatting fails
        return f"Zone spanning {length_km:.1f}km with {zone.get('transect_count', 0)} transects."


def get_zone_narrative_description(zone: Dict[str, Any]) -> str:
    """Generate a narrative description for a zone using default definitions."""
    return get_zone_narrative_description_custom(zone, None)


def create_transect_dict(transects: List[Dict[str, Any]], zone_definitions: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    """
    Create a dictionary of transects with their zone classifications.
    
    Args:
        transects: List of transect features
        zone_definitions: Optional custom zone definitions
        
    Returns:
        Dictionary mapping transect IDs to transect data with zone classification
    """
    transect_dict = {}

    for transect in transects:
        transect_id = transect['properties']['id']
        zone_type = transect.get('zone_classification') or classify_transect_zone(transect, zone_definitions)

        transect_dict[transect_id] = {
            'properties': transect['properties'],
            'geometry': transect['geometry'],
            'zone_classification': zone_type
        }

    return transect_dict


def analyze_site_from_geodataframe(site_id: str, gdf, min_zone_length: int = 3, zone_definitions: Optional[Dict[str, Any]] = None, sort_by_priority: bool = False) -> Dict[str, Any]:
    """
    Complete narrative zoning analysis for a site using a GeoDataFrame.
    
    Args:
        site_id: Site identifier
        gdf: GeoDataFrame containing transect data
        min_zone_length: Minimum transects per zone
        zone_definitions: Optional custom zone definitions. If None, uses defaults.
        sort_by_priority: If True, return zones sorted by zone priority instead of spatial order
        
    Returns:
        Dictionary containing zones and transect classifications
    """
    if not GEOPANDAS_AVAILABLE:
        raise ImportError("geopandas is required for analyze_site_from_geodataframe function")
    
    if zone_definitions is None:
        zone_definitions = get_default_zone_definitions()
    
    # Convert GeoDataFrame to transect format
    transects = convert_geodataframe_to_transects(gdf, site_id)
    
    if not transects:
        result = {
            'site_id': site_id,
            'transect_count': 0,
            'zones': [],
            'transects': {},
            'error': 'No transects found for site'
        }
        return make_json_serializable(result)
    
    # Identify narrative zones
    zones = identify_narrative_zones(transects, min_zone_length, zone_definitions, sort_by_priority)
    
    # Create transect dictionary with zone classifications
    transect_dict = create_transect_dict(transects, zone_definitions)
    
    # Calculate summary statistics
    zone_type_counts = {}
    for zone in zones:
        zone_type = zone['zone_type']
        zone_type_counts[zone_type] = zone_type_counts.get(zone_type, 0) + 1
    
    result = {
        'site_id': site_id,
        'transect_count': len(transects),
        'zone_count': len(zones),
        'zones': zones,
        'zone_type_distribution': zone_type_counts,
        'transects': transect_dict,
        'zone_definitions_used': zone_definitions,
        'analysis_parameters': {
            'min_zone_length': min_zone_length
        }
    }
    
    return make_json_serializable(result)


def analyze_site(site_id: str, transects_file: str, min_zone_length: int = 3, zone_definitions: Optional[Dict[str, Any]] = None, sort_by_priority: bool = False) -> Dict[str, Any]:
    """
    Complete narrative zoning analysis for a site using a file path.
    
    Args:
        site_id: Site identifier
        transects_file: Path to transects GeoJSON file
        min_zone_length: Minimum transects per zone
        zone_definitions: Optional custom zone definitions. If None, uses defaults.
        sort_by_priority: If True, return zones sorted by zone priority instead of spatial order
        
    Returns:
        Dictionary containing zones and transect classifications
    """
    if zone_definitions is None:
        zone_definitions = get_default_zone_definitions()
    
    # Load transects for the site
    transects = load_transects_for_site(site_id, transects_file)
    
    if not transects:
        result = {
            'site_id': site_id,
            'transect_count': 0,
            'zones': [],
            'transects': {},
            'error': 'No transects found for site'
        }
        return make_json_serializable(result)
    
    # Identify narrative zones
    zones = identify_narrative_zones(transects, min_zone_length, zone_definitions, sort_by_priority)
    
    # Create transect dictionary with zone classifications
    transect_dict = create_transect_dict(transects, zone_definitions)
    
    # Calculate summary statistics
    zone_type_counts = {}
    for zone in zones:
        zone_type = zone['zone_type']
        zone_type_counts[zone_type] = zone_type_counts.get(zone_type, 0) + 1
    
    result = {
        'site_id': site_id,
        'transect_count': len(transects),
        'zone_count': len(zones),
        'zones': zones,
        'zone_type_distribution': zone_type_counts,
        'transects': transect_dict,
        'zone_definitions_used': zone_definitions,
        'analysis_parameters': {
            'min_zone_length': min_zone_length
        }
    }
    
    return make_json_serializable(result)


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description='Generate narrative zones for shoreline transects',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python narrative_zoning.py aus0001 transects_extended.geojson
  python narrative_zoning.py aus0002 data/transects.geojson --min-zone-length 5
  python narrative_zoning.py aus0003 data/transects.geojson --zone-definitions custom_zones.json
  python narrative_zoning.py aus0004 data/transects.geojson --sort-by-priority
        """
    )
    
    parser.add_argument('site_id', nargs='?', help='Site ID to analyze (e.g., aus0001)')
    parser.add_argument('transects_file', nargs='?', help='Path to transects GeoJSON file')
    parser.add_argument('--min-zone-length', type=int, default=3,
                       help='Minimum number of transects to form a zone (default: 3)')
    parser.add_argument('--zone-definitions', help='Path to custom zone definitions JSON file')
    parser.add_argument('--sort-by-priority', action='store_true',
                       help='Sort zones by priority instead of spatial order')
    parser.add_argument('--output', '-o', help='Output JSON file (default: stdout)')
    parser.add_argument('--pretty', action='store_true', 
                       help='Pretty-print JSON output')
    parser.add_argument('--show-default-zones', action='store_true',
                       help='Print default zone definitions and exit')
    
    args = parser.parse_args()
    
    # Show default zone definitions if requested
    if args.show_default_zones:
        default_zones = get_default_zone_definitions()
        print(json.dumps(default_zones, indent=2, ensure_ascii=False))
        return
    
    # Check required arguments if not showing defaults
    if not args.site_id or not args.transects_file:
        parser.error("site_id and transects_file are required unless using --show-default-zones")
    
    # Load custom zone definitions if provided
    zone_definitions = None
    if args.zone_definitions:
        try:
            with open(args.zone_definitions, 'r') as f:
                zone_definitions = json.load(f)
            print(f"Loaded custom zone definitions from {args.zone_definitions}", file=sys.stderr)
        except Exception as e:
            print(f"Error loading zone definitions: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Perform analysis
    result = analyze_site(args.site_id, args.transects_file, args.min_zone_length, zone_definitions, args.sort_by_priority)
    
    # Format output
    if args.pretty:
        output = json.dumps(result, indent=2, ensure_ascii=False)
    else:
        output = json.dumps(result, ensure_ascii=False)
    
    # Write output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
