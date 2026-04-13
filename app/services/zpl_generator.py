r"""
zpl_converter.py
Converts BarcodeEditorPage serialized canvas (list[dict]) → ZPL II label string.

KEY FIX 1: Use aabb_x / aabb_y (the visual bounding-box top-left) as Left/Top
for ALL position calculations — both text and barcode elements.

KEY FIX 2: Canvas rotation is COUNTER-CLOCKWISE; ZPL/Delphi rotation is CLOCKWISE.
Convert: zpl_angle = (360 - ccw_angle) % 360
  Canvas CCW 90°  → ZPL CW 270° → ^A0R  (text reads bottom-to-top, left side)
  Canvas CCW 270° → ZPL CW  90° → ^A0B  (text reads top-to-bottom, right side)
  Canvas CCW 180° → ZPL CW 180° → ^A0I
  Canvas CCW   0° → ZPL CW   0° → ^A0N

KEY FIX 3: _resolve_same_with now searches by component_id (design_same_with
stores a UUID) AND by name as a fallback. The old code only searched by name
so all SAME WITH references were silently missed.

KEY FIX 4: _apply_overrides runs BEFORE _resolve_same_with so that overridden
values from barcode_print.py (LINK / BATCH NO / freetext fields) propagate
correctly into SAME WITH targets.

KEY FIX 5: Invisible elements are still included in the SAME WITH lookup maps
so that hidden source elements can still feed their value to visible targets.

KEY FIX 6: MERGE type elements now evaluate their design_merge template using
actual sibling element values, matching the canvas preview behaviour.

KEY FIX 7: The value used for ZPL is determined by a priority chain:
  value_overrides → design_merge evaluation → element["text"]
  This ensures FIX/INPUT/LINK/BATCH_NO all emit the right text.
"""

from __future__ import annotations
import json
import math
import re

# ── Scale factor ──────────────────────────────────────────────────────────────
_SCALE = 2.1


def _r(px: float) -> int:
    """round(px * 2.1) — commercial rounding to match Delphi."""
    return int(math.floor(px * _SCALE + 0.5))


def _px_to_dots(px: float, dpi: int = 203) -> int:
    """For margin-offset calls from barcode_print.py (API compatibility)."""
    return _r(px)


def _ccw_to_cw(ccw: float) -> int:
    """
    Convert canvas counter-clockwise angle → ZPL clockwise angle.
    The canvas stores rotation CCW (Qt convention).
    ZPL / Delphi uses CW.  Snapped to nearest 90°.
      CCW   0 → CW   0  (^A0N)
      CCW  90 → CW 270  (^A0R)  ← text on left, reading bottom-to-top
      CCW 180 → CW 180  (^A0I)
      CCW 270 → CW  90  (^A0B)  ← text on right, reading top-to-bottom
    """
    snapped = int(round(ccw / 90.0)) * 90 % 360
    return (360 - snapped) % 360


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
_MFONTS_FALLBACK: dict[int, tuple[int, int, int, int, int, int]] = {
    2:  (6,   4,  2, 1, 0, 0),
    3:  (8,   7,  2, 1, 0, 0),
    4:  (11,  12, 2, 2, 0, 0),
    5:  (14,  14, 2, 2, 0, 0),
    6:  (17,  16, 2, 2, 0, 0),
    7:  (20,  19, 2, 2, 0, 0),
    8:  (23,  24, 2, 3, 0, 0),
    9:  (25,  24, 2, 3, 0, 0),
    10: (28,  28, 2, 3, 0, 0),
    11: (31,  31, 2, 3, 0, 0),
    12: (34,  33, 2, 4, 0, 0),
    13: (37,  36, 2, 5, 0, 0),
    14: (39,  38, 2, 5, 0, 0),
    15: (42,  40, 2, 5, 0, 0),
    16: (45,  43, 2, 5, 0, 0),
    18: (51,  48, 2, 6, 0, 0),
    20: (57,  54, 2, 7, 0, 0),
    24: (68,  64, 2, 8, 0, 0),
    28: (79,  75, 2, 9, 0, 0),
    32: (91,  86, 2, 10, 0, 0),
    36: (102, 97, 2, 12, 0, 0),
    48: (136, 129, 2, 16, 0, 0),
    72: (204, 193, 2, 24, 0, 0),
}

_MFONTS_CACHE: dict[int, tuple[int, int, int, int, int, int]] | None = None


def _load_mfonts() -> dict[int, tuple[int, int, int, int, int, int]]:
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
            "SELECT mfsize, mfaxis, mfordi, mfdelx, mfdely, "
            "       COALESCE(mfrecx, 0), COALESCE(mfrecy, 0) "
            "FROM barcodesap.mfonts ORDER BY mfsize"
        )
        rows = cur.fetchall()
        cur.close()
        _MFONTS_CACHE = {
            int(r[0]): (int(r[1]), int(r[2]), int(r[3]), int(r[4]),
                        int(r[5]), int(r[6]))
            for r in rows
        }
        print(f"[mfonts] Loaded {len(_MFONTS_CACHE)} rows from DB")
        return _MFONTS_CACHE
    except Exception as exc:
        print(f"[mfonts] DB unavailable ({exc}), using fallback table")
        _MFONTS_CACHE = dict(_MFONTS_FALLBACK)
        return _MFONTS_CACHE


def _font(pt: float) -> tuple[int, int, int, int, int, int]:
    tbl  = _load_mfonts()
    size = int(round(pt))
    if size in tbl:
        return tbl[size]
    keys = sorted(tbl.keys())
    if not keys:
        v = max(10, int(round(pt * 203 / 72)))
        return (v, v, 2, 2, 0, 0)
    nearest = min(keys, key=lambda k: abs(k - size))
    return tbl[nearest]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _aabb_pos(d: dict) -> tuple[float, float]:
    """
    Return the AABB top-left (Left, Top) for an element.

    Priority:
      1. aabb_x / aabb_y  — set by the editor for ALL elements (rotated or not)
      2. x / y            — fallback for axis-aligned elements where aabb == origin
    """
    aabb_x = d.get("aabb_x")
    aabb_y = d.get("aabb_y")
    if aabb_x is not None and aabb_y is not None:
        return float(aabb_x), float(aabb_y)
    return float(d.get("x", 0)), float(d.get("y", 0))


def _natural_size(d: dict) -> tuple[float, float]:
    """
    Return the element's NATURAL (unrotated) width and height.
    """
    rotation = _ccw_to_cw(float(d.get("rotation", 0)))
    w = float(d.get("width",  d.get("w", 50)))
    h = float(d.get("height", d.get("h", 20)))

    if rotation in (90, 270):
        aabb_w = float(d.get("aabb_w", 0) or 0)
        aabb_h = float(d.get("aabb_h", 0) or 0)
        if aabb_w > 0 and aabb_h > 0:
            return aabb_h, aabb_w
        return h, w

    return w, h


# ── Text ──────────────────────────────────────────────────────────────────────

def _convert_text(d: dict) -> str:
    r"""
    Delphi formulae — Left/Top are sourced from aabb_x/aabb_y.

    Angle 0:
      ^FT{round(Left*2.1)+MX},{round(Top*2.1)+AX-1}^A0N,AX,AY^FH\^FD{Caption}^FS

    Angle 90:
      ^FT{round(Left*2.1)+AX},{round(Top*2.1)+round(Height*2.1)-MX}^A0B,AX,AY^FH\^FD{Caption}^FS

    Angle 180:
      ^FT{round(Left*2.1)+round(Width*2.1)},{round(Top*2.1)+MY*2}^A0I,AX,AY^FH\^FD{Caption}^FS

    Angle 270:
      ^FT{round(Left*2.1)+MY*2},{round(Top*2.1)+MY}^A0R,AX,AY^FH\^FD{Caption}^FS
    """  # noqa: W605
    Left, Top     = _aabb_pos(d)
    Width, Height = _natural_size(d)

    rotation = _ccw_to_cw(float(d.get("rotation", 0)))
    pt       = float(d.get("font_size", 10))
    caption  = str(d.get("text", ""))
    do_trim  = bool(d.get("design_trim", False))
    inverse  = bool(d.get("design_inverse", False) or d.get("inverse", False))

    if do_trim:
        caption = caption.strip()

    caption = caption.replace("_", "_5F")

    AX, AY, MX, MY, _DX, _DY = _font(pt)

    rLeft   = _r(Left)
    rTop    = _r(Top)
    rWidth  = _r(Width)
    rHeight = _r(Height)

    if rotation == 0:
        ft_x   = rLeft + MX
        ft_y   = rTop  + AX - 1
        orient = "N"
    elif rotation == 90:
        ft_x   = rLeft + AX
        ft_y   = rTop  + rHeight - MX
        orient = "B"
    elif rotation == 180:
        ft_x   = rLeft + rWidth
        ft_y   = rTop  + MY * 2
        orient = "I"
    elif rotation == 270:
        ft_x   = rLeft + MY * 2
        ft_y   = rTop  + MY
        orient = "R"
    else:
        ft_x   = rLeft + MX
        ft_y   = rTop  + AX - 1
        orient = "N"

    print(
        f"    [TEXT] {d.get('name', '?')!r:14s}  rot={rotation}°  "
        f"aabb({Left},{Top})  AX={AX} AY={AY} MX={MX} MY={MY}  "
        f"→ ^FT{ft_x},{ft_y} ^A0{orient},{AX},{AY}  {caption!r}"
    )

    parts = [f"^FT{ft_x},{ft_y}^A0{orient},{AX},{AY}^FH\\"]
    if inverse:
        parts.append("^FR")
    parts.append(f"^FD{caption}^FS")
    return "".join(parts)


# ── Barcode ───────────────────────────────────────────────────────────────────

def _convert_barcode(d: dict) -> str:
    """
    Use aabb_x/aabb_y as Left/Top (same reasoning as text elements).
    """
    Left, Top = _aabb_pos(d)

    rotation = int(round(float(d.get("rotation", 0)))) % 360
    orient   = _ORIENT.get(rotation, "N")
    design   = (d.get("design") or "CODE 128").upper()
    text     = str(d.get("design_text") or "")

    mag = d.get("design_magnification")
    try:
        module_w = max(1, int(mag))
    except (TypeError, ValueError):
        module_w = 2

    try:
        ratio = max(2, int(d.get("design_ratio") or 3))
    except (TypeError, ValueError):
        ratio = 3

    height_dots_raw = d.get("design_height_dots")
    if height_dots_raw is not None:
        height_dots = max(10, int(height_dots_raw))
    elif rotation in (90, 270):
        cw = d.get("container_width")
        height_dots = max(10, _r(float(cw))) if cw is not None else 50
    else:
        ch = d.get("container_height")
        if ch is not None:
            height_dots = max(10, _r(float(ch)))
        else:
            height_cm   = float(d.get("design_height_cm") or 1.0)
            height_dots = max(10, int(round(height_cm / 2.54 * 203)))

    interp      = (d.get("design_interpretation") or "").upper()
    show_interp = "Y" if "BELOW" in interp else "N"

    check_raw   = (d.get("design_check_digit") or "").upper()
    check_digit = "Y" if "AUTO" in check_raw else "N"

    zpl_cmd = _ZPL_BC.get(design, _ZPL_BC.get(design.split("(")[0].strip(), "^BC"))
    is_2d   = any(t in design for t in ("QR", "DATA MATRIX", "AZTEC"))

    ft_x = _r(Left)
    ft_y = _r(Top)

    print(
        f"    [BARCODE] {d.get('name', '?')!r:14s}  rot={rotation}°  "
        f"aabb({Left},{Top}) → ^FT{ft_x},{ft_y}  "
        f"^BY{module_w},{ratio},{height_dots}  {zpl_cmd}{orient}  {text!r}"
    )

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
    """
    Position from aabb_x/aabb_y (visual top-left of rotated bounding box).
    Dimensions derived from the SCENE bounding box so rotation is accounted for:
      - If aabb_w/aabb_h are stored, use them directly.
      - Otherwise rotate the local endpoint (x2, y2) by the canvas CCW angle
        and take the extent of the resulting bounding box.
    A line is always rendered as a ^GB filled rectangle whose thin dimension
    equals the stroke thickness.
    """
    fx, fy = _aabb_pos(d)
    th_raw = float(d.get("thickness", 2))
    th = max(1, _r(th_raw))

    # Local (unrotated) endpoints relative to item origin
    lx2 = float(d.get("x2", 100))
    ly2 = float(d.get("y2", 0))
    rot_ccw = float(d.get("rotation", 0))

    # Try stored scene bounding-box dimensions first
    aabb_w = float(d.get("aabb_w") or 0)
    aabb_h = float(d.get("aabb_h") or 0)

    if aabb_w > 0 and aabb_h > 0:
        # Use stored scene extents directly
        scene_dx = aabb_w
        scene_dy = aabb_h
    elif rot_ccw == 0:
        scene_dx = abs(lx2)
        scene_dy = abs(ly2)
    else:
        # Rotate the endpoint by the CCW angle to get scene-space delta
        rad = math.radians(rot_ccw)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        sx2 = lx2 * cos_a - ly2 * sin_a
        sy2 = lx2 * sin_a + ly2 * cos_a
        scene_dx = abs(sx2)
        scene_dy = abs(sy2)

    # Determine if line is predominantly horizontal or vertical in scene space
    if scene_dy <= th_raw:
        # Horizontal line
        w = max(th, _r(scene_dx))
        h = th
    elif scene_dx <= th_raw:
        # Vertical line
        w = th
        h = max(th, _r(scene_dy))
    else:
        # Diagonal — approximate as the longer axis
        if scene_dx >= scene_dy:
            w = max(th, _r(scene_dx))
            h = th
        else:
            w = th
            h = max(th, _r(scene_dy))

    pfx, pfy = _r(fx), _r(fy)
    print(f"    [LINE]    {d.get('name', '?')!r:14s}  rot={rot_ccw}°  "
          f"aabb({fx},{fy}) scene_dx={scene_dx:.1f} scene_dy={scene_dy:.1f}  "
          f"^FT{pfx},{pfy} ^GB{w},{h},{th}")
    return f"^FT{pfx},{pfy}^GB{w},{h},{th},B,0^FS"


# ── Rect ──────────────────────────────────────────────────────────────────────

def _convert_rect(d: dict) -> str:
    """
    Position from aabb_x/aabb_y. For rects, rotation just swaps w/h
    (a rotated rect's bounding box has swapped dimensions), so we use
    aabb_w/aabb_h when available, otherwise apply the same swap logic.
    """
    fx, fy   = _aabb_pos(d)
    rot_ccw  = float(d.get("rotation", 0))
    nat_w    = float(d.get("width",  100))
    nat_h    = float(d.get("height",  50))
    bw       = max(1, _r(float(d.get("border_width", 2))))

    # aabb dimensions if stored
    aabb_w = float(d.get("aabb_w") or 0)
    aabb_h = float(d.get("aabb_h") or 0)

    if aabb_w > 0 and aabb_h > 0:
        w = max(1, _r(aabb_w))
        h = max(1, _r(aabb_h))
    else:
        snapped = int(round(rot_ccw / 90.0)) * 90 % 360
        if snapped in (90, 270):
            w = max(1, _r(nat_h))
            h = max(1, _r(nat_w))
        else:
            w = max(1, _r(nat_w))
            h = max(1, _r(nat_h))

    pfx, pfy = _r(fx), _r(fy)
    print(f"    [RECT]    {d.get('name', '?')!r:14s}  rot={rot_ccw}°  "
          f"aabb({fx},{fy})  ^FT{pfx},{pfy} ^GB{w},{h},{bw}")
    return f"^FT{pfx},{pfy}^GB{w},{h},{bw},B,0^FS"


# ── Override helper ───────────────────────────────────────────────────────────

def _apply_overrides(elements: list[dict], overrides: dict) -> list[dict]:
    """
    Apply value_overrides (from barcode_print.py merged_values) onto elements
    BEFORE SAME WITH resolution runs, so that overridden values propagate
    correctly to SAME WITH targets.
    """
    result = []
    for elem in elements:
        name = elem.get("name", "")
        kind = elem.get("type", "")
        if kind == "text" and name in overrides:
            elem = dict(elem)
            elem["text"] = str(overrides[name])
            print(f"  [OVERRIDE text]    {name!r} → {overrides[name]!r}")
        elif kind == "barcode" and name in overrides:
            elem = dict(elem)
            elem["design_text"] = str(overrides[name])
            print(f"  [OVERRIDE barcode] {name!r} → {overrides[name]!r}")
        result.append(elem)
    return result


# ── MERGE evaluator ───────────────────────────────────────────────────────────

def _eval_merge(template: str, name_to_val: dict[str, str]) -> str:
    """
    Evaluate a MERGE template like "{Label1}{Label2}-{Label3}" using the
    current resolved name→value map.  Matches the canvas preview behaviour in
    _CanvasPreview._eval_merge (barcode_print.py).
    """
    def replacer(m: re.Match) -> str:
        return name_to_val.get(m.group(1), "")
    result = re.sub(r"\{(\w+)\}", replacer, template)
    # strip bare "+" separators that remain when a slot was empty
    result = result.replace("+", "")
    return result


def _resolve_merge(elements: list[dict]) -> list[dict]:
    """
    Evaluate all MERGE type elements using the current text values of sibling
    elements.  Must run AFTER _apply_overrides and AFTER _resolve_same_with so
    it sees the final resolved values.
    """
    # Build name → current text map (include invisible elements as value sources)
    name_to_val: dict[str, str] = {}
    for e in elements:
        n = e.get("name", "")
        if not n:
            continue
        if e.get("type") == "text":
            name_to_val[n] = str(e.get("text", ""))
        elif e.get("type") == "barcode":
            name_to_val[n] = str(e.get("design_text", ""))

    result = []
    for elem in elements:
        if (elem.get("type") == "text"
                and (elem.get("design_type") or "").upper() == "MERGE"):
            template = (elem.get("design_merge") or "").strip()
            if template:
                resolved = _eval_merge(template, name_to_val)
                elem = dict(elem)
                elem["text"] = resolved
                print(f"  [MERGE] {elem.get('name')!r} template={template!r} → {resolved!r}")
        result.append(elem)
    return result


def _resolve_same_with(elements: list[dict]) -> list[dict]:
    """
    Resolve SAME WITH references for both text and barcode elements.

    Searches by component_id first (canonical UUID stored in design_same_with),
    then falls back to searching by name.  Invisible source elements ARE
    included in the lookup maps so hidden sources can still feed visible targets.
    """
    # Build name→value and component_id→value lookup maps.
    # Include ALL elements regardless of visibility.
    name_to_text: dict[str, str] = {}
    cid_to_text:  dict[str, str] = {}
    first_lookup_text:  str  = ""
    first_lookup_found: bool = False

    for e in elements:
        n   = e.get("name", "")
        cid = e.get("component_id", "")
        if e.get("type") == "text":
            val = str(e.get("text", ""))
            if n:
                name_to_text[n] = val
            if cid:
                cid_to_text[cid] = val
            if (not first_lookup_found
                    and (e.get("design_type") or "").upper() == "LOOKUP"):
                first_lookup_text  = val
                first_lookup_found = True
        elif e.get("type") == "barcode":
            val = str(e.get("design_text", ""))
            if n:
                name_to_text[n] = val
            if cid:
                cid_to_text[cid] = val

    def _lookup(ref: str) -> tuple[bool, str]:
        """Search by component_id first (canonical), then by name (fallback)."""
        if ref in cid_to_text:
            return True, cid_to_text[ref]
        if ref in name_to_text:
            return True, name_to_text[ref]
        return False, ""

    result = []
    for elem in elements:
        dt   = (elem.get("design_type") or "").upper()
        kind = elem.get("type", "")

        if dt != "SAME WITH":
            result.append(elem)
            continue

        src = (elem.get("design_same_with") or "").strip()
        found, resolved = _lookup(src) if src else (False, "")

        # No explicit source but there is a LOOKUP element → use its value
        if not found and not src and first_lookup_found:
            found, resolved = True, first_lookup_text

        if found:
            elem = dict(elem)
            if kind == "barcode":
                print(f"  [SAME WITH] barcode {elem.get('name')!r} ← {src!r} = {resolved!r}")
                elem["design_text"] = resolved
            else:
                print(f"  [SAME WITH] text    {elem.get('name')!r} ← {src!r} = {resolved!r}")
                elem["text"] = resolved
        else:
            if src:
                print(
                    f"  [SAME WITH] {kind} {elem.get('name')!r} ← {src!r} "
                    f"NOT FOUND in cid/name maps — keeping original value"
                )
            else:
                print(
                    f"  [SAME WITH] {kind} {elem.get('name')!r} ← "
                    f"(no source ref, no LOOKUP fallback) — keeping original value"
                )

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

    Pipeline order (important):
      1. Parse JSON
      2. _apply_overrides   ← inject barcode_print.py merged_values FIRST
      3. _resolve_same_with ← now sees already-overridden values for sources
      4. _resolve_merge     ← evaluate MERGE templates with final resolved values
      5. Sort by z-value
      6. Emit ZPL per element (skip invisible, but they were already used above)
    """
    print("=" * 60)
    print(
        f"[canvas_to_zpl] canvas={canvas_w}×{canvas_h}px  "
        f"dpi={dpi} (scale fixed at 2.1)  qty={print_qty}"
    )
    if value_overrides:
        print(f"  overrides ({len(value_overrides)}): {list(value_overrides.keys())}")
    print("=" * 60)

    if isinstance(canvas_json, str):
        elements: list[dict] = json.loads(canvas_json)
    else:
        elements = list(canvas_json)

    # ── Step 1: apply field-widget values onto element texts ──────────────────
    # Must happen BEFORE _resolve_same_with so SAME WITH targets see the
    # correct source values (e.g. after a master-item lookup).
    if value_overrides:
        elements = _apply_overrides(elements, value_overrides)

    # ── Step 2: propagate SAME WITH references ────────────────────────────────
    elements = _resolve_same_with(elements)

    # ── Step 3: evaluate MERGE templates ──────────────────────────────────────
    # Runs after SAME WITH so merge slots that reference SAME WITH targets
    # also get the correct resolved values.
    elements = _resolve_merge(elements)

    # ── Step 4: sort by z (paint order) ──────────────────────────────────────
    elements_sorted = sorted(elements, key=lambda e: float(e.get("z", 0)))

    pw = _r(canvas_w)

    lines: list[str] = [
        f"^XA^PR{print_speed}^FS",
        f"^PW{pw}",
        "^LH0,0",
    ]
    if label_name:
        lines.append(f"^FX {label_name.replace('^', '').replace('~', '')}")

    for idx, d in enumerate(elements_sorted):
        kind    = d.get("type", "")
        visible = d.get("visible", True)

        print(f"\n  #{idx + 1} {kind!r:8s} {d.get('name', '?')!r:14s}  visible={visible}")

        if not visible:
            print("    SKIPPED (not visible)")
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
                print(f"    SKIPPED (unsupported type: {kind!r})")
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
            raw    = f.read().strip()
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                parsed = json.loads(parsed.get("usrm", "[]"))
        print(canvas_to_zpl(parsed, dpi=dpi_arg, print_qty=qty_arg))
        sys.exit(0)

    # ── Built-in self-test (BC0002 sample) ────────────────────────────────────
    print("Self-test with BC0002 sample data:")
    sample = json.loads(
        '[{"x":-6.0,"y":87.0,"z":12.0,"visible":true,"rotation":270.0,'
        '"name":"Label2","aabb_x":5.0,"aabb_y":76.0,"type":"text","text":"C-1105",'
        '"font_size":8,"font_family":"Arial","design_trim":true},'
        '{"x":1.0,"y":45.0,"z":7.0,"visible":true,"rotation":0.0,'
        '"name":"Label7","aabb_x":1.0,"aabb_y":45.0,"type":"text","text":"22AMN",'
        '"font_size":10,"font_family":"Arial"},'
        '{"x":134.0,"y":129.0,"z":5.0,"visible":true,"rotation":270.0,'
        '"name":"Label11","aabb_x":138.0,"aabb_y":125.0,"type":"text","text":"AGT",'
        '"font_size":7,"font_family":"Arial","design_trim":true},'
        '{"x":117.0,"y":38.0,"z":4.0,"visible":true,"rotation":270.0,'
        '"name":"Label12","aabb_x":138.0,"aabb_y":17.0,"type":"text","text":"10:06:27 AM",'
        '"font_size":7,"font_family":"Arial"},'
        '{"x":107.5,"y":88.5,"z":3.0,"visible":true,"rotation":270.0,'
        '"name":"Label13","aabb_x":118.0,"aabb_y":78.0,"type":"text","text":"kodeSAP",'
        '"font_size":6,"font_family":"Arial","design_trim":true},'
        '{"x":-23.5,"y":82.5,"z":1.0,"visible":true,"rotation":270.0,'
        '"name":"Barcode2","aabb_x":4.0,"aabb_y":55.0,"type":"barcode",'
        '"design":"CODE128","container_width":95,"container_height":40,'
        '"design_magnification":"6","design_ratio":"3",'
        '"design_interpretation":"NO INTERPRETATION","design_text":"0123456789"}]'
    )
    result = canvas_to_zpl(
        sample, canvas_w=152, canvas_h=170, dpi=203,
        label_name="BC0002", print_qty=1,
    )

    print("\n" + "=" * 60)
    print("EXPECTED (from Delphi reference):")
    print("^BY6,3,201^FT8,116^BCR,,N,N^FD0123456789^FS")
    print("^FT232,189^A0R,17,16^FH\\^FDkodeSAP^FS")
    print("^FT252,82^A0R,20,19^FH\\^FD10:06:27 AM^FS")
    print("^FT4,122^A0N,28,28^FH\\^FD22AMN^FS")
    print("^FT288,275^A0R,20,19^FH\\^FDAGT^FS")
    print("^FT6,187^A0R,23,24^FH\\^FDC-1105^FS")
    print("=" * 60)
    print("\nACTUAL:")
    print(result)