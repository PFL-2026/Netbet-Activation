#!/usr/bin/env python3
"""
make_netbet.py — deterministic PFL x NetBet deck build.

Rebuilds from a pristine Polymarket GitHub checkout in a single verified pass.
No stateful edits: run it twice, get byte-identical output.

Usage:  python3 make_netbet.py
"""

import io
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/home/claude")
SRC = ROOT / "polymarket"          # pristine checkout
NB = ROOT / "netbet_assets"        # supplied NetBet assets
OUT = ROOT / "netbet"              # build target

CACHE_BUST = "20260818-netbet1"

# NetBet brand palette, sampled from the supplied logo
NB_RED = "#c62026"
NB_RED_DEEP = "#8e1319"
NB_RED_BRIGHT = "#e63a41"
NB_RED_RGB = (198, 32, 38)

FAILURES = []
CHECKS = 0


def check(cond, label):
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILURES.append(label)


def sub1(text, pattern, repl, label, count=1, flags=0):
    """Regex-replace with an exact-hit-count assertion."""
    new, n = re.subn(pattern, repl, text, count=count, flags=flags)
    check(n == count, f"{label} (expected {count} replacement(s), made {n})")
    return new


def subN(text, pattern, repl, label, flags=0):
    """Regex-replace all, asserting at least one hit."""
    new, n = re.subn(pattern, repl, text, flags=flags)
    check(n > 0, f"{label} (expected >=1 replacement, made 0)")
    return new


# ---------------------------------------------------------------------------
# 1. Pristine source
# ---------------------------------------------------------------------------

def prepare_source():
    if not SRC.exists():
        subprocess.run(
            ["git", "clone", "--depth", "1",
             "https://github.com/PFL-2026/Polymarket.git", str(SRC)],
            check=True, capture_output=True,
        )
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC, OUT, ignore=shutil.ignore_patterns(".git"))
    print(f"  source staged -> {OUT}")


# ---------------------------------------------------------------------------
# 2. Images
# ---------------------------------------------------------------------------

# NetBet source file -> target filename in assets/images/
# Mapped by *content*, not by supplied filename (a couple are swapped).
IMAGE_MAP = {
    "NB Brand Awareness.png":     "netbet_brand_awareness.jpg",   # slide 2, pillar 01
    "NB User Acquisition.png":    "netbet_acquisition.jpg",       # slide 2, pillar 02
    "NB Integrated Content.png":  "netbet_integrated_content.jpg",# slide 2, pillar 03
    "NB Cage Branding.png":       "netbet_cage_branding.jpg",     # slide 6
    "NB Centre Canvas.png":       "netbet_centre_canvas.jpg",     # slide 5
    "NB LED Screens.png":         "netbet_prediction_walkouts.jpg",  # slide 9
    "NB Social Integration.png":  "netbet_social_integration.jpg",# slide 10 (was 11)
    "NB Social Series 2.png":     "netbet_social_port_1.jpg",     # "By the Numbers"
    "NB social series 1.png":     "netbet_social_port_2.jpg",     # "24-4 Record"
    "NB live odds cut in.png":    "netbet_live_odds_cutin.jpg",   # slide 12
    "NB led 1.png":               "netbet_led_1.jpg",             # slide 13
    "NB led 2.png":               "netbet_led_2.jpg",             # slide 13
    "NB highlights.png":          "netbet_highlights.jpg",        # slide 16
    "NB background image.png":    "netbet_watch_bet.png",         # slide 15
    "NB cap.png":                 "netbet_cap.jpg",
    "NB hoodie.png":              "netbet_hoodie.jpg",
    "NB shorts.png":              "netbet_shorts.jpg",
    "NB t shirt.png":             "netbet_tshirt.jpg",
}

# Polymarket originals that are simply renamed (no NetBet replacement supplied)
RENAME_ONLY = {
    "polymarket_watch_bet_poster.jpg": "netbet_watch_bet_poster.jpg",
}

# Dropped with slide 10 (Fightshift Meter)
DELETE_IMAGES = ["polymarket_fightshift_meter.jpg"]


def build_images():
    img_dir = OUT / "assets" / "images"

    for src_name, target in IMAGE_MAP.items():
        src = NB / src_name
        check(src.exists(), f"source asset present: {src_name}")
        if not src.exists():
            continue
        im = Image.open(src)
        dst = img_dir / target
        if target.lower().endswith(".png"):
            im.convert("RGBA").save(dst, "PNG", optimize=True)
        else:
            im.convert("RGB").save(dst, "JPEG", quality=88, optimize=True,
                                   progressive=True)
        check(dst.exists() and dst.stat().st_size > 5000, f"image written: {target}")

    for old, new in RENAME_ONLY.items():
        p = img_dir / old
        check(p.exists(), f"rename source present: {old}")
        if p.exists():
            p.rename(img_dir / new)

    # Superseded Polymarket originals
    for p in sorted(img_dir.glob("polymarket_*")):
        if p.name not in DELETE_IMAGES:
            p.unlink()

    for name in DELETE_IMAGES:
        p = img_dir / name
        if p.exists():
            p.unlink()
        check(not p.exists(), f"deleted orphan image: {name}")

    leftovers = sorted(p.name for p in img_dir.glob("polymarket_*"))
    check(not leftovers, f"no polymarket_* images remain (found {leftovers})")
    print(f"  images: {len(IMAGE_MAP)} replaced, "
          f"{len(RENAME_ONLY)} renamed, {len(DELETE_IMAGES)} deleted")


# ---------------------------------------------------------------------------
# 3. Logos
# ---------------------------------------------------------------------------

def _recolour_netbet(im, net_colour):
    """Recolour the dark 'Net' half of the NetBet wordmark, keep 'Bet' red."""
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            # red glyphs: strongly red-dominant
            if r > 120 and r > g * 2 and r > b * 2:
                px[x, y] = (NB_RED_RGB[0], NB_RED_RGB[1], NB_RED_RGB[2], a)
            else:
                px[x, y] = (*net_colour, a)
    return im


def _all_white(im):
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            a = px[x, y][3]
            px[x, y] = (255, 255, 255, a) if a else (255, 255, 255, 0)
    return im


def _tracked_text(draw, xy, text, font, fill, track):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + track


def _tracked_width(draw, text, font, track):
    return sum(draw.textlength(c, font=font) + track for c in text) - track


def patch_legacy_branding():
    """Overpaint competitor branding baked into inherited photography.

    Two assets survived from earlier versions of this deck and carry rival
    marks: social_grid.jpg ("PRESENTED BY: ARKHAM") and Slide_14.jpg (a
    "Liga Stavok" LED barrier band). Both get a flat-fill patch plus a
    centred NetBet lockup, matching the deck's established overlay treatment.
    """
    import random

    img_dir = OUT / "assets" / "images"
    logo = Image.open(OUT / "assets" / "logos" / "netbet.png").convert("RGBA")
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    # --- social_grid.jpg: swap the presented-by strip -------------------
    p = img_dir / "social_grid.jpg"
    im = Image.open(p).convert("RGB")
    w, h = im.size
    check((w, h) == (540, 799), "social_grid.jpg has expected dimensions")
    y0, y1 = 668, 730
    d = ImageDraw.Draw(im)
    d.rectangle([0, y0, w, y1], fill=(4, 4, 6))
    font = ImageFont.truetype(font_path, 15)
    label, track = "PRESENTED BY:", 3.2
    lw = _tracked_width(d, label, font, track)
    lg = logo.copy()
    lg.thumbnail((400, 30), Image.LANCZOS)
    gap = 16
    sx = (w - (lw + gap + lg.width)) / 2
    cy = (y0 + y1) / 2
    _tracked_text(d, (sx, cy - 9), label, font, (255, 255, 255), track)
    im.paste(lg, (int(sx + lw + gap), int(cy - lg.height / 2)), lg)
    im.save(p, "JPEG", quality=92, optimize=True)

    # --- Slide_14.jpg: rebuild the LED barrier band ---------------------
    p = img_dir / "Slide_14.jpg"
    im = Image.open(p).convert("RGB")
    w, h = im.size
    check((w, h) == (1568, 784), "Slide_14.jpg has expected dimensions")
    y0, y1 = 636, 763
    d = ImageDraw.Draw(im)
    for y in range(y0, y1):
        t = (y - y0) / (y1 - y0)
        v = int(19 - 8 * t)
        d.line([(0, y), (w, y)], fill=(v, int(v * 0.72), int(v * 0.85)))
    rnd = random.Random(7)  # fixed seed -> deterministic grain
    px = im.load()
    for _ in range(9000):
        x = rnd.randrange(w)
        y = rnd.randrange(y0, y1)
        r, g, b = px[x, y]
        n = rnd.randint(-3, 4)
        px[x, y] = (max(0, r + n), max(0, g + n), max(0, b + n))
    lg = logo.copy()
    lg.thumbnail((520, 58), Image.LANCZOS)
    # Knock the lockups back so they read as dim LED, not a bright overlay
    alpha = lg.getchannel("A").point(lambda v: int(v * 0.68))
    lg.putalpha(alpha)
    for i in range(4):
        cx = int(w * (i + 0.5) / 4)
        im.paste(lg, (cx - lg.width // 2, (y0 + y1) // 2 - lg.height // 2), lg)
    im.save(p, "JPEG", quality=92, optimize=True)

    # Assert the rival marks are gone
    import numpy as np
    a = np.asarray(Image.open(img_dir / "Slide_14.jpg").convert("RGB")).astype(int)
    green = ((a[:, :, 1] > a[:, :, 0] + 30) & (a[:, :, 1] > a[:, :, 2] + 20)
             & (a[:, :, 1] > 45))
    check(green[600:, :].sum() < 200,
          f"Liga Stavok green band cleared (residual {green[600:, :].sum()}px)")
    print("  legacy branding patched: social_grid (ARKHAM), Slide_14 (Liga Stavok)")


def build_logos():
    logo_dir = OUT / "assets" / "logos"
    src_logos = NB / "logos"

    master = Image.open(src_logos / "Netbet logo.png").convert("RGBA")

    # Primary mark for the deck's dark surfaces: white "Net" + brand red "Bet"
    _recolour_netbet(master, (255, 255, 255)).save(
        logo_dir / "netbet.png", "PNG", optimize=True)
    # Mono white for the broadcast TV watermark
    _all_white(master).save(logo_dir / "netbet-white.png", "PNG", optimize=True)

    check((logo_dir / "netbet.png").exists(), "logo written: netbet.png")
    check((logo_dir / "netbet-white.png").exists(), "logo written: netbet-white.png")

    # --- Broadcast partner logos ---------------------------------------
    # Reversed out for the dark panel: navy/black elements become white,
    # brand reds are preserved, backgrounds keyed to transparent.
    import cairosvg
    import numpy as np

    def _redmask(arr):
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        return (r > 110) & (r > g * 1.7) & (r > b * 1.7)

    def _whiten(im, only_dark=False):
        a = np.array(im.convert("RGBA")).astype(int)
        keep = _redmask(a)
        target = a[..., 3] > 0
        if only_dark:
            target &= (a[..., 0] < 140) & (a[..., 1] < 140) & (a[..., 2] < 140)
        m = target & ~keep
        for ch in range(3):
            a[..., ch] = np.where(m, 255, a[..., ch])
        return Image.fromarray(a.astype("uint8"))

    rmc_png = cairosvg.svg2png(url=str(src_logos / "RMC Sport.svg"),
                               output_width=1000)
    rmc = Image.open(io.BytesIO(rmc_png)).convert("RGBA")
    rmc = _whiten(rmc.crop(rmc.getbbox()))
    rmc.save(logo_dir / "rmc-sport.png", "PNG", optimize=True)

    yt = Image.open(src_logos / "YouTube.png").convert("RGBA")
    yt = _whiten(yt.crop(yt.getbbox()), only_dark=True)
    yt.thumbnail((1200, 1200), Image.LANCZOS)
    yt.save(logo_dir / "youtube.png", "PNG", optimize=True)

    # talkSPORT ships as a JPEG: crop off the white outer margin, then key
    # the black plate out to transparent via a luminance ramp.
    talk = Image.open(src_logos / "talkSPORT logo.jpeg").convert("RGB")
    talk = talk.crop((4, 4, talk.width - 4, talk.height - 4))
    a = np.array(talk).astype(int)
    lum = a.max(axis=2)
    alpha = np.clip((lum - 28) * (255 / 122), 0, 255)
    Image.fromarray(np.dstack([a[..., 0], a[..., 1], a[..., 2],
                               alpha]).astype("uint8")).save(
        logo_dir / "talksport.png", "PNG", optimize=True)

    for name in ("rmc-sport.png", "talksport.png", "youtube.png"):
        p = logo_dir / name
        check(p.exists(), f"logo written: {name}")
        check(Image.open(p).mode == "RGBA", f"{name} has an alpha channel")

    # --- Retire Polymarket + ESPN --------------------------------------
    for name in ("polymarket.png", "polymarket-white.png", "polymarket.svg",
                 "espn.png"):
        p = logo_dir / name
        if p.exists():
            p.unlink()
        check(not p.exists(), f"retired logo: {name}")

    print("  logos: netbet, netbet-white, rmc-sport, talksport, youtube")


def build_icons():
    """Favicon set — NetBet red tile with a white 'N'. Placeholder-grade."""
    icon_dir = OUT / "assets" / "icons"

    def tile(size):
        im = Image.new("RGBA", (size, size), (*NB_RED_RGB, 255))
        d = ImageDraw.Draw(im)
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                int(size * 0.72))
        except OSError:
            font = ImageFont.load_default()
        bbox = d.textbbox((0, 0), "N", font=font)
        d.text(((size - (bbox[2] - bbox[0])) / 2 - bbox[0],
                (size - (bbox[3] - bbox[1])) / 2 - bbox[1]),
               "N", font=font, fill=(255, 255, 255, 255))
        return im

    tile(32).save(icon_dir / "favicon-32.png")
    tile(192).save(icon_dir / "favicon-192.png")
    tile(180).save(icon_dir / "apple-touch-icon.png")
    tile(64).save(icon_dir / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    for name in ("favicon-32.png", "favicon-192.png",
                 "apple-touch-icon.png", "favicon.ico"):
        check((icon_dir / name).exists(), f"icon written: {name}")
    print("  icons: favicon set regenerated")


# ---------------------------------------------------------------------------
# 4. Video
# ---------------------------------------------------------------------------

def build_video():
    vid_dir = OUT / "assets" / "video"
    pairs = [("fighter_intro_netbet.mp4", "fighter_intro.mp4"),
             ("tale_of_the_tape_netbet.mp4", "tale_of_the_tape.mp4")]
    for src_name, target in pairs:
        src = NB / src_name
        check(src.exists(), f"video source present: {src_name}")
        if src.exists():
            shutil.copy2(src, vid_dir / target)
            check((vid_dir / target).stat().st_size > 1_000_000,
                  f"video written: {target}")
    print("  video: fighter_intro + tale_of_the_tape replaced with NetBet cuts")


# ---------------------------------------------------------------------------
# 5. HTML
# ---------------------------------------------------------------------------

SLIDE4_TEXT_OLD = """    <div class="slide-body">Co-branded Polymarket placements run live on the ESPN US broadcast — banner overlays, sponsor graphics and on-screen promos.</div>
    <div class="social-stats" style="margin-top: 32px;">
      <div class="stat-card"><div class="num">16</div><div class="label">PFL Global Events each year</div></div>
      <div class="stat-card"><div class="num">250k</div><div class="label">Average Unique Viewers</div></div>
      <div class="stat-card"><div class="num">US</div><div class="label">Territory Only</div></div>
    </div>
    <div class="broadcast-on">
      <div class="broadcast-on-label">Broadcast on</div>
      <div class="broadcast-on-logos">
        <div class="bcast-espn-box">
          <img src="assets/logos/espn.png" alt="ESPN" class="bcast-espn-logo" loading="lazy">
        </div>
      </div>
    </div>"""

SLIDE4_TEXT_NEW = """    <div class="slide-body">Co-branded NetBet placements run live across the RMC Sport, talkSPORT and YouTube broadcasts — banner overlays, sponsor graphics and on-screen promos.</div>
    <div class="social-stats" style="margin-top: 32px;">
      <div class="stat-card"><div class="num">2</div><div class="label">PFL Events across territories</div></div>
      <div class="stat-card"><div class="num">450k</div><div class="label">Average Unique Viewers</div></div>
      <div class="stat-card"><div class="num">FR &middot; UK</div><div class="label">Territories</div></div>
    </div>
    <div class="broadcast-on">
      <div class="broadcast-on-label">Broadcast on</div>
      <div class="broadcast-on-logos">
        <div class="bcast-partner">
          <div class="bcast-country">France</div>
          <img src="assets/logos/rmc-sport.png" alt="RMC Sport" class="bcast-logo-lg" loading="lazy">
        </div>
        <div class="bcast-partner">
          <div class="bcast-country">UK</div>
          <img src="assets/logos/talksport.png" alt="talkSPORT" class="bcast-logo-lg" loading="lazy">
        </div>
        <div class="bcast-partner">
          <div class="bcast-country">France &amp; UK</div>
          <img src="assets/logos/youtube.png" alt="YouTube" class="bcast-logo-lg" loading="lazy">
        </div>
      </div>
    </div>"""

BCAST_MODAL_OLD_START = '      <!-- Headline metrics row — 2026 US viewership -->'
BCAST_MODAL_OLD_END = '      <footer class="terms-print-footer">\n        <div>PFL × Polymarket · Broadcast Distribution · Confidential</div>'

BCAST_MODAL_NEW = """      <!-- Headline metrics row — 2026 France & UK viewership -->
      <section class="dist-section">
        <h3 class="terms-section-title">2026 Viewership <span class="dist-section-sub">France &amp; UK broadcast</span></h3>
        <div class="dist-metrics">
          <div class="dist-metric">
            <div class="dist-metric-num">450<span class="dist-metric-unit">k</span></div>
            <div class="dist-metric-label">Average Unique Viewers</div>
            <div class="dist-metric-context">per fight card</div>
          </div>
          <div class="dist-metric">
            <div class="dist-metric-num">137<span class="dist-metric-unit">min</span></div>
            <div class="dist-metric-label">Avg Watch Time</div>
            <div class="dist-metric-context">per viewer</div>
          </div>
          <div class="dist-metric">
            <div class="dist-metric-num">2</div>
            <div class="dist-metric-label">PFL Events</div>
            <div class="dist-metric-context">across territories</div>
          </div>
        </div>
      </section>

      <!-- France & UK distribution -->
      <section class="dist-section">
        <h3 class="terms-section-title">France</h3>
        <div class="dist-channel-grid">
          <div class="dist-channel">
            <div class="dist-channel-tag">Linear feed</div>
            <h4>RMC Sport</h4>
            <ul>
              <li>All broadcast integrations delivered via the <strong>RMC Sport French feed</strong></li>
              <li>Banner overlays, sponsor graphics and on-screen promos across <strong>all RMC Sport coverage</strong></li>
              <li>Geo-targeted to France</li>
            </ul>
          </div>
        </div>
      </section>

      <section class="dist-section">
        <h3 class="terms-section-title">United Kingdom</h3>
        <div class="dist-channel-grid">
          <div class="dist-channel">
            <div class="dist-channel-tag">Linear feed</div>
            <h4>talkSPORT</h4>
            <ul>
              <li>All broadcast integrations delivered via the <strong>talkSPORT UK feed</strong></li>
              <li>Banner overlays, sponsor graphics and on-screen promos across <strong>all talkSPORT coverage</strong></li>
              <li>Geo-targeted to the United Kingdom</li>
            </ul>
          </div>
        </div>
      </section>

      <section class="dist-section">
        <h3 class="terms-section-title">Streaming</h3>
        <div class="dist-channel-grid">
          <div class="dist-channel">
            <div class="dist-channel-tag">Digital feed</div>
            <h4>YouTube</h4>
            <ul>
              <li>Live and on-demand PFL coverage carried across <strong>YouTube</strong> in both territories</li>
              <li>Same co-branded overlay and sponsor-graphic package as the linear feeds</li>
              <li>Geo-targeted to France and the United Kingdom</li>
            </ul>
          </div>
        </div>
      </section>

"""

COMMERCIALS_MODAL = """
<!-- Commercials Modal — opens from the top nav. Source: NetBet_Terms_Sheet_26-27.pptx -->
<div class="dist-modal terms-modal" id="commercialsModal" aria-hidden="true" role="dialog" aria-modal="true" aria-labelledby="commercialsTitle">
  <div class="terms-modal-backdrop" data-close-dist-modal></div>
  <div class="terms-modal-shell">
    <header class="terms-modal-header">
      <div class="terms-modal-titles">
        <div class="terms-modal-eyebrow">Heads of Terms · Confidential</div>
        <h2 id="commercialsTitle" class="terms-modal-title">Commercial <span class="ls-accent">Terms</span></h2>
      </div>
      <div class="terms-modal-actions">
        <button type="button" class="terms-modal-print" data-print-dist aria-label="Download as PDF">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
          <span>Download PDF</span>
        </button>
        <button type="button" class="terms-modal-close" data-close-dist-modal aria-label="Close">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M18 6L6 18"/></svg>
        </button>
      </div>
    </header>

    <div class="terms-modal-body">
      <div class="terms-print-header">
        <div class="terms-print-eyebrow">Heads of Terms · Confidential</div>
        <h1>PFL × NetBet Partnership</h1>
        <div class="terms-print-meta">2026–2027 · France &amp; United Kingdom</div>
      </div>

      <section class="dist-section">
        <h3 class="terms-section-title">Partnership Framework</h3>
        <dl class="terms-grid">
          <dt>Term<span class="terms-grid-sub">2 years</span></dt>
          <dd>Two-year partnership (2026&ndash;2027).
            <ul>
              <li>Year 1: Effective Date &ndash; December 31, 2026</li>
              <li>Year 2: January 1, 2027 &ndash; December 31, 2027</li>
            </ul>
          </dd>

          <dt>Franchises &amp; Events</dt>
          <dd>
            <ul>
              <li><strong>2026:</strong> PFL Lyon &mdash; LDLC Arena, Lyon (Saturday, December 19, 2026)</li>
              <li><strong>2027:</strong> A minimum of two (2) PFL Events hosted within the Territory</li>
            </ul>
          </dd>

          <dt>Territories</dt>
          <dd>France and the United Kingdom</dd>

          <dt>Financial Commitment</dt>
          <dd>
            <ul>
              <li><strong>2026:</strong> &euro;150,000</li>
              <li><strong>2027:</strong> &euro;350,000</li>
              <li>Virtual overlay branding at out-of-Territory events: &euro;20,000 per event, per market</li>
              <li>Athlete ambassadors: costed as an additional line item (see <em>Athlete Ambassador Program</em>, asset 10)</li>
            </ul>
          </dd>
        </dl>
      </section>

      <section class="dist-section">
        <h3 class="terms-section-title">Guaranteed Territory Events &amp; Status</h3>
        <dl class="terms-grid">
          <dt>2026<span class="terms-grid-sub">one event</span></dt>
          <dd>One (1) Event hosted within the Territory &mdash; PFL Lyon, LDLC Arena, December 19, 2026. NetBet to receive <strong>Presenting Partner status</strong> and <strong>exclusive betting category rights</strong> in France and the United Kingdom.</dd>

          <dt>From Jan 1, 2027<span class="terms-grid-sub">two events p.a.</span></dt>
          <dd>PFL guarantees a minimum of two (2) Events per calendar year hosted within the Territory, comprising one (1) Event in France and one (1) Event in the United Kingdom. All guaranteed Territory Events shall include the rights and deliverables set out under <em>Partnership Assets</em> below.</dd>
        </dl>
      </section>

      <section class="dist-section">
        <h3 class="terms-section-title">Partnership Assets</h3>

        <div class="terms-asset">
          <div class="terms-asset-num">01</div>
          <div class="terms-asset-body">
            <h4>Trademark Rights &amp; Official Designations</h4>
            <ul>
              <li>Use of PFL official marks across all marketing platforms</li>
              <li>2026&ndash;2027 &mdash; &lsquo;Exclusive Betting Partner of PFL in France &amp; the United Kingdom&rsquo;; 2026 &mdash; &lsquo;Presenting Partner of PFL Lyon&rsquo;, or other mutually agreed designations</li>
              <li>Non-exclusive designations: &lsquo;Official Partner of PFL&rsquo;</li>
            </ul>
          </div>
        </div>

        <div class="terms-asset">
          <div class="terms-asset-num">02</div>
          <div class="terms-asset-body">
            <h4>Broadcast Integrations</h4>
            <ul>
              <li>NetBet to receive access to custom broadcast opportunities per event, which may include promotional billboards, lower third on-screen / Fight Presenter / Tale of the Tape graphic, and live odds integration</li>
              <li>All of the above subject to approvals with the broadcaster</li>
              <li>All broadcast display limited to feeds distributed solely within the Territory</li>
            </ul>
          </div>
        </div>

        <div class="terms-asset">
          <div class="terms-asset-num">03</div>
          <div class="terms-asset-body">
            <h4>In-Arena Branding</h4>
            <ul>
              <li>1 &times; large canvas</li>
              <li>1 &times; vertical bumper</li>
              <li>One (1) additional full apron placement on cage</li>
            </ul>
          </div>
        </div>

        <div class="terms-asset">
          <div class="terms-asset-num">04</div>
          <div class="terms-asset-body">
            <h4>In-Territory Events <span class="terms-asset-sub">presented by NetBet</span></h4>
            <ul>
              <li>NetBet to be awarded <strong>Presenting Partner status</strong> of each Event in the Territory across 2026 and 2027</li>
              <li><strong>Event marketing &amp; promotion:</strong> NetBet featured and tagged (where appropriate) as presenting partner across all pre-event marketing and promotion &mdash; e.g. &lsquo;PFL Lyon presented by NetBet&rsquo;</li>
              <li><strong>Broadcast integration:</strong>
                <ul>
                  <li>Logo and audio recognition as presenting partner on the show title card open</li>
                  <li>Two (2) &lsquo;Welcome Back Bumpers&rsquo; returning from commercial break, with graphical overlay</li>
                  <li>NetBet presentation of all fight cards</li>
                  <li>NetBet mark alongside the Fight Clock for the first thirty (30) seconds of all Main and Co-Main Events</li>
                </ul>
              </li>
            </ul>
          </div>
        </div>

        <div class="terms-asset">
          <div class="terms-asset-num">05</div>
          <div class="terms-asset-body">
            <h4>Social Content Distribution</h4>
            <ul>
              <li>A total of three (3) social media posts per event</li>
              <li>Logo inclusion and tag of NetBet on each post</li>
            </ul>
          </div>
        </div>

        <div class="terms-asset">
          <div class="terms-asset-num">06</div>
          <div class="terms-asset-body">
            <h4>Virtual Overlay Branding</h4>
            <ul>
              <li>Virtual logo placement at out-of-Territory events on one (1) large canvas, one (1) vertical bumper and one (1) inner middle canvas position</li>
              <li><strong>NetBet will be the exclusive betting operator featured on the canvas</strong></li>
              <li>Charged at &euro;20,000 per event, per market</li>
              <li>Events and markets to be selected by NetBet</li>
              <li>All broadcast display limited to feeds distributed solely within the Territory</li>
            </ul>
          </div>
        </div>

        <div class="terms-asset">
          <div class="terms-asset-num">07</div>
          <div class="terms-asset-body">
            <h4>Sponsored LED Wristbands</h4>
            <ul>
              <li>PFL shall distribute NetBet-branded LED light-up wristbands to attendees</li>
              <li>Wristbands will light up throughout the night for each Sponsored Event to create in-arena fan engagement opportunities reasonably satisfactory to Sponsor</li>
            </ul>
          </div>
        </div>

        <div class="terms-asset">
          <div class="terms-asset-num">08</div>
          <div class="terms-asset-body">
            <h4>PFL Digital &amp; Video Content</h4>
            <ul>
              <li>Pre-event: press conferences, weigh-ins, face-offs, promos, fighter media-day cutdowns</li>
              <li>During event: rapid-turn highlight cutdowns</li>
              <li>Post-event: official photos and recap videos</li>
              <li>All content may be used across NetBet-owned channels, with specified rules</li>
            </ul>
          </div>
        </div>

        <div class="terms-asset">
          <div class="terms-asset-num">09</div>
          <div class="terms-asset-body">
            <h4>Watch &amp; Bet Streaming</h4>
            <ul>
              <li>NetBet will receive non-exclusive live event Watch &amp; Bet rights during the Term &mdash; e.g. live event stream for distribution on Brand platforms, via the PFL</li>
            </ul>
          </div>
        </div>

        <div class="terms-asset">
          <div class="terms-asset-num">10</div>
          <div class="terms-asset-body">
            <h4>Athlete Ambassador Program</h4>
            <ul>
              <li>Access to two (2) fighters from the PFL roster per Event hosted within the Territory to act as NetBet ambassadors, costed as an additional line item</li>
              <li>PFL will work with NetBet to define roles &amp; responsibilities, which can include digital content support, fight kit logo inclusion, consumer-facing programs (appearances / autograph signings), and other roles as mutually agreed</li>
            </ul>
          </div>
        </div>

        <div class="terms-asset">
          <div class="terms-asset-num">11</div>
          <div class="terms-asset-body">
            <h4>VIP Hospitality &amp; Access <span class="terms-asset-sub">NetBet to receive per event</span></h4>
            <ul>
              <li>Three (3) VIP tickets</li>
              <li>Five (5) GA tickets</li>
              <li>Additional ideas may include: on stage + meet and greet at weigh-ins; hosted backstage tour during fight night; invitation to press conferences, weigh-ins and face-offs</li>
            </ul>
          </div>
        </div>

        <div class="terms-asset">
          <div class="terms-asset-num">12</div>
          <div class="terms-asset-body">
            <h4>Account Management</h4>
            <ul>
              <li>For each year of the partnership, PFL will provide NetBet with an Account Director / point-of-contact for turnkey execution of the partnership</li>
            </ul>
          </div>
        </div>
      </section>

      <footer class="terms-print-footer">
        <div>PFL × NetBet · Heads of Terms · Confidential</div>
        <div>2026–2027 · France &amp; United Kingdom</div>
      </footer>
    </div>
  </div>
</div>
"""


def build_html():
    p = OUT / "index.html"
    h = p.read_text()

    # --- 5a. Slide 10 (Fightshift Meter) removal -----------------------
    m = re.search(
        r'\n<section class="slide content-slide flip" data-slide="10">.*?'
        r'<div class="slide-num">10 / 19</div>\n</section>\n',
        h, re.S)
    check(m is not None, "slide 10 block located for deletion")
    if m:
        h = h[:m.start()] + "\n" + h[m.end():]
    check('data-slide="10">' not in h or 'fightshift' not in h.lower(),
          "Fightshift Meter markup removed")

    # --- 5b. Renumber slides 11-19 -> 10-18 ----------------------------
    for old in range(11, 20):
        new = old - 1
        h = sub1(h, rf'<section class="slide([^"]*)" data-slide="{old}">',
                 rf'<section class="slide\1" data-slide="{new}">',
                 f"renumber section data-slide {old}->{new}")
        h = sub1(h, rf'<div class="slide-num">{old:02d} / 19</div>',
                 f'<div class="slide-num">{new:02d} / 18</div>',
                 f"renumber slide-num {old}->{new}")
    # Slides 1-9 keep their number, only the denominator changes
    for n in range(2, 10):
        h = sub1(h, rf'<div class="slide-num">{n:02d} / 19</div>',
                 f'<div class="slide-num">{n:02d} / 18</div>',
                 f"denominator on slide {n}")

    # --- 5c. Top-bar counter + nav -------------------------------------
    h = sub1(h, r'<span class="cur" id="curSlide">01</span> / 19',
             '<span class="cur" id="curSlide">01</span> / 18',
             "top-bar slide counter denominator")
    check("/ 19" not in h, "no '/ 19' labels remain")

    h = sub1(
        h,
        r'<button class="section-btn" data-section="3" data-target="9">Participation</button>',
        '<button class="section-btn" data-section="3" data-target="9">Acquisition</button>',
        "nav label Participation -> Acquisition")
    h = sub1(h, r'<button class="section-btn" data-section="4" data-target="15">Content</button>',
             '<button class="section-btn" data-section="4" data-target="14">Content</button>',
             "nav target Content 15->14")
    h = sub1(h, r'<button class="section-btn" data-section="5" data-target="18">Hospitality</button>',
             '<button class="section-btn" data-section="5" data-target="17">Hospitality</button>',
             "nav target Hospitality 18->17")
    h = sub1(h, r'<button class="section-btn" data-section="7" data-target="19">Close</button>',
             '<button class="section-btn" data-section="6" data-target="18">Close</button>\n'
             '<button class="section-btn section-btn-modal" data-open-dist-modal="commercialsModal">Commercials</button>',
             "nav: Close retargeted + Commercials button appended")

    # --- 5d. Slide 4 rebuild -------------------------------------------
    check(SLIDE4_TEXT_OLD in h, "slide 4 text block located")
    h = h.replace(SLIDE4_TEXT_OLD, SLIDE4_TEXT_NEW, 1)

    # --- 5e. Broadcast distribution modal rebuild ----------------------
    i = h.find(BCAST_MODAL_OLD_START)
    j = h.find(BCAST_MODAL_OLD_END)
    check(i != -1 and j != -1 and i < j, "broadcast modal body located")
    if i != -1 and j != -1 and i < j:
        h = h[:i] + BCAST_MODAL_NEW + h[j:]

    h = sub1(h, r'PFL × Polymarket · 2026–2027 · United States · ESPN',
             'PFL × NetBet · 2026–2027 · France &amp; United Kingdom',
             "broadcast modal print meta")
    h = sub1(h, r'<div>2026–2027 · United States · ESPN</div>',
             '<div>2026–2027 · France &amp; United Kingdom</div>',
             "broadcast modal print footer meta")

    # --- 5f. Slide 7 ambassador swap -----------------------------------
    h = sub1(
        h,
        r'<img src="https://pflmma-prod\.s3\.amazonaws\.com/fighters/bodyshots/'
        r'8905364fb5a16f54ec8ca6eb3fcbfdfd-2\.png" alt="" onerror="this\.style\.display=\'none\'">',
        '<img src="https://pflmma-prod.s3.amazonaws.com/fighters/bodyshots/'
        '9cf13eefc6ab3bd880106403a12e79ce-2-1.png" alt="" onerror="this.style.display=\'none\'">',
        "ambassador 02 bodyshot -> Lapilus")
    h = sub1(h, r'<div class="full">Cris Cyborg</div>',
             '<div class="full">Taylor Lapilus</div>', "ambassador 02 name")
    h = sub1(h, r'<div class="country">BRA · Women\'s Featherweight Champion</div>',
             '<div class="country">FRA · Bantamweight Contender</div>',
             "ambassador 02 country/division")
    h = sub1(h, r'href="https://www\.instagram\.com/criscyborg/"',
             'href="https://www.instagram.com/taylor_d.i_lapilus/"',
             "ambassador 02 instagram href")
    h = sub1(h, r'aria-label="Cris Cyborg on Instagram"',
             'aria-label="Taylor Lapilus on Instagram"',
             "ambassador 02 instagram aria-label")
    h = sub1(h, r'<span>@criscyborg</span>', '<span>@taylor_d.i_lapilus</span>',
             "ambassador 02 instagram handle")
    h = sub1(h, r'<span class="amb-ig-followers">1M</span>',
             '<span class="amb-ig-followers">61K</span>',
             "ambassador 02 follower count")
    check("Cyborg" not in h, "no Cris Cyborg references remain")

    # --- 5g. Social integration figures --------------------------------
    h = sub1(h, r'<div class="stat-card"><div class="num">5\.5M</div>'
                r'<div class="label">Followers Reached</div></div>',
             '<div class="stat-card"><div class="num">2.7M</div>'
             '<div class="label">Followers Reached</div></div>',
             "slide 10 followers 5.5M -> 2.7M")
    h = sub1(h, r'<div class="dist-metric-num">5\.5<span class="dist-metric-unit">m</span></div>',
             '<div class="dist-metric-num">2.7<span class="dist-metric-unit">m</span></div>',
             "social modal followers 5.5m -> 2.7m")
    h = sub1(h, r'<div class="dist-metric-context">across PFL US channels</div>',
             '<div class="dist-metric-context">across PFL FR &amp; UK channels</div>',
             "social modal reach context")
    h = sub1(h, r'<h3 class="terms-section-title">Expected Reach '
                r'<span class="dist-section-sub">US · per fight card</span></h3>',
             '<h3 class="terms-section-title">Expected Reach '
             '<span class="dist-section-sub">France &amp; UK · per fight card</span></h3>',
             "social modal reach subtitle")
    h = sub1(h, r'<li>Distribution via established PFL Instagram, TikTok, Facebook '
                r'&amp; YouTube handles</li>',
             '<li>Distribution via established PFL Instagram, TikTok, Facebook '
             '&amp; YouTube handles across France &amp; the UK</li>',
             "social modal channel line")
    h = sub1(h, r'<p>Native video and photography from every US fight card\.</p>',
             '<p>Native video and photography from every PFL fight card across both territories.</p>',
             "social modal on-ground capture copy")
    h = sub1(h, r'<h4>ESPN Tune-In</h4>\s*\n\s*<p>Tune-in CTAs across all content '
                r'driving traffic to the ESPN US broadcast\.</p>',
             '<h4>Broadcast Tune-In</h4>\n              '
             '<p>Tune-in CTAs across all content driving traffic to the RMC Sport, '
             'talkSPORT and YouTube feeds.</p>',
             "social modal tune-in card")
    h = sub1(h, r'PFL × Polymarket · 2026 · United States',
             'PFL × NetBet · 2026 · France &amp; United Kingdom',
             "social modal print meta")
    h = sub1(h, r'<div>2026 · United States</div>',
             '<div>2026 · France &amp; United Kingdom</div>',
             "social modal print footer meta")

    # --- 5h. Prediction Walkouts copy (prediction-market -> sportsbook) --
    h = sub1(h, r'Every walkout becomes a live market moment — Polymarket questions '
                r'and real-time odds take over the arena halo',
             'Every walkout becomes a live betting moment — NetBet markets and '
             'real-time odds take over the arena halo',
             "slide 9 body copy reframed for sportsbook")

    # --- 5h2. Slide 9 visual panel gets a crop-anchor hook --------------
    h = sub1(h, r'<div class="content-visual">\s*\n\s*<img src="assets/images/'
                r'polymarket_prediction_walkouts\.jpg"',
             '<div class="content-visual walkout-visual">\n    '
             '<img src="assets/images/polymarket_prediction_walkouts.jpg"',
             "slide 9 visual panel tagged walkout-visual")

    # --- 5i. Colour-word copy ------------------------------------------
    h = sub1(h, r'synchronised sea of Polymarket blue',
             'synchronised sea of NetBet red', "LED wristband colour copy")

    # --- 5j. Section eyebrows / pillar title ---------------------------
    h = subN(h, r'<div class="eyebrow">User Participation</div>',
             '<div class="eyebrow">User Acquisition</div>',
             "eyebrow User Participation -> User Acquisition")
    h = sub1(h, r'<div class="pillar-title">User<br>Participation</div>',
             '<div class="pillar-title">User<br>Acquisition</div>',
             "pillar 02 title")
    h = sub1(h, r'engineered to drive reach, user participation and content velocity',
             'engineered to drive reach, user acquisition and content velocity',
             "pillar subtitle copy")
    check(not re.search(r'participation', h, re.I), "no 'participation' strings remain")

    # --- 5k. Pillar 01 gets its own image ------------------------------
    h = sub1(h, r"<div class=\"pillar-img\" style=\"background-image:"
                r"url\('assets/images/polymarket_cage_branding\.jpg'\)\"></div>",
             "<div class=\"pillar-img\" style=\"background-image:"
             "url('assets/images/netbet_brand_awareness.jpg')\"></div>",
             "pillar 01 image -> netbet_brand_awareness")

    # --- 5l. Global asset path + brand-string rewrites ------------------
    h = subN(h, r'assets/images/polymarket_', 'assets/images/netbet_',
             "image paths polymarket_ -> netbet_")
    h = subN(h, r'assets/logos/polymarket-white\.png',
             'assets/logos/netbet-white.png', "white logo path")
    h = subN(h, r'assets/logos/polymarket\.png', 'assets/logos/netbet.png',
             "primary logo path")
    h = subN(h, r'Polymarket', 'NetBet', "brand string Polymarket -> NetBet")
    h = subN(h, r'polymarket', 'netbet', "lowercase brand string")

    # --- 5m. Cache-bust -------------------------------------------------
    h = sub1(h, r'css/styles\.css\?v=[^"]+', f'css/styles.css?v={CACHE_BUST}',
             "css cache-bust")
    h = sub1(h, r'js/deck\.js\?v=[^"]+', f'js/deck.js?v={CACHE_BUST}',
             "js cache-bust")

    # --- 5n. Commercials modal ------------------------------------------
    # MUST be inserted BEFORE the deck.js <script> tag. The script is not
    # deferred, so setupDistModals() captures .dist-modal at parse time —
    # anything appended after it never gets its close handlers bound.
    h = sub1(h, r'\n<script src="js/deck\.js',
             COMMERCIALS_MODAL + '\n<script src="js/deck.js',
             "commercials modal inserted ahead of deck.js")
    check(h.index('id="commercialsModal"') < h.index('<script src="js/deck.js'),
          "commercials modal precedes deck.js in document order")

    # --- final HTML assertions ------------------------------------------
    check("polymarket" not in h.lower(), "zero polymarket references in HTML")
    check("espn.png" not in h, "ESPN logo reference removed")
    check(h.count('data-slide="') == 18, "18 slide sections present")
    check('id="commercialsModal"' in h, "commercials modal present")
    check('>Commercials</button>' in h, "commercials nav button present")
    check(h.count('class="eyebrow">User Acquisition') == 5,
          "5 User Acquisition eyebrows (was 6, minus deleted slide)")
    check("450k" in h and "2.7M" in h, "new headline figures present")
    check("Taylor Lapilus" in h, "new ambassador present")

    p.write_text(h)
    print("  index.html rebuilt")


# ---------------------------------------------------------------------------
# 6. CSS
# ---------------------------------------------------------------------------

IG_PAIR_OLD = """.ig-series-pair {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 14px;
    box-sizing: border-box;
}
.ig-series-pair img {
    width: calc(50% - 6px);
    aspect-ratio: 1.3;
    height: auto;
    max-height: 100%;
    object-fit: cover;
    object-position: center;"""

IG_PAIR_NEW = """.ig-series-pair {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 16px;
    padding: 24px 30px;
    box-sizing: border-box;
}
/* NetBet social-series creatives are landscape (2.19 and 1.71), so they
   stack vertically instead of sitting side by side. Each max-height is its
   share of the column proportional to 1/aspect-ratio, which makes the two
   render at identical widths whether width or height is the binding
   constraint — tidy edges, and no crop or letterboxing either way. */
.ig-series-pair img {
    width: auto;
    max-width: 100%;
    height: auto;
    object-fit: contain;
    object-position: center;"""


def build_css():
    p = OUT / "css" / "styles.css"
    c = p.read_text()

    # --- 6a. Brand tokens ------------------------------------------------
    c = sub1(c, r'--pfl-red: #1ab0e6;', f'--pfl-red: {NB_RED};', "token --pfl-red")
    c = sub1(c, r'--pfl-red-deep: #0079ad;', f'--pfl-red-deep: {NB_RED_DEEP};',
             "token --pfl-red-deep")
    c = sub1(c, r'--ls-green: #1c59ff;', f'--ls-green: {NB_RED};', "token --ls-green")
    c = sub1(c, r'--ls-green-deep: #0e39b8;', f'--ls-green-deep: {NB_RED_DEEP};',
             "token --ls-green-deep")
    c = sub1(c, r'--ls-green-bright: #5c85ff;', f'--ls-green-bright: {NB_RED_BRIGHT};',
             "token --ls-green-bright")
    c = sub1(c,
             r'/\* Polymarket blue — replaces the former Polymarket blue scheme\.\n'
             r'       Variable names kept as --ls-\* so all existing references update at once\. \*/',
             '/* NetBet red — sampled from the supplied NetBet wordmark (#c62026).\n'
             '       Variable names kept as --ls-* so all existing references update at once. */',
             "token comment")

    # --- 6b. Hardcoded blues --------------------------------------------
    c = subN(c, r'#1c59ff', NB_RED, "hardcoded #1c59ff")
    c = subN(c, r'#0e39b8', NB_RED_DEEP, "hardcoded #0e39b8")
    c = subN(c, r'#0079ad', NB_RED_DEEP, "hardcoded #0079ad")
    c = subN(c, r'rgba\(28,\s*89,\s*255\s*,', 'rgba(198, 32, 38,',
             "hardcoded rgba(28,89,255)")
    check(not re.search(r'#1c59ff|#0e39b8|#5c85ff|#0079ad|#1ab0e6|rgba\(28,\s*89,\s*255',
                        c, re.I), "no Polymarket blues remain in CSS")

    # --- 6c. Social-series pair: stack landscape creatives ---------------
    check(IG_PAIR_OLD in c, "ig-series-pair block located")
    c = c.replace(IG_PAIR_OLD, IG_PAIR_NEW, 1)

    # --- 6d. Broadcast partner logo chips --------------------------------
    c = sub1(c, r'/\* Single prominent ESPN broadcast box \(US-only\) \*/\n'
                r'\.broadcast-on-logos:has\(\.bcast-espn-box\) \{\n'
                r'    grid-template-columns: 1fr;\n\}\n'
                r'\.bcast-espn-box \{.*?\n\}\n'
                r'\.bcast-espn-logo \{.*?\n\}\n',
             '',
             "dead ESPN CSS block removed", flags=re.S)
    check('.bcast-espn' not in c, "no ESPN-specific rules remain")

    # --- 6d2. Centre the broadcast box labels ----------------------------
    # text-align centres a wrapped second line; the text-indent cancels the
    # trailing letter-space that otherwise pulls tracked caps optically left.
    c = sub1(c, r'(\.bcast-country \{\n    font-family: var\(--font-cond\);\n)',
             r'\g<1>    text-align: center;\n    text-indent: 0.18em;\n',
             "bcast-country centred")

    # --- 6c2. Slide 10 zoom-out -----------------------------------------
    # The panel already uses contain + a transform-scale to fill; easing the
    # scale back is the zoom-out, and leaves size and layout untouched.
    c = sub1(c, r'(\.content-visual\.social-phone-visual img \{\n'
                r'    object-fit: contain;\n    padding: 0;\n'
                r'    box-sizing: border-box;\n    transform: scale\()1\.32(\);)',
             r'\g<1>1.12\g<2>', "slide 10 img scale 1.32 -> 1.12")
    c = sub1(c, r'(\.slide\.active \.content-visual\.social-phone-visual img \{\n'
                r'    transform: scale\()1\.32(\);)',
             r'\g<1>1.12\g<2>', "slide 10 active-state scale 1.32 -> 1.12")

    # --- 6e. Commercials nav button + placeholder ------------------------
    c += """

/* Height shares for the stacked social-series pair (see .ig-series-pair). */
.ig-series-pair img:nth-of-type(1) { max-height: calc((100% - 16px) * 0.438); }
.ig-series-pair img:nth-of-type(2) { max-height: calc((100% - 16px) * 0.562); }

/* Slide 09 — the walkout creative is portrait (0.89) in a landscape panel,
   so the crop is anchored high to keep the halo-screen lockup in frame. */
.content-visual.walkout-visual img {
    object-position: center 22%;
}

/* The dt qualifier sits on its own line under the label, not inline. */
.terms-grid-sub {
    display: block;
    margin-top: 5px;
}

/* === Commercials nav trigger (opens the commercial terms modal) === */
.section-btn.section-btn-modal {
    color: #fff;
    border: 1px solid var(--ls-green);
    background: rgba(198, 32, 38, 0.16);
    padding: 10px 17px;
    margin-left: 6px;
}
.section-btn.section-btn-modal:hover {
    background: var(--ls-green);
    box-shadow: 0 4px 16px rgba(198, 32, 38, 0.45);
}
.section-btn.section-btn-modal::after {
    transform: scaleX(0);
}
"""

    # --- 6f. Comment hygiene ---------------------------------------------
    c = subN(c, r'Polymarket', 'NetBet', "CSS comment brand strings")
    check("polymarket" not in c.lower(), "zero polymarket references in CSS")

    p.write_text(c)
    print("  styles.css rebuilt")


# ---------------------------------------------------------------------------
# 7. JS
# ---------------------------------------------------------------------------

def build_js():
    p = OUT / "js" / "deck.js"
    j = p.read_text()

    j = sub1(j, r'/\* PFL × Liga Stavok Activation Strategy 2026 — Navigation logic \*/',
             '/* PFL × NetBet Activation Strategy 2026 — Navigation logic */',
             "js header comment")

    old_ranges = """  const SECTION_RANGES = [
    { idx: 0, slides: [1] },
    { idx: 1, slides: [2, 3] },
    { idx: 2, slides: [4, 5, 6, 7, 8] },
    { idx: 3, slides: [9, 10, 11, 12, 13, 14] },
    { idx: 4, slides: [15, 16, 17] },
    { idx: 5, slides: [18] },
    { idx: 6, slides: [19] },
    { idx: 7, slides: [20] },
  ];

  const TOTAL_LOGICAL = 19;"""
    new_ranges = """  const SECTION_RANGES = [
    { idx: 0, slides: [1] },
    { idx: 1, slides: [2, 3] },
    { idx: 2, slides: [4, 5, 6, 7, 8] },
    { idx: 3, slides: [9, 10, 11, 12, 13] },
    { idx: 4, slides: [14, 15, 16] },
    { idx: 5, slides: [17] },
    { idx: 6, slides: [18] },
  ];

  const TOTAL_LOGICAL = 18;"""
    check(old_ranges in j, "SECTION_RANGES block located")
    j = j.replace(old_ranges, new_ranges, 1)

    j = subN(j, r'Polymarket', 'NetBet', "js content-string brand names")
    check("polymarket" not in j.lower(), "zero polymarket references in JS")
    check("TOTAL_LOGICAL = 18" in j, "TOTAL_LOGICAL updated to 18")

    p.write_text(j)
    print("  deck.js rebuilt")


# ---------------------------------------------------------------------------
# 8. Whole-tree audit
# ---------------------------------------------------------------------------

def audit():
    stray = []
    for path in OUT.rglob("*"):
        if path.is_file() and "polymarket" in path.name.lower():
            stray.append(str(path.relative_to(OUT)))
    check(not stray, f"no polymarket-named files remain ({stray})")

    # Every referenced local asset must exist on disk
    html = (OUT / "index.html").read_text()
    css = (OUT / "css" / "styles.css").read_text()
    refs = set(re.findall(r'assets/[A-Za-z0-9_\-./]+', html + css))
    missing = [r for r in sorted(refs) if not (OUT / r).exists()]
    check(not missing, f"all referenced assets exist on disk (missing: {missing})")

    # Every asset on disk must be referenced (orphan hunt)
    on_disk = {str(p.relative_to(OUT)) for p in (OUT / "assets").rglob("*")
               if p.is_file()}
    orphans = sorted(on_disk - refs)
    if orphans:
        print(f"  note: {len(orphans)} unreferenced asset(s): {orphans}")
    return orphans


# ---------------------------------------------------------------------------

def main():
    print("Building PFL x NetBet deck\n")
    prepare_source()
    build_images()
    build_logos()
    patch_legacy_branding()
    build_icons()
    build_video()
    build_html()
    build_css()
    build_js()
    orphans = audit()

    print(f"\n{CHECKS} verification checks run")
    if FAILURES:
        print(f"\n{len(FAILURES)} FAILED:")
        for f in FAILURES:
            print("  x " + f)
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
