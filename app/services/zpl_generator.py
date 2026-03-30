"""
zpl_converter.py
Converts BarcodeEditorPage serialized canvas (list[dict]) → ZPL II label string.

Usage:
    from zpl_converter import canvas_to_zpl

    payload = editor_page.get_design_payload()
    zpl = canvas_to_zpl(
        canvas_json=payload["usrm"],   # the JSON string from get_design_payload()
        canvas_w=editor_page._canvas_w,
        canvas_h=editor_page._canvas_h,
        dpi=203,                        # 203 or 300 — your printer DPI
    )
    print(zpl)
"""

import json
import math
from typing import Any

# ── ZPL barcode-type map ──────────────────────────────────────────────────────
# Maps your design combo values → ZPL ^B command
_ZPL_BARCODE_CMD: dict[str, str] = {
    "CODE 128":            "^BC",
    "CODE 128-A":          "^BC",
    "CODE 128-B":          "^BC",
    "CODE 128-C":          "^BC",
    "CODE128":             "^BC",   # no-space variant
    "CODE128-A":           "^BC",
    "CODE128-B":           "^BC",
    "CODE128-C":           "^BC",
    "CODE 39":             "^B3",
    "CODE 93":             "^BA",
    "CODE 11":             "^B1",
    "EAN 13":              "^BE",
    "EAN 8":               "^B8",
    "UPC A":               "^BU",
    "INTERLEAVED 2 OF 5":  "^BI",
    "QR (2D)":             "^BQ",
    "DATA MATRIX (2D)":    "^BX",
    "AZTEC (2D)":          "^BO",
}

# ZPL orientation map: Qt rotation degrees → ZPL orientation letter
_ORIENT: dict[int, str] = {0: "N", 90: "B", 180: "I", 270: "R"}

# ZPL font map: font-name → ZPL font letter / number
_ZPL_FONT: dict[str, str] = {
    "STANDARD":            "0",
    "ARIAL":               "0",
    "ARIAL BOLD":          "0",
    "ARIAL BLACK":         "0",
    "ARIAL BLACK (GT)":    "0",
    "ARIAL BLACK NEW":     "0",
    "ARIAL NARROW BOLD":   "0",
    "OCR-B":               "B",
    "TAHOMA":              "0",
}

_CANVAS_DPI = 203
_SCREEN_DPI = 96   # canvas pixels are screen pixels at 96 DPI


def _px_to_dots(px: float, dpi: int = 203) -> int:
    """Convert screen pixels (96 DPI) → printer dots at the given DPI."""
    return max(0, int(round(px * dpi / _SCREEN_DPI)))


def _rotation_to_orient(rotation: float) -> str:
    """Map item rotation (Qt degrees) to ZPL orientation letter."""
    r = int(round(rotation)) % 360
    return _ORIENT.get(r, "N")


def _field_origin(x: float, y: float, dpi: int) -> str:
    fx = max(0, int(round(x * dpi / _SCREEN_DPI)))
    fy = max(0, int(round(y * dpi / _SCREEN_DPI)))
    return f"^FO{fx},{fy}"


# ── Individual element converters ─────────────────────────────────────────────

def _convert_text(d: dict, dpi: int) -> str:
    """Convert a text element to ZPL."""
    x = d.get("aabb_x", d.get("x", 0))
    y = d.get("aabb_y", d.get("y", 0))
    rotation = int(round(d.get("rotation", 0))) % 360
    orient = _ORIENT.get(rotation, "N")

    font_name = (d.get("font_family") or "STANDARD").upper()
    zpl_font  = _ZPL_FONT.get(font_name, "0")
    font_size = float(d.get("font_size", 10))

    # font_size is Qt point size (1pt = 1/72 inch).
    # dots = pt / 72 * dpi
    dot_h = max(10, int(round(font_size / 72 * dpi)))
    dot_w = dot_h

    inverse = d.get("design_inverse", False) or d.get("inverse", False)
    text    = d.get("text", "")

    # Escape caret and tilde which are ZPL control chars
    text = text.replace("^", "\\^").replace("~", "\\~")

    print(f"    [TEXT] name={d.get('name','?')!r}")
    print(f"           pos source  : aabb_x={d.get('aabb_x','N/A')}, aabb_y={d.get('aabb_y','N/A')} | raw x={d.get('x','N/A')}, y={d.get('y','N/A')}")
    print(f"           used ^FO    : x={max(0,int(round(x*dpi/_SCREEN_DPI)))}, y={max(0,int(round(y*dpi/_SCREEN_DPI)))}  (scaled from screen px)")
    print(f"           font        : family={font_name!r} → ZPL font={zpl_font!r}, size={font_size}pt → dot_h={dot_h}, dot_w={dot_w}")
    print(f"           rotation    : {rotation}° → orient={orient!r}")
    print(f"           inverse     : {inverse}")
    print(f"           text        : {text!r}")

    lines: list[str] = [
        _field_origin(x, y, dpi),
        f"^A{zpl_font}{orient},{dot_h},{dot_w}",
    ]
    if inverse:
        lines.append("^FR")
    lines.append(f"^FD{text}^FS")
    return "\n".join(lines)


def _convert_barcode(d: dict, dpi: int) -> str:
    """Convert a barcode element to ZPL."""
    x = d.get("aabb_x", d.get("x", 0))
    y = d.get("aabb_y", d.get("y", 0))
    rotation = int(round(d.get("rotation", 0))) % 360
    orient   = _ORIENT.get(rotation, "N")

    design   = (d.get("design") or "CODE 128").upper()
    text     = str(d.get("design_text") or "")

    # ── Barcode height ────────────────────────────────────────────────────────
    # Priority 1: explicit dot value (rare, set programmatically)
    # Priority 2: container_width/container_height — actual screen-px size of
    #             the barcode box as drawn in the editor. For a rotated barcode
    #             (270 or 90deg) the bar length runs along the canvas X axis,
    #             so we use container_width; for 0deg we use container_height.
    # Priority 3: design_height_cm fallback (real-world cm -> dots).
    height_dots_raw = d.get("design_height_dots")
    if height_dots_raw is not None:
        height_dots  = max(10, int(height_dots_raw))
        height_source = f"design_height_dots={height_dots_raw} (explicit)"
    else:
        container_w = d.get("container_width")
        container_h = d.get("container_height")
        if rotation in (90, 270) and container_w is not None:
            height_dots  = max(10, int(round(float(container_w) * dpi / _SCREEN_DPI)))
            height_source = f"container_width={container_w}px -> {height_dots} dots (rotated, scaled)"
        elif container_h is not None:
            height_dots  = max(10, int(round(float(container_h) * dpi / _SCREEN_DPI)))
            height_source = f"container_height={container_h}px -> {height_dots} dots (scaled)"
        else:
            height_cm    = float(d.get("design_height_cm") or 1.0)
            height_dots  = max(10, int(round(height_cm / 2.54 * dpi)))
            height_source = f"design_height_cm={height_cm} -> {height_dots} dots @ {dpi}dpi (fallback)"

    # ── Module width (narrow bar width) ───────────────────────────────────────
    # design_magnification is a unitless 1-10 editor level, NOT screen pixels.
    # It maps directly to ZPL module width in dots — no scaling needed.
    # However the editor uses a wide default (6) which prints very wide;
    # clamp to a safe maximum of 3 for typical small labels.
    mag = d.get("design_magnification")
    try:
        module_w = max(1, min(3, int(mag)))
    except (TypeError, ValueError):
        module_w = 2

    interp = (d.get("design_interpretation") or "").upper()
    show_interp = "Y" if "BELOW" in interp else "N"

    check_digit_raw = (d.get("design_check_digit") or "").upper()
    check_digit = "Y" if "AUTO" in check_digit_raw else "N"

    zpl_cmd = _ZPL_BARCODE_CMD.get(
        design,
        _ZPL_BARCODE_CMD.get(design.split("(")[0].strip(), "^BC"),
    )

    print(f"    [BARCODE] name={d.get('name','?')!r}")
    print(f"              pos source  : aabb_x={d.get('aabb_x','N/A')}, aabb_y={d.get('aabb_y','N/A')} | raw x={d.get('x','N/A')}, y={d.get('y','N/A')}")
    print(f"              used ^FO    : x={max(0,int(round(x*dpi/_SCREEN_DPI)))}, y={max(0,int(round(y*dpi/_SCREEN_DPI)))}  (scaled from screen px)")
    print(f"              design type : {design!r} → ZPL cmd={zpl_cmd!r}")
    print(f"              rotation    : {rotation}° → orient={orient!r}")
    print(f"              height      : {height_source}")
    print(f"              module_w    : mag={mag!r} → module_w={module_w}")
    print(f"              interp line : {interp!r} → show_interp={show_interp!r}")
    print(f"              check digit : {check_digit_raw!r} → check_digit={check_digit!r}")
    print(f"              data        : {text!r}")

    lines: list[str] = [_field_origin(x, y, dpi)]

    is_2d = any(tok in design for tok in ("QR", "DATA MATRIX", "AZTEC"))
    print(f"              is_2d       : {is_2d}")

    if is_2d:
        if "QR" in design:
            lines.append(f"^BQ{orient},2,{module_w}")
            lines.append(f"^FDQA,{text}^FS")
        elif "DATA MATRIX" in design:
            lines.append(f"^BX{orient},{height_dots},200")
            lines.append(f"^FD{text}^FS")
        elif "AZTEC" in design:
            lines.append(f"^BO{orient},{module_w}")
            lines.append(f"^FD{text}^FS")
    else:
        if zpl_cmd == "^BC":
            lines.append(f"^BC{orient},{height_dots},{show_interp},N,N")
        elif zpl_cmd == "^B3":
            lines.append(f"^B3{orient},{check_digit},{height_dots},{show_interp},N")
        elif zpl_cmd == "^BA":
            lines.append(f"^BA{orient},{height_dots},{show_interp},N")
        elif zpl_cmd == "^B1":
            lines.append(f"^B1{orient},{height_dots},{show_interp},N")
        elif zpl_cmd == "^BE":
            lines.append(f"^BE{orient},{height_dots},{show_interp},N")
        elif zpl_cmd == "^B8":
            lines.append(f"^B8{orient},{height_dots},{show_interp},N")
        elif zpl_cmd == "^BU":
            lines.append(f"^BU{orient},{height_dots},{show_interp},N,N")
        elif zpl_cmd == "^BI":
            lines.append(f"^BI{orient},{height_dots},{show_interp},N")
        else:
            lines.append(f"{zpl_cmd}{orient},{height_dots},{show_interp}")

        lines.append(f"^FD{text}^FS")

    return "\n".join(lines)


def _convert_line(d: dict, dpi: int) -> str:
    """Convert a line element to ZPL using ^GB."""
    x = float(d.get("aabb_x", d.get("x", 0)))
    y = float(d.get("aabb_y", d.get("y", 0)))
    x2 = float(d.get("x2", x + 100))
    y2 = float(d.get("y2", y))
    thickness = max(1, _px_to_dots(d.get("thickness", 2), dpi))

    dx = abs(x2 - x)
    dy = abs(y2 - y)

    if dy <= d.get("thickness", 2):
        w = max(thickness, _px_to_dots(dx, dpi))
        h = thickness
        orientation_guess = "horizontal"
    elif dx <= d.get("thickness", 2):
        w = thickness
        h = max(thickness, _px_to_dots(dy, dpi))
        orientation_guess = "vertical"
    else:
        length = _px_to_dots(math.hypot(dx, dy), dpi)
        w = length; h = thickness
        orientation_guess = "diagonal"

    print(f"    [LINE] name={d.get('name','?')!r}")
    print(f"           start       : ({x}, {y})  end: ({x2}, {y2})")
    print(f"           dx={dx}, dy={dy}, thickness={thickness}")
    print(f"           detected    : {orientation_guess}")
    print(f"           ^GB params  : w={w}, h={h}, border={thickness}")

    return (
        f"{_field_origin(x, y, dpi)}\n"
        f"^GB{w},{h},{thickness},B,0^FS"
    )


def _convert_rect(d: dict, dpi: int) -> str:
    """Convert a rectangle element to ZPL using ^GB."""
    x = float(d.get("aabb_x", d.get("x", 0)))
    y = float(d.get("aabb_y", d.get("y", 0)))
    w = max(1, _px_to_dots(float(d.get("width",  100)), dpi))
    h = max(1, _px_to_dots(float(d.get("height",  50)), dpi))
    border = max(1, _px_to_dots(int(d.get("border_width", 2)), dpi))

    print(f"    [RECT] name={d.get('name','?')!r}")
    print(f"           pos         : aabb_x={d.get('aabb_x','N/A')}, aabb_y={d.get('aabb_y','N/A')}")
    print(f"           size source : width={d.get('width','N/A')}, height={d.get('height','N/A')} → dots w={w}, h={h}")
    print(f"           border      : border_width={d.get('border_width','N/A')} → {border} dots")
    print(f"           ^GB params  : w={w}, h={h}, border={border}")

    return (
        f"{_field_origin(x, y, dpi)}\n"
        f"^GB{w},{h},{border},B,0^FS"
    )


# ── Main converter ────────────────────────────────────────────────────────────

def canvas_to_zpl(
    canvas_json: "str | list",
    canvas_w: int = 600,
    canvas_h: int = 400,
    dpi: int = 203,
    label_name: str = "",
    value_overrides: "dict[str, str] | None" = None,
) -> str:
    """
    Convert a serialized canvas (JSON string or already-parsed list) to a ZPL string.
    """
    print("=" * 60)
    print("[canvas_to_zpl] START")
    print(f"  canvas_w    : {canvas_w} px")
    print(f"  canvas_h    : {canvas_h} px")
    print(f"  dpi         : {dpi}")
    print(f"  label_name  : {label_name!r}")
    print(f"  overrides   : {list(value_overrides.keys()) if value_overrides else 'none'}")

    # Physical size: scale canvas px (96dpi screen) → dots → mm
    phys_w_mm = (canvas_w * dpi / _SCREEN_DPI) / dpi * 25.4
    phys_h_mm = (canvas_h * dpi / _SCREEN_DPI) / dpi * 25.4
    print(f"  physical    : {phys_w_mm:.1f} mm × {phys_h_mm:.1f} mm  (canvas px scaled from 96dpi → {dpi}dpi)")
    print("=" * 60)

    if isinstance(canvas_json, str):
        elements: list[dict] = json.loads(canvas_json)
        print(f"[canvas_to_zpl] Parsed JSON string → {len(elements)} element(s)")
    else:
        elements = list(canvas_json)
        print(f"[canvas_to_zpl] Received list → {len(elements)} element(s)")

    # Apply live value overrides
    if value_overrides:
        print(f"[canvas_to_zpl] Applying {len(value_overrides)} value override(s)...")
        elements = _apply_overrides(elements, value_overrides)

    # Sort by z-value ascending
    elements_sorted = sorted(elements, key=lambda d: float(d.get("z", 0)))
    print(f"[canvas_to_zpl] Element z-order (name → z):")
    for e in elements_sorted:
        print(f"  {e.get('type','?'):7s} {e.get('name','?')!r:20s} z={e.get('z', 0)}")

    # Count by type
    type_counts: dict[str, int] = {}
    for e in elements:
        t = e.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    print(f"[canvas_to_zpl] Element type counts: {type_counts}")

    lines: list[str] = []

    # ── Label start ───────────────────────────────────────────────────────────
    label_len_dots = _px_to_dots(canvas_h, dpi)
    print_w_dots   = _px_to_dots(canvas_w, dpi)
    print(f"[canvas_to_zpl] ZPL header: ^LL={label_len_dots} dots, ^PW={print_w_dots} dots")

    lines.append("^XA")
    lines.append("^CI28")
    lines.append("^LH0,0")
    lines.append(f"^LL{label_len_dots}")
    lines.append(f"^PW{print_w_dots}")

    if label_name:
        safe_name = label_name.replace("^", "").replace("~", "")
        lines.append(f"^FX Label: {safe_name}")

    # ── Elements ──────────────────────────────────────────────────────────────
    print(f"[canvas_to_zpl] Converting {len(elements_sorted)} element(s)...")
    for idx, d in enumerate(elements_sorted):
        kind    = d.get("type", "")
        visible = d.get("visible", True)

        print(f"\n  ── Element #{idx+1}: type={kind!r}, name={d.get('name','?')!r}, visible={visible} ──")

        if not visible:
            print(f"     SKIPPED (visible=False)")
            continue

        try:
            if kind == "text":
                zpl_elem = _convert_text(d, dpi)
                lines.append(zpl_elem)
            elif kind == "barcode":
                zpl_elem = _convert_barcode(d, dpi)
                lines.append(zpl_elem)
            elif kind == "line":
                zpl_elem = _convert_line(d, dpi)
                lines.append(zpl_elem)
            elif kind == "rect":
                zpl_elem = _convert_rect(d, dpi)
                lines.append(zpl_elem)
            else:
                print(f"     SKIPPED (unsupported type={kind!r})")
        except Exception as exc:
            print(f"     ERROR converting element: {exc}")
            lines.append(f"^FO0,0^A0N,20,20^FD[ZPL error in {kind}: {exc}]^FS")

    # ── Label end ─────────────────────────────────────────────────────────────
    lines.append("^XZ")

    zpl_output = "\n".join(lines)
    print(f"\n[canvas_to_zpl] DONE — ZPL output: {len(zpl_output)} chars, {zpl_output.count(chr(10))+1} lines")
    print("=" * 60)

    return zpl_output


def _apply_overrides(elements: list[dict], overrides: dict) -> list[dict]:
    """Return a new list with text overrides applied (non-mutating)."""
    result = []
    for elem in elements:
        if elem.get("type") == "text":
            name = elem.get("name", "")
            if name in overrides:
                elem = dict(elem)
                elem["text"] = str(overrides[name])
                print(f"  [OVERRIDE] {name!r} → {overrides[name]!r}")
        result.append(elem)
    return result


# ── Convenience: convert directly from BarcodeEditorPage ─────────────────────

def editor_to_zpl(editor_page, dpi: int = 203) -> str:
    """
    Shortcut that accepts a live BarcodeEditorPage instance.
    """
    print(f"[editor_to_zpl] editor_page._canvas_w={editor_page._canvas_w}, _canvas_h={editor_page._canvas_h}")
    print(f"[editor_to_zpl] design_name={editor_page._design_name!r}, dpi={dpi}")
    payload = editor_page.get_design_payload()
    return canvas_to_zpl(
        canvas_json=payload["usrm"],
        canvas_w=editor_page._canvas_w,
        canvas_h=editor_page._canvas_h,
        dpi=dpi,
        label_name=editor_page._design_name,
    )


# ── CLI quick-test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python zpl_converter.py <usrm.json> [dpi]")
        print("\nSample output for built-in test elements:")
        sample = [
            {"type": "text",    "aabb_x": 10,  "aabb_y": 10,  "text": "Hello ZPL",
             "font_size": 14, "font_family": "ARIAL", "rotation": 0, "visible": True,
             "design_inverse": False, "z": 0},
            {"type": "barcode", "aabb_x": 10,  "aabb_y": 50,
             "design": "CODE 128", "design_text": "123456789",
             "design_height_cm": 1.5, "design_magnification": "2",
             "design_interpretation": "BELOW BARCODE",
             "design_check_digit": "AUTO GENERATE",
             "rotation": 0, "visible": True, "z": 1},
            {"type": "line",    "aabb_x": 10,  "aabb_y": 120, "x2": 200, "y2": 120,
             "thickness": 2, "rotation": 0, "visible": True, "z": 2},
            {"type": "rect",    "aabb_x": 10,  "aabb_y": 140,
             "width": 200, "height": 60, "border_width": 3, "rotation": 0,
             "visible": True, "z": 3},
        ]
        print(canvas_to_zpl(sample, canvas_w=400, canvas_h=300, dpi=203))
        sys.exit(0)

    json_path = sys.argv[1]
    dpi_arg   = int(sys.argv[2]) if len(sys.argv) > 2 else 203

    with open(json_path) as f:
        raw = f.read().strip()
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed = json.loads(parsed.get("usrm", "[]"))

    result = canvas_to_zpl(parsed, dpi=dpi_arg)
    print(result)