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
# Maps your design combo values → (ZPL ^B command, orientation-aware)
_ZPL_BARCODE_CMD: dict[str, str] = {
    "CODE 128":             "^BC",   # Code 128 auto subset
    "CODE 128-A":           "^BC",
    "CODE 128-B":           "^BC",
    "CODE 128-C":           "^BC",
    "CODE 39":              "^B3",
    "CODE 93":              "^BA",
    "CODE 11":              "^B1",
    "EAN 13":               "^BE",
    "EAN 8":                "^B8",
    "UPC A":                "^BU",
    "INTERLEAVED 2 OF 5":  "^BI",
    "QR (2D)":              "^BQ",
    "DATA MATRIX (2D)":    "^BX",
    "AZTEC (2D)":           "^BO",
}

# ZPL orientation map: your display degrees → ZPL orientation letter
_ORIENT: dict[int, str] = {0: "N", 90: "R", 180: "I", 270: "B"}

# ZPL font map: your font-name combo → ZPL font letter / number
_ZPL_FONT: dict[str, str] = {
    "STANDARD":             "0",
    "ARIAL":                "0",
    "ARIAL BOLD":           "0",
    "ARIAL BLACK":          "0",
    "ARIAL BLACK (GT)":     "0",
    "ARIAL BLACK NEW":      "0",
    "ARIAL NARROW BOLD":    "0",
    "OCR-B":                "B",   # ZPL built-in OCR-B
    "TAHOMA":               "0",
    # Add custom downloaded fonts here, e.g.:
    # "MONTSERRAT BOLD": "R",
}


def _px_to_dots(px: float, dpi: int = 203) -> int:
    """Convert canvas pixels to ZPL dots. Assumes canvas uses 1 px ≈ 1 dot at 203 dpi."""
    return int(round(px))


def _rotation_to_orient(rotation: float) -> str:
    """Map item rotation (Qt degrees) to ZPL orientation letter."""
    r = int(round(rotation)) % 360
    return _ORIENT.get(r, "N")


def _field_origin(x: float, y: float, dpi: int) -> str:
    return f"^FO{_px_to_dots(x, dpi)},{_px_to_dots(y, dpi)}"


# ── Individual element converters ─────────────────────────────────────────────

def _convert_text(d: dict, dpi: int) -> str:
    """Convert a text element to ZPL."""
    lines: list[str] = []

    x = d.get("aabb_x", d.get("x", 0))
    y = d.get("aabb_y", d.get("y", 0))
    rotation = int(round(d.get("rotation", 0))) % 360
    orient = _ORIENT.get(rotation, "N")

    font_name = d.get("font_family", "STANDARD")
    zpl_font  = _ZPL_FONT.get(font_name.upper(), "0")
    font_size = int(d.get("font_size", 10))
    # ZPL font height in dots: rough mapping from pt → dots
    # 72 pt = 1 inch; dots_per_inch / 72 * pt_size
    dot_h = max(10, int(round(font_size * dpi / 72)))
    dot_w = dot_h  # square cell by default

    inverse = d.get("design_inverse", False) or d.get("inverse", False)
    text    = d.get("text", "")

    lines.append(_field_origin(x, y, dpi))
    lines.append(f"^A{zpl_font}{orient},{dot_h},{dot_w}")

    if inverse:
        lines.append(f"^FR")   # field reverse (white on black)

    lines.append(f"^FD{text}^FS")
    return "\n".join(lines)


def _convert_barcode(d: dict, dpi: int) -> str:
    """Convert a barcode element to ZPL."""
    lines: list[str] = []

    x = d.get("aabb_x", d.get("x", 0))
    y = d.get("aabb_y", d.get("y", 0))
    rotation = int(round(d.get("rotation", 0))) % 360
    orient   = _ORIENT.get(rotation, "N")

    design   = (d.get("design") or "CODE 128").upper()
    text     = d.get("design_text", "") or ""
    height_cm: float = float(d.get("design_height_cm") or 1.0)
    height_dots = int(round(height_cm / 2.54 * dpi))  # cm → inches → dots

    # Magnification → module width in dots (1..10 → 1..10)
    mag = d.get("design_magnification")
    try:
        module_w = max(1, int(mag))
    except (TypeError, ValueError):
        module_w = 2

    # Interpretation line (human-readable text below barcode)
    interp = (d.get("design_interpretation") or "NO INTERPRETATION").upper()
    show_interp = "Y" if "BELOW" in interp else "N"

    # Check digit
    check_digit_raw = (d.get("design_check_digit") or "").upper()
    check_digit = "Y" if "AUTO" in check_digit_raw else "N"

    zpl_cmd = _ZPL_BARCODE_CMD.get(
        design,
        _ZPL_BARCODE_CMD.get(design.split("(")[0].strip(), "^BC")
    )

    lines.append(_field_origin(x, y, dpi))

    is_2d = any(tok in design for tok in ("QR", "DATA MATRIX", "AZTEC"))

    if is_2d:
        if "QR" in design:
            # ^BQ orientation, model, magnification
            lines.append(f"^BQ{orient},2,{module_w}")
            lines.append(f"^FDQA,{text}^FS")
        elif "DATA MATRIX" in design:
            lines.append(f"^BX{orient},{module_w}")
            lines.append(f"^FD{text}^FS")
        elif "AZTEC" in design:
            lines.append(f"^BO{orient},{module_w}")
            lines.append(f"^FD{text}^FS")
    else:
        # Linear barcodes: ^Bx orientation, height, interp, check_digit
        if zpl_cmd in ("^BC",):
            # CODE 128: ^BC orientation, height, print interp, check digit N/A
            lines.append(f"^BC{orient},{height_dots},{show_interp},N,N")
        elif zpl_cmd == "^B3":
            # CODE 39
            lines.append(f"^B3{orient},{check_digit},{height_dots},{show_interp},N")
        elif zpl_cmd in ("^BE", "^B8", "^BU"):
            # EAN / UPC
            lines.append(f"{zpl_cmd}{orient},{height_dots},{show_interp}")
        elif zpl_cmd == "^BI":
            # Interleaved 2 of 5
            lines.append(f"^BI{orient},{height_dots},{show_interp},{check_digit}")
        else:
            lines.append(f"{zpl_cmd}{orient},{height_dots},{show_interp},{check_digit}")
        lines.append(f"^FD{text}^FS")

    return "\n".join(lines)


def _convert_line(d: dict, dpi: int) -> str:
    """Convert a line element to ZPL using ^GB (Graphic Box as a thin box)."""
    x = d.get("aabb_x", d.get("x", 0))
    y = d.get("aabb_y", d.get("y", 0))
    x2 = float(d.get("x2", x + 100))
    y2 = float(d.get("y2", y))
    thickness = max(1, int(d.get("thickness", 2)))

    # Determine line direction
    dx = abs(x2 - x)
    dy = abs(y2 - y)

    if dy <= thickness:
        # Horizontal line → GB with height = thickness
        w = max(1, int(round(dx)))
        h = thickness
    elif dx <= thickness:
        # Vertical line → GB with width = thickness
        w = thickness
        h = max(1, int(round(dy)))
    else:
        # Diagonal — ZPL doesn't support diagonals natively; render as horizontal projection
        w = max(1, int(round(math.hypot(dx, dy))))
        h = thickness

    return (
        f"{_field_origin(x, y, dpi)}\n"
        f"^GB{w},{h},{thickness}^FS"
    )


def _convert_rect(d: dict, dpi: int) -> str:
    """Convert a rectangle element to ZPL using ^GB."""
    x = d.get("aabb_x", d.get("x", 0))
    y = d.get("aabb_y", d.get("y", 0))
    w = max(1, int(round(float(d.get("width",  100)))))
    h = max(1, int(round(float(d.get("height",  50)))))
    border = max(0, int(d.get("border_width", 2)))

    # ^GB width, height, border_thickness, color, corner_rounding
    return (
        f"{_field_origin(x, y, dpi)}\n"
        f"^GB{w},{h},{border}^FS"
    )


# ── Main converter ────────────────────────────────────────────────────────────

def canvas_to_zpl(
    canvas_json: str | list,
    canvas_w: int = 600,
    canvas_h: int = 400,
    dpi: int = 203,
    label_name: str = "",
) -> str:
    """
    Convert a serialized canvas (JSON string or already-parsed list) to a ZPL string.

    Args:
        canvas_json:  The "usrm" value from get_design_payload(), or an already-parsed list.
        canvas_w:     Canvas width in pixels (from _canvas_w).
        canvas_h:     Canvas height in pixels (from _canvas_h).
        dpi:          Printer DPI — 203 (standard) or 300 (high-res).
        label_name:   Optional label identifier (inserted as a comment).

    Returns:
        A complete ZPL II string ready to send to a Zebra printer.
    """
    if isinstance(canvas_json, str):
        elements: list[dict] = json.loads(canvas_json)
    else:
        elements = list(canvas_json)

    # Sort by z-value ascending so lower layers print first
    elements_sorted = sorted(elements, key=lambda d: float(d.get("z", 0)))

    lines: list[str] = []

    # ── Label start ───────────────────────────────────────────────────────────
    lines.append("^XA")

    if label_name:
        lines.append(f"^CI28")          # UTF-8 character set
        lines.append(f"^LH0,0")         # label home origin

    # Label dimensions: ^LL (label length in dots) — for continuous media
    label_length_dots = _px_to_dots(canvas_h, dpi)
    lines.append(f"^LL{label_length_dots}")

    # Print width
    label_width_dots = _px_to_dots(canvas_w, dpi)
    lines.append(f"^PW{label_width_dots}")

    # ── Elements ──────────────────────────────────────────────────────────────
    for d in elements_sorted:
        kind    = d.get("type", "")
        visible = d.get("visible", True)

        if not visible:
            continue  # hidden elements are skipped

        try:
            if kind == "text":
                lines.append(_convert_text(d, dpi))
            elif kind == "barcode":
                lines.append(_convert_barcode(d, dpi))
            elif kind == "line":
                lines.append(_convert_line(d, dpi))
            elif kind == "rect":
                lines.append(_convert_rect(d, dpi))
            else:
                lines.append(f"^FO0,0^FD[unknown type: {kind}]^FS")
        except Exception as exc:
            lines.append(f"^FO0,0^FD[ZPL error in {kind}: {exc}]^FS")

    # ── Label end ─────────────────────────────────────────────────────────────
    lines.append("^XZ")

    return "\n".join(lines)


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
        print("\nExample JSON (usrm) content:")
        sample = [
            {"type": "text",    "aabb_x": 10,  "aabb_y": 10,  "text": "Hello ZPL",
             "font_size": 14, "font_family": "ARIAL", "rotation": 0, "visible": True,
             "design_inverse": False},
            {"type": "barcode", "aabb_x": 10,  "aabb_y": 50,
             "design": "CODE 128", "design_text": "123456789",
             "design_height_cm": 1.5, "design_magnification": "2",
             "design_interpretation": "BELOW BARCODE",
             "design_check_digit": "AUTO GENERATE",
             "rotation": 0, "visible": True},
            {"type": "line",    "aabb_x": 10,  "aabb_y": 120, "x2": 300, "y2": 0,
             "thickness": 2, "rotation": 0, "visible": True},
            {"type": "rect",    "aabb_x": 10,  "aabb_y": 140,
             "width": 200, "height": 60, "border_width": 3, "rotation": 0, "visible": True},
        ]
        print(canvas_to_zpl(sample, canvas_w=400, canvas_h=300, dpi=203))
        sys.exit(0)

    json_path = sys.argv[1]
    dpi_arg   = int(sys.argv[2]) if len(sys.argv) > 2 else 203

    with open(json_path) as f:
        raw = f.read().strip()
        # Accept either a bare list or {"usrm": "..."}
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed = json.loads(parsed.get("usrm", "[]"))

    result = canvas_to_zpl(parsed, dpi=dpi_arg)
    print(result)