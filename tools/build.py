#!/usr/bin/env python3
"""
RophysJpeg static site builder.

    python3 tools/build.py                      # build HTML into site/ from content/site.json
    python3 tools/build.py --media --archive ../rophysjpeg-rebuild-kit
                                                # also (re)generate images, posters, favicon
    python3 tools/build.py --videos --archive ../rophysjpeg-rebuild-kit
                                                # copy / web-optimise the four MP4s

Only the Python standard library is needed for HTML. Image processing needs
Pillow (pip install Pillow); video processing needs ffmpeg.
Media steps are incremental: files that already exist are skipped, and
--max-seconds lets a long run stop cleanly and resume on the next call.
"""
import datetime
import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from xml.sax.saxutils import escape as xml_escape

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
SRC = os.path.join(PROJECT, "src")
OUT = os.path.abspath(os.environ.get("SITE_OUT") or os.path.join(PROJECT, "site"))

WIDTHS = [640, 1024, 1600, 2048]   # responsive WebP widths (capped at source width)
OG_WIDTH = 1200                    # social-preview JPEG width
MAX_SITE_FILE = 25 * 1024 * 1024   # Cloudflare Pages per-file limit (25 MiB)

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)


# --------------------------------------------------------------------------- helpers
def load_content():
    with open(os.path.join(PROJECT, "content", "site.json"), encoding="utf-8") as f:
        site = json.load(f)
    ed_path = os.path.join(PROJECT, "content", "editor.json")
    if os.path.exists(ed_path):                       # Pages CMS edits win over site.json
        sys.path.insert(0, HERE)
        import cms
        with open(ed_path, encoding="utf-8") as f:
            cms.apply(site, json.load(f))
    return site


def widths_for(photo):
    w = int(photo["width"])
    ws = [x for x in WIDTHS if x < w]
    top = min(w, WIDTHS[-1])
    if top not in ws:
        ws.append(top)
    return ws


def img_url(photo, w):
    return f"/media/photos/{photo['web_name']}-{w}.webp"


def srcset(photo):
    return ", ".join(f"{img_url(photo, w)} {w}w" for w in widths_for(photo))


def default_src(photo, prefer=1024):
    ws = widths_for(photo)
    best = min(ws, key=lambda w: abs(w - prefer))
    return img_url(photo, best)


def largest(photo):
    return img_url(photo, widths_for(photo)[-1])


def page_heading(page):
    t = re.sub(r"\s*-\s*ROPHYSJPEG\s*$", "", page["meta"]["title"]).strip()
    return re.sub(r"\s{2,}", " ", t)


def file_hash(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()[:10]


def img_tag(photo, alt, sizes, cls="", eager=False, high=False):
    w, h = int(photo["width"]), int(photo["height"])
    attrs = [
        f'src="{E(default_src(photo))}"',
        f'srcset="{E(srcset(photo))}"',
        f'sizes="{E(sizes)}"',
        f'width="{w}" height="{h}"',
        f'alt="{E(alt)}"',
        'decoding="async"',
        'loading="eager"' if eager else 'loading="lazy"',
    ]
    if high:
        attrs.append('fetchpriority="high"')
    if cls:
        attrs.append(f'class="{cls}"')
    return "<img " + " ".join(attrs) + ">"


ICONS = {
    "instagram": '<svg class="social-icon" viewBox="-70 -150 1000 1000" aria-hidden="true" focusable="false"><path fill="currentColor" d="M571 500q0-59-41-101t-101-42-101 42-42 101 42 101 101 42 101-42 41-101zm77 0q0 91-64 156t-155 64-156-64-64-156 64-156 156-64 155 64 64 156zm61-229q0 21-15 36t-37 15-36-15-15-36 15-36 36-15 37 15 15 36zM429 148H327l-54 2-57 5-40 11q-28 11-49 32t-33 49q-6 16-10 40t-6 58-1 53 0 59 0 43 0 43 0 59 1 53 6 58l10 40q12 28 33 49t49 32q16 6 40 11t57 5 54 2 59 0 43 0 42 0 59 0 54-2 58-5 39-11q28-11 50-32t32-49q6-16 10-40t6-58 1-53 0-59 0-43 0-43 0-59-1-53-6-58l-10-40q-11-28-32-49t-50-32q-16-6-39-11t-58-5-54-2-59 0-42 0zm428 352q0 128-3 177-5 116-69 180t-179 69q-50 3-177 3t-177-3q-116-6-180-69T3 677q-3-49-3-177t3-177q5-116 69-180t180-69q49-3 177-3t177 3q116 6 179 69t69 180q3 49 3 177z"/></svg>',
    "linkedin": '<svg class="social-icon" viewBox="-60 -150 1000 1000" aria-hidden="true" focusable="false"><path fill="currentColor" d="M195 349v553H11V349h184zm12-171q0 41-29 68t-75 27h-1q-46 0-74-27T0 178t29-68 75-27 74 27 29 68zm650 407v317H674V606q0-59-23-92t-71-33q-35 0-58 19t-36 48q-6 17-6 45v309H296q1-223 1-361V376l-1-27h184v80h-1q11-18 23-31t31-29 49-24 64-9q95 0 153 63t58 186z"/></svg>',
}

WIGGLE = ("M8.5,0 C8.5,6.16623005 0.2,6.16623005 0.2,12.3324601 C0.2,18.4986902 8.5,18.4986902 8.5,24.6649202 "
          "C8.5,30.8311503 0.2,30.8311503 0.2,36.9973803 C0.2,43.1636104 8.5,43.1636104 8.5,49.3298404 "
          "C8.5,55.4960705 0.2,55.4960705 0.2,61.6623005 C0.2,67.8285306 8.5,67.8285306 8.5,73.9947606 "
          "C8.5,80.1609907 0.2,80.1609907 0.2,86.3272207 C0.2,92.4934508 8.5,92.4934508 8.5,98.6596808 "
          "C8.5,104.825911 0.2,104.675535 0.2,110.94703 C0.2,117.218525 8.5,117.451277 8.5,123.742525 "
          "C8.5,130.033773 0.2,130.241724 0.2,136.114651 C0.2,141.987577 8.5,141.473653 8.5,147.240982 "
          "C8.5,153.008311 0.2,153.714125 0.2,160.023604 C0.2,166.333083 8.5,166.73752 8.5,172.480118 "
          "C8.5,178.222715 0.2,177.368865 0.2,183")


# --------------------------------------------------------------------------- layout
def head(site, page, photos, asset_ver):
    m = page["meta"]
    base = site["site"]["base_url"].rstrip("/")
    canonical = m.get("og_url") or (base + page["route"])
    og_img = ""
    pid = m.get("og_image_photo")
    if pid and pid in photos:
        og_img = f"{base}/media/og/{photos[pid]['web_name']}.jpg"
    out = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{E(m['title'])}</title>",
        f'<meta name="description" content="{E(m["description"])}">',
        f'<meta name="robots" content="{E(m.get("robots", ""))}">',
        f'<link rel="canonical" href="{E(canonical)}">',
        (f'<meta name="author" content="{E(site["site"]["author"])}">' if site["site"].get("author") else ""),
        f'<meta property="og:site_name" content="{E(site["site"]["og_site_name"])}">',
        f'<meta property="og:title" content="{E(m["og_title"])}">',
        f'<meta property="og:description" content="{E(m["og_description"])}">',
        f'<meta property="og:type" content="{E(m.get("og_type", "website"))}">',
        f'<meta property="og:url" content="{E(canonical)}">',
    ]
    if og_img:
        p = photos[pid]
        oh = round(OG_WIDTH * int(p["height"]) / int(p["width"])) if int(p["width"]) > OG_WIDTH else int(p["height"])
        ow = min(OG_WIDTH, int(p["width"]))
        out += [f'<meta property="og:image" content="{E(og_img)}">',
                f'<meta property="og:image:width" content="{ow}">',
                f'<meta property="og:image:height" content="{oh}">']
    if page.get("route") == "/" and site["site"].get("author"):
        ld = {"@context": "https://schema.org", "@type": "Person", "name": site["site"]["author"],
              "alternateName": "ROPHYSJPEG", "jobTitle": "Sports Photographer and Media Producer", "url": base,
              "address": {"@type": "PostalAddress", "addressRegion": "FL", "addressCountry": "US"},
              "areaServed": "Worldwide", "sameAs": [s_["href"].split("?")[0] for s_ in site.get("social", [])]}
        out.append('<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    out += [
        f'<meta name="twitter:card" content="{E(m.get("twitter_card", "summary_large_image"))}">',
        f'<meta name="twitter:title" content="{E(m["og_title"])}">',
        f'<meta name="twitter:description" content="{E(m["og_description"])}">',
        '<meta name="theme-color" content="#000000">',
        '<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">',
        '<link rel="icon" href="/favicon-192.png" sizes="192x192" type="image/png">',
        '<link rel="apple-touch-icon" href="/apple-touch-icon.png">',
        '<link rel="preload" href="/assets/fonts/archivo-black-latin-400.woff2" as="font" type="font/woff2" crossorigin>',
        f'<link rel="stylesheet" href="/assets/css/site.css?v={asset_ver}">',
        "<script>document.documentElement.classList.add('js')</script>",
        f'<script src="/config.js?v={asset_ver}" defer></script>',
        f'<script src="/assets/js/site.js?v={asset_ver}" defer></script>',
    ]
    return "\n".join(out)


def nav_items(site, page, mobile=False):
    lis = []
    for n in site["navigation"]:
        cur = page.get("nav_active") == n["href"]
        cls = "item selected" if cur else "item"
        aria = ' aria-current="page"' if cur and page["route"] == n["href"] else (' aria-current="true"' if cur else "")
        lis.append(f'<li class="{cls}"><a href="{E(n["href"])}"{aria}>{E(n["label"])}</a></li>')
    socials = "".join(
        f'<li class="social-link"><a href="{E(s["href"])}" target="_blank" rel="noopener" '
        f'aria-label="{E(s["label"])} (opens in a new tab)" title="{E(s["label"])}">{ICONS[s["icon"]]}</a></li>'
        for s in site["social"])
    if mobile:
        return f'<ul class="menu-list">{"".join(lis)}</ul><ul class="social-links">{socials}</ul>'
    return f'<ul class="menu-list">{"".join(lis)}<li class="social-item"><ul class="social-links">{socials}</ul></li></ul>'


def header(site, page):
    name = site["site"]["name"]
    letters = "".join(f"<span>{E(c)}</span>" for c in name)
    return f"""<a class="skip-link" href="#main">Skip to content</a>
<header class="site-header" data-header>
  <div class="header-wrap">
    <p class="logo"><a href="/" aria-label="{E(name)} - home"><span class="logo-wrap" aria-hidden="true">{letters}</span></a></p>
    <nav class="menu menu-desktop" aria-label="Main">{nav_items(site, page)}</nav>
    <button class="menu-toggle" type="button" aria-expanded="false" aria-controls="mobile-menu" data-menu-toggle>
      <span class="visually-hidden" data-menu-label>Open menu</span>
    </button>
  </div>
  <div class="mobile-menu" id="mobile-menu" data-mobile-menu hidden>
    <nav class="menu" aria-label="Main">{nav_items(site, page, mobile=True)}</nav>
  </div>
</header>"""


def lightbox():
    return """<div class="lightbox" data-lightbox role="dialog" aria-modal="true" aria-label="Enlarged photograph" hidden>
  <figure class="lightbox-figure">
    <img class="lightbox-img" alt="" data-lightbox-img>
    <figcaption class="lightbox-caption"><span class="lightbox-count" data-lightbox-count></span></figcaption>
  </figure>
  <button class="lightbox-btn lightbox-close" type="button" data-lightbox-close aria-label="Close enlarged photograph"><span aria-hidden="true">&times;</span></button>
  <button class="lightbox-btn lightbox-prev" type="button" data-lightbox-prev aria-label="Previous photograph"><span aria-hidden="true">&#8249;</span></button>
  <button class="lightbox-btn lightbox-next" type="button" data-lightbox-next aria-label="Next photograph"><span aria-hidden="true">&#8250;</span></button>
</div>"""


def footer_links(site):
    links = site.get("footer_links") or []
    if not links:
        return ""
    return ('<nav class="footer-links" aria-label="More">'
            + "".join(f'<a href="{E(l["href"])}"' + (' target="_blank" rel="noopener"' if l["href"].startswith("http") else "") + f'>{E(l["label"])}</a>' for l in links) + "</nav>")


def document(site, page, photos, body_cls, main_html, asset_ver, extra=""):
    return f"""<!doctype html>
<html lang="{E(site['site'].get('lang', 'en'))}">
<head>
{head(site, page, photos, asset_ver)}
</head>
<body class="{body_cls}">
{header(site, page)}
<main id="main" class="container" tabindex="-1">
{main_html}
</main>
<footer class="site-footer">{footer_links(site)}<p>&copy; {datetime.date.today().year} RophysJpeg. All rights reserved.</p></footer>
{extra}
</body>
</html>
"""


# --------------------------------------------------------------------------- page bodies
def masonry_positions(items, photos):
    """Shortest-column placement (same rule as the original Masonry.js setup).
    Units are % of the listing width, so the result is width-independent:
    each tile = image (46% wide) + 4% bottom gutter."""
    cols = [0.0, 0.0]
    pos = []
    for it in items:
        p = photos[it["photo"]]
        hgt = 46.0 * int(p["height"]) / int(p["width"]) + 4.0
        c = 0 if cols[0] <= cols[1] + 1e-6 else 1
        pos.append((c, cols[c]))
        cols[c] += hgt
    return pos, max(cols)


def listing_body(site, page, photos):
    parts = []
    hero = page.get("hero") or {}
    heading = page_heading(page)
    if hero.get("kind") == "image":
        hp = photos[hero["photo"]]
        parts.append(f'<h1 class="visually-hidden">{E(heading)}</h1>')
        parts.append('<div class="title-element title-image">'
                     + img_tag(hp, hp.get("alt", ""), "(max-width: 1024px) 90vw, 47vw", eager=True, high=True)
                     + "</div>")
    elif hero.get("kind") == "heading":
        parts.append(f'<div class="title-element title-text"><h1>{E(hero["text"])}</h1></div>')
    else:
        parts.append(f'<h1 class="visually-hidden">{E(heading)}</h1>')

    items = page["items"]
    layout = site["site"].get("listing_layout", "masonry")
    if layout == "grid":
        routes = {pg["route"]: pg for pg in site["pages"]}
        lis = []
        for i, it in enumerate(items):
            p = photos[it["photo"]]
            title = re.sub(r"\s{2,}", " ", it["title"])
            g = routes.get(it["href"])
            n = len(g.get("photos", [])) if g else 0
            lis.append(
                f'<li class="pcard"><a class="pcard-link" href="{E(it["href"])}">'
                f'<span class="pcard-thumb">' + img_tag(p, "", "(max-width: 1024px) 45vw, 27vw", eager=i < 3)
                + (f'<span class="vdur vcount" aria-hidden="true">{n} photos</span>' if n else "")
                + f'</span><span class="pcard-title">{E(title)}</span></a></li>')
        parts.append('<ul class="pgrid">' + "".join(lis) + "</ul>")
        return '<div class="listing">' + "\n".join(parts) + "</div>"
    pos, total = masonry_positions(items, photos)
    lis = []
    for i, it in enumerate(items):
        p = photos[it["photo"]]
        col, top = pos[i]
        style = f' style="--col:{col};--top:{top:.4f}"'
        title = re.sub(r"\s{2,}", " ", it["title"])
        lis.append(
            f'<li class="project"{style}><a class="project-link" href="{E(it["href"])}">'
            + img_tag(p, p.get("alt", ""), "(max-width: 768px) 90vw, 46vw", eager=i < 2)
            + f'<span class="project-title">{E(title)}</span></a></li>')
    parts.append(f'<ul class="projects" data-layout="{E(layout)}" style="--masonry-height:{total:.4f}">'
                 + "".join(lis) + "</ul>")
    return '<div class="listing">' + "\n".join(parts) + "</div>"


def gallery_body(site, page, photos):
    ids = page["photos"]
    n = len(ids)
    heading = page_heading(page)
    rows = []
    for r in range(0, n, 2):
        cells = []
        for i in range(r, min(r + 2, n)):
            p = photos[ids[i]]
            # The original galleries showed no visible captions (Format rendered them black on
            # black), so caption text is only used as alt text for screen readers.
            cap = p.get("caption", "")
            alt = p.get("alt") or cap or f"{heading} - photograph {i + 1} of {n}"
            orient = "is-portrait" if int(p["height"]) >= int(p["width"]) else "is-landscape"
            cells.append(
                f'<figure class="gallery-item {orient}" data-index="{i}">'
                f'<a class="zoom" href="{E(largest(p))}" data-full-srcset="{E(srcset(p))}" '
                f'aria-label="{E(f"Enlarge photograph {i + 1} of {n}")}">'
                + img_tag(p, alt, "(max-width: 1024px) 90vw, 44vw", eager=i < 2)
                + "</a></figure>")
        rows.append(f'<div class="gallery-row">{"".join(cells)}</div>')
    prog = ""
    if page.get("progress_indicator", True):
        prog = (f'<div class="progress-indicator" aria-hidden="true"><svg width="11" height="183" viewBox="0 0 11 183">'
                f'<path class="stroke" d="{WIGGLE}" transform="translate(1 0)" pathLength="231" fill="none" '
                f'stroke="#7AC8FF" stroke-width="2" stroke-linecap="round"/></svg></div>')
    intro = page.get("intro")
    if intro:
        head = (f'<section class="gallery-intro" aria-labelledby="gallery-title">'
                + (f'<p class="gi-kicker">{E(intro["kicker"])}</p>' if intro.get("kicker") else "")
                + f'<h1 id="gallery-title">{E(heading)}</h1>'
                + f'<p class="gi-text">{E(intro["text"])}'
                + (f' <a class="gi-inline" href="{E(intro["link"]["href"])}" target="_blank" rel="noopener">'
                   f'{E(intro["link"]["label"])}<span class="visually-hidden"> (opens in a new tab)</span>&nbsp;<span aria-hidden="true">&#8599;</span></a>'
                   if intro.get("link") and intro["link"].get("inline") else "")
                + '</p>'
                + (f'<p class="gi-credit">{E(intro["credit"])}</p>' if intro.get("credit") else "")
                + (f'<p class="gi-link"><a href="{E(intro["link"]["href"])}" target="_blank" rel="noopener">'
                   f'{E(intro["link"]["label"])}<span class="visually-hidden"> (opens in a new tab)</span> <span aria-hidden="true">&#8599;</span></a></p>'
                   if intro.get("link") and not intro["link"].get("inline") else "")
                + '</section>')
    else:
        head = f'<h1 class="visually-hidden">{E(heading)}</h1>'
    return (prog + head
            + f'<div class="gallery" data-gallery aria-label="{E(heading)} - {n} photographs">' + "".join(rows) + "</div>")


def _fmt_dur(sec):
    try:
        s = int(round(float(sec)))
    except (TypeError, ValueError):
        return ""
    return f"{s // 60}:{s % 60:02d}"


def _split_caption(v):
    """Title = caption up to ' Filmed…'; credit = the 'Filmed…' sentence."""
    if v.get("title"):
        return v["title"], v.get("credit", "")
    cap = v.get("caption", "")
    m = re.search(r"\s(Filmed\b.*)$", cap)
    if m:
        return cap[:m.start()].rstrip(" ."), m.group(1)
    return cap.rstrip("."), ""


PLAY_SVG = ('<svg class="vplay-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
            '<path fill="currentColor" d="M8 5v14l11-7z"/></svg>')


def _vext(v):
    l = v.get("link")
    if not l:
        return ""
    return (f'<a class="vext" href="{E(l["href"])}" target="_blank" rel="noopener">{E(l["label"])}'
            f'<span aria-hidden="true"> ↗</span><span class="visually-hidden"> (opens in a new tab)</span></a>')


def video_body(site, page, photos):
    vids = sorted(page["videos"], key=lambda v: v.get("order", 999))
    feat = next((v for v in vids if v.get("featured")), vids[0])
    rest = [v for v in vids if v is not feat]
    ordered = [feat] + rest

    def data_attrs(v, i):
        title, credit = _split_caption(v)
        return (f'data-vindex="{i}" ' + (f'data-youtube="{E(v["youtube"])}" ' if v.get("youtube") else f'data-src="{E(v["src"])}" ') + f'data-poster="{E(v["poster"])}" '
                f'data-title="{E(title)}" data-credit="{E(credit)}" data-tag="{E(v.get("tag", ""))}" '
                f'data-w="{int(v["width"])}" data-h="{int(v["height"])}"' + (f' data-link="{E(v["link"]["href"])}" data-link-label="{E(v["link"]["label"])}"' if v.get("link") else ''))

    # featured
    ft, fc = _split_caption(feat)
    fw, fh = int(feat["width"]), int(feat["height"])
    hero = f"""<section class="vfeature" aria-labelledby="vfeature-title">
  <div class="vfeature-media" style="--ratio:{fw}/{fh}">
    <video class="vfeature-video" muted loop playsinline preload="metadata" poster="{E(feat['poster'])}"
      width="{fw}" height="{fh}" aria-hidden="true" tabindex="-1" data-autopreview><source src="{E(feat['src'])}" type="video/mp4"></video>
    <a class="vfeature-hit" href="{E(feat['src'])}" {data_attrs(feat, 0)} aria-label="{E('Play video: ' + ft)}">{PLAY_SVG}</a>
  </div>
  <div class="vfeature-text">
    <p class="vkicker">Featured{(' &middot; ' + E(feat.get('tag'))) if feat.get('tag') else ''}</p>
    <h2 id="vfeature-title">{E(ft)}</h2>{('<p class="vsub">' + E(feat['subtitle']) + '</p>') if feat.get('subtitle') else ''}
    <p class="vcredit">{E(fc.rstrip('.'))}{(' &middot; ' + _fmt_dur(feat.get('duration'))) if feat.get('duration') else ''}</p>
  </div>
</section>"""

    cards = []
    for i, v in enumerate(rest, start=1):
        title, credit = _split_caption(v)
        dur = _fmt_dur(v.get("duration"))
        orient = "landscape" if int(v["width"]) >= int(v["height"]) else "portrait"
        cards.append(
            f'<li class="vcard-item"><a class="vcard vcard-{orient}" href="{E(v["src"])}" {data_attrs(v, i)} '
            f'aria-label="{E("Play video: " + title + (" (" + dur + ")" if dur else ""))}">'
            f'<span class="vthumb"><img src="{E(v["poster"])}" alt="" loading="lazy" decoding="async">'
            f'<span class="vplay" aria-hidden="true">{PLAY_SVG}</span>'
            + (f'<span class="vdur" aria-hidden="true">{dur}</span>' if dur else "")
            + '</span><span class="vcard-text">'
            + (f'<span class="vtag">{E(v["tag"])}</span>' if v.get("tag") else "")
            + f'<span class="vtitle">{E(title)}</span>' + (f'<span class="vsub">{E(v["subtitle"])}</span>' if v.get("subtitle") else '') + f'<span class="vcredit">{E(credit)}</span></span></a>' + _vext(v) + '</li>')

    cta = ""
    c = page.get("cta")
    if c:
        cta = (f'<section class="vcta"><h2>{E(c["heading"])}</h2>'
               + (f'<p>{E(c["text"])}</p>' if c.get("text") else "")
               + f'<a class="btn" href="{E(c["href"])}">{E(c["button"])}</a></section>')

    heading = page.get("heading") or page_heading(page)
    return ('<div class="video-page">'
            + (f'<div class="title-element title-text"><h1>{E(heading)}</h1></div>' if page.get("show_heading", True)
               else f'<h1 class="visually-hidden">{E(heading)}</h1>')
            + hero
            + f'<ul class="vgrid" aria-label="More videos">{"".join(cards)}</ul>'
            + cta + '</div>')


GRID_SVG = ('<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
            '<path fill="currentColor" d="M3 3h8v8H3zM13 3h8v8h-8zM3 13h8v8H3zM13 13h8v8h-8z"/></svg>')


def _vdata(v, i, title, credit, tag):
    return (f'data-vindex="{i}" ' + (f'data-youtube="{E(v["youtube"])}" ' if v.get("youtube") else f'data-src="{E(v["src"])}" ') + f'data-poster="{E(v["poster"])}" '
            f'data-title="{E(title)}" data-credit="{E(credit)}" data-tag="{E(tag)}" '
            f'data-w="{int(v["width"])}" data-h="{int(v["height"])}"' + (f' data-link="{E(v["link"]["href"])}" data-link-label="{E(v["link"]["label"])}"' if v.get("link") else ''))


def home_body(site, page, photos):
    """Home: WELCOME artwork, a featured film, then a mixed grid of galleries and videos."""
    parts = []
    hi = page.get("intro_block")
    if hi:
        btns = "".join(f'<a class="btn{" btn-ghost" if i else ""}" href="{E(b["href"])}">{E(b["label"])}</a>'
                       for i, b in enumerate(hi.get("buttons", [])))
        brands = "".join(f"<li>{E(n)}</li>" for n in hi.get("brands", []))
        h1 = (f'<h1 id="hintro-h">{E(hi["heading"])}</h1>' if hi.get("heading")
              else f'<h1 id="hintro-h" class="visually-hidden">{E(page_heading(page))}</h1>')
        parts.append(f'<section class="hintro" aria-labelledby="hintro-h">{h1}'
                     + (f'<p class="hintro-sub">{E(hi["sub"])}</p>' if hi.get("sub") else "")
                     + (f'<div class="hintro-btns">{btns}</div>' if btns else "")
                     + (f'<ul class="hbrands" aria-label="{E(hi.get("brands_label", "Brands and competitions"))}">{brands}</ul>' if brands else "")
                     + '</section>')
    else:
        parts.append(f'<h1 class="visually-hidden">{E(page_heading(page))}</h1>')
    if page.get("hero", {}).get("show", True) and page.get("hero", {}).get("photo"):
        hp = photos[page["hero"]["photo"]]
        parts.append('<div class="title-element title-image">'
                     + img_tag(hp, hp.get("alt", ""), "(max-width: 1024px) 90vw, 47vw", eager=True, high=True)
                     + "</div>")

    vids = {v["id"]: v for v in next(p for p in site["pages"] if p["slug"] == "video")["videos"]}
    routes = {p["route"]: p for p in site["pages"]}
    sc = page["showcase"]

    # featured film (same component as the Video page)
    feat = vids[sc["featured_video"]]
    ft, fc = _split_caption(feat)
    ftag = feat.get("tag", "")
    fw, fh = int(feat["width"]), int(feat["height"])
    hero = f"""<section class="vfeature" aria-labelledby="vfeature-title">
  <div class="vfeature-media" style="--ratio:{fw}/{fh}">
    <video class="vfeature-video" muted loop playsinline preload="metadata" poster="{E(feat['poster'])}"
      width="{fw}" height="{fh}" aria-hidden="true" tabindex="-1" data-autopreview><source src="{E(feat['src'])}" type="video/mp4"></video>
    <a class="vfeature-hit" href="{E(feat['src'])}" {_vdata(feat, 0, ft, fc, ftag)} aria-label="{E('Play video: ' + ft)}">{PLAY_SVG}</a>
  </div>
  <div class="vfeature-text">
    <p class="vkicker">Featured video</p>
    <h2 id="vfeature-title">{E(ft)}</h2>{('<p class="vsub">' + E(feat['subtitle']) + '</p>') if feat.get('subtitle') else ''}
    <p class="vcredit">{E(fc.rstrip('.'))}{(' &middot; ' + _fmt_dur(feat.get('duration'))) if feat.get('duration') else ''}</p>
  </div>
</section>"""

    fg = sc.get("feature_gallery")
    if fg:
        g = routes[fg["gallery"]]
        cov = photos[fg.get("photo") or g["photos"][0]]
        cw, ch = int(cov["width"]), int(cov["height"])
        n = len(g["photos"])
        peek = [img_url(photos[x], 640) for x in g["photos"] if x != fg.get("photo")][:4]
        gtitle = fg.get("title") or page_heading(g)
        hero = f"""<section class="vfeature vfeature-pair" aria-label="Featured work">
  <div class="vfp-item">
    <div class="vfeature-media" style="--ratio:{fw}/{fh}">
      <video class="vfeature-video" muted loop playsinline preload="metadata" poster="{E(feat['poster'])}"
        width="{fw}" height="{fh}" aria-hidden="true" tabindex="-1" data-autopreview><source src="{E(feat['src'])}" type="video/mp4"></video>
      <a class="vfeature-hit" href="{E(feat['src'])}" {_vdata(feat, 0, ft, fc, ftag)} aria-label="{E('Play video: ' + ft)}">{PLAY_SVG}</a>
    </div>
    <div class="vfeature-text">
      <p class="vkicker">Featured video</p>
      <h2 id="vfeature-title">{E(ft)}</h2>{('<p class="vsub">' + E(feat['subtitle']) + '</p>') if feat.get('subtitle') else ''}
      <p class="vcredit">{E(fc.rstrip('.'))}{(' &middot; ' + _fmt_dur(feat.get('duration'))) if feat.get('duration') else ''}</p>
    </div>
  </div>
  <div class="vfp-item">
    <a class="vfp-gallery" href="{E(fg['gallery'])}" data-peek="{E(' '.join(peek))}" aria-label="{E('View gallery: ' + gtitle + ' (' + str(n) + ' photos)')}">
      <span class="vthumb vfeature-media vfp-thumb" style="--ratio:{cw}/{ch}">{img_tag(cov, "", "(max-width: 1024px) 90vw, 40vw", eager=True)}<span class="vgal" aria-hidden="true">{GRID_SVG}</span><span class="vdur vcount" aria-hidden="true">{n} photos</span></span>
    </a>
    <div class="vfeature-text">
      <p class="vkicker">{E(fg.get("kicker", "Featured gallery"))}</p>
      <h2><a class="vfp-title" href="{E(fg['gallery'])}">{E(gtitle)}</a></h2>{('<p class="vsub">' + E(fg['subtitle']) + '</p>') if fg.get('subtitle') else ''}
      <p class="vcredit">Photographed by Rophy &middot; {n} photos</p>
    </div>
  </div>
</section>"""

    cards, vi = [], 0
    sizes = "(max-width: 1024px) 45vw, 27vw"
    for it in sc["items"]:
        if "video" in it:
            v = vids[it["video"]]
            vi += 1
            title, credit = _split_caption(v)
            tag = v.get("tag", "")
            dur = _fmt_dur(v.get("duration"))
            label = "Video" + (" · " + tag if tag else "")
            cards.append(
                f'<li class="vcard-item"><a class="vcard vcard-video" href="{E(v["src"])}" {_vdata(v, vi, title, credit, tag)} '
                f'aria-label="{E("Play video: " + title + (" (" + dur + ")" if dur else ""))}">'
                f'<span class="vthumb"><img src="{E(v["poster"])}" alt="" loading="lazy" decoding="async">'
                f'<span class="vplay" aria-hidden="true">{PLAY_SVG}</span>'
                + (f'<span class="vdur" aria-hidden="true">{dur}</span>' if dur else "")
                + f'</span><span class="vcard-text"><span class="vtag">{E(label)}</span>'
                f'<span class="vtitle">{E(title)}</span>' + (f'<span class="vsub">{E(v["subtitle"])}</span>' if v.get("subtitle") else '') + f'<span class="vcredit">{E(credit)}</span></span></a>' + _vext(v) + '</li>')
        else:
            g = routes[it["gallery"]]
            ph = g["photos"]
            cover = photos[it.get("photo") or ph[0]]
            peek = [img_url(photos[x], 640) for x in it.get("peek", [p for p in ph if p != it.get("photo")][:3])]
            n = len(ph)
            title = it.get("title") or page_heading(g)
            cards.append(
                f'<li class="vcard-item"><a class="vcard vcard-gallery" href="{E(it["gallery"])}" data-peek="{E(" ".join(peek))}" '
                f'aria-label="{E("View gallery: " + title + " (" + str(n) + " photos)")}">'
                f'<span class="vthumb">' + img_tag(cover, "", sizes)
                + f'<span class="vgal" aria-hidden="true">{GRID_SVG}</span>'
                f'<span class="vdur vcount" aria-hidden="true">{n} photos</span></span>'
                f'<span class="vcard-text"><span class="vtag">{E(it.get("tag", "Photo"))}</span>'
                f'<span class="vtitle">{E(title)}</span><span class="vcredit">{E(it.get("subtitle", ""))}</span></span></a>' + _vext(it) + '</li>')

    more = "".join(f'<a class="btn" href="{E(l["href"])}">{E(l["label"])}</a>' for l in sc.get("more", []))
    parts.append('<div class="video-page home-work">' + hero
                 + (f'<h2 class="hsection">{E(sc["heading"])}</h2>' if sc.get("heading") else "")
                 + f'<ul class="vgrid" aria-label="{E(sc.get("heading") or "Selected work")}">{"".join(cards)}</ul>'
                 + (f'<nav class="hmore" aria-label="More work">{more}</nav>' if more else "")
                 + '</div>')
    hc = page.get("contact_strip")
    if hc:
        parts.append(f'<section class="hcontact" aria-labelledby="hcontact-h"><h2 id="hcontact-h">{E(hc["heading"])}</h2>'
                     f'<p><a href="mailto:{E(hc["email"])}">{E(hc["email"])}</a></p>'
                     f'<a class="btn" href="{E(hc["href"])}">{E(hc["button"])}</a></section>')
    return '<div class="listing home">' + "\n".join(parts) + "</div>"


def video_modal():
    return """<div class="vmodal" data-vmodal role="dialog" aria-modal="true" aria-labelledby="vmodal-title" hidden>
  <div class="vmodal-inner">
    <video class="vmodal-video" controls playsinline preload="auto" data-vmodal-video></video>
    <iframe class="vmodal-yt" data-vmodal-yt hidden allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen referrerpolicy="strict-origin-when-cross-origin" title="Video player"></iframe>
    <div class="vmodal-meta">
      <p class="vtag" data-vmodal-tag></p>
      <h2 id="vmodal-title" data-vmodal-title></h2>
      <p class="vcredit" data-vmodal-credit></p>
      <a class="vext" data-vmodal-link href="#" target="_blank" rel="noopener" hidden></a>
    </div>
  </div>
  <button class="lightbox-btn lightbox-close" type="button" data-vmodal-close aria-label="Close video"><span aria-hidden="true">&times;</span></button>
  <button class="lightbox-btn lightbox-prev" type="button" data-vmodal-prev aria-label="Previous video"><span aria-hidden="true">&#8249;</span></button>
  <button class="lightbox-btn lightbox-next" type="button" data-vmodal-next aria-label="Next video"><span aria-hidden="true">&#8250;</span></button>
</div>"""


def _mailto(html):
    """Turn plain email addresses in already-escaped text into mailto links."""
    return re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]*\w", lambda m: f'<a href="mailto:{m.group(0)}">{m.group(0)}</a>', html)


def about_body(site, page, photos):
    p = photos[page["portrait"]]
    alt = p.get("alt") or "Portrait of Rophy"
    lead = "".join(f'<p class="ab-lead">{_mailto(E(x))}</p>' for x in page["intro"])
    meta = f'<p class="ab-meta">{E(page["meta_line"])}</p>' if page.get("meta_line") else ""
    parts = [f"""<section class="content-row ab-intro">
  <div class="ab-portrait">{img_tag(p, alt, "(max-width: 768px) 90vw, 40vw", eager=True, high=True)}</div>
  <div class="ab-intro-text">
    {('<p class="ab-kicker">' + E(page["kicker"]) + "</p>") if page.get("kicker") else ""}
    <h1>{E(page["heading"])}</h1>
    {lead}{meta}
  </div>
</section>"""]
    if page.get("stats"):
        st = page["stats"]
        items = "".join(f'<li><span class="ab-num">{E(s["value"])}</span><span class="ab-label">{E(s["label"])}</span></li>'
                        for s in st["items"])
        src = (f'<p class="ab-source"><a href="{E(st["source_href"])}" target="_blank" rel="noopener">{E(st["source_label"])}</a></p>'
               if st.get("source_href") else "")
        parts.append(f'<section class="content-row ab-stats" aria-label="By the numbers"><ul>{items}</ul>{src}</section>')
    if page.get("story"):
        s = page["story"]
        paras = "".join(f"<p>{_mailto(E(x))}</p>" for x in s["paragraphs"])
        parts.append(f'<section class="content-row ab-story"><p class="ab-kicker">{E(s.get("kicker", ""))}</p>'
                     f'<h2>{E(s["heading"])}</h2><div class="ab-story-text">{paras}</div></section>')
    if page.get("services"):
        s = page["services"]
        items = "".join(f'<li><h3>{E(x["title"])}</h3><p>{E(x["text"])}</p></li>' for x in s["items"])
        parts.append(f'<section class="content-row ab-services">' + (f'<p class="ab-kicker">{E(s["kicker"])}</p>' if s.get("kicker") else "")
                     + f'<h2>{E(s["heading"])}</h2><ul class="ab-cols">{items}</ul></section>')
    if page.get("published_by"):
        s = page["published_by"]
        names = "".join(f"<li>{E(n)}</li>" for n in s["names"])
        parts.append(f'<section class="content-row ab-clients"><p class="ab-kicker">{E(s["heading"])}</p><ul>{names}</ul></section>')
    if page.get("process"):
        s = page["process"]
        steps = "".join(f'<li><span class="ab-step">{i:02d}</span><h3>{E(x["title"])}</h3><p>{E(x["text"])}</p></li>'
                        for i, x in enumerate(s["steps"], 1))
        parts.append(f'<section class="content-row ab-process"><p class="ab-kicker">{E(s.get("kicker", ""))}</p>'
                     f'<h2>{E(s["heading"])}</h2><ol class="ab-cols">{steps}</ol></section>')
    if page.get("cta"):
        c = page["cta"]
        links = "".join(f'<a href="{E(l["href"])}" target="_blank" rel="noopener">{E(l["label"])}</a>' for l in page.get("links", []))
        parts.append(f'<section class="content-row ab-cta"><h2>{E(c["heading"])}</h2><p>{_mailto(E(c["text"]))}</p>'
                     f'<a class="btn" href="{E(c["href"])}">{E(c["button"])}</a>'
                     + (f'<p class="ab-links">{links}</p>' if links else "") + '</section>')
    if page.get("contact"):
        parts.append(contact_section(page["contact"]))
    return '<div class="content-page about-page ab">' + "\n".join(parts) + "</div>"


def contact_form(f):
    req = ' <span class="ct-req">(required)</span>'
    return f"""<form class="ct-form" data-contact-form data-recipient="{E(f["recipient"])}" novalidate>
    <div class="ct-field"><label for="cf-email">Email Address{req}</label><input id="cf-email" name="email" type="email" autocomplete="email" required></div>
    <div class="ct-field"><label for="cf-subject">Subject{req}</label><input id="cf-subject" name="subject" type="text" required></div>
    <div class="ct-field"><label for="cf-message">Message{req}</label><textarea id="cf-message" name="message" rows="7" required></textarea></div>
    <div class="hp" aria-hidden="true"><label for="cf-company">Leave this field empty</label><input id="cf-company" name="_gotcha" type="text" tabindex="-1" autocomplete="off"></div>
    <button class="btn ct-submit" type="submit" data-contact-submit>{E(f["submit_label"])}</button>
    <p class="form-status ct-status" role="status" aria-live="polite" data-contact-status></p>
  </form>"""


def contact_section(c):
    intro = "".join(f"<p>{_mailto(E(x))}</p>" for x in c["intro"])
    return (f'<section class="content-row ct-one ct-simple ab-contact" id="contact" aria-labelledby="contact-h">'
            f'<h2 id="contact-h">{E(c["heading"])}</h2>{intro}{contact_form(c["form"])}</section>')


def notfound_body():
    return ('<div class="content-page notfound-page"><section class="content-row">'
            '<h1>Page not found</h1><p><a class="text-link" href="/">Back to the homepage</a></p></section></div>')


# --------------------------------------------------------------------------- build html
def build_html(site, verbose=True):
    photos = site["photos"]
    os.makedirs(OUT, exist_ok=True)
    # static assets
    for sub in ("assets/css", "assets/js"):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    shutil.copy2(os.path.join(SRC, "site.css"), os.path.join(OUT, "assets/css/site.css"))
    shutil.copy2(os.path.join(SRC, "site.js"), os.path.join(OUT, "assets/js/site.js"))
    if not os.path.exists(os.path.join(OUT, "config.js")):          # never overwrite a configured file
        shutil.copy2(os.path.join(SRC, "config.js"), os.path.join(OUT, "config.js"))
    fonts_dst = os.path.join(OUT, "assets", "fonts")
    os.makedirs(fonts_dst, exist_ok=True)
    for fn in os.listdir(os.path.join(SRC, "fonts")):
        shutil.copy2(os.path.join(SRC, "fonts", fn), os.path.join(fonts_dst, fn))
    for fn in ("_headers", "_redirects"):
        if os.path.exists(os.path.join(SRC, fn)):
            shutil.copy2(os.path.join(SRC, fn), os.path.join(OUT, fn))
    ver = hashlib.sha1((file_hash(os.path.join(SRC, "site.css")) + file_hash(os.path.join(SRC, "site.js"))
                        + file_hash(os.path.join(OUT, "config.js"))).encode()).hexdigest()[:8]

    written = []
    for page in site["pages"]:
        t = page["type"]
        if t == "redirect":
            # retired route: keep old links working by sending visitors to page["to"]
            to = page["to"]
            base = site["site"]["base_url"].rstrip("/")
            with open(os.path.join(OUT, page["output"]), "w", encoding="utf-8") as f:
                f.write(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Redirecting - ROPHYSJPEG</title>
<meta name="robots" content="noindex">
<link rel="canonical" href="{E(base + to)}">
<meta http-equiv="refresh" content="0; url={E(to)}">
<script>location.replace({json.dumps(to)})</script>
<style>body{{background:#000;color:#fff;font-family:Arial,sans-serif;padding:40px}}a{{color:#fff}}</style>
</head><body><p>This page has moved to <a href="{E(to)}">{E(base + to)}</a>.</p></body></html>
""")
            written.append(page["output"])
            continue
        if t == "home":
            body, cls = home_body(site, page, photos), "listing"
        elif t == "listing":
            body, cls = listing_body(site, page, photos), "listing"
        elif t == "gallery":
            body, cls = gallery_body(site, page, photos), "gallery"
        elif page["slug"] == "video":
            body, cls = video_body(site, page, photos), "content"
        elif page["slug"] == "about":
            body, cls = about_body(site, page, photos), "content"
        elif page["slug"] == "contact":
            body, cls = contact_body(site, page, photos), "content"
        else:
            raise SystemExit(f"unknown page type for {page['slug']}")
        extra = lightbox() if t == "gallery" else (video_modal() if page["slug"] in ("video", "home") else "")
        doc = document(site, page, photos, f"{cls} page-{page['slug']}", body, ver, extra)
        path = os.path.join(OUT, page["output"])
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc)
        written.append(page["output"])

    nf = {"slug": "404", "route": "/404", "nav_active": "", "type": "content",
          "meta": {"title": "Page not found - ROPHYSJPEG", "description": "", "robots": "noindex",
                   "og_title": "Page not found - ROPHYSJPEG", "og_description": "",
                   "og_url": site["site"]["base_url"] + "/404"}}
    with open(os.path.join(OUT, "404.html"), "w", encoding="utf-8") as f:
        f.write(document(site, nf, photos, "content page-404", notfound_body(), ver))

    base = site["site"]["base_url"].rstrip("/")
    urls = "".join(f"<url><loc>{xml_escape(base + (p['route'] if p['route'] != '/' else '/'))}</loc></url>"
                   for p in site["pages"] if p["type"] != "redirect")
    with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    with open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n")
    if verbose:
        print(f"html: wrote {len(written)} routes + 404.html, sitemap.xml, robots.txt into {OUT}")
    return written


# --------------------------------------------------------------------------- media
def _make_derivatives(job):
    """Worker: create the WebP widths (and optional OG JPEG) for one photo.
    Writes to a temp name first so an interrupted run never leaves half files."""
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = None
    src, size, need, ogp = job
    notes = []
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        im = im.convert("RGBA" if has_alpha else "RGB")
        if tuple(im.size) != tuple(size):
            notes.append(f"{os.path.basename(src)} is {im.size}, content map says {size}")
        for w, path in sorted(need, reverse=True):
            h = round(im.height * w / im.width)
            r = im if w == im.width else im.resize((w, h), Image.LANCZOS)
            tmp = path + ".part"
            r.save(tmp, "WEBP", quality=82, method=4)
            os.replace(tmp, path)
        if ogp:
            w = min(OG_WIDTH, im.width)
            r = im.convert("RGB").resize((w, round(im.height * w / im.width)), Image.LANCZOS)
            tmp = ogp + ".part"
            r.save(tmp, "JPEG", quality=84, optimize=True, progressive=True)
            os.replace(tmp, ogp)
    return notes


def build_media(site, archive, max_seconds, verbose=True, workers=None):
    from multiprocessing import Pool
    from PIL import Image, ImageOps
    t0 = time.time()
    photos = site["photos"]
    pdir = os.path.join(OUT, "media", "photos")
    odir = os.path.join(OUT, "media", "og")
    os.makedirs(pdir, exist_ok=True)
    os.makedirs(odir, exist_ok=True)
    og_ids = {p.get("meta", {}).get("og_image_photo") for p in site["pages"]} - {None}
    jobs = []
    for pid, p in photos.items():
        targets = [(w, os.path.join(pdir, f"{p['web_name']}-{w}.webp")) for w in widths_for(p)]
        need = [t for t in targets if not os.path.exists(t[1])]
        ogp = os.path.join(odir, p["web_name"] + ".jpg") if pid in og_ids else None
        if ogp and os.path.exists(ogp):
            ogp = None
        if need or ogp:
            jobs.append((os.path.join(archive, p["source"]), (int(p["width"]), int(p["height"])), need, ogp))
    made = 0
    finished = True
    if jobs:
        pool = Pool(workers or os.cpu_count() or 2)
        try:
            for notes in pool.imap_unordered(_make_derivatives, jobs):
                made += 1
                for n in notes:
                    print("  note:", n)
                if max_seconds and time.time() - t0 > max_seconds and made < len(jobs):
                    finished = False
                    break
        finally:
            pool.terminate()
            pool.join()
        for fn in os.listdir(pdir) + os.listdir(odir):      # clean interrupted temp files
            if fn.endswith(".part"):
                for d in (pdir, odir):
                    if os.path.exists(os.path.join(d, fn)):
                        os.remove(os.path.join(d, fn))
    # favicon (square centre crop of the image the old site used)
    fav = site["site"].get("favicon_source")
    if fav and not os.path.exists(os.path.join(OUT, "favicon-32.png")):
        with Image.open(os.path.join(archive, fav)) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            sq = ImageOps.fit(im, (512, 512), Image.LANCZOS)
            for size, name in ((32, "favicon-32.png"), (192, "favicon-192.png"), (180, "apple-touch-icon.png")):
                sq.resize((size, size), Image.LANCZOS).save(os.path.join(OUT, name), optimize=True)
            sq.resize((48, 48), Image.LANCZOS).save(os.path.join(OUT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
    if verbose:
        left = len(jobs) - made if not finished else 0
        print(f"media: {made} photos processed this run, {left} still to do, {len(photos)} photos in content map")
    return finished


def build_videos(site, archive, verbose=True):
    from PIL import Image
    vdir = os.path.join(OUT, "media", "video")
    os.makedirs(vdir, exist_ok=True)
    page = next(p for p in site["pages"] if p["slug"] == "video")
    for i, v in enumerate(page["videos"], 1):
        if not v.get("source"):          # added later straight into site/media/video
            continue
        src = os.path.join(archive, v["source"])
        dst = os.path.join(PROJECT, "site", v["src"].lstrip("/"))
        if not os.path.exists(dst):
            if os.path.getsize(src) <= MAX_SITE_FILE:
                # already web-ready H.264/AAC: copy with the moov atom moved to the front for fast start
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-c", "copy",
                                "-movflags", "+faststart", dst], check=True)
            else:
                # Above the 25 MiB per-file limit of Cloudflare Pages: re-encode (H.264/AAC, same
                # resolution and frame rate) to roughly 23 MiB. The archive keeps the original.
                dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                            "-of", "csv=p=0", src], capture_output=True, text=True,
                                           check=True).stdout.strip())
                vkbps = int((23 * 8 * 1024 * 1024 / dur) / 1000 * 0.92) - 128
                print(f"video {i}: {os.path.getsize(src)/1e6:.1f} MB -> re-encoding at {vkbps} kb/s")
                tmp = dst + ".part.mp4"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-c:v", "libx264", "-preset", "slow",
                                "-b:v", f"{vkbps}k", "-maxrate", f"{int(vkbps * 1.5)}k", "-bufsize", f"{vkbps * 2}k",
                                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
                                "-movflags", "+faststart", tmp], check=True)
                os.replace(tmp, dst)
            if os.path.getsize(dst) > MAX_SITE_FILE:
                print(f"WARNING video {i}: {dst} is larger than 25 MiB")
        psrc = os.path.join(archive, v["poster_source"])
        pdst = os.path.join(PROJECT, "site", v["poster"].lstrip("/"))
        if not os.path.exists(pdst):
            with Image.open(psrc) as im:
                im = im.convert("RGB")
                if im.width > 1600:
                    im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
                im.save(pdst, "JPEG", quality=84, optimize=True, progressive=True)
    if verbose:
        print("videos: done")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", help="path to rophysjpeg-rebuild-kit (needed for --media/--videos)")
    ap.add_argument("--media", action="store_true")
    ap.add_argument("--videos", action="store_true")
    ap.add_argument("--max-seconds", type=float, default=0)
    args = ap.parse_args()
    site = load_content()
    build_html(site)
    if args.media or args.videos:
        if not args.archive:
            raise SystemExit("--archive is required for --media/--videos")
        archive = os.path.abspath(args.archive)
        if args.videos:
            build_videos(site, archive)
        if args.media:
            ok = build_media(site, archive, args.max_seconds)
            if not ok:
                return 3


if __name__ == "__main__":
    sys.exit(main() or 0)
