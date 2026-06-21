"""Export workflow designer view to a light-theme PNG."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from PIL import Image, ImageDraw, ImageFont

from intent_workflow.config import DEFAULT_CONFIG_PATH, PROJECT_ROOT

OUTPUT_PATH = PROJECT_ROOT / "designer" / "workflow-workspace.png"

NODE_W, NODE_H = 190, 72
COL_SPACING, GROUP_GAP = 240, 80
PAD = 48

BG = "#f8fafc"
GROUP_FILL = "#ffffff"
GROUP_STROKE = "#cbd5e1"
GROUP_LABEL = "#334155"
NODE_FILL = "#ffffff"
NODE_STROKE = "#94a3b8"
NODE_TITLE = "#0f172a"
NODE_SUB = "#64748b"
EDGE = "#64748b"
EDGE_CROSS = "#ea580c"
EDGE_LABEL = "#475569"
EDGE_LABEL_CROSS = "#c2410c"
CLASSIFY_FILL = "#eff6ff"
FINALIZE_FILL = "#f0fdf4"


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeui.ttf" if not bold else "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arial.ttf" if not bold else "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def init_positions(intents: dict[str, Any]) -> dict[str, tuple[float, float]]:
    positions: dict[str, tuple[float, float]] = {}
    cursor_y = 70.0
    for intent_id, intent in intents.items():
        stage_ids = list((intent.get("stages") or {}).keys())
        max_forks = max((len((intent["stages"][sid].get("forks") or {})) for sid in stage_ids), default=1)
        row_spacing = max(100, max_forks * 26)
        center_y = cursor_y + row_spacing / 2 + NODE_H / 2
        group_h = row_spacing + NODE_H + 40

        for node_id in ["classify", *stage_ids, "finalize"]:
            if node_id == "classify":
                x, y = 60.0, center_y
            elif node_id == "finalize":
                x = 60.0 + 260 + len(stage_ids) * COL_SPACING
                y = center_y
            else:
                idx = stage_ids.index(node_id)
                x = 60.0 + 260 + idx * COL_SPACING
                y = center_y + (-row_spacing / 2 if idx % 2 == 0 else row_spacing / 2)
            positions[f"{intent_id}:{node_id}"] = (x, y)

        cursor_y += group_h + GROUP_GAP
    return positions


def _is_cross_intent(next_val: str, source_intent: str, intents: dict[str, Any]) -> bool:
    if ":" not in next_val or next_val == "finalize":
        return False
    ref_intent, _ = next_val.split(":", 1)
    return ref_intent in intents and ref_intent != source_intent


def draw_node(
    draw: ImageDraw.ImageDraw,
    pos: tuple[float, float],
    title: str,
    subtitle: str,
    fill: str,
    font_title: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    font_sub: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    x, y = pos
    draw.rounded_rectangle((x, y, x + NODE_W, y + NODE_H), radius=10, fill=fill, outline=NODE_STROKE, width=1)
    draw.text((x + 12, y + 16), title[:26], fill=NODE_TITLE, font=font_title)
    draw.text((x + 12, y + 38), subtitle[:30], fill=NODE_SUB, font=font_sub)


def bezier_points(x1, y1, x2, y2, bx=0.0, by=0.0, steps=24):
    cpx = (x1 + x2) / 2 + bx
    pts = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1 - t
        x = mt**3 * x1 + 3 * mt**2 * t * cpx + 3 * mt * t**2 * cpx + t**3 * x2
        y = mt**3 * y1 + 3 * mt**2 * t * (y1 + by) + 3 * mt * t**2 * (y2 + by) + t**3 * y2
        pts.append((x, y))
    return pts


def export_workflow_png(
    config: dict[str, Any] | None = None,
    output_path: Path | None = None,
) -> Path:
    if config is None:
        with DEFAULT_CONFIG_PATH.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

    intents = config["intents"]
    positions = init_positions(intents)
    out = output_path or OUTPUT_PATH

    max_x = max(x + NODE_W for x, _ in positions.values()) + PAD
    max_y = max(y + NODE_H for _, y in positions.values()) + PAD
    img = Image.new("RGB", (int(max_x), int(max_y)), BG)
    draw = ImageDraw.Draw(img)
    font_title = load_font(12, bold=True)
    font_sub = load_font(10)
    font_edge = load_font(9)

    for intent_id, intent in intents.items():
        stage_ids = list((intent.get("stages") or {}).keys())
        node_ids = ["classify", *stage_ids, "finalize"]
        pts = [positions[f"{intent_id}:{nid}"] for nid in node_ids]
        min_x = min(x for x, _ in pts) - 32
        min_y = min(y for _, y in pts) - 52
        max_gx = max(x + NODE_W for x, _ in pts) + 32
        max_gy = max(y + NODE_H for _, y in pts) + 24
        draw.rounded_rectangle((min_x, min_y, max_gx, max_gy), radius=16, fill=GROUP_FILL, outline=GROUP_STROKE, width=1)
        draw.text((min_x + 12, min_y + 14), intent.get("label") or intent_id, fill=GROUP_LABEL, font=font_title)

    edges: list[tuple] = []
    for intent_id, intent in intents.items():
        if intent.get("start_stage"):
            edges.append((intent_id, "classify", intent_id, intent["start_stage"], "start", False))
        for stage_id, stage in (intent.get("stages") or {}).items():
            for fork_id, fork in (stage.get("forks") or {}).items():
                nxt = fork.get("next")
                if not isinstance(nxt, str):
                    continue
                cross = _is_cross_intent(nxt, intent_id, intents)
                to_intent, to_stage = (nxt.split(":", 1) if cross else (intent_id, nxt))
                label = fork_id
                if cross:
                    label = f"→ {(intents.get(to_intent) or {}).get('label', to_intent)}: {to_stage}"
                edges.append((intent_id, stage_id, to_intent, to_stage, label, cross))

    for from_i, from_n, to_i, to_n, label, cross in edges:
        f = positions.get(f"{from_i}:{from_n}")
        t = positions.get(f"{to_i}:{to_n}")
        if not f or not t:
            continue
        x1, y1 = f[0] + NODE_W, f[1] + NODE_H / 2
        x2, y2 = t[0], t[1] + NODE_H / 2
        color = EDGE_CROSS if cross else EDGE
        pts = bezier_points(x1, y1, x2, y2)
        draw.line(pts, fill=color, width=2 if cross else 1)
        draw.ellipse((x2 - 4, y2 - 4, x2 + 4, y2 + 4), fill=color)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        draw.text((mx - 20, my - 14), label[:28], fill=EDGE_LABEL_CROSS if cross else EDGE_LABEL, font=font_edge)

    for intent_id, intent in intents.items():
        stage_ids = list((intent.get("stages") or {}).keys())
        draw_node(
            draw,
            positions[f"{intent_id}:classify"],
            "Classifier",
            f"{len(intent.get('keywords') or [])} keywords",
            CLASSIFY_FILL,
            font_title,
            font_sub,
        )
        for stage_id in stage_ids:
            stage = intent["stages"][stage_id]
            sub = "start stage" if stage_id == intent.get("start_stage") else stage["action"]["type"]
            draw_node(draw, positions[f"{intent_id}:{stage_id}"], stage.get("title") or stage_id, sub, NODE_FILL, font_title, font_sub)
        draw_node(draw, positions[f"{intent_id}:finalize"], "Finalize", "return response", FINALIZE_FILL, font_title, font_sub)

    title = config.get("workflow", {}).get("name", "Workflow")
    draw.text((PAD, 12), title, fill="#1e293b", font=load_font(16, bold=True))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    return out
