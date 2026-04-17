import os
import couchdb
import cfg
import perceive
import project
import match

# 1. Connect to Local CouchDB
COUCH_URL = "http://admin:yourpassword@127.0.0.1:5984/"
DB_NAME = "nazargeo_buildings"

couch = couchdb.Server(COUCH_URL)
if DB_NAME not in couch:
    db = couch.create(DB_NAME)
else:
    db = couch[DB_NAME]

def process_and_store(start_frame, end_frame, frame_step=15):
    """
    frame_step=15 means processing 2 frames per second (for a 30 FPS video).
    """
    for fid in range(start_frame, end_frame + 1, frame_step):
        print(f"\n--- Processing Frame {fid} ---")
        
        # Step A: Perceive (YOLO + SAM + LiDAR)
        perc_res = perceive.run_frame(fid)
        if not perc_res:
            continue
            
        # Step B: Project (Geopy)
        proj_res = project.run_frame(fid)
        
        # Step C: Match (GOB Database)
        match_res = match.run_frame(fid)
        if not match_res or not match_res.get("best_match"):
            continue
            
        best = match_res["best_match"]
        
        # Create a unique ID using the precise GOB centroid
        b_id = f"bldg_{best['centroid_lat']}_{best['centroid_lon']}".replace(".", "_")
        
        doc_data = {
            "_id": b_id,
            "type": "feature",
            "lat": best["centroid_lat"],
            "lon": best["centroid_lon"],
            "best_frame": fid,
            "score": best["score"],
            "depth_m": proj_res["depth_m"],
            "confidence": best["confidence"],
            "image_url": f"/static/out/perceive_vis/frame_{fid:06d}_perceive_vis.jpg" 
        }

        # Deduplication & Score Maximization
        if b_id in db:
            existing_doc = db[b_id]
            # Only update if this frame gives a better match score
            if doc_data["score"] > existing_doc["score"]:
                print(f"[DB] Updating {b_id} with better score: {doc_data['score']:.1f}")
                doc_data["_rev"] = existing_doc["_rev"] # Required by CouchDB to update
                db.save(doc_data)
            else:
                print(f"[DB] Skipped {b_id} - existing score was better.")
        else:
            print(f"[DB] Inserted NEW building: {b_id}")
            db.save(doc_data)

if __name__ == "__main__":
    # Example: Process first 1000 frames
    process_and_store(cfg.FRAME_START, cfg.FRAME_END, frame_step=15)