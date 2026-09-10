"""
tcn_lstm_model.py
==================
Temporal Convolutional Network (TCN) + BiLSTM + Attention
for skeleton-sequence action / fall classification.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import List, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from configs.config import MODEL_CONFIG


# ─────────────────────────────────────────────
# POSITIONAL ENCODING
# ─────────────────────────────────────────────
class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 512, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(dropout)

        pe = torch.zeros(max_len, d_model)
        pos = torch.arange(0, max_len).unsqueeze(1).float()
        div = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )

        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)

        self.register_buffer("pe", pe.unsqueeze(0))  # (1, max_len, d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, D)
        x = x + self.pe[:, :x.size(1)]
        return self.dropout(x)


# ─────────────────────────────────────────────
# TCN BLOCKS
# ─────────────────────────────────────────────
class _CausalConv1d(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, kernel: int, dilation: int):
        super().__init__()
        self.pad = (kernel - 1) * dilation
        self.conv = nn.Conv1d(
            in_ch,
            out_ch,
            kernel,
            dilation=dilation,
            padding=0,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.pad(x, (self.pad, 0))
        return self.conv(x)


class TCNResidualBlock(nn.Module):
    def __init__(
        self,
        in_ch: int,
        out_ch: int,
        kernel: int,
        dilation: int,
        dropout: float = 0.2,
    ):
        super().__init__()

        self.net = nn.Sequential(
            _CausalConv1d(in_ch, out_ch, kernel, dilation),
            nn.BatchNorm1d(out_ch),
            nn.GELU(),
            nn.Dropout(dropout),

            _CausalConv1d(out_ch, out_ch, kernel, dilation),
            nn.BatchNorm1d(out_ch),
            nn.GELU(),
            nn.Dropout(dropout),
        )

        self.downsample = nn.Conv1d(in_ch, out_ch, 1) if in_ch != out_ch else nn.Identity()
        self.act = nn.GELU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.net(x) + self.downsample(x))


class TCNEncoder(nn.Module):
    def __init__(
        self,
        in_features: int,
        channels: List[int],
        kernel: int = 3,
        dropout: float = 0.2,
    ):
        super().__init__()

        layers = []
        prev = in_features
        for i, ch in enumerate(channels):
            dilation = 2 ** i
            layers.append(TCNResidualBlock(prev, ch, kernel, dilation, dropout))
            prev = ch

        self.network = nn.Sequential(*layers)
        self.out_features = prev

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, F) -> (B, F, T) -> TCN -> (B, T, F')
        return self.network(x.permute(0, 2, 1)).permute(0, 2, 1)


# ─────────────────────────────────────────────
# TEMPORAL ATTENTION
# ─────────────────────────────────────────────
class TemporalAttention(nn.Module):
    def __init__(self, d_model: int):
        super().__init__()
        self.query = nn.Linear(d_model, d_model)
        self.key = nn.Linear(d_model, d_model)
        self.value = nn.Linear(d_model, d_model)
        self.scale = math.sqrt(d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        q = self.query(x)
        k = self.key(x)
        v = self.value(x)

        scores = torch.bmm(q, k.transpose(1, 2)) / self.scale
        weights = F.softmax(scores, dim=-1)
        return torch.bmm(weights, v)


# ─────────────────────────────────────────────
# MAIN MODEL
# ─────────────────────────────────────────────
class TCNBiLSTMClassifier(nn.Module):
    def __init__(
        self,
        in_features: int = 51,
        tcn_channels: Optional[List[int]] = None,
        tcn_kernel: int = 3,
        lstm_hidden: int = 256,
        lstm_layers: int = 2,
        num_classes: int = 8,
        dropout: float = 0.4,
    ):
        super().__init__()

        tcn_channels = tcn_channels or MODEL_CONFIG["tcn_num_channels"]

        self.input_proj = nn.Sequential(
            nn.Linear(in_features, tcn_channels[0]),
            nn.LayerNorm(tcn_channels[0]),
            nn.GELU(),
        )

        self.pos_enc = PositionalEncoding(
            tcn_channels[0],
            dropout=0.1,
        )

        self.tcn = TCNEncoder(
            in_features=tcn_channels[0],
            channels=tcn_channels,
            kernel=tcn_kernel,
            dropout=dropout,
        )

        self.lstm = nn.LSTM(
            input_size=self.tcn.out_features,
            hidden_size=lstm_hidden,
            num_layers=lstm_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if lstm_layers > 1 else 0.0,
        )

        self.attention = TemporalAttention(lstm_hidden * 2)

        self.head = nn.Sequential(
            nn.LayerNorm(lstm_hidden * 2),
            nn.Dropout(dropout),
            nn.Linear(lstm_hidden * 2, lstm_hidden),
            nn.GELU(),
            nn.Dropout(dropout / 2),
            nn.Linear(lstm_hidden, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, 51)
        x = self.input_proj(x)
        x = self.pos_enc(x)
        x = self.tcn(x)
        x, _ = self.lstm(x)
        x = self.attention(x)
        x = x.mean(dim=1)
        return self.head(x)

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            return F.softmax(self(x), dim=-1)


# ─────────────────────────────────────────────
# FACTORY
# ─────────────────────────────────────────────
def build_model(
    in_features: int = 51,
    num_classes: int | None = None,
) -> TCNBiLSTMClassifier:
    mc = MODEL_CONFIG

    if num_classes is None:
        num_classes = mc["num_classes"]

    return TCNBiLSTMClassifier(
        in_features=in_features,
        tcn_channels=mc["tcn_num_channels"],
        tcn_kernel=mc["tcn_kernel_size"],
        lstm_hidden=mc["lstm_hidden"],
        lstm_layers=mc["lstm_layers"],
        num_classes=num_classes,
        dropout=0.3,
    )


if __name__ == "__main__":
    print("Testing default multiclass model...")
    model = build_model()
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)

    print("TCN-BiLSTM model")
    print(f"  Total params    : {total:,}")
    print(f"  Trainable params: {trainable:,}")

    dummy = torch.randn(4, 30, 51)
    out = model(dummy)

    print(f"  Input shape  : {dummy.shape}")
    print(f"  Output shape : {out.shape}")

    print("\nTesting binary fall model...")
    binary_model = build_model(num_classes=2)
    binary_out = binary_model(dummy)
    print(f"  Binary output shape : {binary_out.shape}")

    print("\nTesting activity model...")
    activity_model = build_model(num_classes=7)
    activity_out = activity_model(dummy)
    print(f"  Activity output shape : {activity_out.shape}")

    print("\nModel OK.")