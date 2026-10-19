"""Simple editing layer for Pages CMS.

content/editor.json holds the fields that are safe and useful to edit by hand
(menu labels, home page picks, gallery titles/intros, page order, video text,
Contact page text). tools/build.py loads content/site.json and then applies
editor.json on top, so editor.json wins for those fields.

    python3 tools/cms.py export   # (re)create content/editor.json from site.json  (only if missing, or --force)
    python3 tools/cms.py config   # regenerate .pages.yml (dropdown options follow site.json)
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
SUFFIX = " - ROPHYSJPEG"


def _pages(site):
    return {p["slug"]: p for p in site["pages"]}


def _routes(site):
    return {p["route"]: p for p in site["pages"]}


def _gtitle(p):
    return p.get("meta", {}).get("title", p["slug"]).replace(SUFFIX, "").strip()


def galleries(site):
    return [p for p in site["pages"] if p.get("type") == "gallery"]


def _split(v):
    if v.get("title"):
        return v["title"], v.get("credit", "")
    cap = v.get("caption", "")
    m = re.search(r"\s(Filmed\b.*)$", cap)
    if m:
        return cap[:m.start()].rstrip(" ."), m.group(1)
    return cap.rstrip("."), ""


# --------------------------------------------------------------------------- export
def export(site):
    P = _pages(site)
    R = _routes(site)
    home = next(p for p in site["pages"] if p["route"] == "/")
    sc = home["showcase"]
    vids = P["video"]["videos"]
    ed = {"_note": "Edited with Pages CMS. tools/build.py applies these values on top of site.json."}
    ed["menu"] = [{"link": n["href"], "label": n["label"]} for n in site["navigation"]]
    sw = []
    for it in sc["items"]:
        if "video" in it:
            sw.append({"item": "video:" + it["video"], "title": "", "subtitle": "", "label": "", "link_label": "", "link_url": ""})
        else:
            l = it.get("link") or {}
            sw.append({"item": "gallery:" + it["gallery"], "title": it.get("title", ""), "subtitle": it.get("subtitle", ""),
                       "label": it.get("tag", ""), "link_label": l.get("label", ""), "link_url": l.get("href", "")})
    fg = sc.get("feature_gallery") or {}
    cs = home.get("contact_strip") or {}
    ed["home"] = {
        "featured_video": sc["featured_video"],
        "featured_gallery": fg.get("gallery", ""),
        "featured_gallery_label": fg.get("kicker", "Featured gallery"),
        "selected_work_heading": sc.get("heading", "Selected Work"),
        "selected_work": sw,
        "contact_heading": cs.get("heading", ""),
        "contact_email": cs.get("email", ""),
        "contact_button": cs.get("button", ""),
    }
    for key, slug in (("work", "editorial"), ("sport", "sport")):
        pg = P[slug]
        hero = pg.get("hero") or {}
        ed[key] = {"heading": hero.get("text", _gtitle(pg)),
                   "galleries": [{"gallery": it["href"]} for it in pg["items"]]}
    gl = []
    for g in galleries(site):
        intro = g.get("intro") or {}
        l = intro.get("link") or {}
        gl.append({"gallery": g["route"], "title": _gtitle(g), "label": intro.get("kicker", ""),
                   "intro": intro.get("text", ""), "link_label": l.get("label", ""), "link_url": l.get("href", "")})
    ed["galleries"] = gl
    vl = []
    for v in vids:
        t, c = _split(v)
        l = v.get("link") or {}
        vl.append({"video": v["id"], "title": t, "subtitle": v.get("subtitle", ""), "credit": c, "label": v.get("tag", ""),
                   "link_label": l.get("label", ""), "link_url": l.get("href", ""), "show": True})
    for v in P["video"].get("_removed_videos", []):
        t, c = _split(v)
        l = v.get("link") or {}
        vl.append({"video": v["id"], "title": t, "subtitle": v.get("subtitle", ""), "credit": c, "label": v.get("tag", ""),
                   "link_label": l.get("label", ""), "link_url": l.get("href", ""), "show": False})
    ed["videos"] = vl
    a = P["about"]
    sv = a.get("services") or {}
    ct = a.get("contact") or {}
    ed["contact"] = {
        "heading": a.get("heading", ""),
        "bio": "\n\n".join(a.get("intro", [])),
        "services_heading": sv.get("heading", ""),
        "services": [{"title": x["title"], "text": x["text"]} for x in sv.get("items", [])],
        "form_heading": ct.get("heading", ""),
        "form_text": "\n\n".join(ct.get("intro", [])),
    }
    return ed


# --------------------------------------------------------------------------- apply
def _link(label, url):
    url = (url or "").strip()
    return {"href": url, "label": (label or "").strip() or "Open link"} if url else None


def apply(site, ed):
    P = _pages(site)
    R = _routes(site)
    if ed.get("menu"):
        labels = {m["link"]: m["label"] for m in ed["menu"] if m.get("link")}
        for n in site["navigation"]:
            if labels.get(n["href"]):
                n["label"] = labels[n["href"]].strip()

    # galleries first (titles feed the listings)
    for g in ed.get("galleries", []):
        p = R.get(g.get("gallery"))
        if not p or p.get("type") != "gallery":
            continue
        t = (g.get("title") or "").strip()
        if t:
            p["meta"]["title"] = p["meta"]["og_title"] = t + SUFFIX
        intro = {}
        if (g.get("label") or "").strip():
            intro["kicker"] = g["label"].strip()
        if (g.get("intro") or "").strip():
            intro["text"] = g["intro"].strip()
        l = _link(g.get("link_label"), g.get("link_url"))
        if l and intro.get("text"):
            intro["link"] = dict(l, inline=True)
        old = p.get("intro") or {}
        if old.get("credit"):
            intro["credit"] = old["credit"]
        if intro:
            p["intro"] = intro
        else:
            p.pop("intro", None)

    for key, slug in (("work", "editorial"), ("sport", "sport")):
        e = ed.get(key)
        if not e:
            continue
        pg = P[slug]
        if (e.get("heading") or "").strip() and (pg.get("hero") or {}).get("kind") == "heading":
            pg["hero"]["text"] = e["heading"].strip()
            pg["meta"]["title"] = pg["meta"]["og_title"] = e["heading"].strip() + SUFFIX
        old = {it["href"]: it for it in pg["items"]}
        items = []
        for x in e.get("galleries", []):
            r = x.get("gallery")
            g = R.get(r)
            if not g or g.get("type") != "gallery" or not g.get("photos"):
                continue
            it = dict(old.get(r) or {"href": r, "photo": g["meta"].get("og_image_photo") or g["photos"][0]})
            if it["photo"] not in site["photos"]:
                it["photo"] = g["photos"][0]
            it["title"] = _gtitle(g)
            items.append(it)
        if items:
            pg["items"] = items

    vp = P["video"]
    allv = {v["id"]: v for v in vp["videos"] + vp.get("_removed_videos", [])}
    if ed.get("videos"):
        shown, hidden = [], []
        seen = set()
        for x in ed["videos"]:
            v = allv.get(x.get("video"))
            if not v or v["id"] in seen:
                continue
            seen.add(v["id"])
            if (x.get("title") or "").strip():
                v["title"] = x["title"].strip()
                v["credit"] = (x.get("credit") or "").strip()
            if (x.get("subtitle") or "").strip():
                v["subtitle"] = x["subtitle"].strip()
            else:
                v.pop("subtitle", None)
            v["tag"] = (x.get("label") or "").strip()
            l = _link(x.get("link_label"), x.get("link_url"))
            if l:
                v["link"] = l
            else:
                v.pop("link", None)
            (shown if x.get("show", True) else hidden).append(v)
        for vid, v in allv.items():
            if vid not in seen:
                (shown if v in vp["videos"] else hidden).append(v)
        for i, v in enumerate(shown, 1):
            if "order" in v:
                v["order"] = i
        vp["videos"] = shown
        vp["_removed_videos"] = hidden
    vids = {v["id"] for v in vp["videos"]}

    home = next(p for p in site["pages"] if p["route"] == "/")
    sc = home["showcase"]
    h = ed.get("home") or {}
    if h.get("featured_video") in vids:
        sc["featured_video"] = h["featured_video"]
    fg = h.get("featured_gallery")
    if fg is not None:
        g = R.get(fg)
        if g and g.get("type") == "gallery":
            cur = sc.get("feature_gallery") or {}
            photo = cur.get("photo") if cur.get("gallery") == fg and cur.get("photo") in site["photos"] else (g["meta"].get("og_image_photo") or g["photos"][0])
            sc["feature_gallery"] = {"gallery": fg, "photo": photo, "title": _gtitle(g),
                                     "kicker": (h.get("featured_gallery_label") or "Featured gallery").strip()}
        elif fg == "":
            sc.pop("feature_gallery", None)
    if (h.get("selected_work_heading") or "").strip():
        sc["heading"] = h["selected_work_heading"].strip()
    if h.get("selected_work"):
        old = {}
        for it in sc["items"]:
            old[("video:" + it["video"]) if "video" in it else ("gallery:" + it["gallery"])] = it
        items = []
        for x in h["selected_work"]:
            ref = x.get("item") or ""
            if ref.startswith("video:"):
                if ref[6:] in vids:
                    items.append({"video": ref[6:]})
            elif ref.startswith("gallery:"):
                g = R.get(ref[8:])
                if not g or g.get("type") != "gallery":
                    continue
                it = dict(old.get(ref) or {"gallery": ref[8:], "photo": g["meta"].get("og_image_photo") or g["photos"][0]})
                it["title"] = (x.get("title") or "").strip() or _gtitle(g)
                it["subtitle"] = (x.get("subtitle") or "").strip()
                it["tag"] = (x.get("label") or "").strip() or "Photo"
                l = _link(x.get("link_label"), x.get("link_url"))
                if l:
                    it["link"] = l
                else:
                    it.pop("link", None)
                items.append(it)
        if items:
            sc["items"] = items
    # never point at a hidden video
    if sc.get("featured_video") not in vids and vp["videos"]:
        sc["featured_video"] = vp["videos"][0]["id"]
    sc["items"] = [it for it in sc["items"] if "video" not in it or it["video"] in vids]
    if home.get("contact_strip") is not None or h.get("contact_heading"):
        cs = home.setdefault("contact_strip", {"href": "/about#contact"})
        for k, ek in (("heading", "contact_heading"), ("email", "contact_email"), ("button", "contact_button")):
            if (h.get(ek) or "").strip():
                cs[k] = h[ek].strip()

    c = ed.get("contact") or {}
    a = P["about"]
    if (c.get("heading") or "").strip():
        a["heading"] = c["heading"].strip()
    if (c.get("bio") or "").strip():
        a["intro"] = [x.strip() for x in re.split(r"\n\s*\n", c["bio"].strip()) if x.strip()]
    if c.get("services") is not None:
        items = [{"title": x["title"].strip(), "text": (x.get("text") or "").strip()} for x in c["services"] if (x.get("title") or "").strip()]
        if items:
            a["services"] = {"kicker": "", "heading": (c.get("services_heading") or "What I Do").strip(), "items": items}
        else:
            a.pop("services", None)
    ct = a.get("contact")
    if ct:
        if (c.get("form_heading") or "").strip():
            ct["heading"] = c["form_heading"].strip()
        if (c.get("form_text") or "").strip():
            ct["intro"] = [x.strip() for x in re.split(r"\n\s*\n", c["form_text"].strip()) if x.strip()]
    return site


# --------------------------------------------------------------------------- .pages.yml
def _q(s):
    return json.dumps(s, ensure_ascii=False)


def pages_yml(site):
    P = _pages(site)
    gal = [(g["route"], _gtitle(g)) for g in galleries(site)]
    vp = P["video"]
    vlist = [(v["id"], _split(v)[0]) for v in vp["videos"] + vp.get("_removed_videos", [])]
    def opts(pairs, indent):
        sp = " " * indent
        return "\n".join(f"{sp}- name: {_q(n)}\n{sp}  label: {_q(l)}" for n, l in pairs)
    gal_opts = lambda ind: opts(gal, ind)
    vid_opts = lambda ind: opts(vlist, ind)
    item_opts = lambda ind: opts([("gallery:" + r, "Gallery · " + t) for r, t in gal] + [("video:" + i, "Video · " + t) for i, t in vlist], ind)
    menu_opts = lambda ind: opts([(n["href"], n["href"]) for n in site["navigation"]], ind)
    return f"""# Pages CMS configuration (https://app.pagescms.org). Regenerate with: python3 tools/cms.py config
content:
  - name: site
    label: Edit website
    type: file
    path: content/editor.json
    format: json
    fields:
      - name: menu
        label: Menu
        description: Rename the menu tabs. Drag to reorder is not used; links stay the same.
        type: object
        list:
          collapsible:
            collapsed: true
            summary: "{{label}}"
        fields:
          - name: link
            label: Page
            type: select
            readonly: true
            options:
              values:
{menu_opts(16)}
          - name: label
            label: Tab name
            type: string
      - name: home
        label: Home page
        type: object
        fields:
          - name: featured_video
            label: Featured video (big video at the top)
            type: select
            options:
              values:
{vid_opts(16)}
          - name: featured_gallery
            label: Featured gallery (next to the featured video)
            type: select
            options:
              values:
{gal_opts(16)}
          - name: featured_gallery_label
            label: Small label above the featured gallery title
            type: string
          - name: selected_work_heading
            label: Heading above the grid
            type: string
          - name: selected_work
            label: Selected Work grid (top to bottom)
            description: Pick a gallery or a video for each box. Title, subtitle, label and link are only used for galleries (videos use their own text from the Videos section).
            type: object
            list:
              collapsible:
                collapsed: true
                summary: "{{index}}. {{item}}"
            fields:
              - name: item
                label: Gallery or video
                type: select
                options:
                  values:
{item_opts(20)}
              - name: title
                label: Title (galleries only, leave empty to use the gallery title)
                type: string
              - name: subtitle
                label: Subtitle (galleries only)
                type: string
              - name: label
                label: Small red label (galleries only), e.g. Photo · PUMA
                type: string
              - name: link_label
                label: Extra link text (optional), e.g. See the post on Instagram
                type: string
              - name: link_url
                label: Extra link address (optional)
                type: string
          - name: contact_heading
            label: Bottom contact section heading
            type: string
          - name: contact_email
            label: Email shown at the bottom
            type: string
          - name: contact_button
            label: Bottom button text
            type: string
      - name: work
        label: Work page
        type: object
        fields:
          - name: heading
            label: Page heading
            type: string
          - name: galleries
            label: Galleries on the Work page (top to bottom)
            type: object
            list:
              collapsible:
                collapsed: true
                summary: "{{index}}. {{gallery}}"
            fields:
              - name: gallery
                label: Gallery
                type: select
                options:
                  values:
{gal_opts(20)}
      - name: sport
        label: Sport page
        type: object
        fields:
          - name: heading
            label: Page heading
            type: string
          - name: galleries
            label: Galleries on the Sport page (top to bottom)
            type: object
            list:
              collapsible:
                collapsed: true
                summary: "{{index}}. {{gallery}}"
            fields:
              - name: gallery
                label: Gallery
                type: select
                options:
                  values:
{gal_opts(20)}
      - name: galleries
        label: Gallery text (titles and intros)
        description: The photos themselves are managed separately; this edits the words.
        type: object
        list:
          collapsible:
            collapsed: true
            summary: "{{title}}"
        fields:
          - name: gallery
            label: Gallery page
            type: select
            readonly: true
            options:
              values:
{gal_opts(16)}
          - name: title
            label: Title
            type: string
          - name: label
            label: Small red label above the title (optional)
            type: string
          - name: intro
            label: Intro text (optional, shown in a box above the photos)
            type: text
          - name: link_label
            label: Link text (optional), e.g. See the published post on Instagram
            type: string
          - name: link_url
            label: Link address (optional)
            type: string
      - name: videos
        label: Videos (Video page order, top to bottom)
        description: The first video in this list is not automatically featured; pick the featured video under Home page.
        type: object
        list:
          collapsible:
            collapsed: true
            summary: "{{index}}. {{title}}"
        fields:
          - name: video
            label: Video file
            type: select
            readonly: true
            options:
              values:
{vid_opts(16)}
          - name: show
            label: Show on the site
            type: boolean
          - name: title
            label: Title
            type: string
          - name: subtitle
            label: Subtitle (optional)
            type: string
          - name: credit
            label: Credit line, e.g. Filmed and edited by Rophy.
            type: string
          - name: label
            label: Small red label, e.g. Concacaf Gold Cup
            type: string
          - name: link_label
            label: Link text (optional), e.g. Watch on TikTok
            type: string
          - name: link_url
            label: Link address (optional)
            type: string
      - name: contact
        label: Contact page
        type: object
        fields:
          - name: heading
            label: Main heading
            type: string
          - name: bio
            label: Bio (leave an empty line between paragraphs)
            type: text
          - name: services_heading
            label: Services heading
            type: string
          - name: services
            label: Services
            type: object
            list:
              collapsible:
                collapsed: true
                summary: "{{title}}"
            fields:
              - name: title
                label: Title
                type: string
              - name: text
                label: Text
                type: text
          - name: form_heading
            label: Contact form heading
            type: string
          - name: form_text
            label: Text above the form (email addresses become links)
            type: text
"""


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    with open(os.path.join(PROJECT, "content", "site.json"), encoding="utf-8") as f:
        site = json.load(f)
    if cmd == "export":
        path = os.path.join(PROJECT, "content", "editor.json")
        if os.path.exists(path) and "--force" not in sys.argv:
            raise SystemExit("content/editor.json exists (use --force to overwrite)")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(export(site), f, indent=2, ensure_ascii=False)
            f.write("\n")
        print("wrote", path)
    elif cmd == "config":
        ed_path = os.path.join(PROJECT, "content", "editor.json")
        if os.path.exists(ed_path):
            with open(ed_path, encoding="utf-8") as f:
                apply(site, json.load(f))
        with open(os.path.join(PROJECT, ".pages.yml"), "w", encoding="utf-8") as f:
            f.write(pages_yml(site))
        print("wrote .pages.yml")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
