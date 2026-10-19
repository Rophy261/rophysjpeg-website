#!/usr/bin/env python3
"""
One-time importer: converts the RophysJpeg recovery kit into the editable
content map used by the website (content/site.json).

    python3 tools/import_archive.py --archive ../rophysjpeg-rebuild-kit

It reads site-content.json, PHOTO-PLACEMENT.csv, data/video-manifest.json and
the sanitized original HTML in source/ (for the recorded active-menu states).
Gallery order is taken verbatim from PHOTO-PLACEMENT.csv (never sorted).

You normally run this once. After that, edit content/site.json directly.
"""
import argparse
import csv
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)

ROUTE_ORDER = [
    "home", "sport", "editorial", "music", "video", "about", "contact",
    # sport projects (listing order)
    "fifa-club-world-cup-2025", "inter-miami", "gold-cup", "leon-bailey",
    "hugo-ekitike", "orel-mangala", "christian-pulisic-portraits",
    "personal-project-tennis",
    # editorial / commercial projects (listing order)
    "manchester-city-x-aguero", "admiral-2025-kits-release", "kidsuper-x-puma",
    "montegobay-united-fc", "manchester-city-x-usa-tour",
    "football-for-the-world-foundation",
    "demario-phillips-montegobay-united-fc-24-25-signing",
]


def strip_hash_prefix(path):
    """'assets/photos/d3dffbc0c8c6-Name.jpg' -> 'Name.jpg' (original filename)."""
    base = os.path.basename(path)
    m = re.match(r"^[0-9a-f]{12}-(.+)$", base)
    return m.group(1) if m else base


def slugify(text):
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return re.sub(r"-{2,}", "-", text) or "image"


def image_size(archive, rel, fallback):
    try:
        from PIL import Image  # optional
        with Image.open(os.path.join(archive, rel)) as im:
            return list(im.size)
    except Exception:
        return list(fallback) if fallback else None


def text_of(fragment):
    t = re.sub(r"<[^>]+>", "", fragment or "")
    return html.unescape(t).strip()


def photo_record(archive, asset_id, local_image, local_original, dims, caption, alt):
    filename = strip_hash_prefix(local_image)
    stem = os.path.splitext(filename)[0]
    size = image_size(archive, local_image, dims)
    rec = {
        "id": str(asset_id),
        "filename": filename,
        "web_name": f"{asset_id}-{slugify(stem)}",
        "source": local_image,
        "source_original": local_original or None,
        "width": size[0],
        "height": size[1],
        "caption": caption or "",
        "alt": alt or "",
    }
    if local_original:
        rec["source_original_size"] = image_size(archive, local_original, None)
    return rec


def active_nav_from_source(archive, slug):
    fname = "home.html" if slug == "home" else f"{slug}.html"
    path = os.path.join(archive, "source", fname)
    if not os.path.exists(path):
        return None
    s = open(path, encoding="utf-8", errors="replace").read()
    head = s[s.find("<header"): s.find("mobile-header-items-container")]
    m = re.search(r'item item selected">\s*<a href="([^"]+)"', head)
    return m.group(1) if m else ""


def meta_for(page, og_photo_id):
    m = page.get("metadata") or {}
    return {
        "title": page["title"],
        "description": m.get("description", ""),
        "robots": m.get("robots", "noai, noimageai"),
        "og_title": m.get("og:title", page["title"]),
        "og_description": m.get("og:description", m.get("description", "")),
        "og_url": m.get("og:url", ""),
        "og_type": m.get("og:type", "website"),
        "twitter_card": m.get("twitter:card", "summary_large_image"),
        "og_image_photo": og_photo_id,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True, help="path to rophysjpeg-rebuild-kit")
    ap.add_argument("--out", default=os.path.join(PROJECT, "content", "site.json"))
    args = ap.parse_args()
    archive = os.path.abspath(args.archive)

    sc = json.load(open(os.path.join(archive, "site-content.json"), encoding="utf-8"))
    pages = {p["slug"]: p for p in sc["pages"]}
    rows = list(csv.DictReader(open(os.path.join(archive, "PHOTO-PLACEMENT.csv"), encoding="utf-8")))
    vids = json.load(open(os.path.join(archive, "data", "video-manifest.json"), encoding="utf-8"))

    photos = {}  # id -> record (shared library)

    def add_photo(asset_id, local_image, local_original, dims, caption="", alt=""):
        pid = str(asset_id)
        if pid not in photos:
            photos[pid] = photo_record(archive, asset_id, local_image, local_original, dims, caption, alt)
        return pid

    by_page = {}
    for r in rows:
        by_page.setdefault(r["page"], []).append(r)
    for k in by_page:  # keep CSV positions exactly (no alphabetical sorting)
        by_page[k].sort(key=lambda r: int(r["position"]))

    out_pages = []
    default_nav = {"home": "/sport", "sport": "/sport", "editorial": "/editorial", "music": "/music",
                   "video": "/video", "about": "/about", "contact": "/contact"}

    for slug in ROUTE_ORDER:
        p = pages[slug]
        nav = active_nav_from_source(archive, slug)
        if nav is None:
            nav = default_nav.get(slug, "")
        rec = {
            "slug": slug,
            "route": "/" if slug == "home" else p["route"],
            "output": "index.html" if slug == "home" else p["route"].strip("/") + ".html",
            "type": p["type"],
            "nav_active": nav,
        }
        og_photo = None

        if p["type"] == "listing":
            hero = p.get("hero") or {}
            if hero.get("local_image"):
                # The artwork has the word WELCOME baked in, so screen readers get it via alt text.
                alt = "WELCOME. " + (hero.get("alt_text") or "").strip()
                hid = add_photo(f"hero-{hero['id']}", hero["local_image"], None,
                                hero.get("archive_image_dimensions"), "", alt)
                rec["hero"] = {"kind": "image", "photo": hid,
                               "note": "WELCOME is part of this artwork; do not add a separate heading."}
                og_photo = hid
            elif hero.get("copy"):
                rec["hero"] = {"kind": "heading", "text": text_of(hero["copy"])}
            items = []
            for r in by_page.get(slug, []):
                a = p["assets"][int(r["position"]) - 1]
                pid = add_photo(r["asset_id"], r["local_image"], r["local_original"], a.get("dimensions"),
                                "", r["alt_text"])
                items.append({"title": r["title_or_caption"], "href": r["destination"], "photo": pid})
            rec["items"] = items
            if og_photo is None and items:
                og_photo = items[0]["photo"]

        elif p["type"] == "gallery":
            gal = []
            for r in by_page.get(slug, []):
                a = p["assets"][int(r["position"]) - 1]
                pid = add_photo(r["asset_id"], r["local_image"], r["local_original"], a.get("dimensions"),
                                r["title_or_caption"], r["alt_text"])
                gal.append(pid)
            rec["photos"] = gal
            rec["progress_indicator"] = True
            og_photo = gal[0] if gal else None

        elif slug == "video":
            vlist = []
            by_asset = {}
            for v in vids:
                by_asset.setdefault(v["asset_id"], {})[v["type"]] = v
            for m in p["content_modules"]:
                ca = m["content_page_assets"]
                uv = ca["uploaded_video"]
                files = by_asset.get(uv["id"], {})
                vname = os.path.basename(files.get("video", {}).get("local_path", f"video-{uv['id']}.mp4"))
                pname = os.path.basename(files.get("poster", {}).get("local_path", f"video-{uv['id']}-poster.jpg"))
                vlist.append({
                    "id": str(uv["id"]),
                    "src": f"/media/video/{vname}",
                    "poster": f"/media/video/{pname}",
                    "source": files.get("video", {}).get("local_path"),
                    "poster_source": files.get("poster", {}).get("local_path"),
                    "width": uv["width"],
                    "height": uv["height"],
                    "caption": text_of(ca.get("caption_1", {}).get("copy", "")),
                })
            rec["videos"] = vlist

        elif slug == "about":
            mod = p["content_modules"][0]["content_page_assets"]
            img = mod["image_1"]
            pid = add_photo(f"about-{img['id']}", img["local_image"], None,
                            img.get("archive_image_dimensions"), "", img.get("alt_text", ""))
            copy = mod["text_1"]["copy"]
            heading = text_of(re.search(r"<h2[^>]*>(.*?)</h2>", copy, re.S).group(1))
            paras = [text_of(x) for x in re.findall(r"<p[^>]*>(.*?)</p>", copy, re.S)]
            links = re.findall(r'href="([^"]+)"', copy)
            rec["portrait"] = pid
            rec["heading"] = re.sub(r"\s+", " ", heading)
            rec["paragraphs"] = [x for x in paras if x and not x.startswith("http")]
            rec["links"] = [{"href": h, "label": h} for h in links]
            ig = text_of(p["content_modules"][2]["content_page_assets"]["title_1"]["copy"])
            rec["instagram"] = {"heading": ig, "profile": sc["social_links"]["instagram"],
                                "link_label": "View @rophysjpeg on Instagram",
                                "note": "The old Format Instagram widget used a now-revoked token. "
                                        "This section links to the profile unless a new authorized feed is configured."}
            og_photo = pid

        elif slug == "contact":
            mods = p["content_modules"]
            copy = mods[0]["content_page_assets"]["text_1"]["copy"]
            rec["heading"] = text_of(re.search(r"<h2[^>]*>(.*?)</h2>", copy, re.S).group(1))
            rec["paragraphs"] = [text_of(x) for x in re.findall(r"<p[^>]*>(.*?)</p>", copy, re.S)]
            labels = mods[1]["content_page_assets"]
            rec["form"] = {
                "name_label": text_of(labels["label_1"]["copy"]),
                "email_label": text_of(labels["label_2"]["copy"]),
                "message_label": text_of(labels["label_3"]["copy"]),
                "submit_label": re.sub(r"\s+", " ", text_of(labels["label_4"]["copy"])),
            }

        rec["meta"] = meta_for(p, og_photo)
        out_pages.append(rec)

    # favicon source recorded in the original <head>
    fav = "assets/photos/52a320e0559d-Inter Miami October 19-Rophy-43.jpg"

    site = {
        "_readme": [
            "RophysJpeg website content map. Edit this file, then run: python3 tools/build.py",
            "photos{}: every image used by the site, keyed by id. 'source' = layout crop from the archive "
            "(local_image); 'source_original' = larger published copy (local_original) when one was saved.",
            "pages[]: gallery order is the order of the 'photos' list. Listing order is the order of 'items'.",
            "alt: the archive recorded no alt text for gallery photos; the build falls back to "
            "'<project title> - photograph N of M'. Add real descriptions here when you can.",
        ],
        "site": {
            "name": sc["site_name"],
            "og_site_name": "ROPHYSJPEG",
            "base_url": "https://www.rophysjpeg.com",
            "lang": "en",
            "copyright": "© rophysjpeg. All rights reserved.",
            "favicon_source": fav,
            "listing_layout": "masonry",
            "_listing_layout_options": "masonry = original Format behaviour (shortest-column stacking); "
                                       "rows = strict two-column rows, top-aligned",
        },
        "navigation": [{"label": n["label"], "href": n["route"]} for n in sc["navigation"]],
        "social": [
            {"label": "Instagram", "href": sc["social_links"]["instagram"], "icon": "instagram"},
            {"label": "LinkedIn", "href": sc["social_links"]["linkedin"], "icon": "linkedin"},
        ],
        "pages": out_pages,
        "photos": photos,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(site, f, indent=1, ensure_ascii=False)
    n_gal = sum(len(p.get("photos", [])) for p in out_pages)
    print(f"wrote {args.out}: {len(out_pages)} routes, {len(photos)} photo records, {n_gal} gallery placements")


if __name__ == "__main__":
    sys.exit(main())
