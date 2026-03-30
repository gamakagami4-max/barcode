"""
zpl_converter.py
Converts BarcodeEditorPage serialized canvas (list[dict]) → ZPL II label string.

Key design decisions (matching original Delphi generator exactly):
  • Position uses RAW x,y  — NOT aabb_x/aabb_y
      dots = round(raw_x * 203/96)   [Delphi used literal 2.1, same ratio]
  • Font metrics come from barcodesap.mfonts keyed by mfsize (= font pt)
  • Text uses ^FT + ^A0{orient},{ax},{ay}^FH\^FD{text}^FS
  • Barcode uses ^BY{mag},{ratio},{height}^FT{x},{y}^BC{orient},,{interp},N
  • magnification passed as-is to ^BY (no clamping)
  • Barcode height: container_width for rot 90/270, container_height for 0/180

Usage:
    zpl = canvas_to_zpl(
        canvas_json=payload["usrm"],
        canvas_w=editor_page._canvas_w,
        canvas_h=editor_page._canvas_h,
        dpi=203,
        label_name=code,
        value_overrides=merged_values,
        print_qty=copies,
    )
"""

import json
import math

# ── Scale factor ──────────────────────────────────────────────────────────────
# 203 dots/inch ÷ 96 px/inch = 2.1146…  (Delphi used literal 2.1, same effect)
_DPI  = 203
_SDPI = 96   # screen/canvas DPI


def _d(px: float) -> int:
    """Convert screen pixels → printer dots at current DPI."""
    return max(0, int(round(px * _DPI / _SDPI)))


# ── ZPL barcode command map ───────────────────────────────────────────────────
_ZPL_BC: dict[str, str] = {
    "CODE 128":           "^BC", "CODE 128-A":         "^BC",
    "CODE 128-B":         "^BC", "CODE 128-C":         "^BC",
    "CODE128":            "^BC", "CODE128-A":          "^BC",
    "CODE128-B":          "^BC", "CODE128-C":          "^BC",
    "CODE 39":            "^B3", "CODE 93":            "^BA",
    "CODE 11":            "^B1", "EAN 13":             "^BE",
    "EAN 8":              "^B8", "UPC A":              "^BU",
    "INTERLEAVED 2 OF 5": "^BI", "QR (2D)":            "^BQ",
    "DATA MATRIX (2D)":   "^BX", "AZTEC (2D)":         "^BO",
}

_ORIENT: dict[int, str] = {0: "N", 90: "B", 180: "I", 270: "R"}


# ── mfonts table ─────────────────────────────────────────────────────────────
# (mfaxis, mfordi, mfdelx, mfdely)  ← from barcodesap.mfonts
_MFONTS_FALLBACK: dict[int, tuple[int,int,int,int]] = {
    2:  (6,   4,  2, 1),  3:  (8,   7,  2, 1),
    4:  (11,  12, 2, 2),  5:  (14,  14, 2, 2),
    6:  (17,  16, 2, 2),  7:  (20,  19, 2, 2),
    8:  (23,  24, 2, 3),  9:  (25,  24, 2, 3),
    10: (28,  28, 2, 3),  11: (31,  31, 2, 3),
    12: (34,  33, 2, 4),  13: (37,  36, 2, 5),
    14: (39,  38, 2, 5),  15: (42,  40, 2, 5),
    16: (45,  43, 2, 5),  18: (51,  48, 2, 6),
    20: (57,  54, 2, 7),  24: (68,  64, 2, 8),
    28: (79,  75, 2, 9),  32: (91,  86, 2,10),
    36: (102, 97, 2,12),  48: (136,129, 2,16),
    72: (204,193, 2,24),
}

_MFONTS_CACHE: dict[int, tuple[int,int,int,int]] | None = None


def _load_mfonts() -> dict[int, tuple[int,int,int,int]]:
    global _MFONTS_CACHE
    if _MFONTS_CACHE is not None:
        return _MFONTS_CACHE
    try:
        try:
            from server.db import get_connection
        except ImportError:
            from server.connection import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "SELECT mfsize, mfaxis, mfordi, mfdelx, mfdely "
            "FROM barcodesap.mfonts ORDER BY mfsize"
        )
        rows = cur.fetchall()
        cur.close()
        _MFONTS_CACHE = {
            int(r[0]): (int(r[1]), int(r[2]), int(r[3]), int(r[4]))
            for r in rows
        }
        print(f"[mfonts] Loaded {len(_MFONTS_CACHE)} rows from DB")
        return _MFONTS_CACHE
    except Exception as exc:
        print(f"[mfonts] DB unavailable ({exc}), using fallback table")
        _MFONTS_CACHE = dict(_MFONTS_FALLBACK)
        return _MFONTS_CACHE


def _font(pt: float) -> tuple[int,int,int,int]:
    """Return (mfaxis, mfordi, mfdelx, mfdely) for the given point size."""
    tbl  = _load_mfonts()
    size = int(round(pt))
    if size in tbl:
        return tbl[size]
    keys = sorted(tbl.keys())
    if not keys:
        v = max(10, int(round(pt * _DPI / 72)))
        return (v, v, 2, 2)
    nearest = min(keys, key=lambda k: abs(k - size))
    return tbl[nearest]


# ── Text ──────────────────────────────────────────────────────────────────────

def _convert_text(d: dict) -> str:
    """
    Delphi reference (uses raw Left/Top, NOT aabb):

    Angle 0:
      ^FT{round(Left*2.1)+MX},{round(Top*2.1)+AX-1}^A0N,AX,AY^FH\^FD{Caption}^FS

    Angle 90:
      ^FT{round(Left*2.1)+AX},{round(Top*2.1)+(round(Height*2.1))-MX}^A0B,AX,AY^FH\^FD{Caption}^FS

    Angle 180:
      ^FT{round(Left*2.1)+round(Width*2.1)},{round(Top*2.1)+(MY*2)}^A0I,AX,AY^FH\^FD{Caption}^FS

    Angle 270:
      ^FT{round(Left*2.1)+(MY*2)},{round(Top*2.1)+MY}^A0R,AX,AY^FH\^FD{Caption}^FS

    AX=mfaxis, AY=mfordi, MX=mfdelx, MY=mfdely
    """
    # ── Use RAW x,y (not aabb_x/aabb_y) ─────────────────────────────────────
    left   = float(d.get("x", 0))
    top    = float(d.get("y", 0))
    width  = float(d.get("width",  d.get("w", 50)))
    height = float(d.get("height", d.get("h", 20)))

    rotation = int(round(d.get("rotation", 0))) % 360
    pt       = float(d.get("font_size", 10))
    text     = str(d.get("text", ""))
    inverse  = bool(d.get("design_inverse", False) or d.get("inverse", False))
    do_trim  = bool(d.get("design_trim", False))

    if do_trim:
        text = text.strip()

    # In ^FH\ mode underscore introduces hex — encode literal _ as _5F
    text = text.replace("_", "_5F")

    ax, ay, MX, MY = _font(pt)

    left_d   = _d(left)
    top_d    = _d(top)
    width_d  = _d(width)
    height_d = _d(height)

    if rotation == 0:
        ft_x, ft_y, orient = left_d + MX,       top_d + ax - 1,      "N"
    elif rotation == 90:
        ft_x, ft_y, orient = left_d + ax,        top_d + height_d - MX, "B"
    elif rotation == 180:
        ft_x, ft_y, orient = left_d + width_d,   top_d + MY * 2,      "I"
    elif rotation == 270:
        ft_x, ft_y, orient = left_d + MY * 2,    top_d + MY,          "R"
    else:
        ft_x, ft_y, orient = left_d + MX,        top_d + ax - 1,      "N"

    print(f"    [TEXT] {d.get('name','?')!r:14s} rot={rotation}° "
          f"raw({left},{top}) → ^FT{ft_x},{ft_y} ^A0{orient},{ax},{ay}  {text!r}")

    parts = [f"^FT{ft_x},{ft_y}^A0{orient},{ax},{ay}^FH\\"]
    if inverse:
        parts.append("^FR")
    parts.append(f"^FD{text}^FS")
    return "".join(parts)


# ── Barcode ───────────────────────────────────────────────────────────────────

def _convert_barcode(d: dict) -> str:
    """
    Delphi reference (CODE128, angle 270 example):
      ^BY6,3,201^FT8,116^BCR,,N,N
      ^FD0123456789^FS

    Position: raw x,y (not aabb).
    Height:   container_width  when rot=90/270 (bar runs along canvas X axis)
              container_height when rot=0/180
    module_w: design_magnification passed as-is to ^BY (no clamping).
    """
    # ── RAW position ─────────────────────────────────────────────────────────
    left = float(d.get("x", 0))
    top  = float(d.get("y", 0))

    rotation = int(round(d.get("rotation", 0))) % 360
    orient   = _ORIENT.get(rotation, "N")
    design   = (d.get("design") or "CODE 128").upper()
    text     = str(d.get("design_text") or "")

    # module width — use raw magnification value (Delphi passes it straight)
    mag = d.get("design_magnification")
    try:
        module_w = max(1, int(mag))
    except (TypeError, ValueError):
        module_w = 2

    ratio = 3  # ZPL default wide-to-narrow ratio

    # ── Bar height ────────────────────────────────────────────────────────────
    # For a barcode rotated 90/270° the bars run along the canvas X axis,
    # so the "height" (length of bars) maps to container_width.
    height_dots_raw = d.get("design_height_dots")
    if height_dots_raw is not None:
        height_dots = max(10, int(height_dots_raw))
    elif rotation in (90, 270):
        cw = d.get("container_width")
        height_dots = max(10, _d(float(cw))) if cw is not None else 50
    else:
        ch = d.get("container_height")
        if ch is not None:
            height_dots = max(10, _d(float(ch)))
        else:
            height_cm   = float(d.get("design_height_cm") or 1.0)
            height_dots = max(10, int(round(height_cm / 2.54 * _DPI)))

    interp      = (d.get("design_interpretation") or "").upper()
    show_interp = "Y" if "BELOW" in interp else "N"

    check_raw   = (d.get("design_check_digit") or "").upper()
    check_digit = "Y" if "AUTO" in check_raw else "N"

    zpl_cmd = _ZPL_BC.get(design, _ZPL_BC.get(design.split("(")[0].strip(), "^BC"))
    is_2d   = any(t in design for t in ("QR", "DATA MATRIX", "AZTEC"))

    ft_x = _d(left)
    ft_y = _d(top)

    print(f"    [BARCODE] {d.get('name','?')!r:14s} rot={rotation}° "
          f"raw({left},{top}) → ^FT{ft_x},{ft_y}  "
          f"^BY{module_w},{ratio},{height_dots}  {zpl_cmd}{orient}  {text!r}")

    lines: list[str] = []
    if is_2d:
        lines.append(f"^FT{ft_x},{ft_y}")
        if "QR" in design:
            lines.append(f"^BQ{orient},2,{module_w}^FDQA,{text}^FS")
        elif "DATA MATRIX" in design:
            lines.append(f"^BX{orient},{height_dots},200^FD{text}^FS")
        elif "AZTEC" in design:
            lines.append(f"^BO{orient},{module_w}^FD{text}^FS")
    else:
        lines.append(f"^BY{module_w},{ratio},{height_dots}^FT{ft_x},{ft_y}")
        if zpl_cmd == "^BC":
            lines.append(f"^BC{orient},,{show_interp},N")
        elif zpl_cmd == "^B3":
            lines.append(f"^B3{orient},{check_digit},{height_dots},{show_interp},N")
        elif zpl_cmd == "^BE":
            lines.append(f"^BE{orient},{height_dots},{show_interp},N")
        elif zpl_cmd == "^B8":
            lines.append(f"^B8{orient},{height_dots},{show_interp},N")
        elif zpl_cmd == "^BU":
            lines.append(f"^BU{orient},{height_dots},{show_interp},N,N")
        else:
            lines.append(f"{zpl_cmd}{orient},{height_dots},{show_interp}")
        lines.append(f"^FD{text}^FS")

    return "\n".join(lines)


# ── Line ──────────────────────────────────────────────────────────────────────

def _convert_line(d: dict) -> str:
    x  = float(d.get("x", 0))
    y  = float(d.get("y", 0))
    x2 = float(d.get("x2", x + 100))
    y2 = float(d.get("y2", y))
    th = max(1, _d(float(d.get("thickness", 2))))
    dx = abs(x2 - x); dy = abs(y2 - y)
    if dy <= d.get("thickness", 2):
        w, h = max(th, _d(dx)), th
    elif dx <= d.get("thickness", 2):
        w, h = th, max(th, _d(dy))
    else:
        w, h = _d(math.hypot(dx, dy)), th
    fx, fy = _d(x), _d(y)
    print(f"    [LINE]    {d.get('name','?')!r:14s} ^FT{fx},{fy} ^GB{w},{h},{th}")
    return f"^FT{fx},{fy}^GB{w},{h},{th},B,0^FS"


# ── Rect ──────────────────────────────────────────────────────────────────────

def _convert_rect(d: dict) -> str:
    x  = float(d.get("x", 0))
    y  = float(d.get("y", 0))
    w  = max(1, _d(float(d.get("width",  100))))
    h  = max(1, _d(float(d.get("height",  50))))
    bw = max(1, _d(float(d.get("border_width", 2))))
    fx, fy = _d(x), _d(y)
    print(f"    [RECT]    {d.get('name','?')!r:14s} ^FT{fx},{fy} ^GB{w},{h},{bw}")
    return f"^FT{fx},{fy}^GB{w},{h},{bw},B,0^FS"


# ── Override helper ───────────────────────────────────────────────────────────

def _apply_overrides(elements: list[dict], overrides: dict) -> list[dict]:
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


# ── Main entry point ──────────────────────────────────────────────────────────

def canvas_to_zpl(
    canvas_json: "str | list",
    canvas_w: int = 600,
    canvas_h: int = 400,
    dpi: int = 203,
    label_name: str = "",
    value_overrides: "dict[str, str] | None" = None,
    print_speed: str = "B",
    print_qty: int = 1,
) -> str:
    """
    Convert a serialized canvas → ZPL II.

    Output format:
        ^XA^PRB^FS
        ^PW{canvas_w_dots}
        ^LH0,0
        ... elements (text/barcode/line/rect) ...
        ^PQ{qty},0,1,Y^XZ
        ^XZ
    """
    global _DPI, _SDPI
    _DPI = dpi  # allow 300 dpi override

    print("=" * 60)
    print(f"[canvas_to_zpl] canvas={canvas_w}×{canvas_h}px  dpi={dpi}  qty={print_qty}")
    if value_overrides:
        print(f"  overrides: {list(value_overrides.keys())}")
    print("=" * 60)

    if isinstance(canvas_json, str):
        elements: list[dict] = json.loads(canvas_json)
    else:
        elements = list(canvas_json)

    if value_overrides:
        elements = _apply_overrides(elements, value_overrides)

    elements_sorted = sorted(elements, key=lambda e: float(e.get("z", 0)))

    pw = _d(canvas_w)
    lines: list[str] = [
        f"^XA^PR{print_speed}^FS",
        f"^PW{pw}",
        "^LH0,0",
    ]
    if label_name:
        lines.append(f"^FX {label_name.replace('^','').replace('~','')}")

    for idx, d in enumerate(elements_sorted):
        kind    = d.get("type", "")
        visible = d.get("visible", True)

        print(f"\n  #{idx+1} {kind!r:8s} {d.get('name','?')!r:14s}  visible={visible}")

        if not visible:
            print("    SKIPPED")
            continue

        try:
            if kind == "text":
                lines.append(_convert_text(d))
            elif kind == "barcode":
                lines.append(_convert_barcode(d))
            elif kind == "line":
                lines.append(_convert_line(d))
            elif kind == "rect":
                lines.append(_convert_rect(d))
            else:
                print(f"    SKIPPED (unsupported type)")
        except Exception as exc:
            import traceback
            traceback.print_exc()
            lines.append(f"^FT0,20^A0N,20,20^FD[ZPL err {kind}: {exc}]^FS")

    lines.append(f"^PQ{print_qty},0,1,Y^XZ")
    lines.append("^XZ")

    zpl = "\n".join(lines)
    print(f"\n[canvas_to_zpl] DONE — {len(zpl)} chars")
    return zpl


# ── Convenience wrapper ───────────────────────────────────────────────────────

def editor_to_zpl(editor_page, dpi: int = 203) -> str:
    payload = editor_page.get_design_payload()
    return canvas_to_zpl(
        canvas_json=payload["usrm"],
        canvas_w=editor_page._canvas_w,
        canvas_h=editor_page._canvas_h,
        dpi=dpi,
        label_name=editor_page._design_name,
    )


# ── CLI / self-test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 2 and sys.argv[1] != "--test":
        json_path = sys.argv[1]
        dpi_arg   = int(sys.argv[2]) if len(sys.argv) > 2 else 203
        qty_arg   = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        with open(json_path) as f:
            raw = f.read().strip()
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                parsed = json.loads(parsed.get("usrm", "[]"))
        print(canvas_to_zpl(parsed, dpi=dpi_arg, print_qty=qty_arg))
        sys.exit(0)

    # Built-in self-test using the BC0002 sample data
    print("Self-test with BC0002 sample data:")
    sample = json.loads('[{"x":-6.0,"y":87.0,"z":12.0,"visible":true,"rotation":270.0,"name":"Label2","aabb_x":5.0,"aabb_y":76.0,"type":"text","text":"C-1105","font_size":8,"font_family":"Arial","design_trim":true},{"x":1.0,"y":45.0,"z":7.0,"visible":true,"rotation":0.0,"name":"Label7","aabb_x":1.0,"aabb_y":45.0,"type":"text","text":"22AMN","font_size":10,"font_family":"Arial"},{"x":134.0,"y":129.0,"z":5.0,"visible":true,"rotation":270.0,"name":"Label11","aabb_x":138.0,"aabb_y":125.0,"type":"text","text":"AGT","font_size":7,"font_family":"Arial","design_trim":true},{"x":117.0,"y":38.0,"z":4.0,"visible":true,"rotation":270.0,"name":"Label12","aabb_x":138.0,"aabb_y":17.0,"type":"text","text":"10:06:27 AM","font_size":7,"font_family":"Arial"},{"x":107.5,"y":88.5,"z":3.0,"visible":true,"rotation":270.0,"name":"Label13","aabb_x":118.0,"aabb_y":78.0,"type":"text","text":"kodeSAP","font_size":6,"font_family":"Arial","design_trim":true},{"x":-23.5,"y":82.5,"z":1.0,"visible":true,"rotation":270.0,"name":"Barcode2","aabb_x":4.0,"aabb_y":55.0,"type":"barcode","design":"CODE128","container_width":95,"container_height":40,"design_magnification":"6","design_interpretation":"NO INTERPRETATION","design_text":"0123456789"}]')
    result = canvas_to_zpl(sample, canvas_w=152, canvas_h=170, dpi=203, label_name="BC0002", print_qty=1)
    print("\n" + "="*60)
    print("EXPECTED (from Delphi reference):")
    print("^BY6,3,201^FT0,175^BCR,,N,N^FD0123456789^FS")
    print("^FT232,189^A0R,17,16^FH\\^FDkodeSAP^FS")
    print("^FT252,82^A0R,20,19^FH\\^FD10:06:27 AM^FS")
    print("^FT4,122^A0N,28,28^FH\\^FD22AMN^FS")
    print("^FT288,275^A0R,20,19^FH\\^FDAGT^FS")
    print("^FT6,187^A0R,23,24^FH\\^FDC-1105^FS")
    print("="*60)
    print("\nACTUAL:")
    print(result)