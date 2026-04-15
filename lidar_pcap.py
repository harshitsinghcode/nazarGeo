import numpy as np
import struct
import math

def load_pcap(path):
    print(f"[DEBUG] Extracting Velodyne V16 Point Cloud: {path}")
    import dpkt

    angles_deg = [-15, 1, -13, 3, -11, 5, -9, 7, -7, 9, -5, 11, -3, 13, -1, 15]
    omega = [math.radians(a) for a in angles_deg]
    cos_omega = np.cos(omega)
    sin_omega = np.sin(omega)

    points = []
    with open(path, "rb") as f:
        pcap = dpkt.pcap.Reader(f)
        for _, buf in pcap:
            if len(buf) < 42: continue
            payload = buf[42:]
            if len(payload) != 1206: continue

            for i in range(12):
                block_offset = i * 100
                flag = struct.unpack_from('<H', payload, block_offset)[0]
                if flag != 0xEEFF: continue

                azimuth = struct.unpack_from('<H', payload, block_offset + 2)[0] / 100.0
                alpha = math.radians(azimuth)
                cos_alpha = math.cos(alpha)
                sin_alpha = math.sin(alpha)

                for firing in range(2):
                    for laser_id in range(16):
                        data_offset = block_offset + 4 + (firing * 48) + (laser_id * 3)
                        dist_raw = struct.unpack_from('<H', payload, data_offset)[0]
                        distance = dist_raw * 0.002 
                        
                        if distance > 1.0: # Keep everything beyond 1 meter
                            # RAW VELODYNE: X=Right, Y=Forward, Z=Up
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
    if pts1 is not None and pts2 is not None:
        return np.vstack([pts1, pts2])
    return pts1