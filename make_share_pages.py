#!/usr/bin/env python3
"""Crea una pagina leggera per ogni torneo (cartella e/) con titolo, descrizione e immagine
per le anteprime di WhatsApp e Telegram. Chi apre il link viene portato nell'app, già sul torneo.
Serve la variabile SITE_URL (indirizzo del sito). Solo libreria standard."""
import html, json, os
from datetime import datetime
try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # senza Pillow resta l'immagine fissa share-card.jpg
    Image = None

SITE = os.environ.get("SITE_URL", "").rstrip("/")
MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]

def eh(u):  # stessa sigla usata dalla pagina e dai promemoria
    h = 5381
    for ch in u:
        h = (h * 33 + ord(ch)) & 0xFFFFFFFF
    d, n = "0123456789abcdefghijklmnopqrstuvwxyz", ""
    while h:
        n = d[h % 36] + n; h //= 36
    return n or "0"

def when(e):
    try:
        d = datetime.strptime(e["date"], "%Y-%m-%d"); s = "%d %s" % (d.day, MESI[d.month - 1])
        if e.get("end"):
            f = datetime.strptime(e["end"], "%Y-%m-%d")
            s = ("%d–%d %s" % (d.day, f.day, MESI[d.month - 1])) if (f.month == d.month and f.year == d.year) else s + "–%d %s" % (f.day, MESI[f.month - 1])
        return s + (" ore " + e["time"] if e.get("time") else "")
    except Exception:
        return ""

def desc(e):
    p = []
    if e.get("type") and e["type"] != "Torneo": p.append(e["type"])
    if e.get("cash") is True: p.append("Money tournament")
    elif e.get("cash") is False: p.append("For Fun")
    p.append("Online" if e.get("mode") == "online" else (e.get("where") or "Dal vivo"))
    if when(e): p.append(when(e))
    if e.get("reg"): p.append("Reg. " + e["reg"])
    if e.get("fee") == 0: p.append("Gratis")
    elif e.get("fee"): p.append("Iscrizione %s %s" % (str(e["fee"]).replace(".", ","), e.get("cur") or "€"))
    if e.get("prize") and e.get("cash"): p.append("Premio: " + e["prize"])
    return " · ".join(p)

FONT_B = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"]
FONT_R = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"]

def font(paths, size):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    return lines + ([cur] if cur else [])

def tag(e):
    t = e.get("type") or ""
    if t == "Mondiale": return "MONDIALI", (0, 0, 0), (255, 255, 255)
    if t == "Internazionale": return "INTERNAZIONALE", (11, 122, 84), (255, 255, 255)
    if t == "Special Event": return "SPECIAL EVENT", (255, 210, 31), (74, 54, 0)
    if t == "Regionale": return "REGIONALE", (217, 119, 6), (255, 255, 255)
    if t == "Global Challenge": return "GLOBAL CHALLENGE", (255, 255, 255), (42, 18, 48)
    if e.get("cash") is True: return "MONEY TOURNAMENT", (255, 210, 31), (74, 54, 0)
    if e.get("cash") is False: return "FOR FUN", (200, 190, 215), (42, 18, 48)
    return "TORNEO ONLINE", (124, 58, 237), (255, 255, 255)

def card(e, path):
    """Immagine 1200x630 per l'anteprima del singolo torneo."""
    W, H = 1200, 630
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    a, b, c = (11, 12, 36), (74, 24, 120), (160, 20, 50)
    for x in range(W):
        t = x / (W - 1)
        col = tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3)) if t < .7 else tuple(int(b[i] * (1 - (t - .7) / .3) + c[i] * ((t - .7) / .3)) for i in range(3))
        d.line([(x, 0), (x, H)], fill=col)
    try:
        egg = Image.open("logo-egg.webp").convert("RGBA"); eh_ = 520
        egg = egg.resize((int(eh_ * egg.width / egg.height), eh_)); im.paste(egg, (50, 55), egg)
    except Exception:
        pass
    x0 = 500; label, bg, fg = tag(e)
    fl = font(FONT_B, 26); tw = d.textlength(label, font=fl)
    d.rounded_rectangle([x0, 50, x0 + tw + 44, 100], radius=25, fill=bg); d.text((x0 + 22, 58), label, font=fl, fill=fg)
    parts = e["name"].split(" | ")
    title, extra = parts[0], [p for p in parts[1:] if not p.lower().startswith("reg")]
    fn = font(FONT_B, 66); lines = wrap(d, title, fn, W - x0 - 50)[:3]; y = 125
    for ln in lines:
        d.text((x0, y), ln, font=fn, fill="white"); y += 78
    y = max(y + 12, 330)
    if when(e): d.text((x0, y), when(e), font=font(FONT_B, 40), fill=(255, 220, 225)); y += 56
    det = ["Online" if e.get("mode") == "online" else (e.get("where") or "Dal vivo")]
    if e.get("reg"): det.append("Reg. " + e["reg"])
    if e.get("fee") == 0: det.append("Gratis")
    elif e.get("fee"): det.append("%s %s" % (str(e["fee"]).replace(".", ","), e.get("cur") or "€"))
    det += extra[:1]
    fd = font(FONT_R, 32); maxw = W - x0 - 50
    while len(det) > 1 and d.textlength(" · ".join(det), font=fd) > maxw: det.pop()
    if d.textlength(" · ".join(det), font=fd) > maxw: fd = font(FONT_R, 26)
    d.text((x0, y), " · ".join(det), font=fd, fill=(230, 215, 245)); y += 52
    opened = bool(e.get("signup")) or "limitlesstcg.com" in (e.get("url") or "")
    if e.get("regClose"):
        try:
            c = datetime.strptime(e["regClose"], "%Y-%m-%d"); st = "Iscrizioni fino al %d %s" % (c.day, MESI[c.month - 1])
        except Exception:
            st = "Iscrizioni aperte"
    else:
        st = "Iscrizioni aperte" if opened else ""
    if st: d.text((x0, y), st, font=font(FONT_B, 34), fill=(120, 235, 170))
    d.line([x0, 560, W - 50, 560], fill=(255, 255, 255), width=2)
    d.text((x0, 574), "rAKings VGC  ·  tornei Pokémon", font=font(FONT_B, 28), fill="white")
    im.save(path, quality=82, optimize=True)

def page(e, img=None):
    h = eh(e["url"]); url = "%s/e/%s.html" % (SITE, h)
    t = html.escape(e["name"] + " · rAKings VGC", True); ds = html.escape(desc(e), True); img = img or SITE + "/share-card.jpg"
    return """<!doctype html>
<html lang="it"><head><meta charset="utf-8"><title>%(t)s</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<meta property="og:type" content="website"><meta property="og:site_name" content="rAKings VGC">
<meta property="og:title" content="%(t)s"><meta property="og:description" content="%(d)s">
<meta property="og:url" content="%(u)s"><meta property="og:image" content="%(i)s">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="%(t)s">
<meta name="twitter:description" content="%(d)s"><meta name="twitter:image" content="%(i)s">
<link rel="canonical" href="%(u)s">
<script>location.replace("../index.html#e=%(h)s")</script></head>
<body style="font-family:system-ui,sans-serif;background:#1d0b0d;color:#fff;text-align:center;padding:40px 16px">
<p>Apro rAKings VGC…</p><p><a style="color:#ff6b78" href="../index.html#e=%(h)s">Apri il torneo nell'app</a></p></body></html>
""" % {"t": t, "d": ds, "u": url, "i": img, "h": h}

def main():
    if not SITE.startswith("http"):
        print("SITE_URL non impostato: pagine di condivisione non create"); return
    ev = json.load(open("events.json", encoding="utf-8")).get("events", [])
    os.makedirs("e", exist_ok=True); keep = set()
    for e in ev:
        if not e.get("url"): continue
        h = eh(e["url"]); n = h + ".html"; keep.add(n)
        jpg = "e/%s.jpg" % h; ok = False
        if Image is not None:
            try:
                p0 = "e/" + n; old = open(p0, encoding="utf-8").read() if os.path.exists(p0) else ""
                if (not os.path.exists(jpg)) or old != page(e, SITE + "/e/%s.jpg" % h):
                    card(e, jpg)
                ok = True; keep.add(h + ".jpg")
            except Exception as ex:
                print("Carta non creata per %s: %s" % (e["name"], ex))
        p = page(e, SITE + "/e/%s.jpg" % h if ok else None)
        if not os.path.exists("e/" + n) or open("e/" + n, encoding="utf-8").read() != p:
            open("e/" + n, "w", encoding="utf-8").write(p)
    for f in os.listdir("e"):
        if f.endswith((".html", ".jpg")) and f not in keep: os.remove("e/" + f)
    print("Pagine di condivisione: %d" % len(keep))

main()
