from __future__ import annotations

import argparse
import base64
import glob
import re
import time
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from configs.config import ACTIVITY_COLOR_MAP, DASHBOARD_CONFIG, MODEL_CONFIG, ROOT_DIR



def _safe_filename(name: str | None) -> str:
    if not name:
        return "uploaded_video.mp4"
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return cleaned or "uploaded_video.mp4"

def _load_predictions(root_dir: str) -> pd.DataFrame:
    pattern = os.path.join(root_dir, "outputs", "**", "*predictions*.csv")
    csvs = sorted(glob.glob(pattern, recursive=True))
    if not csvs:
        csvs = sorted(glob.glob(os.path.join(root_dir, "outputs", "*predictions*.csv")))
    if not csvs:
        return pd.DataFrame(
            columns=[
                "frame_idx",
                "timestamp_s",
                "label",
                "confidence",
                "fall_confidence",
                "fall_status",
                "activity_label",
                "activity_confidence",
                "gait_risk",
                "gait_level",
            ]
        )
    return pd.read_csv(csvs[-1])


def _load_training_log(root_dir: str) -> pd.DataFrame:
    candidates = [
        os.path.join(root_dir, "outputs", "binary_fall_training_log.csv"),
        os.path.join(root_dir, "outputs", "training_log.csv"),
        os.path.join(root_dir, "outputs", "activity_training_log.csv"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return pd.read_csv(path)
    return pd.DataFrame()


def _load_sos_alerts(root_dir: str) -> pd.DataFrame:
    path = os.path.join(root_dir, "logs", "sos_alerts.csv")
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame()


def _find_latest_video(root_dir: str) -> str | None:
    patterns = [
        os.path.join(root_dir, "outputs", "*_skeleton.mp4"),
        os.path.join(root_dir, "outputs", "*.mp4"),
    ]
    videos = []
    for pattern in patterns:
        videos.extend(glob.glob(pattern))
    if not videos:
        return None
    videos = sorted(videos, key=os.path.getmtime)
    return videos[-1]


def _run_inference_command(root_dir: str, source: str, tag: str, show_live: bool = False) -> str:
    outputs_dir = os.path.join(root_dir, "outputs")
    os.makedirs(outputs_dir, exist_ok=True)

    out_video = os.path.join(outputs_dir, f"{tag}_skeleton.mp4")
    out_csv = os.path.join(outputs_dir, f"{tag}_predictions.csv")

    cmd = [
        sys.executable,
        os.path.join(root_dir, "pipeline", "inference.py"),
        "--root_dir", root_dir,
        "--source", str(source),
        "--out_video", out_video,
        "--out_csv", out_csv,
        "--fall_threshold", "0.30",
        "--frame_skip", "3",
    ]

    if show_live:
        cmd.append("--show_live")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Inference failed.\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
        )

    return out_video


def _build_timeline(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No prediction data yet — run inference first",
            showarrow=False,
            font=dict(color="#8b949e", size=13),
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0d1117",
            plot_bgcolor="#0d1117",
            height=180,
        )
        return fig

    timeline_col = "activity_label" if "activity_label" in df.columns else "label"
    conf_col = "activity_confidence" if "activity_confidence" in df.columns else "confidence"

    df = df.copy().sort_values("timestamp_s")
    spans = []
    prev_label = df.iloc[0][timeline_col]
    prev_start = df.iloc[0]["timestamp_s"]
    prev_conf = df.iloc[0][conf_col]

    for _, row in df.iloc[1:].iterrows():
        if row[timeline_col] != prev_label:
            spans.append(
                {
                    "label": prev_label,
                    "start": prev_start,
                    "end": row["timestamp_s"],
                    "conf": prev_conf,
                }
            )
            prev_label = row[timeline_col]
            prev_start = row["timestamp_s"]
            prev_conf = row[conf_col]

    spans.append(
        {
            "label": prev_label,
            "start": prev_start,
            "end": df.iloc[-1]["timestamp_s"] + 1,
            "conf": prev_conf,
        }
    )

    fig = go.Figure()
    seen_labels = set()
    for span in spans:
        color = ACTIVITY_COLOR_MAP.get(span["label"], "#636e72")
        show_legend = span["label"] not in seen_labels
        seen_labels.add(span["label"])

        fig.add_trace(
            go.Bar(
                x=[span["end"] - span["start"]],
                y=["Activity"],
                base=[span["start"]],
                orientation="h",
                marker_color=color,
                name=span["label"],
                showlegend=show_legend,
                hovertemplate=(
                    f"<b>{str(span['label']).upper()}</b><br>"
                    f"Start: {span['start']:.1f}s<br>"
                    f"End: {span['end']:.1f}s<br>"
                    f"Duration: {span['end'] - span['start']:.1f}s<br>"
                    f"Conf: {float(span['conf']):.0%}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        barmode="stack",
        xaxis_title="Time (seconds)",
        yaxis_title="",
        template="plotly_dark",
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font=dict(family="monospace", color="#e6edf3"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=60, r=20, t=10, b=40),
        height=180,
    )
    return fig


def _build_confidence_chart(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0d1117",
            plot_bgcolor="#0d1117",
            height=180,
        )
        return fig

    y_col = "fall_confidence" if "fall_confidence" in df.columns else "confidence"

    fig = go.Figure(
        go.Scatter(
            x=df["timestamp_s"],
            y=df[y_col],
            mode="lines",
            line=dict(color="#4ECDC4", width=2),
            fill="tozeroy",
            fillcolor="rgba(78,205,196,0.15)",
            hovertemplate="t=%{x:.1f}s<br>conf=%{y:.0%}<extra></extra>",
        )
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font=dict(family="monospace", color="#e6edf3"),
        xaxis_title="Time (s)",
        yaxis_title="Fall Confidence",
        yaxis=dict(tickformat=".0%", range=[0, 1]),
        margin=dict(l=60, r=20, t=10, b=40),
        height=180,
    )
    return fig


def _build_gait_chart(df: pd.DataFrame) -> go.Figure:
    if df.empty or "gait_risk" not in df.columns:
        fig = go.Figure()
        fig.add_annotation(
            text="No gait data yet",
            showarrow=False,
            font=dict(color="#8b949e"),
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0d1117",
            plot_bgcolor="#0d1117",
            height=180,
        )
        return fig

    colors = df["gait_level"].map(
        {
            "LOW": "#00c853",
            "MEDIUM": "#ff9100",
            "HIGH": "#ff1744",
            "unknown": "#636e72",
        }
    ).fillna("#636e72")

    fig = go.Figure(
        go.Scatter(
            x=df["timestamp_s"],
            y=df["gait_risk"],
            mode="lines+markers",
            line=dict(color="#ff9100", width=2),
            marker=dict(color=colors, size=5),
            hovertemplate="t=%{x:.1f}s<br>risk=%{y:.2f}<extra></extra>",
        )
    )

    fig.add_hline(y=0.7, line_dash="dash", line_color="#ff1744", annotation_text="HIGH", annotation_position="right")
    fig.add_hline(y=0.4, line_dash="dash", line_color="#ff9100", annotation_text="MEDIUM", annotation_position="right")

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font=dict(family="monospace", color="#e6edf3"),
        xaxis_title="Time (s)",
        yaxis_title="Gait Risk Score",
        yaxis=dict(range=[0, 1]),
        margin=dict(l=60, r=60, t=10, b=40),
        height=180,
    )
    return fig


def _build_pie(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure()

    pie_col = "activity_label" if "activity_label" in df.columns else "label"
    counts = df.groupby(pie_col).size().reset_index(name="count")
    counts.columns = ["label", "count"]
    colors = [ACTIVITY_COLOR_MAP.get(l, "#636e72") for l in counts["label"]]

    fig = go.Figure(
        go.Pie(
            labels=counts["label"],
            values=counts["count"],
            marker_colors=colors,
            hole=0.45,
            textinfo="label+percent",
            hovertemplate="%{label}: %{value} frames (%{percent})<extra></extra>",
        )
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0d1117",
        font=dict(family="monospace", color="#e6edf3"),
        showlegend=False,
        margin=dict(l=10, r=10, t=10, b=10),
        height=260,
    )
    return fig


def _build_training_curves(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    if df.empty:
        fig.add_annotation(
            text="Training log not found yet",
            showarrow=False,
            font=dict(color="#8b949e"),
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0d1117",
            plot_bgcolor="#0d1117",
            height=260,
        )
        return fig

    if "val_accuracy" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["epoch"],
                y=df["val_accuracy"],
                name="Val Accuracy (%)",
                line=dict(color="#4ECDC4", width=2),
            )
        )
    if "train_loss" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["epoch"],
                y=df["train_loss"],
                name="Train Loss",
                line=dict(color="#FF6B6B", width=2, dash="dot"),
                yaxis="y2",
            )
        )
    if "fall_f1" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["epoch"],
                y=df["fall_f1"],
                name="Fall F1",
                line=dict(color="#FF3B3B", width=2),
            )
        )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font=dict(family="monospace", color="#e6edf3"),
        xaxis_title="Epoch",
        legend=dict(orientation="h"),
        margin=dict(l=60, r=60, t=10, b=40),
        height=260,
        yaxis=dict(title="Accuracy / F1"),
        yaxis2=dict(title="Loss", overlaying="y", side="right"),
    )
    return fig


_CARD = {
    "background": "#161b22",
    "borderRadius": "14px",
    "padding": "20px",
    "marginBottom": "16px",
    "border": "1px solid #30363d",
    "boxShadow": "0 4px 16px rgba(0,0,0,0.25)",
}

_TITLE = {
    "fontFamily": "monospace",
    "fontSize": "11px",
    "letterSpacing": "2px",
    "textTransform": "uppercase",
    "color": "#8b949e",
    "marginBottom": "12px",
}

_BADGE = {
    "display": "inline-block",
    "padding": "4px 10px",
    "borderRadius": "20px",
    "fontFamily": "monospace",
    "fontSize": "11px",
    "fontWeight": "700",
    "marginRight": "6px",
}


def _sos_badge(label: str) -> html.Span:
    colors = {
        "fall": "#FF3B3B",
        "wave_sos": "#FF8C00",
        "prolonged_sleep": "#6C5CE7",
        "prolonged_inactivity": "#636e72",
        "fall_risk": "#FF8C00",
        "alerttype.fall_risk": "#FF8C00",
    }
    color = colors.get(label.lower(), "#333")
    return html.Span(
        label.replace("_", " ").upper(),
        style={**_BADGE, "background": color, "color": "#fff"},
    )


def build_layout(root_dir: str) -> html.Div:
    class_names = MODEL_CONFIG["class_names"]

    legend_chips = [
        html.Span(
            cls,
            style={
                **_BADGE,
                "background": ACTIVITY_COLOR_MAP.get(cls, "#636e72"),
                "color": "#000" if cls in ("eat", "other") else "#fff",
            },
        )
        for cls in class_names
    ]

    return html.Div(
        style={
            "background": "#0d1117",
            "minHeight": "100vh",
            "fontFamily": "Inter, Segoe UI, Arial, sans-serif",
            "color": "#e6edf3",
            "padding": "24px 32px",
        },
        children=[
            html.Div(id="alert-popup"),
            html.Div(
                [
                    html.H1(
                        "⚕ ElderSafe AI Monitor",
                        style={"margin": "0 0 4px", "fontSize": "28px", "fontWeight": "800", "color": "#f0f6fc"},
                    ),
                    html.P(
                        "Fall Detection · Activity Recognition · Gait Analysis · SOS Alerting",
                        style={"color": "#8b949e", "fontSize": "14px", "margin": "0 0 16px"},
                    ),
                    html.Div(legend_chips),
                ],
                style={"marginBottom": "24px"},
            ),
            dcc.Interval(id="refresh-interval", interval=DASHBOARD_CONFIG["refresh_interval_ms"], n_intervals=0),
            html.Div(id="live-status-bar", style=_CARD),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div([html.P("Activity Timeline", style=_TITLE), dcc.Graph(id="timeline-graph", config={"displayModeBar": False})], style=_CARD),
                            html.Div([html.P("Prediction Confidence", style=_TITLE), dcc.Graph(id="confidence-graph", config={"displayModeBar": False})], style=_CARD),
                            html.Div([html.P("Gait Risk Over Time", style=_TITLE), dcc.Graph(id="gait-graph", config={"displayModeBar": False})], style=_CARD),
                            html.Div([html.P("Training Metrics", style=_TITLE), dcc.Graph(id="training-graph", figure=_build_training_curves(_load_training_log(root_dir)), config={"displayModeBar": False})], style=_CARD),
                        ],
                        style={"flex": "2", "marginRight": "16px"},
                    ),
                    html.Div(
                        [
                            html.Div([html.P("Activity Breakdown", style=_TITLE), dcc.Graph(id="pie-graph", config={"displayModeBar": False})], style=_CARD),
                            html.Div([html.P("Current Gait Status", style=_TITLE), html.Div(id="gait-status-box")], style=_CARD),
                            html.Div([html.P("SOS Event Log", style=_TITLE), html.Div(id="sos-log")], style=_CARD),
                            html.Div(
                                [
                                    html.P("Inference Controls", style=_TITLE),
                                    dcc.Upload(
                                        id="upload-video",
                                        children=html.Div(["Drag and Drop or ", html.A("Select Video")]),
                                        style={
                                            "width": "100%",
                                            "height": "60px",
                                            "lineHeight": "60px",
                                            "borderWidth": "1px",
                                            "borderStyle": "dashed",
                                            "borderRadius": "10px",
                                            "textAlign": "center",
                                            "marginBottom": "10px",
                                            "color": "#e6edf3",
                                        },
                                        multiple=False,
                                    ),
                                    html.Div(
                                        [
                                            html.Button(
                                                "Extract / Run Uploaded Video",
                                                id="run-upload-btn",
                                                n_clicks=0,
                                                style={
                                                    "marginRight": "8px",
                                                    "padding": "10px 14px",
                                                    "background": "#238636",
                                                    "color": "white",
                                                    "border": "none",
                                                    "borderRadius": "8px",
                                                    "cursor": "pointer",
                                                },
                                            ),
                                            html.Button(
                                                "Run Camera",
                                                id="run-camera-btn",
                                                n_clicks=0,
                                                style={
                                                    "padding": "10px 14px",
                                                    "background": "#1f6feb",
                                                    "color": "white",
                                                    "border": "none",
                                                    "borderRadius": "8px",
                                                    "cursor": "pointer",
                                                },
                                            ),
                                        ],
                                        style={"marginBottom": "12px"},
                                    ),
                                    html.Div(
                                        id="inference-status",
                                        style={"fontSize": "12px", "color": "#8b949e", "marginBottom": "10px"},
                                    ),
                                    html.Video(
                                        id="video-player",
                                        controls=True,
                                        autoPlay=False,
                                        muted=False,
                                        style={
                                            "width": "100%",
                                            "borderRadius": "10px",
                                            "marginTop": "10px",
                                            "background": "#000",
                                        },
                                        children=[html.Source(id="video-source", src="", type="video/mp4")],
                                    ),
                                    html.Div(
                                        id="video-caption",
                                        style={"marginTop": "8px", "fontSize": "11px", "color": "#8b949e", "wordBreak": "break-all"},
                                    ),
                                ],
                                style=_CARD,
                            ),
                        ],
                        style={"flex": "1"},
                    ),
                ],
                style={"display": "flex", "alignItems": "flex-start"},
            ),
        ],
    )


def create_app(root_dir: str) -> Dash:
    assets_dir = os.path.join(os.path.dirname(__file__), "assets")
    os.makedirs(assets_dir, exist_ok=True)

    app = Dash(
        __name__,
        title="ElderSafe AI Monitor",
        suppress_callback_exceptions=True,
        serve_locally=True,
    )
    app.layout = build_layout(root_dir)

    @app.callback(Output("alert-popup", "children"), Input("refresh-interval", "n_intervals"))
    def show_alert(n):
        df = _load_predictions(root_dir)
        if df.empty:
            return ""

        last = df.iloc[-1]
        if last.get("fall_status") == "FALLING":
            return html.Div(
                "🚨 FALL DETECTED!",
                style={
                    "position": "fixed",
                    "top": "20px",
                    "right": "20px",
                    "background": "#ff1744",
                    "color": "white",
                    "padding": "15px 25px",
                    "borderRadius": "12px",
                    "fontSize": "18px",
                    "fontWeight": "bold",
                    "zIndex": "9999",
                    "boxShadow": "0 4px 16px rgba(0,0,0,0.35)",
                },
            )
        return ""

    @app.callback(Output("live-status-bar", "children"), Input("refresh-interval", "n_intervals"))
    def update_status(n):
        df = _load_predictions(root_dir)
        if df.empty:
            return html.P(
                "Waiting for inference data — upload a video and click Extract / Run Uploaded Video",
                style={"color": "#8b949e", "fontSize": "13px"},
            )

        last = df.iloc[-1]
        fall_status = last.get("fall_status", "NOT FALLING")
        fall_conf = float(last.get("fall_confidence", 0.0))
        activity_label = last.get("activity_label", last.get("label", "other"))
        activity_conf = float(last.get("activity_confidence", last.get("confidence", 0.0)))
        ts = float(last.get("timestamp_s", 0))
        gait = last.get("gait_level", "unknown")

        status_color = "#ff1744" if fall_status == "FALLING" else "#00c853"

        return html.Div(
            [
                html.Span("LIVE", style={**_BADGE, "background": "#238636", "color": "#fff"}),
                html.Span(
                    fall_status,
                    style={"fontWeight": "800", "fontSize": "22px", "color": status_color, "marginRight": "14px"},
                ),
                html.Span(
                    f"Fall Confidence: {fall_conf:.0%}",
                    style={"color": "#8b949e", "fontSize": "13px", "marginRight": "16px"},
                ),
                html.Span(
                    f"Activity: {str(activity_label).upper()} ({activity_conf:.0%})",
                    style={"color": "#8b949e", "fontSize": "13px", "marginRight": "16px"},
                ),
                html.Span(
                    f"t = {ts:.1f}s",
                    style={"color": "#8b949e", "fontSize": "13px", "marginRight": "16px"},
                ),
                html.Span(
                    f"Gait: {gait}",
                    style={"color": "#ff9100", "fontSize": "13px"},
                ),
            ],
            style={"display": "flex", "alignItems": "center", "flexWrap": "wrap", "gap": "8px"},
        )

    @app.callback(
        Output("timeline-graph", "figure"),
        Output("confidence-graph", "figure"),
        Output("gait-graph", "figure"),
        Output("pie-graph", "figure"),
        Input("refresh-interval", "n_intervals"),
    )
    def update_charts(n):
        df = _load_predictions(root_dir)
        return _build_timeline(df), _build_confidence_chart(df), _build_gait_chart(df), _build_pie(df)

    @app.callback(Output("gait-status-box", "children"), Input("refresh-interval", "n_intervals"))
    def update_gait_status(n):
        df = _load_predictions(root_dir)
        if df.empty or "gait_risk" not in df.columns:
            return html.P("No gait data yet", style={"color": "#8b949e", "fontSize": "12px"})

        last = df.iloc[-1]
        level = last.get("gait_level", "unknown")
        score = float(last.get("gait_risk", 0.0))

        color_map = {
            "LOW": "#00c853",
            "MEDIUM": "#ff9100",
            "HIGH": "#ff1744",
            "unknown": "#636e72",
        }
        color = color_map.get(level, "#636e72")

        return html.Div(
            [
                html.Div(level, style={"fontSize": "32px", "fontWeight": "900", "color": color, "marginBottom": "8px"}),
                html.Div(f"Risk Score: {score:.2f}", style={"color": "#8b949e", "fontSize": "13px"}),
            ]
        )

    @app.callback(Output("sos-log", "children"), Input("refresh-interval", "n_intervals"))
    def update_sos_log(n):
        df = _load_sos_alerts(root_dir)
        if df.empty:
            return html.P("No alerts yet", style={"color": "#8b949e", "fontSize": "12px"})

        items = []
        for _, row in df.tail(8).iloc[::-1].iterrows():
            items.append(
                html.Div(
                    [
                        _sos_badge(str(row.get("alert_type", "unknown"))),
                        html.Br(),
                        html.Span(str(row.get("message", ""))[:120], style={"fontSize": "11px", "color": "#e6edf3"}),
                        html.Br(),
                        html.Span(str(row.get("timestamp", "")), style={"fontSize": "10px", "color": "#8b949e"}),
                    ],
                    style={"marginBottom": "10px", "paddingBottom": "10px", "borderBottom": "1px solid #30363d"},
                )
            )
        return items

    @app.callback(
        Output("inference-status", "children"),
        Input("run-upload-btn", "n_clicks"),
        State("upload-video", "contents"),
        State("upload-video", "filename"),
        prevent_initial_call=True,
    )
    def run_uploaded_inference(n_clicks, contents, filename):
        if not contents:
            return "Please upload a video first."

        uploads_dir = os.path.join(root_dir, "dashboard", "assets", "uploads")
        os.makedirs(uploads_dir, exist_ok=True)

        safe_name = _safe_filename(filename)
        input_path = os.path.join(uploads_dir, safe_name)

        try:
            _, content_string = contents.split(",")
            decoded = base64.b64decode(content_string)

            with open(input_path, "wb") as f:
                f.write(decoded)

            out_video = _run_inference_command(root_dir, input_path, "uploaded_result", show_live=False)
            return f"✅ Finished processing: {safe_name} → {os.path.basename(out_video)}"
        except Exception as e:
            return f"Upload / inference failed: {e}"

    @app.callback(
        Output("inference-status", "children", allow_duplicate=True),
        Input("run-camera-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def run_camera_inference(n_clicks):
        try:
            thread = threading.Thread(
                target=_run_inference_command,
                args=(root_dir, "0", "camera_result", True),
                daemon=True,
            )
            thread.start()
            return "Camera started. Press Q in the OpenCV window to stop and save output."
        except Exception as e:
            return f"Camera inference failed: {e}"

    @app.callback(
        Output("video-source", "src"),
        Output("video-caption", "children"),
        Input("refresh-interval", "n_intervals"),
    )
    def update_video(n):
        latest_video = _find_latest_video(root_dir)
        if latest_video is None:
            return "", "No skeleton video found yet."

        assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        os.makedirs(assets_dir, exist_ok=True)

        dst_name = os.path.basename(latest_video)
        dst_path = os.path.join(assets_dir, dst_name)

        try:
            src_mtime = os.path.getmtime(latest_video)
            dst_mtime = os.path.getmtime(dst_path) if os.path.exists(dst_path) else -1

            if (not os.path.exists(dst_path)) or (src_mtime > dst_mtime):
                shutil.copy2(latest_video, dst_path)

            shutil.copy2(latest_video, dst_path)
            return f"/assets/{dst_name}?v={int(time.time())}", f"Playing: {dst_name}"
        except Exception as e:
            return "", f"Video found but could not copy into assets/: {e}"

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root_dir", default=ROOT_DIR)
    parser.add_argument("--port", type=int, default=DASHBOARD_CONFIG["port"])
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app = create_app(args.root_dir)
    print(f"\n🚀 ElderSafe Dashboard → http://localhost:{args.port}\n")
    app.run(debug=args.debug, host="0.0.0.0", port=args.port)