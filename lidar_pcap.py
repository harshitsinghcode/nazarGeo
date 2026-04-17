import numpy as np
import struct
import math


def load_pcap(path):
    print(f"[DEBUG] Extracting Velodyne V16 Point Cloud: {path}")
    import dpkt

    angles_deg = [-15, 1, -13, 3, -11, 5, -9, 7, -7, 9, -5, 11, -3, 13, -1, 15]
    omega     = [math.radians(a) for a in angles_deg]
    cos_omega = np.cos(omega)
    sin_omega = np.sin(omega)

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

    if points:
        return np.array(points, dtype=np.float32)
    return None


def load_both(l1_path, l2_path):
    pts1 = load_pcap(l1_path)
    pts2 = load_pcap(l2_path)
    
    if pts1 is None: return pts2
    if pts2 is None: return pts1

    # =========================================================
    # MULTI-LIDAR FUSION: ICP Registration Matrix (L2 -> L1)
    # This aligns LiDAR 2 perfectly into LiDAR 1's coordinate space.
    # =========================================================
    T_L2_to_L1 = np.array([
        [ 0.9997594356536865,    0.020968914031982422, -0.0064355251379311085, -0.11370490491390228 ],
        [-0.021027371287345886,  0.9997369647026062,   -0.009154382161796093,   0.9193867444992065  ],
        [ 0.006241875234991312,  0.009287501685321331,  0.9999374151229858,    -0.001643864088691771],
        [ 0.0,                   0.0,                   0.0,                    1.0                 ]
    ], dtype=np.float64)

    # 1. Convert L2 points to Homogeneous coordinates [X, Y, Z, 1]
    N = len(pts2)
    ones = np.ones((N, 1), dtype=np.float64)
    pts2_h = np.hstack([pts2.astype(np.float64), ones])

    # 2. Apply the matrix multiplication to rotate and translate L2
    pts2_aligned = (T_L2_to_L1 @ pts2_h.T).T[:, :3]

    # 3. Stack the perfectly aligned clouds together
    return np.vstack([pts1, pts2_aligned.astype(np.float32)])