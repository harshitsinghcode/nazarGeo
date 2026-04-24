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


class GPSStabilizer:
    def __init__(self,
                 min_score_gate=45.0,
                 max_smoothing_cap_m=40.0):
        self.sort              = BuildingSORT()
        self._frame_results    = []
        self.min_score_gate    = min_score_gate
        self.max_smoothing_cap = max_smoothing_cap_m

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

        active = self.sort.update(detections)

        raw_lat = best["centroid_lat"]
        raw_lon = best["centroid_lon"]

        provisional = False
        if not active:
            all_trks = self.sort.all_tracks()
            if not all_trks:
                return None
            candidate = min(
                all_trks,
                key=lambda t: _haversine_m(t["lat"], t["lon"], raw_lat, raw_lon)
            )
            if _haversine_m(candidate["lat"], candidate["lon"],
                            raw_lat, raw_lon) > self.max_smoothing_cap:
                return None
            active       = [candidate]
            provisional  = True

        def _track_score(t):
            dist_to_raw = _haversine_m(t["lat"], t["lon"], raw_lat, raw_lon)
            return t["hits"] * 10.0 + t["mean_score"] - dist_to_raw * 0.1

        best_track  = max(active, key=_track_score)
        smoothing_m = _haversine_m(raw_lat, raw_lon,
                                   best_track["lat"], best_track["lon"])

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
            "provisional":       provisional,
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

    def summary(self):
        if not self._frame_results:
            return {}

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