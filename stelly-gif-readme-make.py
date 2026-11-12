"""Stelly walking banner for a GitHub README.

Renders seamless looping pixel art GIFs: Stelly walks right through an
overgrown solarpunk city while parallax layers scroll behind him.
Two themes with the same scene: night (dark mode) and day (light mode).

Usage:
    python make.py                  # writes stelly-night.gif and stelly-day.gif
    python make.py --theme day      # just one theme
    python make.py --preview        # also saves a few PNG frames to check

Needs Pillow (pip install pillow).

How the loop stays seamless: every moving thing repeats a whole number of
times in N frames. Each scrolling layer is a tile whose width divides the
total distance it moves, and every animation period (walk, blink, stars,
turbines, steam) divides N. check_loop() verifies this before saving.
"""
import argparse
import math
import random

from PIL import Image, ImageDraw

# ---------- settings ----------
W, H = 240, 60        # low-res canvas (pixel art size)
SCALE = 4             # final GIF is 960 x 240
N = 240               # frames in one loop
FRAME_MS = 50         # 240 x 50 ms = 12 second loop

# layer: (tile width, pixels moved per frame); tile must divide N * speed
CLOUD_TILE, CLOUD_EVERY = 120, 2      # clouds move 1 px every 2 frames
FAR_TILE, FAR_SPEED = 240, 1
MID_TILE, MID_SPEED = 240, 2
GROUND_TILE, GROUND_SPEED = 120, 3
GROUND_Y = 46
NEAR_TILE, NEAR_SPEED = 240, 3      # one big turbine just behind the path
NEAR_TURBINE_X = 40
STELLY_X, STELLY_Y = 96, 21

# animation periods (all must divide N)
WALK_PERIOD = 8
STAR_PERIOD = 40
TURBINE_PERIOD = 12   # one third turn, blades look the same after 120 deg
STEAM_PERIOD = 40
BLINK_PERIOD = 80
GLANCE_PERIOD = 120

NIGHT = dict(
    # sky
    sky1=(12, 14, 40), sky2=(20, 24, 62), sky3=(32, 36, 86), sky4=(48, 46, 104),
    moon=(236, 232, 210), moon_core=(255, 252, 235), star=(255, 250, 220), star_dim=(150, 150, 200),
    cloud=(70, 72, 124), cloud_shade=(52, 54, 100),
    # far skyline
    far=(34, 52, 78), far_green=(36, 82, 72), far_window=(255, 214, 120),
    # mid buildings
    bld=(58, 62, 92), bld_shade=(44, 46, 72), window=(255, 206, 110), dark=(26, 28, 46),
    vine=(48, 120, 76), vine_dark=(30, 84, 56), moss=(64, 140, 82), trunk=(70, 52, 44),
    turbine=(170, 176, 210), turbine_pole=(118, 124, 160), rust=(86, 62, 62), rust_dark=(62, 46, 50),
    steam=(150, 150, 186), steam_dark=(96, 98, 140),
    # ground
    grass=(34, 86, 58), grass_dark=(22, 62, 44), path=(84, 76, 96), path_dark=(64, 58, 78),
    flower1=(170, 96, 140), flower2=(176, 166, 100), flower3=(128, 108, 190),
    # Stelly
    outline=(96, 74, 170), shell=(44, 40, 54), shell_side=(30, 27, 38), shell_hi=(78, 72, 96),
    screen=(10, 12, 18), eye=(139, 92, 246), smile=(196, 181, 253),
    accent=(139, 92, 246), accent_dark=(100, 62, 196), shadow=(50, 44, 64),
)
DAY = dict(
    NIGHT,
    sky1=(110, 185, 250), sky2=(140, 205, 252), sky3=(175, 222, 252), sky4=(210, 238, 245),
    moon=(255, 214, 90), moon_core=(255, 240, 160),          # becomes the sun
    cloud=(255, 255, 255), cloud_shade=(222, 236, 250),
    far=(158, 200, 196), far_green=(118, 178, 140), far_window=(120, 160, 172),
    bld=(204, 198, 180), bld_shade=(176, 168, 150), window=(150, 196, 210), dark=(86, 90, 104),
    vine=(72, 164, 84), vine_dark=(42, 120, 62), moss=(104, 176, 92), trunk=(126, 90, 62),
    turbine=(244, 244, 238), turbine_pole=(150, 158, 168), rust=(162, 100, 74), rust_dark=(122, 74, 58),
    steam=(248, 248, 252), steam_dark=(214, 220, 234),
    grass=(96, 184, 74), grass_dark=(62, 142, 52), path=(218, 194, 144), path_dark=(194, 166, 112),
    flower1=(206, 136, 164), flower2=(214, 204, 112), flower3=(164, 146, 214),
    # Stelly in his demo-site light colors: white shell, mint screen, black face
    outline=(40, 150, 92), shell=(240, 250, 244), shell_side=(208, 234, 220), shell_hi=(255, 255, 255),
    screen=(194, 245, 220), eye=(17, 17, 17), smile=(17, 17, 17),
    accent=(52, 190, 120), accent_dark=(34, 150, 90), shadow=(184, 162, 116),
)
THEMES = {"night": NIGHT, "day": DAY}
C = NIGHT          # active palette, set per theme in main()
FLOWERS = ["flower1", "flower2", "flower3"]


def rect(d, x, y, w, h, color, tile=None):
    """Filled rectangle. With tile set, also draws wrapped copies so the tile repeats cleanly."""
    for xx in [x] if tile is None else [x - tile, x, x + tile]:
        d.rectangle([xx, y, xx + w - 1, y + h - 1], fill=C[color])


def ellipse(d, box, color, tile):
    x0, y0, x1, y1 = box
    for k in (-tile, 0, tile):
        d.ellipse([x0 + k, y0, x1 + k, y1], fill=C[color])


# ---------- static layers ----------
def make_sky():
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    bands = [(0, 12, "sky1"), (12, 24, "sky2"), (24, 36, "sky3"), (36, H, "sky4")]
    for y0, y1, c in bands:
        rect(d, 0, y0, W, y1 - y0, c)
    for (_, y, upper), _ in zip(bands, bands[1:]):      # checker dither on each band edge
        for x in range(0, W, 2):
            d.point((x, y), fill=C[upper])
    d.ellipse([198, 5, 212, 19], fill=C["moon"])        # crescent moon at night, sun by day
    d.ellipse([200, 7, 208, 15], fill=C["moon_core"])
    if C is NIGHT:
        d.ellipse([203, 3, 215, 15], fill=C["sky1"])
    return img


def make_stars():
    rng = random.Random(3)
    stars = [(rng.randrange(W), rng.randrange(0, 34), rng.randrange(4)) for _ in range(45)]
    return [s for s in stars if not (196 <= s[0] <= 216 and s[1] <= 21)]   # keep clear of moon


def make_clouds():
    img = Image.new("RGBA", (CLOUD_TILE, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for x, y, w in [(10, 8, 22), (70, 16, 16), (95, 5, 12)]:
        rect(d, x, y + 3, w + 1, 4, "cloud_shade", CLOUD_TILE)
        rect(d, x + 2, y + 1, w - 3, 4, "cloud", CLOUD_TILE)
        rect(d, x + w // 3, y - 1, w // 3 + 1, 4, "cloud", CLOUD_TILE)
    return img


def make_far(rng):
    img = Image.new("RGBA", (FAR_TILE, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = 0
    while x < FAR_TILE:
        w, h = rng.randint(7, 15), rng.randint(9, 24)
        rect(d, x, 46 - h, w, h, "far", FAR_TILE)
        rect(d, x, 46 - h - 1, w, 2, "far_green", FAR_TILE)
        if rng.random() < .5:
            rect(d, x + w // 2 - 1, 46 - h - 3, 3, 2, "far_green", FAR_TILE)
        for wy in range(46 - h + 3, 44, 4):
            for wx in range(x + 2, x + w - 2, 3):
                if rng.random() < .15:
                    rect(d, wx, wy, 1, 2, "far_window", FAR_TILE)
        x += w + rng.randint(0, 3)
    return img


def tree(d, x, base, size):
    rect(d, x + size // 2 - 1, base - 6, 2, 6, "trunk", MID_TILE)
    ellipse(d, [x, base - 6 - size, x + size, base - 4], "vine_dark", MID_TILE)
    ellipse(d, [x + 1, base - 6 - size, x + size - 2, base - 7], "vine", MID_TILE)


def make_mid(rng):
    """Abandoned, overgrown buildings plus the factory. Returns the layer, turbine hubs, and steam vents."""
    T = MID_TILE
    img = Image.new("RGBA", (T, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    turbines, vents = [], []
    fx, fw = 118, 40                                     # factory spot, kept clear of buildings

    x = 4
    while x < T - 10:
        if x + 30 > fx and x < fx + fw + 2:
            x = fx + fw + 3
            continue
        if rng.random() < .35:
            tree(d, x, 48, rng.randint(9, 13))
            x += 13
            continue
        w, h = rng.randint(16, 26), rng.randint(14, 26)
        top = 48 - h
        rect(d, x, top, w, h, "bld", T)
        rect(d, x + w - 3, top, 3, h, "bld_shade", T)
        if rng.random() < .5:                            # crumbled roof corner
            cw = rng.randint(3, 7)
            rect(d, x + w - cw, top, cw, rng.randint(2, 5), "dark", T)
        for wy in range(top + 4, 44, 5):                 # mostly dark windows
            for wx in range(x + 3, x + w - 5, 5):
                rect(d, wx, wy, 2, 3, "window" if rng.random() < .12 else "dark", T)
        rect(d, x + rng.randint(2, w - 4), top + rng.randint(3, h - 4), 1, 4, "dark", T)   # crack
        for _ in range(rng.randint(2, 4)):               # moss
            rect(d, x + rng.randint(0, w - 4), top + rng.randint(2, h - 3), rng.randint(2, 4), 2, "moss", T)
        rect(d, x - 1, top - 2, w + 2, 3, "vine_dark", T)   # overgrown roof
        for bx in range(x, x + w - 1, 3):
            rect(d, bx, top - 4, 3, 2, "vine", T)
        if rng.random() < .45:
            tree(d, x + rng.randint(1, max(1, w - 10)), top - 1, 7)
        elif rng.random() < .5:
            px = x + w // 2
            rect(d, px - 2, top - 5, 5, 2, "dark", T)              # roof mount
            rect(d, px, top - 10, 2, 6, "turbine_pole", T)        # pole
            turbines.append((px + 1, top - 10))
        for vx in range(x, x + w - 1, rng.randint(2, 4)):   # hanging vines
            rect(d, vx, top, 1, rng.randint(4, h - 2), "vine", T)
        rect(d, x, 44, w, 4, "vine_dark", T)             # bushes at the base
        x += w + rng.randint(2, 6)

    # factory with smokestack
    ft = 33
    rect(d, fx, ft, fw, 48 - ft, "rust", T)
    rect(d, fx + fw - 3, ft, 3, 48 - ft, "rust_dark", T)
    for tx in range(fx, fx + fw - 6, 8):                 # sawtooth roof
        for i in range(6):
            rect(d, tx + i, ft - 1 - i, 1, i + 1, "rust", T)
        rect(d, tx + 6, ft - 6, 2, 6, "dark", T)
    for wx in range(fx + 3, fx + fw - 5, 6):
        rect(d, wx, ft + 4, 4, 3, "window" if wx % 4 == 0 else "dark", T)
    rect(d, fx + 4, 41, 7, 7, "dark", T)                 # big door
    sx = fx + fw - 10
    rect(d, sx, 10, 6, ft - 10, "rust_dark", T)
    rect(d, sx, 10, 6, 1, "turbine", T)
    for by in (16, 24):
        rect(d, sx, by, 6, 1, "rust", T)
    for vy in range(14, ft, 3):
        rect(d, sx + (vy % 2) * 4, vy, 2, 2, "moss", T)
    for vx in range(fx, fx + fw, 3):
        rect(d, vx, ft - 1, 1, rng.randint(3, 10), "vine", T)
    rect(d, fx - 1, 44, fw + 2, 4, "vine_dark", T)
    for _ in range(6):
        rect(d, fx + rng.randint(0, fw - 4), rng.randint(ft, 44), 3, 2, "moss", T)
    vents.append((sx + 3, 9))
    return img, turbines, vents


def make_ground():
    T = GROUND_TILE
    img = Image.new("RGB", (T, H - GROUND_Y))
    d = ImageDraw.Draw(img)
    rect(d, 0, 0, T, 14, "grass")
    rect(d, 0, 4, T, 6, "path")
    rect(d, 0, 9, T, 1, "path_dark")
    for i in range(0, T, 3):
        rect(d, i, 0, 1, 1 + (i * 7) % 3, "grass_dark", T)
        if (i * 13) % 7 == 0:
            rect(d, i, 6, 2, 1, "path_dark", T)
    rng = random.Random(11)
    for _ in range(26):                                  # tiny scattered flowers
        i, fy = rng.randrange(T), rng.choice([0, 1, 2, 11, 12, 13])
        rect(d, i, fy, 1, 1, rng.choice(FLOWERS), T)
        if rng.random() < .3:
            rect(d, (i + rng.choice([2, 3])) % T, min(13, fy + rng.choice([0, 1])), 1, 1, rng.choice(FLOWERS), T)
    return img


# ---------- per-frame drawing ----------
def paste_scrolled(dst, layer, offset, y=0):
    tw = layer.width
    offset %= tw
    for k in range(-1, W // tw + 2):
        pos = (k * tw - offset, y)
        dst.paste(layer, pos, layer if layer.mode == "RGBA" else None)


def screen_copies(x, offset, tile, margin):
    """Screen x positions of a point on a scrolling tile, including wrapped copies near the edges."""
    base = (x - offset) % tile
    return [base + k * tile for k in (-1, 0, 1) if -margin < base + k * tile < W + margin]


def draw_stars(d, stars, f):
    for x, y, phase in stars:
        state = (f * 4 // STAR_PERIOD + phase) % 4
        d.point((x, y), fill=C["star"] if state else C["star_dim"])
        if state == 2:
            d.point((x - 1, y), fill=C["star_dim"])
            d.point((x + 1, y), fill=C["star_dim"])


def draw_blades(d, cx, hy, angle, length, width=1):
    for b in range(3):
        a = angle + b * 2 * math.pi / 3
        d.line([cx, hy, cx + math.cos(a) * length, hy + math.sin(a) * length], fill=C["turbine"], width=width)
    d.rectangle([cx - 1, hy - 1, cx, hy], fill=C["turbine_pole"])     # hub


def draw_turbines(d, hubs, f):
    angle = (f % TURBINE_PERIOD) / TURBINE_PERIOD * (2 * math.pi / 3)
    for hx, hy in hubs:
        for cx in screen_copies(hx, f * MID_SPEED, MID_TILE, 8):
            draw_blades(d, cx, hy, angle, 5)


def draw_near_turbine(d, f):
    """A giant turbine just behind the path. Only its tower fits in frame, which shows how huge it is."""
    base, half = GROUND_Y + 3, 4
    for cx in screen_copies(NEAR_TURBINE_X, f * NEAR_SPEED, NEAR_TILE, 10):
        d.rectangle([cx - half - 2, base - 2, cx + half + 2, base], fill=C["dark"])      # footing
        d.rectangle([cx - half, 0, cx + half, base - 2], fill=C["turbine"])             # tower down to the footing
        d.rectangle([cx + half - 2, 0, cx + half, base - 2], fill=C["turbine_pole"])     # shaded side


def draw_steam(d, vents, f):
    puffs = 8
    for vx, vy in vents:
        for cx in screen_copies(vx, f * MID_SPEED, MID_TILE, 30):
            for i in range(puffs):
                age = (f + i * STEAM_PERIOD // puffs) % STEAM_PERIOD
                r = 1 + age // 8
                px, py = cx + age * 0.4, vy - age * 0.22
                d.ellipse([px - r, py - r, px + r, py + r], fill=C["steam"] if age < 22 else C["steam_dark"])


def draw_stelly(d, f):
    """Rounded, boxy Stelly facing right, with nub arms and feet."""
    ox, oy = STELLY_X, STELLY_Y
    step = f % WALK_PERIOD
    bob = 1 if step in (1, 2, 5, 6) else 0
    swing = [-2, -1, 0, 1, 2, 1, 0, -1][step]
    front_up = 1 if swing > 0 else 0
    back_up = 1 if swing < 0 else 0

    def box(x0, y0, x1, y1, c, radius):
        d.rounded_rectangle([ox + x0, oy + y0, ox + x1, oy + y1], radius=radius, fill=C[c])

    def oval(x0, y0, x1, y1, c):
        d.ellipse([ox + x0, oy + y0, ox + x1, oy + y1], fill=C[c])

    def hline(x0, x1, y, c):
        d.line([ox + x0, oy + y, ox + x1, oy + y], fill=C[c])

    oval(3, 30, 19, 33, "shadow")
    oval(6 - swing, 27 - back_up, 11 - swing, 31 - back_up, "accent_dark")       # back foot

    y = bob
    oval(0, 15 + y + back_up, 4, 20 + y + back_up, "accent_dark")                # back arm
    box(3, 4 + y, 18, 28 + y, "outline", 5)                                      # body
    box(4, 5 + y, 17, 27 + y, "shell_side", 4)
    box(7, 5 + y, 17, 27 + y, "shell", 4)
    hline(9, 14, 5 + y, "shell_hi")

    box(8, 8 + y, 16, 17 + y, "screen", 2)                                       # face
    look = 1 if 20 <= f % GLANCE_PERIOD < 100 else 0      # glances forward; steady across the loop point
    blink = (f % BLINK_PERIOD) in (40, 41, 42)
    for ex in (9, 13):
        top = 12 if blink else 10
        d.rectangle([ox + ex + look, oy + top + y, ox + ex + look + 1, oy + 12 + y], fill=C["eye"])
    for sx in (9, 14):
        d.point((ox + sx + look, oy + 14 + y), fill=C["smile"])
    hline(10 + look, 13 + look, 15 + y, "smile")

    hline(10, 15, 21 + y, "accent_dark")                                         # vents
    hline(10, 15, 23 + y, "accent_dark")

    oval(17, 15 + y + front_up, 21, 20 + y + front_up, "outline")                # front arm
    oval(18, 16 + y + front_up, 20, 19 + y + front_up, "accent")
    oval(11 + swing, 27 - front_up, 16 + swing, 31 - front_up, "outline")       # front foot
    oval(12 + swing, 28 - front_up, 15 + swing, 30 - front_up, "accent")


# ---------- build ----------
def build_scene():
    rng = random.Random(7)
    far = make_far(rng)
    mid, turbines, vents = make_mid(rng)
    return dict(sky=make_sky(), stars=make_stars() if C is NIGHT else [], clouds=make_clouds(), far=far,
                mid=mid, turbines=turbines, vents=vents, ground=make_ground())


def render(scene, f):
    img = scene["sky"].copy()
    d = ImageDraw.Draw(img)
    draw_stars(d, scene["stars"], f)
    paste_scrolled(img, scene["clouds"], f // CLOUD_EVERY)
    paste_scrolled(img, scene["far"], f * FAR_SPEED)
    paste_scrolled(img, scene["mid"], f * MID_SPEED)
    draw_turbines(d, scene["turbines"], f)
    draw_steam(d, scene["vents"], f)
    paste_scrolled(img, scene["ground"], f * GROUND_SPEED, GROUND_Y)
    draw_near_turbine(d, f)
    draw_stelly(d, f)
    return img


def check_loop(scene):
    """Frame N must match frame 0 exactly, or the GIF jumps when it restarts."""
    periods = [WALK_PERIOD, STAR_PERIOD, TURBINE_PERIOD, STEAM_PERIOD, BLINK_PERIOD, GLANCE_PERIOD]
    assert all(N % p == 0 for p in periods), "an animation period does not divide N"
    assert (N // CLOUD_EVERY) % CLOUD_TILE == 0
    assert (N * FAR_SPEED) % FAR_TILE == 0
    assert (N * MID_SPEED) % MID_TILE == 0
    assert (N * GROUND_SPEED) % GROUND_TILE == 0
    assert (N * NEAR_SPEED) % NEAR_TILE == 0
    assert render(scene, 0).tobytes() == render(scene, N).tobytes(), "loop is not seamless"


def save_theme(name, preview):
    global C
    C = THEMES[name]
    scene = build_scene()
    check_loop(scene)

    palette = Image.new("P", (1, 1))
    flat = [v for c in C.values() for v in c]
    palette.putpalette(flat + [0] * (768 - len(flat)))

    frames = []
    for f in range(N):
        big = render(scene, f).resize((W * SCALE, H * SCALE), Image.NEAREST)
        frames.append(big.quantize(palette=palette, dither=Image.Dither.NONE))
        if preview and f in (0, 60, 120, 180):
            big.save(f"preview-{name}-{f}.png")

    out = f"stelly-{name}.gif"
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=FRAME_MS,
                   loop=0, disposal=1, optimize=False)
    print(f"saved {out}: {N} frames, {N * FRAME_MS / 1000:.0f}s loop")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", choices=["night", "day", "both"], default="both")
    ap.add_argument("--preview", action="store_true", help="save a few PNG frames")
    args = ap.parse_args()
    for name in (["night", "day"] if args.theme == "both" else [args.theme]):
        save_theme(name, args.preview)


if __name__ == "__main__":
    main()
