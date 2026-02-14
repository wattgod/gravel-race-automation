"""Gear essentials grid — 5 key items every gravel racer needs."""
from PIL import Image, ImageDraw

from .base import (
    load_font, load_editorial_font, hex_to_rgb, draw_gold_rule,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, GOLD,
    LIGHT_GOLD, WARM_PAPER, DARK_BROWN, NEAR_BLACK, WHITE, WARM_BROWN,
)

ITEMS = [
    {
        "name": "BIKE FRAME",
        "icon": "frame",
        "spec": "Drop bars, 38mm+ clearance",
        "skip": "Carbon, aero geometry",
        "color": DARK_TEAL,
    },
    {
        "name": "TIRES",
        "icon": "tires",
        "spec": "40-50mm tubeless",
        "skip": "Boutique brands, TPU",
        "color": PRIMARY_BROWN,
    },
    {
        "name": "HELMET",
        "icon": "helmet",
        "spec": "Modern MIPS certified",
        "skip": "Aero road helmets",
        "color": DARK_TEAL,
    },
    {
        "name": "REPAIR KIT",
        "icon": "repair",
        "spec": "Tube, plugs, CO2, tool",
        "skip": "Exotic chain lubes",
        "color": PRIMARY_BROWN,
    },
    {
        "name": "HYDRATION",
        "icon": "hydration",
        "spec": "2-3 bottles + electrolytes",
        "skip": "Hydration packs <100mi",
        "color": DARK_TEAL,
    },
]


def _draw_icon(draw, cx, cy, size, icon_type, color, outline_color):
    """Draw a geometric icon centered at (cx, cy) within a bounding box of `size`."""
    s = size
    half = s // 2
    stroke = max(2, s // 20)
    rgb = hex_to_rgb(color)
    out = hex_to_rgb(outline_color)

    if icon_type == "frame":
        # Diamond shape (bike frame silhouette) + seat tube line
        pts = [
            (cx, cy - half + s // 8),           # top
            (cx + half - s // 8, cy),            # right
            (cx, cy + half - s // 8),            # bottom
            (cx - half + s // 8, cy),            # left
        ]
        draw.polygon(pts, outline=out, fill=None)
        # Thicken the diamond outline
        draw.line(pts + [pts[0]], fill=rgb, width=stroke)
        # Seat tube (vertical line from top vertex down to center)
        draw.line([(cx, cy - half + s // 8), (cx, cy + s // 10)],
                  fill=rgb, width=stroke)

    elif icon_type == "tires":
        # Two nested squares (outer tire + inner rim)
        outer = s // 3
        inner = s // 6
        draw.rectangle([(cx - outer, cy - outer), (cx + outer, cy + outer)],
                       outline=rgb, width=stroke)
        draw.rectangle([(cx - inner, cy - inner), (cx + inner, cy + inner)],
                       outline=out, width=stroke)

    elif icon_type == "helmet":
        # Angular chevron/dome — wide polygon shape
        pts = [
            (cx - half + s // 6, cy + s // 5),    # bottom-left
            (cx - s // 4, cy - s // 6),            # mid-left
            (cx, cy - half + s // 8),              # apex
            (cx + s // 4, cy - s // 6),            # mid-right
            (cx + half - s // 6, cy + s // 5),     # bottom-right
        ]
        draw.polygon(pts, outline=out, fill=None)
        draw.line(pts, fill=rgb, width=stroke)
        # Brim line across bottom
        draw.line([(cx - half + s // 8, cy + s // 5),
                   (cx + half - s // 8, cy + s // 5)],
                  fill=rgb, width=stroke)

    elif icon_type == "repair":
        # Plus/cross: two intersecting rectangles
        arm_w = s // 8
        arm_len = s // 3
        # Vertical bar
        draw.rectangle([(cx - arm_w, cy - arm_len),
                        (cx + arm_w, cy + arm_len)],
                       fill=rgb, outline=out, width=max(1, stroke // 2))
        # Horizontal bar
        draw.rectangle([(cx - arm_len, cy - arm_w),
                        (cx + arm_len, cy + arm_w)],
                       fill=rgb, outline=out, width=max(1, stroke // 2))

    elif icon_type == "hydration":
        # Bottle outline: rectangle body + narrower neck on top
        body_w = s // 4
        body_h = s // 3
        neck_w = s // 7
        neck_h = s // 6
        # Body
        draw.rectangle([(cx - body_w, cy - body_h + neck_h),
                        (cx + body_w, cy + body_h)],
                       outline=rgb, width=stroke)
        # Neck
        draw.rectangle([(cx - neck_w, cy - body_h - neck_h // 2),
                        (cx + neck_w, cy - body_h + neck_h)],
                       outline=rgb, width=stroke)
        # Cap line
        draw.rectangle([(cx - neck_w - 1, cy - body_h - neck_h // 2 - stroke),
                        (cx + neck_w + 1, cy - body_h - neck_h // 2)],
                       fill=out)


def render(width: int = 1200, height: int = 800) -> Image.Image:
    """Render a 5-item gear essentials grid."""
    s = width / 1200

    img = Image.new("RGB", (width, height), hex_to_rgb(WARM_PAPER))
    draw = ImageDraw.Draw(img)

    font_title = load_editorial_font(size=int(26 * s))
    font_subtitle = load_font(bold=False, size=int(13 * s))
    font_name = load_font(bold=True, size=int(18 * s))
    font_label = load_font(bold=True, size=int(12 * s))
    font_spec = load_font(bold=False, size=int(13 * s))
    font_xs = load_font(bold=False, size=int(11 * s))

    pad = int(40 * s)

    # Title — Source Serif 4
    draw.text((pad, int(14 * s)), "GEAR ESSENTIALS",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.text((pad + int(300 * s), int(22 * s)), "What you actually need — nothing more",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_subtitle)
    rule_y = int(50 * s)
    draw_gold_rule(draw, pad, rule_y, width - pad, width=max(2, int(2 * s)))

    # 5 columns — top row of 3, bottom row of 2 centered
    col_gap = int(16 * s)
    top_cols = 3
    bottom_cols = 2
    col_w = (width - pad * 2 - col_gap * (top_cols - 1)) // top_cols
    card_h = int(310 * s)
    top_y = int(66 * s)
    bottom_y = top_y + card_h + col_gap

    icon_size = int(60 * s)

    def draw_card(x, y, item):
        color = item["color"]

        # Card outline
        draw.rectangle([(x, y), (x + col_w, y + card_h)],
                       fill=hex_to_rgb(WHITE), outline=hex_to_rgb(DARK_BROWN),
                       width=max(2, int(2 * s)))

        # Colored header strip
        strip_h = int(42 * s)
        draw.rectangle([(x, y), (x + col_w, y + strip_h)],
                       fill=hex_to_rgb(color))

        # Name centered in strip
        bbox = draw.textbbox((0, 0), item["name"], font=font_name)
        tw = bbox[2] - bbox[0]
        draw.text((x + (col_w - tw) // 2, y + int(10 * s)),
                  item["name"], fill=hex_to_rgb(WHITE), font=font_name)

        # Geometric icon centered
        icon_cx = x + col_w // 2
        icon_cy = y + strip_h + int(20 * s) + icon_size // 2
        _draw_icon(draw, icon_cx, icon_cy, icon_size,
                   item["icon"], color, DARK_BROWN)

        # Key spec
        spec_y = y + strip_h + int(20 * s) + icon_size + int(16 * s)
        draw.text((x + int(14 * s), spec_y), "KEY SPEC",
                  fill=hex_to_rgb(color), font=font_label)
        draw.text((x + int(14 * s), spec_y + int(18 * s)), item["spec"],
                  fill=hex_to_rgb(NEAR_BLACK), font=font_spec)

        # Divider
        div_y = spec_y + int(48 * s)
        draw.line([(x + int(14 * s), div_y), (x + col_w - int(14 * s), div_y)],
                  fill=hex_to_rgb(WARM_BROWN), width=max(1, int(1 * s)))

        # Skip until later
        skip_y = div_y + int(12 * s)
        draw.text((x + int(14 * s), skip_y), "SKIP UNTIL LATER",
                  fill=hex_to_rgb(SECONDARY_BROWN), font=font_label)
        draw.text((x + int(14 * s), skip_y + int(18 * s)), item["skip"],
                  fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)

    # Top row: 3 cards
    for i in range(top_cols):
        cx = pad + i * (col_w + col_gap)
        draw_card(cx, top_y, ITEMS[i])

    # Bottom row: 2 cards centered
    bottom_total = bottom_cols * col_w + (bottom_cols - 1) * col_gap
    bottom_start = (width - bottom_total) // 2
    for i in range(bottom_cols):
        cx = bottom_start + i * (col_w + col_gap)
        draw_card(cx, bottom_y, ITEMS[top_cols + i])

    return img
