from __future__ import annotations

import torch
import torch.nn as nn


class ActivityStatsClassifier(nn.Module):
    """Stable activity-only classifier for small pose sequence datasets.

    The input is still a pose sequence shaped (batch, frames, 51), so inference
    can use the same frame buffer. The model summarizes posture and motion with
    simple temporal statistics instead of a large recurrent stack.
    """

    def __init__(self, in_features: int = 51, num_classes: int = 7, hidden: int = 192):
        super().__init__()
        self.net = nn.Sequential(
            nn.LayerNorm(in_features * 4),
            nn.Linear(in_features * 4, hidden),
            nn.ReLU(),
            nn.Dropout(0.20),
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
            nn.Dropout(0.10),
            nn.Linear(hidden // 2, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = torch.nan_to_num(x, nan=0.0, posinf=1.0, neginf=0.0).clamp(0.0, 1.0)
        mean = x.mean(dim=1)
        std = x.std(dim=1, unbiased=False)
        minv = x.min(dim=1).values
        maxv = x.max(dim=1).values
        feats = torch.cat([mean, std, minv, maxv], dim=1)
        return self.net(feats)


def build_activity_model(in_features: int = 51, num_classes: int = 7) -> ActivityStatsClassifier:
    return ActivityStatsClassifier(in_features=in_features, num_classes=num_classes)
