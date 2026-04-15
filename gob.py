import math
import pandas as pd
from geopy.distance import geodesic


def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_gob(csv_path, ego_lat, ego_lon, radius_m, conf_min=0.0):
    df = pd.read_csv(csv_path)

    possible_lat = [c for c in df.columns if "lat" in c.lower()]
    possible_lon = [c for c in df.columns if "lon" in c.lower()]
    possible_conf = [c for c in df.columns if "conf" in c.lower()]
    possible_poly = [c for c in df.columns if "poly" in c.lower() or "geom" in c.lower() or "wkt" in c.lower()]

    lat_col  = possible_lat[0]  if possible_lat  else "latitude"
    lon_col  = possible_lon[0]  if possible_lon  else "longitude"
    conf_col = possible_conf[0] if possible_conf else None
    poly_col = possible_poly[0] if possible_poly else None

    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
    df = df.dropna(subset=[lat_col, lon_col])

    if conf_col:
        df[conf_col] = pd.to_numeric(df[conf_col], errors="coerce").fillna(0)
        df = df[df[conf_col] >= conf_min]

    lat_deg_per_m = 1 / 111320.0
    lon_deg_per_m = 1 / (111320.0 * math.cos(math.radians(ego_lat)))
    lat_range = radius_m * lat_deg_per_m
    lon_range = radius_m * lon_deg_per_m

    nearby = df[
        (df[lat_col] >= ego_lat - lat_range) &
        (df[lat_col] <= ego_lat + lat_range) &
        (df[lon_col] >= ego_lon - lon_range) &
        (df[lon_col] <= ego_lon + lon_range)
    ].copy()

    nearby["_dist_m"] = nearby.apply(
        lambda r: _haversine_m(ego_lat, ego_lon, r[lat_col], r[lon_col]),
        axis=1
    )
    nearby = nearby[nearby["_dist_m"] <= radius_m].reset_index(drop=True)

    result = []
    for _, row in nearby.iterrows():
        entry = {
            "centroid_lat": float(row[lat_col]),
            "centroid_lon": float(row[lon_col]),
            "dist_m":       float(row["_dist_m"]),
            "confidence":   float(row[conf_col]) if conf_col else None,
            "footprint_w_m": None,
            "raw":          row.to_dict()
        }

        if poly_col and pd.notna(row.get(poly_col)):
            try:
                wkt = str(row[poly_col])
                coords = _parse_wkt_polygon(wkt)
                if coords and len(coords) >= 2:
                    entry["footprint_w_m"] = _polygon_max_side_m(coords)
            except Exception:
                pass

        result.append(entry)

    return result


def _parse_wkt_polygon(wkt):
    import re
    nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", wkt)
    if len(nums) < 4:
        return None
    coords = []
    for i in range(0, len(nums) - 1, 2):
        coords.append((float(nums[i+1]), float(nums[i])))
    return coords


def _polygon_max_side_m(coords):
    max_side = 0.0
    for i in range(len(coords) - 1):
        d = geodesic(coords[i], coords[i+1]).meters
        if d > max_side:
            max_side = d
    return max_side