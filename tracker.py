# # import numpy as np
# # import math
# # from collections import defaultdict


# # def _haversine_m(lat1, lon1, lat2, lon2):
# #     R = 6371000.0
# #     phi1, phi2 = math.radians(lat1), math.radians(lat2)
# #     dphi = math.radians(lat2 - lat1)
# #     dlam = math.radians(lon2 - lon1)
# #     a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
# #     return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


# # class BuildingKalmanFilter:
# #     def __init__(self, lat, lon, depth_m):
# #         self.x = np.array([lat, lon, depth_m, 0.0, 0.0], dtype=np.float64)

# #         self.P = np.diag([
# #             (5e-5)**2,
# #             (5e-5)**2,
# #             10.0**2,
# #             (1e-5)**2,
# #             (1e-5)**2
# #         ])

# #         self.Q = np.diag([
# #             (1e-6)**2,
# #             (1e-6)**2,
# #             0.5**2,
# #             (5e-7)**2,
# #             (5e-7)**2
# #         ])

# #         self.R = np.diag([
# #             (3e-5)**2,
# #             (3e-5)**2,
# #             5.0**2
# #         ])

# #         self.F = np.eye(5)
# #         self.F[0, 3] = 1.0
# #         self.F[1, 4] = 1.0

# #         self.H = np.zeros((3, 5))
# #         self.H[0, 0] = 1.0
# #         self.H[1, 1] = 1.0
# #         self.H[2, 2] = 1.0

# #         self.hits       = 1
# #         self.misses     = 0
# #         self.age        = 0
# #         self.track_id   = None

# #     def predict(self):
# #         self.x = self.F @ self.x
# #         self.P = self.F @ self.P @ self.F.T + self.Q
# #         self.age += 1
# #         self.misses += 1

# #     def update(self, lat, lon, depth_m):
# #         z = np.array([lat, lon, depth_m])
# #         y = z - self.H @ self.x
# #         S = self.H @ self.P @ self.H.T + self.R
# #         K = self.P @ self.H.T @ np.linalg.inv(S)
# #         self.x = self.x + K @ y
# #         self.P = (np.eye(5) - K @ self.H) @ self.P
# #         self.hits += 1
# #         self.misses = 0

# #     @property
# #     def lat(self):
# #         return float(self.x[0])

# #     @property
# #     def lon(self):
# #         return float(self.x[1])

# #     @property
# #     def depth(self):
# #         return float(self.x[2])

# #     def distance_to(self, lat, lon):
# #         return _haversine_m(self.lat, self.lon, lat, lon)


# # class BuildingSORT:
# #     def __init__(self,
# #                  max_misses=5,
# #                  min_hits=2,
# #                  association_threshold_m=25.0):
# #         self.tracks              = []
# #         self.next_id             = 1
# #         self.max_misses          = max_misses
# #         self.min_hits            = min_hits
# #         self.assoc_thresh        = association_threshold_m
# #         self._confirmed_history  = defaultdict(list)

# #     def _hungarian(self, cost):
# #         from scipy.optimize import linear_sum_assignment
# #         r, c = linear_sum_assignment(cost)
# #         return list(zip(r, c))

# #     def update(self, detections):
# #         for trk in self.tracks:
# #             trk.predict()

# #         if not self.tracks:
# #             for det in detections:
# #                 kf = BuildingKalmanFilter(det["lat"], det["lon"], det["depth"])
# #                 kf.track_id = self.next_id
# #                 self.next_id += 1
# #                 self.tracks.append(kf)
# #             return self._active_tracks()

# #         if not detections:
# #             self.tracks = [t for t in self.tracks if t.misses <= self.max_misses]
# #             return self._active_tracks()

# #         cost = np.zeros((len(self.tracks), len(detections)))
# #         for i, trk in enumerate(self.tracks):
# #             for j, det in enumerate(detections):
# #                 cost[i, j] = trk.distance_to(det["lat"], det["lon"])

# #         pairs = self._hungarian(cost)

# #         matched_trk = set()
# #         matched_det = set()
# #         for i, j in pairs:
# #             if cost[i, j] < self.assoc_thresh:
# #                 self.tracks[i].update(detections[j]["lat"],
# #                                       detections[j]["lon"],
# #                                       detections[j]["depth"])
# #                 matched_trk.add(i)
# #                 matched_det.add(j)

# #         for j, det in enumerate(detections):
# #             if j not in matched_det:
# #                 kf = BuildingKalmanFilter(det["lat"], det["lon"], det["depth"])
# #                 kf.track_id = self.next_id
# #                 self.next_id += 1
# #                 self.tracks.append(kf)

# #         self.tracks = [t for t in self.tracks if t.misses <= self.max_misses]

# #         return self._active_tracks()

# #     def _active_tracks(self):
# #         confirmed = []
# #         for t in self.tracks:
# #             if t.hits >= self.min_hits:
# #                 confirmed.append({
# #                     "track_id": t.track_id,
# #                     "lat":      t.lat,
# #                     "lon":      t.lon,
# #                     "depth":    t.depth,
# #                     "hits":     t.hits,
# #                     "misses":   t.misses,
# #                     "age":      t.age
# #                 })
# #         return confirmed


# # class GPSStabilizer:
# #     def __init__(self):
# #         self.sort = BuildingSORT()
# #         self._frame_results = []

# #     def ingest(self, frame_id, match_result, perceive_result):
# #         if match_result is None or perceive_result is None:
# #             self.sort.update([])
# #             return None

# #         best = match_result["best_match"]
# #         depth = perceive_result.get("median_depth", 25.0)

# #         detections = [{
# #             "lat":   best["centroid_lat"],
# #             "lon":   best["centroid_lon"],
# #             "depth": depth,
# #             "score": best["score"],
# #         }]

# #         for cand in match_result.get("all_candidates", [])[1:4]:
# #             detections.append({
# #                 "lat":   cand["centroid_lat"],
# #                 "lon":   cand["centroid_lon"],
# #                 "depth": depth,
# #                 "score": cand["score"],
# #             })

# #         active = self.sort.update(detections)

# #         if not active:
# #             return None

# #         best_track = max(active, key=lambda t: t["hits"])

# #         result = {
# #             "frame_id":    frame_id,
# #             "track_id":    best_track["track_id"],
# #             "stable_lat":  best_track["lat"],
# #             "stable_lon":  best_track["lon"],
# #             "stable_depth":best_track["depth"],
# #             "track_hits":  best_track["hits"],
# #             "track_age":   best_track["age"],
# #             "raw_lat":     best["centroid_lat"],
# #             "raw_lon":     best["centroid_lon"],
# #             "raw_score":   best["score"],
# #             "smoothing_delta_m": _haversine_m(
# #                 best["centroid_lat"], best["centroid_lon"],
# #                 best_track["lat"],   best_track["lon"]
# #             ),
# #             "gmaps": f"https://www.google.com/maps/search/?api=1&query={best_track['lat']},{best_track['lon']}"
# #         }

# #         self._frame_results.append(result)
# #         return result

# #     def summary(self):
# #         if not self._frame_results:
# #             return {}
# #         lats   = [r["stable_lat"]  for r in self._frame_results]
# #         lons   = [r["stable_lon"]  for r in self._frame_results]
# #         deltas = [r["smoothing_delta_m"] for r in self._frame_results]
# #         return {
# #             "frames_processed": len(self._frame_results),
# #             "mean_lat":         float(np.mean(lats)),
# #             "mean_lon":         float(np.mean(lons)),
# #             "lat_std_m":        float(np.std(lats) * 111320),
# #             "lon_std_m":        float(np.std(lons) * 111320 * math.cos(math.radians(np.mean(lats)))),
# #             "mean_smoothing_delta_m": float(np.mean(deltas)),
# #             "max_smoothing_delta_m":  float(np.max(deltas)),
# #         }

# # #--------------------------------------------------------------------------------------------------------------------


# # # import numpy as np
# # # import math
# # # from collections import defaultdict


# # # # ─── HELPERS ──────────────────────────────────────────────────────────────────

# # # def _haversine_m(lat1, lon1, lat2, lon2):
# # #     R = 6371000.0
# # #     phi1, phi2 = math.radians(lat1), math.radians(lat2)
# # #     dphi = math.radians(lat2 - lat1)
# # #     dlam = math.radians(lon2 - lon1)
# # #     a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
# # #     return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


# # # # ─── PER-BUILDING KALMAN FILTER ───────────────────────────────────────────────
# # # # State: [lat, lon, depth, vel_lat, vel_lon]
# # # # Buildings are STATIC — velocity should stay near zero.
# # # # We use a very small process noise on velocity to allow slow drift correction
# # # # but strongly resist large jumps.

# # # class BuildingKalmanFilter:
# # #     def __init__(self, lat, lon, depth_m, score=50.0):
# # #         self.x = np.array([lat, lon, depth_m, 0.0, 0.0], dtype=np.float64)

# # #         # Initial uncertainty: ~5m in position, 10m in depth
# # #         self.P = np.diag([
# # #             (4.5e-5)**2,   # lat  (~5 m)
# # #             (4.5e-5)**2,   # lon  (~5 m)
# # #             8.0**2,        # depth (8 m)
# # #             (5e-7)**2,     # vel_lat (tiny)
# # #             (5e-7)**2,     # vel_lon (tiny)
# # #         ])

# # #         # Process noise: buildings don't move, velocity virtually zero
# # #         self.Q = np.diag([
# # #             (3e-7)**2,     # lat drift per frame
# # #             (3e-7)**2,     # lon drift per frame
# # #             0.1**2,        # depth drift per frame
# # #             (1e-8)**2,     # vel_lat (near-zero)
# # #             (1e-8)**2,     # vel_lon (near-zero)
# # #         ])

# # #         # Measurement noise — scaled by detection score later
# # #         self._R_base = np.diag([
# # #             (3.5e-5)**2,   # lat  (~3.9 m)
# # #             (3.5e-5)**2,   # lon  (~3.9 m)
# # #             6.0**2,        # depth (6 m)
# # #         ])

# # #         # State transition: static model, velocity adds to position
# # #         self.F = np.eye(5)
# # #         self.F[0, 3] = 1.0
# # #         self.F[1, 4] = 1.0

# # #         # Observation: we observe lat, lon, depth directly
# # #         self.H = np.zeros((3, 5))
# # #         self.H[0, 0] = 1.0
# # #         self.H[1, 1] = 1.0
# # #         self.H[2, 2] = 1.0

# # #         self.hits     = 1
# # #         self.misses   = 0
# # #         self.age      = 0
# # #         self.track_id = None
# # #         self.score_history = [score]

# # #     # ── Kalman predict step ───────────────────────────────────────────────
# # #     def predict(self):
# # #         self.x = self.F @ self.x
# # #         self.P = self.F @ self.P @ self.F.T + self.Q
# # #         self.age   += 1
# # #         self.misses += 1

# # #     # ── Kalman update step ────────────────────────────────────────────────
# # #     # score_weight: higher score → trust measurement more → smaller R
# # #     def update(self, lat, lon, depth_m, score=50.0):
# # #         self.score_history.append(score)

# # #         # Scale measurement noise inversely with score confidence
# # #         # score 100 → trust fully (R * 0.5)
# # #         # score 50  → normal      (R * 1.0)
# # #         # score 30  → distrust    (R * 2.0)
# # #         scale = max(0.4, min(2.5, 100.0 / max(score, 10.0)))
# # #         R = self._R_base * scale

# # #         z = np.array([lat, lon, depth_m])
# # #         y = z - self.H @ self.x
# # #         S = self.H @ self.P @ self.H.T + R
# # #         K = self.P @ self.H.T @ np.linalg.inv(S)
# # #         self.x = self.x + K @ y
# # #         self.P = (np.eye(5) - K @ self.H) @ self.P
# # #         self.hits   += 1
# # #         self.misses  = 0

# # #     # ── Properties ───────────────────────────────────────────────────────
# # #     @property
# # #     def lat(self):
# # #         return float(self.x[0])

# # #     @property
# # #     def lon(self):
# # #         return float(self.x[1])

# # #     @property
# # #     def depth(self):
# # #         return float(self.x[2])

# # #     @property
# # #     def mean_score(self):
# # #         return float(np.mean(self.score_history[-5:]))  # rolling 5-frame mean

# # #     def distance_to(self, lat, lon):
# # #         return _haversine_m(self.lat, self.lon, lat, lon)


# # # # ─── MULTI-OBJECT TRACKER (SORT-style) ────────────────────────────────────────

# # # class BuildingSORT:
# # #     def __init__(self,
# # #                  max_misses=4,
# # #                  min_hits=2,
# # #                  association_threshold_m=20.0,
# # #                  min_score_to_init=45.0,
# # #                  min_score_to_update=35.0):
# # #         """
# # #         max_misses            : kill track after this many consecutive missed frames
# # #         min_hits              : track must reach this hit count before being 'confirmed'
# # #         association_threshold_m: max distance (m) to associate detection with track
# # #         min_score_to_init     : minimum match score to START a new track
# # #         min_score_to_update   : minimum match score to UPDATE an existing track
# # #         """
# # #         self.tracks             = []
# # #         self.next_id            = 1
# # #         self.max_misses         = max_misses
# # #         self.min_hits           = min_hits
# # #         self.assoc_thresh       = association_threshold_m
# # #         self.min_score_init     = min_score_to_init
# # #         self.min_score_update   = min_score_to_update

# # #     # ── Hungarian assignment ──────────────────────────────────────────────
# # #     def _hungarian(self, cost):
# # #         from scipy.optimize import linear_sum_assignment
# # #         r, c = linear_sum_assignment(cost)
# # #         return list(zip(r, c))

# # #     # ── Main update call — pass detections each frame ─────────────────────
# # #     def update(self, detections):
# # #         """
# # #         detections: list of dicts with keys lat, lon, depth, score
# # #         Returns list of confirmed active tracks.
# # #         """
# # #         # Step 1: predict all existing tracks forward one timestep
# # #         for trk in self.tracks:
# # #             trk.predict()

# # #         # Step 2: handle edge cases
# # #         if not self.tracks:
# # #             for det in detections:
# # #                 if det["score"] >= self.min_score_init:
# # #                     kf = BuildingKalmanFilter(det["lat"], det["lon"],
# # #                                               det["depth"], det["score"])
# # #                     kf.track_id = self.next_id
# # #                     self.next_id += 1
# # #                     self.tracks.append(kf)
# # #             self._prune()
# # #             return self._active_tracks()

# # #         if not detections:
# # #             self._prune()
# # #             return self._active_tracks()

# # #         # Step 3: build cost matrix (haversine distance in metres)
# # #         cost = np.zeros((len(self.tracks), len(detections)))
# # #         for i, trk in enumerate(self.tracks):
# # #             for j, det in enumerate(detections):
# # #                 cost[i, j] = trk.distance_to(det["lat"], det["lon"])

# # #         # Step 4: Hungarian assignment
# # #         pairs = self._hungarian(cost)

# # #         matched_trk = set()
# # #         matched_det = set()

# # #         for i, j in pairs:
# # #             dist = cost[i, j]
# # #             det  = detections[j]

# # #             # Reject association if too far OR score too low
# # #             if dist > self.assoc_thresh:
# # #                 continue
# # #             if det["score"] < self.min_score_update:
# # #                 # Don't update with weak detection — let track coast
# # #                 matched_trk.add(i)   # mark as "handled" so we don't kill it
# # #                 matched_det.add(j)
# # #                 continue

# # #             self.tracks[i].update(det["lat"], det["lon"],
# # #                                    det["depth"], det["score"])
# # #             matched_trk.add(i)
# # #             matched_det.add(j)

# # #         # Step 5: spawn new tracks for unmatched strong detections
# # #         for j, det in enumerate(detections):
# # #             if j not in matched_det and det["score"] >= self.min_score_init:
# # #                 kf = BuildingKalmanFilter(det["lat"], det["lon"],
# # #                                           det["depth"], det["score"])
# # #                 kf.track_id = self.next_id
# # #                 self.next_id += 1
# # #                 self.tracks.append(kf)

# # #         # Step 6: prune dead tracks
# # #         self._prune()

# # #         return self._active_tracks()

# # #     def _prune(self):
# # #         self.tracks = [t for t in self.tracks if t.misses <= self.max_misses]

# # #     def _active_tracks(self):
# # #         """Return only confirmed tracks (hit count ≥ min_hits)."""
# # #         confirmed = []
# # #         for t in self.tracks:
# # #             if t.hits >= self.min_hits:
# # #                 confirmed.append({
# # #                     "track_id":   t.track_id,
# # #                     "lat":        t.lat,
# # #                     "lon":        t.lon,
# # #                     "depth":      t.depth,
# # #                     "hits":       t.hits,
# # #                     "misses":     t.misses,
# # #                     "age":        t.age,
# # #                     "mean_score": t.mean_score,
# # #                 })
# # #         return confirmed


# # # # ─── GPS STABILIZER (top-level interface for run.py / run_batch.py) ───────────

# # # class GPSStabilizer:
# # #     def __init__(self,
# # #                  min_score_gate=40.0,
# # #                  max_smoothing_report_m=150.0):
# # #         """
# # #         min_score_gate        : frames with best-match score below this are
# # #                                 skipped entirely (no tracker update, no result)
# # #         max_smoothing_report_m: if stable GPS is farther than this from raw match,
# # #                                 fall back to reporting raw GPS instead
# # #         """
# # #         self.sort                    = BuildingSORT()
# # #         self._frame_results          = []
# # #         self.min_score_gate          = min_score_gate
# # #         self.max_smoothing_report_m  = max_smoothing_report_m

# # #     # ── Ingest one frame ─────────────────────────────────────────────────
# # #     def ingest(self, frame_id, match_result, perceive_result):
# # #         """
# # #         Returns a result dict or None if the frame is unusable.
# # #         """
# # #         # ── Guard: nothing to process ────────────────────────────────────
# # #         if match_result is None or perceive_result is None:
# # #             self.sort.update([])
# # #             return None

# # #         best  = match_result["best_match"]
# # #         depth = perceive_result.get("median_depth", 25.0)
# # #         score = best["score"]

# # #         # ── Score gate: skip very weak matches entirely ───────────────────
# # #         if score < self.min_score_gate:
# # #             print(f"[tracker] frame {frame_id} score={score:.1f} below gate "
# # #                   f"({self.min_score_gate}) — skipping tracker update")
# # #             self.sort.update([])
# # #             return None

# # #         # ── Build detection list (best + top candidates) ──────────────────
# # #         # Only pass candidates that are reasonably strong
# # #         detections = [{
# # #             "lat":   best["centroid_lat"],
# # #             "lon":   best["centroid_lon"],
# # #             "depth": depth,
# # #             "score": score,
# # #         }]

# # #         for cand in match_result.get("all_candidates", [])[1:4]:
# # #             if cand["score"] >= 35.0:
# # #                 detections.append({
# # #                     "lat":   cand["centroid_lat"],
# # #                     "lon":   cand["centroid_lon"],
# # #                     "depth": depth,
# # #                     "score": cand["score"],
# # #                 })

# # #         # ── Update tracker ────────────────────────────────────────────────
# # #         active = self.sort.update(detections)

# # #         if not active:
# # #             return None

# # #         # ── Pick best track: prefer high hits, then high mean score ───────
# # #         best_track = max(active, key=lambda t: (t["hits"], t["mean_score"]))

# # #         # ── Compute smoothing delta ───────────────────────────────────────
# # #         smoothing_m = _haversine_m(
# # #             best["centroid_lat"], best["centroid_lon"],
# # #             best_track["lat"],   best_track["lon"]
# # #         )

# # #         # ── Fallback: if Kalman drifted too far, trust raw GPS instead ────
# # #         if smoothing_m > self.max_smoothing_report_m:
# # #             print(f"[tracker] frame {frame_id} smoothing={smoothing_m:.1f}m "
# # #                   f"exceeds cap — using raw GPS")
# # #             report_lat = best["centroid_lat"]
# # #             report_lon = best["centroid_lon"]
# # #             smoothing_m = 0.0
# # #         else:
# # #             report_lat = best_track["lat"]
# # #             report_lon = best_track["lon"]

# # #         result = {
# # #             "frame_id":          frame_id,
# # #             "track_id":          best_track["track_id"],
# # #             "stable_lat":        report_lat,
# # #             "stable_lon":        report_lon,
# # #             "stable_depth":      best_track["depth"],
# # #             "track_hits":        best_track["hits"],
# # #             "track_age":         best_track["age"],
# # #             "track_mean_score":  best_track["mean_score"],
# # #             "raw_lat":           best["centroid_lat"],
# # #             "raw_lon":           best["centroid_lon"],
# # #             "raw_score":         score,
# # #             "smoothing_delta_m": round(smoothing_m, 2),
# # #             "gmaps": (
# # #                 f"https://www.google.com/maps/search/?api=1"
# # #                 f"&query={report_lat:.8f},{report_lon:.8f}"
# # #             )
# # #         }

# # #         self._frame_results.append(result)
# # #         return result

# # #     # ── Batch summary ─────────────────────────────────────────────────────
# # #     def summary(self):
# # #         if not self._frame_results:
# # #             return {}

# # #         lats   = [r["stable_lat"]        for r in self._frame_results]
# # #         lons   = [r["stable_lon"]        for r in self._frame_results]
# # #         deltas = [r["smoothing_delta_m"] for r in self._frame_results]
# # #         scores = [r["raw_score"]         for r in self._frame_results]

# # #         mean_lat = float(np.mean(lats))
# # #         return {
# # #             "frames_processed":       len(self._frame_results),
# # #             "mean_lat":               mean_lat,
# # #             "mean_lon":               float(np.mean(lons)),
# # #             "lat_spread_m":           float(np.std(lats) * 111320),
# # #             "lon_spread_m":           float(
# # #                 np.std(lons) * 111320 * math.cos(math.radians(mean_lat))
# # #             ),
# # #             "mean_smoothing_delta_m": float(np.mean(deltas)),
# # #             "max_smoothing_delta_m":  float(np.max(deltas)),
# # #             "mean_raw_score":         float(np.mean(scores)),
# # #             "min_raw_score":          float(np.min(scores)),
# # #             "max_raw_score":          float(np.max(scores)),
# # #         }


# # #----------------------------------------------------------------------------


# # # import numpy as np
# # # import math
# # # from collections import defaultdict


# # # # ─── HELPERS ──────────────────────────────────────────────────────────────────

# # # def _haversine_m(lat1, lon1, lat2, lon2):
# # #     R = 6371000.0
# # #     phi1, phi2 = math.radians(lat1), math.radians(lat2)
# # #     dphi = math.radians(lat2 - lat1)
# # #     dlam = math.radians(lon2 - lon1)
# # #     a = (math.sin(dphi/2)**2
# # #          + math.cos(phi1) * math.cos(phi2) * math.sin(dlam/2)**2)
# # #     return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# # # # ─── PER-BUILDING KALMAN FILTER ───────────────────────────────────────────────
# # # # State vector: [lat, lon, depth, vel_lat, vel_lon]
# # # # Buildings are static — velocity terms stay near zero and serve only as
# # # # a gentle smoother when the same building is observed across consecutive frames.

# # # class BuildingKalmanFilter:
# # #     def __init__(self, lat, lon, depth_m, score=50.0):
# # #         self.x = np.array([lat, lon, depth_m, 0.0, 0.0], dtype=np.float64)

# # #         # Initial covariance — ~5 m position uncertainty, 8 m depth uncertainty
# # #         self.P = np.diag([
# # #             (4.5e-5) ** 2,   # lat   ≈ 5 m
# # #             (4.5e-5) ** 2,   # lon   ≈ 5 m
# # #             8.0 ** 2,        # depth ≈ 8 m
# # #             (5e-7)  ** 2,    # vel_lat — tiny
# # #             (5e-7)  ** 2,    # vel_lon — tiny
# # #         ])

# # #         # Process noise — buildings don't move
# # #         self.Q = np.diag([
# # #             (3e-7) ** 2,     # lat  drift per frame
# # #             (3e-7) ** 2,     # lon  drift per frame
# # #             0.1   ** 2,      # depth drift per frame
# # #             (1e-8) ** 2,     # vel_lat
# # #             (1e-8) ** 2,     # vel_lon
# # #         ])

# # #         # Base measurement noise (scaled by score at update time)
# # #         self._R_base = np.diag([
# # #             (3.5e-5) ** 2,   # lat  ≈ 3.9 m
# # #             (3.5e-5) ** 2,   # lon  ≈ 3.9 m
# # #             6.0      ** 2,   # depth 6 m
# # #         ])

# # #         # State transition: static model with velocity component
# # #         self.F = np.eye(5)
# # #         self.F[0, 3] = 1.0   # lat  += vel_lat
# # #         self.F[1, 4] = 1.0   # lon  += vel_lon

# # #         # Observation matrix: observe lat, lon, depth directly
# # #         self.H = np.zeros((3, 5))
# # #         self.H[0, 0] = 1.0
# # #         self.H[1, 1] = 1.0
# # #         self.H[2, 2] = 1.0

# # #         self.hits          = 1
# # #         self.misses        = 0
# # #         self.age           = 0
# # #         self.track_id      = None
# # #         self.score_history = [score]

# # #         # Store the EGO position at track creation for staleness detection
# # #         self._init_lat = lat
# # #         self._init_lon = lon

# # #     # ── Predict ───────────────────────────────────────────────────────────
# # #     def predict(self):
# # #         self.x       = self.F @ self.x
# # #         self.P       = self.F @ self.P @ self.F.T + self.Q
# # #         self.age    += 1
# # #         self.misses += 1

# # #     # ── Update ────────────────────────────────────────────────────────────
# # #     # Higher score → smaller R → measurement trusted more
# # #     def update(self, lat, lon, depth_m, score=50.0):
# # #         self.score_history.append(score)

# # #         # score 100 → scale 0.5  (trust measurement more)
# # #         # score 50  → scale 1.0  (normal)
# # #         # score 30  → scale 2.0  (distrust, barely moves state)
# # #         scale = max(0.4, min(2.5, 100.0 / max(score, 10.0)))
# # #         R = self._R_base * scale

# # #         z = np.array([lat, lon, depth_m])
# # #         y = z - self.H @ self.x
# # #         S = self.H @ self.P @ self.H.T + R
# # #         K = self.P @ self.H.T @ np.linalg.inv(S)
# # #         self.x      = self.x + K @ y
# # #         self.P      = (np.eye(5) - K @ self.H) @ self.P
# # #         self.hits  += 1
# # #         self.misses = 0

# # #     # ── Properties ────────────────────────────────────────────────────────
# # #     @property
# # #     def lat(self):        return float(self.x[0])

# # #     @property
# # #     def lon(self):        return float(self.x[1])

# # #     @property
# # #     def depth(self):      return float(self.x[2])

# # #     @property
# # #     def mean_score(self):
# # #         return float(np.mean(self.score_history[-5:]))

# # #     def distance_to(self, lat, lon):
# # #         return _haversine_m(self.lat, self.lon, lat, lon)


# # # # ─── MULTI-OBJECT TRACKER ─────────────────────────────────────────────────────

# # # class BuildingSORT:
# # #     def __init__(self,
# # #                  max_misses=3,
# # #                  min_hits=2,
# # #                  association_threshold_m=18.0,
# # #                  min_score_to_init=48.0,
# # #                  min_score_to_update=38.0):
# # #         """
# # #         max_misses             : kill a track after this many consecutive
# # #                                  frames with no matching detection
# # #         min_hits               : track must accumulate this many hits before
# # #                                  being 'confirmed' and returned to callers
# # #         association_threshold_m: max haversine distance (metres) allowed when
# # #                                  matching a detection to an existing track —
# # #                                  CRITICAL: keep this tight so a building 82 m
# # #                                  away is never associated with the wrong track
# # #         min_score_to_init      : minimum match score to START a brand-new track
# # #         min_score_to_update    : minimum match score to UPDATE an existing track
# # #                                  (below this the track coasts without update)
# # #         """
# # #         self.tracks           = []
# # #         self.next_id          = 1
# # #         self.max_misses       = max_misses
# # #         self.min_hits         = min_hits
# # #         self.assoc_thresh     = association_threshold_m
# # #         self.min_score_init   = min_score_to_init
# # #         self.min_score_update = min_score_to_update

# # #     # ── Hungarian assignment ──────────────────────────────────────────────
# # #     @staticmethod
# # #     def _hungarian(cost):
# # #         from scipy.optimize import linear_sum_assignment
# # #         r, c = linear_sum_assignment(cost)
# # #         return list(zip(r, c))

# # #     # ── Main update ───────────────────────────────────────────────────────
# # #     def update(self, detections):
# # #         """
# # #         detections : list of dicts — {lat, lon, depth, score}
# # #         returns    : list of confirmed track dicts
# # #         """
# # #         # Step 1 — predict all tracks forward
# # #         for trk in self.tracks:
# # #             trk.predict()

# # #         # Step 2 — no existing tracks: spawn from strong detections
# # #         if not self.tracks:
# # #             for det in detections:
# # #                 if det["score"] >= self.min_score_init:
# # #                     self._spawn(det)
# # #             self._prune()
# # #             return self._active_tracks()

# # #         # Step 3 — no detections this frame: let tracks coast
# # #         if not detections:
# # #             self._prune()
# # #             return self._active_tracks()

# # #         # Step 4 — build cost matrix (metres)
# # #         n_trk = len(self.tracks)
# # #         n_det = len(detections)
# # #         cost  = np.full((n_trk, n_det), fill_value=9999.0)
# # #         for i, trk in enumerate(self.tracks):
# # #             for j, det in enumerate(detections):
# # #                 cost[i, j] = trk.distance_to(det["lat"], det["lon"])

# # #         # Step 5 — Hungarian assignment
# # #         pairs       = self._hungarian(cost)
# # #         matched_trk = set()
# # #         matched_det = set()

# # #         for i, j in pairs:
# # #             dist = cost[i, j]
# # #             det  = detections[j]

# # #             # Hard distance gate — prevents 82 m cross-building assignment
# # #             if dist > self.assoc_thresh:
# # #                 continue

# # #             matched_trk.add(i)
# # #             matched_det.add(j)

# # #             if det["score"] >= self.min_score_update:
# # #                 self.tracks[i].update(det["lat"], det["lon"],
# # #                                       det["depth"], det["score"])
# # #             # else: track coasts — predict already applied, no state update

# # #         # Step 6 — spawn new tracks for unmatched strong detections
# # #         for j, det in enumerate(detections):
# # #             if j not in matched_det and det["score"] >= self.min_score_init:
# # #                 self._spawn(det)

# # #         # Step 7 — prune dead tracks
# # #         self._prune()
# # #         return self._active_tracks()

# # #     def _spawn(self, det):
# # #         kf           = BuildingKalmanFilter(det["lat"], det["lon"],
# # #                                             det["depth"], det["score"])
# # #         kf.track_id  = self.next_id
# # #         self.next_id += 1
# # #         self.tracks.append(kf)

# # #     def _prune(self):
# # #         self.tracks = [t for t in self.tracks
# # #                        if t.misses <= self.max_misses]

# # #     def _active_tracks(self):
# # #         return [
# # #             {
# # #                 "track_id":   t.track_id,
# # #                 "lat":        t.lat,
# # #                 "lon":        t.lon,
# # #                 "depth":      t.depth,
# # #                 "hits":       t.hits,
# # #                 "misses":     t.misses,
# # #                 "age":        t.age,
# # #                 "mean_score": t.mean_score,
# # #             }
# # #             for t in self.tracks
# # #             if t.hits >= self.min_hits
# # #         ]


# # # # ─── GPS STABILIZER ───────────────────────────────────────────────────────────

# # # class GPSStabilizer:
# # #     def __init__(self,
# # #                  min_score_gate=45.0,
# # #                  max_smoothing_cap_m=40.0):
# # #         """
# # #         min_score_gate     : frames whose best-match score is below this are
# # #                              skipped entirely — tracker NOT updated, no result
# # #                              returned.  Prevents a 54/100 match for a totally
# # #                              different building from corrupting active tracks.

# # #         max_smoothing_cap_m: if the Kalman stable position is farther than this
# # #                              from the raw match GPS, fall back to reporting the
# # #                              raw GPS directly.  Catches the 82 m drift case.
# # #         """
# # #         self.sort               = BuildingSORT()
# # #         self._frame_results     = []
# # #         self.min_score_gate     = min_score_gate
# # #         self.max_smoothing_cap  = max_smoothing_cap_m

# # #     # ── Ingest one frame ─────────────────────────────────────────────────
# # #     def ingest(self, frame_id, match_result, perceive_result):
# # #         # Guard — nothing to work with
# # #         if match_result is None or perceive_result is None:
# # #             self.sort.update([])
# # #             return None

# # #         best  = match_result["best_match"]
# # #         depth = perceive_result.get("median_depth", 25.0)
# # #         score = best["score"]

# # #         # ── Hard score gate ───────────────────────────────────────────────
# # #         # Frame 3599 has score 54 for a building 82 m from the frame-716/717
# # #         # track.  With gate=45 it still passes — but association_threshold=18 m
# # #         # in BuildingSORT will prevent it from latching onto the wrong track.
# # #         # It will spawn its OWN track (hits=1) which won't be confirmed yet,
# # #         # so the result is None for this frame — correct behaviour.
# # #         if score < self.min_score_gate:
# # #             print(f"[tracker] frame {frame_id}  score={score:.1f} < gate "
# # #                   f"({self.min_score_gate:.0f}) — skipping")
# # #             self.sort.update([])
# # #             return None

# # #         # ── Build detection list ──────────────────────────────────────────
# # #         detections = [{
# # #             "lat":   best["centroid_lat"],
# # #             "lon":   best["centroid_lon"],
# # #             "depth": depth,
# # #             "score": score,
# # #         }]

# # #         # Include secondary candidates only if they are reasonably strong
# # #         for cand in match_result.get("all_candidates", [])[1:4]:
# # #             if cand["score"] >= 38.0:
# # #                 detections.append({
# # #                     "lat":   cand["centroid_lat"],
# # #                     "lon":   cand["centroid_lon"],
# # #                     "depth": depth,
# # #                     "score": cand["score"],
# # #                 })

# # #         # ── Update tracker ────────────────────────────────────────────────
# # #         active = self.sort.update(detections)

# # #         if not active:
# # #             return None

# # #         # ── Pick best confirmed track ─────────────────────────────────────
# # #         # Prefer the track closest to the best raw detection rather than
# # #         # just the one with the most hits — avoids a stale distant track
# # #         # winning because it accumulated hits from earlier frames.
# # #         raw_lat = best["centroid_lat"]
# # #         raw_lon = best["centroid_lon"]

# # #         def _track_score(t):
# # #             dist_to_raw = _haversine_m(t["lat"], t["lon"], raw_lat, raw_lon)
# # #             # Penalise tracks that are far from this frame's raw match.
# # #             # 1 hit counts for 10 pts, but 50 m distance costs 5 pts each.
# # #             return t["hits"] * 10.0 + t["mean_score"] - dist_to_raw * 0.1

# # #         best_track = max(active, key=_track_score)

# # #         # ── Smoothing cap ─────────────────────────────────────────────────
# # #         smoothing_m = _haversine_m(raw_lat, raw_lon,
# # #                                    best_track["lat"], best_track["lon"])

# # #         if smoothing_m > self.max_smoothing_cap:
# # #             print(f"[tracker] frame {frame_id}  smoothing={smoothing_m:.1f} m "
# # #                   f"> cap ({self.max_smoothing_cap:.0f} m) — using raw GPS")
# # #             report_lat  = raw_lat
# # #             report_lon  = raw_lon
# # #             smoothing_m = 0.0
# # #         else:
# # #             report_lat = best_track["lat"]
# # #             report_lon = best_track["lon"]

# # #         result = {
# # #             "frame_id":          frame_id,
# # #             "track_id":          best_track["track_id"],
# # #             "stable_lat":        report_lat,
# # #             "stable_lon":        report_lon,
# # #             "stable_depth":      best_track["depth"],
# # #             "track_hits":        best_track["hits"],
# # #             "track_age":         best_track["age"],
# # #             "track_mean_score":  best_track["mean_score"],
# # #             "raw_lat":           raw_lat,
# # #             "raw_lon":           raw_lon,
# # #             "raw_score":         score,
# # #             "smoothing_delta_m": round(smoothing_m, 2),
# # #             "gmaps": (
# # #                 f"https://www.google.com/maps/search/?api=1"
# # #                 f"&query={report_lat:.8f},{report_lon:.8f}"
# # #             ),
# # #         }

# # #         self._frame_results.append(result)
# # #         return result

# # #     # ── Batch summary ─────────────────────────────────────────────────────
# # #     def summary(self):
# # #         if not self._frame_results:
# # #             return {}

# # #         lats   = [r["stable_lat"]        for r in self._frame_results]
# # #         lons   = [r["stable_lon"]        for r in self._frame_results]
# # #         deltas = [r["smoothing_delta_m"] for r in self._frame_results]
# # #         scores = [r["raw_score"]         for r in self._frame_results]

# # #         mean_lat = float(np.mean(lats))
# # #         mean_lon = float(np.mean(lons))

# # #         # Spread in metres — meaningful only when frames observe the SAME building
# # #         lat_spread_m = float(np.std(lats) * 111320.0)
# # #         lon_spread_m = float(
# # #             np.std(lons) * 111320.0 * math.cos(math.radians(mean_lat))
# # #         )

# # #         return {
# # #             "frames_processed":       len(self._frame_results),
# # #             "mean_lat":               mean_lat,
# # #             "mean_lon":               mean_lon,
# # #             "lat_spread_m":           lat_spread_m,
# # #             "lon_spread_m":           lon_spread_m,
# # #             "mean_smoothing_delta_m": float(np.mean(deltas)),
# # #             "max_smoothing_delta_m":  float(np.max(deltas)),
# # #             "mean_raw_score":         float(np.mean(scores)),
# # #             "min_raw_score":          float(np.min(scores)),
# # #             "max_raw_score":          float(np.max(scores)),
# # #         }

# import numpy as np
# import math
# from collections import defaultdict


# def _haversine_m(lat1, lon1, lat2, lon2):
#     R = 6371000.0
#     phi1, phi2 = math.radians(lat1), math.radians(lat2)
#     dphi = math.radians(lat2 - lat1)
#     dlam = math.radians(lon2 - lon1)
#     a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
#     return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


# class BuildingKalmanFilter:
#     def __init__(self, lat, lon, depth_m, score=50.0):
#         self.x = np.array([lat, lon, depth_m, 0.0, 0.0], dtype=np.float64)

#         self.P = np.diag([
#             (4.5e-5)**2,
#             (4.5e-5)**2,
#             8.0**2,
#             (5e-7)**2,
#             (5e-7)**2
#         ])

#         self.Q = np.diag([
#             (3e-7)**2,
#             (3e-7)**2,
#             0.1**2,
#             (1e-8)**2,
#             (1e-8)**2
#         ])

#         self._R_base = np.diag([
#             (3.5e-5)**2,
#             (3.5e-5)**2,
#             6.0**2
#         ])

#         self.F = np.eye(5)
#         self.F[0, 3] = 1.0
#         self.F[1, 4] = 1.0

#         self.H = np.zeros((3, 5))
#         self.H[0, 0] = 1.0
#         self.H[1, 1] = 1.0
#         self.H[2, 2] = 1.0

#         self.hits          = 1
#         self.misses        = 0
#         self.age           = 0
#         self.track_id      = None
#         self.score_history = [score]

#     def predict(self):
#         self.x       = self.F @ self.x
#         self.P       = self.F @ self.P @ self.F.T + self.Q
#         self.age    += 1
#         self.misses += 1

#     def update(self, lat, lon, depth_m, score=50.0):
#         self.score_history.append(score)
#         scale = max(0.4, min(2.5, 100.0 / max(score, 10.0)))
#         R = self._R_base * scale

#         z = np.array([lat, lon, depth_m])
#         y = z - self.H @ self.x
#         S = self.H @ self.P @ self.H.T + R
#         K = self.P @ self.H.T @ np.linalg.inv(S)
#         self.x      = self.x + K @ y
#         self.P      = (np.eye(5) - K @ self.H) @ self.P
#         self.hits  += 1
#         self.misses = 0

#     @property
#     def lat(self):        return float(self.x[0])
#     @property
#     def lon(self):        return float(self.x[1])
#     @property
#     def depth(self):      return float(self.x[2])
#     @property
#     def mean_score(self): return float(np.mean(self.score_history[-5:]))

#     def distance_to(self, lat, lon):
#         return _haversine_m(self.lat, self.lon, lat, lon)


# class BuildingSORT:
#     def __init__(self,
#                  max_misses=3,
#                  min_hits=2,
#                  association_threshold_m=18.0,
#                  min_score_to_init=48.0,
#                  min_score_to_update=38.0):
#         self.tracks           = []
#         self.next_id          = 1
#         self.max_misses       = max_misses
#         self.min_hits         = min_hits
#         self.assoc_thresh     = association_threshold_m
#         self.min_score_init   = min_score_to_init
#         self.min_score_update = min_score_to_update

#     @staticmethod
#     def _hungarian(cost):
#         from scipy.optimize import linear_sum_assignment
#         r, c = linear_sum_assignment(cost)
#         return list(zip(r, c))

#     def update(self, detections):
#         for trk in self.tracks:
#             trk.predict()

#         if not self.tracks:
#             for det in detections:
#                 if det["score"] >= self.min_score_init:
#                     self._spawn(det)
#             self._prune()
#             return self._active_tracks()

#         if not detections:
#             self._prune()
#             return self._active_tracks()

#         n_trk = len(self.tracks)
#         n_det = len(detections)
#         cost  = np.full((n_trk, n_det), fill_value=9999.0)
#         for i, trk in enumerate(self.tracks):
#             for j, det in enumerate(detections):
#                 cost[i, j] = trk.distance_to(det["lat"], det["lon"])

#         pairs       = self._hungarian(cost)
#         matched_trk = set()
#         matched_det = set()

#         for i, j in pairs:
#             if cost[i, j] > self.assoc_thresh:
#                 continue
#             matched_trk.add(i)
#             matched_det.add(j)
#             det = detections[j]
#             if det["score"] >= self.min_score_update:
#                 self.tracks[i].update(det["lat"], det["lon"],
#                                        det["depth"], det["score"])

#         for j, det in enumerate(detections):
#             if j not in matched_det and det["score"] >= self.min_score_init:
#                 self._spawn(det)

#         self._prune()
#         return self._active_tracks()

#     def _spawn(self, det):
#         kf           = BuildingKalmanFilter(det["lat"], det["lon"],
#                                              det["depth"], det["score"])
#         kf.track_id  = self.next_id
#         self.next_id += 1
#         self.tracks.append(kf)

#     def _prune(self):
#         self.tracks = [t for t in self.tracks if t.misses <= self.max_misses]

#     def _active_tracks(self):
#         return [
#             {
#                 "track_id":   t.track_id,
#                 "lat":        t.lat,
#                 "lon":        t.lon,
#                 "depth":      t.depth,
#                 "hits":       t.hits,
#                 "misses":     t.misses,
#                 "age":        t.age,
#                 "mean_score": t.mean_score,
#             }
#             for t in self.tracks
#             if t.hits >= self.min_hits
#         ]


# class GPSStabilizer:
#     def __init__(self, min_score_gate=45.0, max_smoothing_cap_m=40.0):
#         self.sort               = BuildingSORT()
#         self._frame_results     = []
#         self.min_score_gate     = min_score_gate
#         self.max_smoothing_cap  = max_smoothing_cap_m

#     def ingest(self, frame_id, match_result, perceive_result):
#         if match_result is None or perceive_result is None:
#             self.sort.update([])
#             return None

#         best  = match_result["best_match"]
#         depth = perceive_result.get("median_depth", 25.0)
#         score = best["score"]

#         if score < self.min_score_gate:
#             print(f"[tracker] frame {frame_id}  score={score:.1f} < gate — skip")
#             self.sort.update([])
#             return None

#         detections = [{
#             "lat":   best["centroid_lat"],
#             "lon":   best["centroid_lon"],
#             "depth": depth,
#             "score": score,
#         }]

#         for cand in match_result.get("all_candidates", [])[1:4]:
#             if cand["score"] >= 38.0:
#                 detections.append({
#                     "lat":   cand["centroid_lat"],
#                     "lon":   cand["centroid_lon"],
#                     "depth": depth,
#                     "score": cand["score"],
#                 })

#         active = self.sort.update(detections)

#         if not active:
#             return None

#         raw_lat = best["centroid_lat"]
#         raw_lon = best["centroid_lon"]

#         def _track_score(t):
#             dist_to_raw = _haversine_m(t["lat"], t["lon"], raw_lat, raw_lon)
#             return t["hits"] * 10.0 + t["mean_score"] - dist_to_raw * 0.1

#         best_track = max(active, key=_track_score)

#         smoothing_m = _haversine_m(raw_lat, raw_lon,
#                                    best_track["lat"], best_track["lon"])

#         if smoothing_m > self.max_smoothing_cap:
#             print(f"[tracker] frame {frame_id}  smoothing={smoothing_m:.1f}m > cap — raw GPS")
#             report_lat  = raw_lat
#             report_lon  = raw_lon
#             smoothing_m = 0.0
#         else:
#             report_lat = best_track["lat"]
#             report_lon = best_track["lon"]

#         result = {
#             "frame_id":          frame_id,
#             "track_id":          best_track["track_id"],
#             "stable_lat":        report_lat,
#             "stable_lon":        report_lon,
#             "stable_depth":      best_track["depth"],
#             "track_hits":        best_track["hits"],
#             "track_age":         best_track["age"],
#             "track_mean_score":  best_track["mean_score"],
#             "raw_lat":           raw_lat,
#             "raw_lon":           raw_lon,
#             "raw_score":         score,
#             "smoothing_delta_m": round(smoothing_m, 2),
#             "gmaps": (
#                 f"https://www.google.com/maps/search/?api=1"
#                 f"&query={report_lat:.8f},{report_lon:.8f}"
#             ),
#         }

#         self._frame_results.append(result)
#         return result

#     def summary(self):
#         if not self._frame_results:
#             return {}

#         lats   = [r["stable_lat"]        for r in self._frame_results]
#         lons   = [r["stable_lon"]        for r in self._frame_results]
#         deltas = [r["smoothing_delta_m"] for r in self._frame_results]
#         scores = [r["raw_score"]         for r in self._frame_results]
#         mean_lat = float(np.mean(lats))

#         return {
#             "frames_processed":       len(self._frame_results),
#             "mean_lat":               mean_lat,
#             "mean_lon":               float(np.mean(lons)),
#             "lat_spread_m":           float(np.std(lats) * 111320),
#             "lon_spread_m":           float(np.std(lons) * 111320 * math.cos(math.radians(mean_lat))),
#             "mean_smoothing_delta_m": float(np.mean(deltas)),
#             "max_smoothing_delta_m":  float(np.max(deltas)),
#             "mean_raw_score":         float(np.mean(scores)),
#             "min_raw_score":          float(np.min(scores)),
#             "max_raw_score":          float(np.max(scores)),
#         }
import numpy as np
import math


def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ─── KALMAN FILTER ────────────────────────────────────────────────────────────

class BuildingKalmanFilter:
    def __init__(self, lat, lon, depth_m, score=50.0):
        self.x = np.array([lat, lon, depth_m, 0.0, 0.0], dtype=np.float64)

        self.P = np.diag([
            (4.5e-5) ** 2,
            (4.5e-5) ** 2,
            8.0 ** 2,
            (5e-7) ** 2,
            (5e-7) ** 2,
        ])
        self.Q = np.diag([
            (3e-7) ** 2,
            (3e-7) ** 2,
            0.1 ** 2,
            (1e-8) ** 2,
            (1e-8) ** 2,
        ])
        self._R_base = np.diag([
            (3.5e-5) ** 2,
            (3.5e-5) ** 2,
            6.0 ** 2,
        ])

        self.F = np.eye(5)
        self.F[0, 3] = 1.0
        self.F[1, 4] = 1.0

        self.H = np.zeros((3, 5))
        self.H[0, 0] = 1.0
        self.H[1, 1] = 1.0
        self.H[2, 2] = 1.0

        self.hits          = 1
        self.misses        = 0
        self.age           = 0
        self.track_id      = None
        self.score_history = [score]

    def predict(self):
        self.x       = self.F @ self.x
        self.P       = self.F @ self.P @ self.F.T + self.Q
        self.age    += 1
        self.misses += 1

    def update(self, lat, lon, depth_m, score=50.0):
        self.score_history.append(score)
        scale = max(0.4, min(2.5, 100.0 / max(score, 10.0)))
        R = self._R_base * scale

        z = np.array([lat, lon, depth_m])
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x      = self.x + K @ y
        self.P      = (np.eye(5) - K @ self.H) @ self.P
        self.hits  += 1
        self.misses = 0

    @property
    def lat(self):        return float(self.x[0])
    @property
    def lon(self):        return float(self.x[1])
    @property
    def depth(self):      return float(self.x[2])
    @property
    def mean_score(self): return float(np.mean(self.score_history[-5:]))

    def distance_to(self, lat, lon):
        return _haversine_m(self.lat, self.lon, lat, lon)


# ─── SORT TRACKER ─────────────────────────────────────────────────────────────

class BuildingSORT:
    def __init__(self,
                 max_misses=3,
                 min_hits=2,
                 association_threshold_m=18.0,
                 min_score_to_init=48.0,
                 min_score_to_update=38.0):
        self.tracks           = []
        self.next_id          = 1
        self.max_misses       = max_misses
        self.min_hits         = min_hits
        self.assoc_thresh     = association_threshold_m
        self.min_score_init   = min_score_to_init
        self.min_score_update = min_score_to_update

    @staticmethod
    def _hungarian(cost):
        from scipy.optimize import linear_sum_assignment
        r, c = linear_sum_assignment(cost)
        return list(zip(r, c))

    def update(self, detections):
        for trk in self.tracks:
            trk.predict()

        if not self.tracks:
            for det in detections:
                if det["score"] >= self.min_score_init:
                    self._spawn(det)
            self._prune()
            return self._active_tracks()

        if not detections:
            self._prune()
            return self._active_tracks()

        cost = np.full((len(self.tracks), len(detections)), fill_value=9999.0)
        for i, trk in enumerate(self.tracks):
            for j, det in enumerate(detections):
                cost[i, j] = trk.distance_to(det["lat"], det["lon"])

        matched_trk = set()
        matched_det = set()
        for i, j in self._hungarian(cost):
            if cost[i, j] > self.assoc_thresh:
                continue
            matched_trk.add(i)
            matched_det.add(j)
            det = detections[j]
            if det["score"] >= self.min_score_update:
                self.tracks[i].update(det["lat"], det["lon"],
                                      det["depth"], det["score"])

        for j, det in enumerate(detections):
            if j not in matched_det and det["score"] >= self.min_score_init:
                self._spawn(det)

        self._prune()
        return self._active_tracks()

    def _spawn(self, det):
        kf          = BuildingKalmanFilter(det["lat"], det["lon"],
                                           det["depth"], det["score"])
        kf.track_id = self.next_id
        self.next_id += 1
        self.tracks.append(kf)

    def _prune(self):
        self.tracks = [t for t in self.tracks if t.misses <= self.max_misses]

    def _active_tracks(self):
        return [
            {
                "track_id":   t.track_id,
                "lat":        t.lat,
                "lon":        t.lon,
                "depth":      t.depth,
                "hits":       t.hits,
                "misses":     t.misses,
                "age":        t.age,
                "mean_score": t.mean_score,
            }
            for t in self.tracks if t.hits >= self.min_hits
        ]

    # ── NEW: expose all unconfirmed tracks too (hits=1) ───────────────────
    # Used by GPSStabilizer to return a provisional result for first-seen
    # buildings rather than silently dropping the frame.
    def all_tracks(self):
        return [
            {
                "track_id":   t.track_id,
                "lat":        t.lat,
                "lon":        t.lon,
                "depth":      t.depth,
                "hits":       t.hits,
                "misses":     t.misses,
                "age":        t.age,
                "mean_score": t.mean_score,
            }
            for t in self.tracks
        ]


# ─── GPS STABILIZER ───────────────────────────────────────────────────────────

class GPSStabilizer:
    def __init__(self,
                 min_score_gate=45.0,
                 max_smoothing_cap_m=40.0):
        self.sort              = BuildingSORT()
        self._frame_results    = []
        self.min_score_gate    = min_score_gate
        self.max_smoothing_cap = max_smoothing_cap_m

    # ── Ingest one frame ──────────────────────────────────────────────────
    def ingest(self, frame_id, match_result, perceive_result):
        if match_result is None or perceive_result is None:
            self.sort.update([])
            return None

        best  = match_result["best_match"]
        depth = perceive_result.get("median_depth", 25.0)
        score = best["score"]

        if score < self.min_score_gate:
            print(f"[tracker] frame {frame_id}  score={score:.1f} < gate — skip")
            self.sort.update([])
            return None

        detections = [{
            "lat":   best["centroid_lat"],
            "lon":   best["centroid_lon"],
            "depth": depth,
            "score": score,
        }]
        for cand in match_result.get("all_candidates", [])[1:4]:
            if cand["score"] >= 38.0:
                detections.append({
                    "lat":   cand["centroid_lat"],
                    "lon":   cand["centroid_lon"],
                    "depth": depth,
                    "score": cand["score"],
                })

        # Update tracker — returns confirmed tracks (hits >= min_hits)
        active = self.sort.update(detections)

        raw_lat = best["centroid_lat"]
        raw_lon = best["centroid_lon"]

        # ── FIX: if no confirmed track yet, try unconfirmed (hits=1) ─────
        # This prevents the first frame of a new building from being silently
        # dropped. We flag it as provisional so callers can treat it differently.
        provisional = False
        if not active:
            all_trks = self.sort.all_tracks()
            if not all_trks:
                return None
            # Pick the unconfirmed track closest to the raw detection
            candidate = min(
                all_trks,
                key=lambda t: _haversine_m(t["lat"], t["lon"], raw_lat, raw_lon)
            )
            # Only use it if it's actually close to the raw match
            if _haversine_m(candidate["lat"], candidate["lon"],
                            raw_lat, raw_lon) > self.max_smoothing_cap:
                return None
            active       = [candidate]
            provisional  = True

        # ── Pick best confirmed (or provisional) track ────────────────────
        def _track_score(t):
            dist_to_raw = _haversine_m(t["lat"], t["lon"], raw_lat, raw_lon)
            return t["hits"] * 10.0 + t["mean_score"] - dist_to_raw * 0.1

        best_track  = max(active, key=_track_score)
        smoothing_m = _haversine_m(raw_lat, raw_lon,
                                   best_track["lat"], best_track["lon"])

        # ── Smoothing cap ────────────────────────────────────────────────
        if smoothing_m > self.max_smoothing_cap:
            print(f"[tracker] frame {frame_id}  smoothing={smoothing_m:.1f}m "
                  f"> cap — raw GPS")
            report_lat  = raw_lat
            report_lon  = raw_lon
            smoothing_m = 0.0
        else:
            report_lat = best_track["lat"]
            report_lon = best_track["lon"]

        result = {
            "frame_id":          frame_id,
            "track_id":          best_track["track_id"],
            "stable_lat":        report_lat,
            "stable_lon":        report_lon,
            "stable_depth":      best_track["depth"],
            "track_hits":        best_track["hits"],
            "track_age":         best_track["age"],
            "track_mean_score":  best_track["mean_score"],
            "provisional":       provisional,   # True = first observation, not yet confirmed
            "raw_lat":           raw_lat,
            "raw_lon":           raw_lon,
            "raw_score":         score,
            "smoothing_delta_m": round(smoothing_m, 2),
            "gmaps": (
                f"https://www.google.com/maps/search/?api=1"
                f"&query={report_lat:.8f},{report_lon:.8f}"
            ),
        }

        self._frame_results.append(result)
        return result

    # ── Per-track summary ─────────────────────────────────────────────────
    # Groups results by track_id so the summary reports EACH building
    # separately rather than averaging across completely different buildings.
    def summary(self):
        if not self._frame_results:
            return {}

        # Group by track_id
        from collections import defaultdict
        by_track = defaultdict(list)
        for r in self._frame_results:
            by_track[r["track_id"]].append(r)

        track_summaries = []
        for tid, results in sorted(by_track.items()):
            lats   = [r["stable_lat"]        for r in results]
            lons   = [r["stable_lon"]        for r in results]
            deltas = [r["smoothing_delta_m"] for r in results]
            scores = [r["raw_score"]         for r in results]
            mean_lat = float(np.mean(lats))
            mean_lon = float(np.mean(lons))

            track_summaries.append({
                "track_id":               tid,
                "frames":                 len(results),
                "mean_lat":               mean_lat,
                "mean_lon":               mean_lon,
                "lat_spread_m":           float(np.std(lats) * 111320.0),
                "lon_spread_m":           float(
                    np.std(lons) * 111320.0
                    * math.cos(math.radians(mean_lat))
                ),
                "mean_smoothing_delta_m": float(np.mean(deltas)),
                "max_smoothing_delta_m":  float(np.max(deltas)),
                "mean_raw_score":         float(np.mean(scores)),
                "min_raw_score":          float(np.min(scores)),
                "gmaps": (
                    f"https://www.google.com/maps/search/?api=1"
                    f"&query={mean_lat:.8f},{mean_lon:.8f}"
                ),
            })

        # Also keep a flat overall summary for the batch print
        all_deltas = [r["smoothing_delta_m"] for r in self._frame_results]
        all_scores = [r["raw_score"]         for r in self._frame_results]

        return {
            "frames_processed":       len(self._frame_results),
            "tracks_confirmed":       len(track_summaries),
            "per_track":              track_summaries,
            "mean_smoothing_delta_m": float(np.mean(all_deltas)),
            "max_smoothing_delta_m":  float(np.max(all_deltas)),
            "mean_raw_score":         float(np.mean(all_scores)),
            "min_raw_score":          float(np.min(all_scores)),
            "max_raw_score":          float(np.max(all_scores)),
        }