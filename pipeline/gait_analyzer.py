import numpy as np


class GaitAnalyzer:
    def __init__(self):
        self.history = []
        self.max_history = 90   # ~3 seconds at 30 fps
        self.min_history = 30   # need enough frames before analysis
        self.risk_threshold = 0.6

    def _get(self, p: dict, key: str) -> float:
        return float(p.get(key, 0.0) or 0.0)

    def update(self, keypoints: dict) -> dict:
        if not isinstance(keypoints, dict):
            return {"risk_score": 0.0, "risk_level": "unknown"}

        self.history.append(keypoints)

        if len(self.history) > self.max_history:
            self.history.pop(0)

        if len(self.history) < self.min_history:
            return {"risk_score": 0.0, "risk_level": "unknown"}

        return self.analyze()

    def analyze(self) -> dict:
        scores = []

        # 1. Center of mass instability (normalized by hip width)
        com_offsets = []
        for p in self.history:
            left_hip_x = self._get(p, "left_hip_x")
            right_hip_x = self._get(p, "right_hip_x")
            left_ankle_x = self._get(p, "left_ankle_x")
            right_ankle_x = self._get(p, "right_ankle_x")

            hip_width = abs(left_hip_x - right_hip_x) + 1e-6
            hip_center = (left_hip_x + right_hip_x) / 2.0
            ankle_center = (left_ankle_x + right_ankle_x) / 2.0

            offset = abs(hip_center - ankle_center) / hip_width
            com_offsets.append(offset)

        com_instability = float(np.std(com_offsets)) if com_offsets else 0.0
        scores.append(min(com_instability * 3.0, 1.0))

        # 2. Trunk sway (normalized by shoulder width)
        shoulder_sways = []
        for p in self.history:
            left_shoulder_x = self._get(p, "left_shoulder_x")
            right_shoulder_x = self._get(p, "right_shoulder_x")
            left_shoulder_y = self._get(p, "left_shoulder_y")
            right_shoulder_y = self._get(p, "right_shoulder_y")

            shoulder_width = abs(left_shoulder_x - right_shoulder_x) + 1e-6
            sway = abs(left_shoulder_y - right_shoulder_y) / shoulder_width
            shoulder_sways.append(sway)

        trunk_sway = float(np.mean(shoulder_sways)) if shoulder_sways else 0.0
        scores.append(min(trunk_sway * 2.5, 1.0))

        # 3. Step asymmetry
        left_ankle_y = [self._get(p, "left_ankle_y") for p in self.history]
        right_ankle_y = [self._get(p, "right_ankle_y") for p in self.history]

        if left_ankle_y and right_ankle_y:
            asymmetry = abs(np.std(left_ankle_y) - np.std(right_ankle_y))
        else:
            asymmetry = 0.0

        scores.append(min(asymmetry * 8.0, 1.0))

        # 4. Knee flexion proxy
        knee_angles = []
        for p in self.history:
            left_hip_y = self._get(p, "left_hip_y")
            left_knee_y = self._get(p, "left_knee_y")
            left_ankle_y_val = self._get(p, "left_ankle_y")

            knee_proxy = abs(left_hip_y - left_knee_y) + abs(left_knee_y - left_ankle_y_val)
            knee_angles.append(knee_proxy)

        mean_knee_flexion = float(np.mean(knee_angles)) if knee_angles else 0.0
        reduced_flexion = 1.0 - min(mean_knee_flexion * 2.5, 1.0)
        scores.append(reduced_flexion)

        # Weighted final score
        weights = [0.35, 0.25, 0.25, 0.15]
        risk_score = float(sum(w * s for w, s in zip(weights, scores)))

        if risk_score > 0.65:
            risk_level = "HIGH"
        elif risk_score > 0.40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "risk_score": round(risk_score, 3),
            "risk_level": risk_level,
            "com_instability": round(com_instability, 3),
            "trunk_sway": round(trunk_sway, 3),
            "step_asymmetry": round(asymmetry, 3),
            "knee_flexion": round(mean_knee_flexion, 3),
        }