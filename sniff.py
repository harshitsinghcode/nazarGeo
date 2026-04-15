import dpkt

pcap_path = r"C:\Users\Admin\Desktop\falcons\l1_sliced_740_to_940.pcap"

try:
    with open(pcap_path, 'rb') as f:
        pcap = dpkt.pcap.Reader(f)
        for ts, buf in pcap:
            payload = len(buf) - 42
            print("\n========================================")
            print(f"🔍 First Packet Payload Size: {payload} bytes")
            
            if payload in [1200, 1164, 1206, 1248]:
                print("🎯 DIAGNOSIS: You have a VELODYNE or ROBOSENSE!")
            elif payload == 1080:
                print("🎯 DIAGNOSIS: You have a HESAI!")
            elif payload in [6400, 12608, 24832]:
                print("🎯 DIAGNOSIS: You have an OUSTER!")
            else:
                print("🎯 DIAGNOSIS: Unknown format.")
            print("========================================\n")
            break
except Exception as e:
    print(f"Error: {e}")