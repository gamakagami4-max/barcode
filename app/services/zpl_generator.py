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

# ZPL orientation map: rotation degrees → ZPL orientation letter
_ORIENT: dict[int, str] = {0: "N", 90: "R", 180: "I", 270: "B"}

# ZPL font map: font-name → ZPL font letter / number
_ZPL_FONT: dict[str, str] = {
    "STANDARD":            "0",
    "ARIAL":               "0",
    "ARIAL BOLD":          "0",
    "ARIAL BLACK":         "0",
    "ARIAL BLACK (GT)":    "0",
    "ARIAL BLACK NEW":     "0",
    "ARIAL NARROW BOLD":   "0",
    "OCR-B":               "B",   # ZPL built-in OCR-B
    "TAHOMA":              "0",
    # Add custom downloaded fonts here, e.g.:
    # "MONTSERRAT BOLD": "R",
}

# Canvas is designed at 96 dpi (screen pixels).
# Dots = px * (printer_dpi / 96)
_CANVAS_DPI = 96


def _px_to_dots(px: float, dpi: int = 203) -> int:
    """Convert canvas pixels (96 dpi) to ZPL printer dots."""
    return max(1, int(round(px * dpi / _CANVAS_DPI)))


def _rotation_to_orient(rotation: float) -> str:
    """Map item rotation (Qt degrees) to ZPL orientation letter."""
    r = int(round(rotation)) % 360
    return _ORIENT.get(r, "N")


def _field_origin(x: float, y: float, dpi: int) -> str:
    return f"^FO{_px_to_dots(x, dpi)},{_px_to_dots(y, dpi)}"


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

    # Font height in dots: pt → inches → dots  (1 pt = 1/72 inch)
    dot_h = max(10, _px_to_dots(font_size * 96 / 72, dpi))
    dot_w = dot_h  # square cell (width = height is ZPL default)

    inverse = d.get("design_inverse", False) or d.get("inverse", False)
    text    = d.get("text", "")

    # Escape caret and tilde which are ZPL control chars
    text = text.replace("^", "\\^").replace("~", "\\~")

    lines: list[str] = [
        _field_origin(x, y, dpi),
        f"^A{zpl_font}{orient},{dot_h},{dot_w}",
    ]
    if inverse:
        lines.append("^FR")   # field reverse (white on black) — must precede ^FD
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

    # Height: prefer explicit height in dots; fall back to cm → dots
    height_dots_raw = d.get("design_height_dots")
    if height_dots_raw is not None:
        height_dots = max(10, int(height_dots_raw))
    else:
        height_cm = float(d.get("design_height_cm") or 1.0)
        height_dots = max(10, int(round(height_cm / 2.54 * dpi)))

    # Module width (narrow bar width in dots, 1–10)
    mag = d.get("design_magnification")
    try:
        module_w = max(1, min(10, int(mag)))
    except (TypeError, ValueError):
        module_w = 2

    # Interpretation line
    interp = (d.get("design_interpretation") or "").upper()
    show_interp = "Y" if "BELOW" in interp else "N"

    # Check digit
    check_digit_raw = (d.get("design_check_digit") or "").upper()
    check_digit = "Y" if "AUTO" in check_digit_raw else "N"

    zpl_cmd = _ZPL_BARCODE_CMD.get(
        design,
        _ZPL_BARCODE_CMD.get(design.split("(")[0].strip(), "^BC"),
    )

    lines: list[str] = [_field_origin(x, y, dpi)]

    is_2d = any(tok in design for tok in ("QR", "DATA MATRIX", "AZTEC"))

    if is_2d:
        if "QR" in design:
            # ^BQ o, model, magnification, error_correction, mask
            lines.append(f"^BQ{orient},2,{module_w}")
            lines.append(f"^FDQA,{text}^FS")
        elif "DATA MATRIX" in design:
            # ^BX o, h, quality, columns, rows, format, escape
            lines.append(f"^BX{orient},{height_dots},200")
            lines.append(f"^FD{text}^FS")
        elif "AZTEC" in design:
            # ^BO o, magnification, ECIValue
            lines.append(f"^BO{orient},{module_w}")
            lines.append(f"^FD{text}^FS")
    else:
        # ── Linear barcodes ────────────────────────────────────────────────
        # ZPL ^BC  (Code 128): o, h, f, g, e
        #   o=orientation  h=height  f=print_interp  g=UCC  e=mode(N/A/D/U/A/B/C)
        if zpl_cmd == "^BC":
            lines.append(f"^BC{orient},{height_dots},{show_interp},N,N")

        # ZPL ^B3  (Code 39): o, e, h, f, g
        #   o=orientation  e=check_digit  h=height  f=print_interp  g=print_start_stop
        elif zpl_cmd == "^B3":
            lines.append(f"^B3{orient},{check_digit},{height_dots},{show_interp},N")

        # ZPL ^BA  (Code 93): o, h, f, g, e
        elif zpl_cmd == "^BA":
            lines.append(f"^BA{orient},{height_dots},{show_interp},N")

        # ZPL ^B1  (Code 11): o, h, f, g
        elif zpl_cmd == "^B1":
            lines.append(f"^B1{orient},{height_dots},{show_interp},N")

        # ZPL ^BE  (EAN-13): o, h, f, g
        elif zpl_cmd == "^BE":
            lines.append(f"^BE{orient},{height_dots},{show_interp},N")

        # ZPL ^B8  (EAN-8): o, h, f, g
        elif zpl_cmd == "^B8":
            lines.append(f"^B8{orient},{height_dots},{show_interp},N")

        # ZPL ^BU  (UPC-A): o, h, f, g, e
        elif zpl_cmd == "^BU":
            lines.append(f"^BU{orient},{height_dots},{show_interp},N,N")

        # ZPL ^BI  (I2of5): o, h, f, g
        #   o=orientation  h=height  f=print_interp  g=print_start_stop
        #   NOTE: check digit is NOT a parameter of ^BI — use ^B2 for that variant
        elif zpl_cmd == "^BI":
            lines.append(f"^BI{orient},{height_dots},{show_interp},N")

        else:
            # Generic fallback — orientation, height, interp
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
        # Horizontal line
        w = max(thickness, _px_to_dots(dx, dpi))
        h = thickness
    elif dx <= d.get("thickness", 2):
        # Vertical line
        w = thickness
        h = max(thickness, _px_to_dots(dy, dpi))
    else:
        # Diagonal — project onto longer axis
        length = _px_to_dots(math.hypot(dx, dy), dpi)
        w = length; h = thickness

    # ^GB width, height, border_thickness, color (B=black), corner_rounding
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

    # ^GB width, height, border_thickness, color, corner_rounding
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

    Args:
        canvas_json:      The "usrm" value from get_design_payload(), or a parsed list.
        canvas_w:         Canvas width in pixels (from _canvas_w).
        canvas_h:         Canvas height in pixels (from _canvas_h).
        dpi:              Printer DPI — 203 (standard) or 300 (high-res).
        label_name:       Optional label identifier (used for ^XA comment).
        value_overrides:  dict of {element_name: text} — overrides the static
                          "text" field in matching elements before ZPL conversion.
                          Use this to bake in live field values from BarcodePrintPage.

    Returns:
        A complete ZPL II string ready to send to a Zebra printer.
    """
    if isinstance(canvas_json, str):
        elements: list[dict] = json.loads(canvas_json)
    else:
        elements = list(canvas_json)

    # Apply live value overrides (from the print-fields panel)
    if value_overrides:
        for elem in elements:
            if elem.get("type") == "text":
                name = elem.get("name", "")
                if name in value_overrides:
                    elem = dict(elem)           # shallow copy — don't mutate original
                    elem["text"] = value_overrides[name]
            # Re-assign back into the list by index to keep the copy
        elements = _apply_overrides(elements, value_overrides)

    # Sort by z-value ascending so lower layers print first
    elements_sorted = sorted(elements, key=lambda d: float(d.get("z", 0)))

    lines: list[str] = []

    # ── Label start ───────────────────────────────────────────────────────────
    lines.append("^XA")
    lines.append("^CI28")          # UTF-8 character encoding
    lines.append("^LH0,0")         # label home — top-left origin

    # Label length in dots (continuous media height)
    lines.append(f"^LL{_px_to_dots(canvas_h, dpi)}")
    # Print width in dots
    lines.append(f"^PW{_px_to_dots(canvas_w, dpi)}")

    if label_name:
        # Embed label name as a ZPL comment (^FX)
        safe_name = label_name.replace("^", "").replace("~", "")
        lines.append(f"^FX Label: {safe_name}")

    # ── Elements ──────────────────────────────────────────────────────────────
    for d in elements_sorted:
        kind    = d.get("type", "")
        visible = d.get("visible", True)

        if not visible:
            continue

        try:
            if kind == "text":
                lines.append(_convert_text(d, dpi))
            elif kind == "barcode":
                lines.append(_convert_barcode(d, dpi))
            elif kind == "line":
                lines.append(_convert_line(d, dpi))
            elif kind == "rect":
                lines.append(_convert_rect(d, dpi))
            # image / unknown types are silently skipped
        except Exception as exc:
            lines.append(f"^FO0,0^A0N,20,20^FD[ZPL error in {kind}: {exc}]^FS")

    # ── Label end ─────────────────────────────────────────────────────────────
    lines.append("^XZ")

    return "\n".join(lines)


def _apply_overrides(elements: list[dict], overrides: dict) -> list[dict]:
    """Return a new list with text overrides applied (non-mutating)."""
    result = []
    for elem in elements:
        if elem.get("type") == "text":
            name = elem.get("name", "")
            if name in overrides:
                elem = dict(elem)
                elem["text"] = str(overrides[name])
        result.append(elem)
    return result


# ── Convenience: convert directly from BarcodeEditorPage ─────────────────────

def editor_to_zpl(editor_page, dpi: int = 203) -> str:
    """
    Shortcut that accepts a live BarcodeEditorPage instance.

    Example:
        zpl = editor_to_zpl(my_editor_page, dpi=300)
        with open("label.zpl", "w") as f:
            f.write(zpl)
    """
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