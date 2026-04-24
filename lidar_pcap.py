import numpy as np
import struct
import math

_cache = {} 


def load_pcap(path):
    if path in _cache:
        print(f"[LiDAR] cache hit: {path}")
        return _cache[path]

    print(f"[DEBUG] Extracting Velodyne V16 Point Cloud: {path}")
    import dpkt

    angles_deg = [-15, 1, -13, 3, -11, 5, -9, 7, -7, 9, -5, 11, -3, 13, -1, 15]
    omega      = [math.radians(a) for a in angles_deg]
    cos_omega  = np.cos(omega)
    sin_omega  = np.sin(omega)

    points = []

    with open(path, "rb") as f:
        pcap = dpkt.pcap.Reader(f)
        for _, buf in pcap:
            if len(buf) < 42:
                continue
            payload = buf[42:]
            if len(payload) != 1206:
                continue

            for i in range(12):
                block_offset = i * 100
                flag = struct.unpack_from('<H', payload, block_offset)[0]
                if flag != 0xEEFF:
                    continue

                azimuth   = struct.unpack_from('<H', payload, block_offset + 2)[0] / 100.0
                alpha     = math.radians(azimuth)
                cos_alpha = math.cos(alpha)
                sin_alpha = math.sin(alpha)

                for firing in range(2):
                    for laser_id in range(16):
                        data_offset = block_offset + 4 + (firing * 48) + (laser_id * 3)
                        dist_raw    = struct.unpack_from('<H', payload, data_offset)[0]
                        distance    = dist_raw * 0.002

                        if distance > 1.0:
                            x = distance * cos_omega[laser_id] * sin_alpha
                            y = distance * cos_omega[laser_id] * cos_alpha
                            z = distance * sin_omega[laser_id]
                            points.append((x, y, z))

    result = np.array(points, dtype=np.float32) if points else None
    _cache[path] = result
    return result


def load_both(l1_path, l2_path):
    pts1 = load_pcap(l1_path)
    pts2 = load_pcap(l2_path)

    if pts1 is None:
        return pts2
    if pts2 is None:
        return pts1

    T_L2_to_L1 = np.array([
        [ 0.9997594356536865,    0.020968914031982422, -0.0064355251379311085, -0.11370490491390228 ],
        [-0.021027371287345886,  0.9997369647026062,   -0.009154382161796093,   0.9193867444992065  ],
        [ 0.006241875234991312,  0.009287501685321331,  0.9999374151229858,    -0.001643864088691771],
        [ 0.0,                   0.0,                   0.0,                    1.0                 ]
    ], dtype=np.float64)

    N     = len(pts2)
    ones  = np.ones((N, 1), dtype=np.float64)
    pts2_h       = np.hstack([pts2.astype(np.float64), ones])
    pts2_aligned = (T_L2_to_L1 @ pts2_h.T).T[:, :3]

    return np.vstack([pts1, pts2_aligned.astype(np.float32)])