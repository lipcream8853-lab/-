#!/usr/bin/env python3
"""池田生花店ブログ用のアイキャッチ画像（1200x630）を生成する。

使い方:
    python3 scripts/generate_eyecatch.py "記事タイトル" blog/images/output.png
"""
import sys
import textwrap
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 630

# ブランドカラー（暖色・草花をイメージした落ち着いた配色）
BG_TOP = (250, 244, 235)      # アイボリー
BG_BOTTOM = (241, 231, 214)   # 淡いベージュ
ACCENT_PINK = (214, 132, 130)   # 淡い赤紫（花びら）
ACCENT_PINK_LIGHT = (232, 176, 170)
ACCENT_GREEN = (122, 143, 105)  # 葉の緑
ACCENT_GREEN_DARK = (90, 108, 78)
TEXT_COLOR = (58, 48, 42)       # こげ茶（本文向け濃色）
LABEL_COLOR = (122, 143, 105)

FONT_PATH_BOLD = "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf"
FONT_PATH_REGULAR = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"


def vertical_gradient(draw, top, bottom, width, height):
    for y in range(height):
        t = y / height
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def draw_flower(draw, cx, cy, petal_r, center_r, petal_color, center_color, petals=6):
    import math
    for i in range(petals):
        angle = (2 * math.pi / petals) * i
        px = cx + petal_r * 0.9 * math.cos(angle)
        py = cy + petal_r * 0.9 * math.sin(angle)
        draw.ellipse(
            [px - petal_r, py - petal_r, px + petal_r, py + petal_r],
            fill=petal_color,
        )
    draw.ellipse(
        [cx - center_r, cy - center_r, cx + center_r, cy + center_r],
        fill=center_color,
    )


def draw_leaf(draw, x, y, w, h, color, angle=0):
    leaf = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    ld = ImageDraw.Draw(leaf)
    ld.ellipse([0, 0, w * 2, h * 2], fill=color)
    leaf = leaf.rotate(angle, expand=True)
    draw._image.paste(leaf, (int(x - leaf.width / 2), int(y - leaf.height / 2)), leaf)


def generate(title: str, out_path: str, label: str = "池田生花店ブログ"):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_TOP)
    draw = ImageDraw.Draw(img)
    draw._image = img
    vertical_gradient(draw, BG_TOP, BG_BOTTOM, WIDTH, HEIGHT)

    # 右下に花のモチーフ（大小2輪＋葉）
    draw_leaf(draw, WIDTH - 120, HEIGHT - 90, 70, 30, (*ACCENT_GREEN, 255), angle=25)
    draw_leaf(draw, WIDTH - 260, HEIGHT - 60, 60, 26, (*ACCENT_GREEN_DARK, 255), angle=-15)
    draw_flower(draw, WIDTH - 150, HEIGHT - 160, 46, 22, ACCENT_PINK, (247, 214, 150), petals=6)
    draw_flower(draw, WIDTH - 280, HEIGHT - 110, 30, 15, ACCENT_PINK_LIGHT, (247, 214, 150), petals=6)

    # ラベル（上部）
    font_label = ImageFont.truetype(FONT_PATH_BOLD, 30)
    draw.text((80, 70), label, font=font_label, fill=LABEL_COLOR)

    # 左上の角に小さな花（アクセント、ラベル文字とは重ならない位置）
    draw_leaf(draw, 40, 36, 26, 12, (*ACCENT_GREEN, 255), angle=200)
    draw_flower(draw, 32, 32, 15, 7, ACCENT_PINK_LIGHT, (247, 214, 150), petals=5)

    # タイトル（改行を入れて中央寄り左に配置）
    font_title = ImageFont.truetype(FONT_PATH_BOLD, 58)
    max_chars_per_line = 13
    lines = textwrap.wrap(title, width=max_chars_per_line)
    if len(lines) > 4:
        lines = lines[:4]
        lines[-1] = lines[-1][:-1] + "…"

    line_height = 78
    total_h = line_height * len(lines)
    start_y = (HEIGHT - total_h) / 2 + 10

    for i, line in enumerate(lines):
        y = start_y + i * line_height
        draw.text((82, 82), "", font=font_label)  # no-op keep font cache
        draw.text((80, y), line, font=font_title, fill=TEXT_COLOR)

    # 下部にアンダーライン装飾
    underline_y = start_y + total_h + 20
    draw.rectangle([80, underline_y, 260, underline_y + 6], fill=ACCENT_GREEN)

    img.save(out_path, "PNG")
    print(f"saved: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: generate_eyecatch.py <title> <output_path> [label]")
        sys.exit(1)
    title_arg = sys.argv[1]
    out_arg = sys.argv[2]
    label_arg = sys.argv[3] if len(sys.argv) > 3 else "池田生花店ブログ"
    generate(title_arg, out_arg, label_arg)
