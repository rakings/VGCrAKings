#!/usr/bin/env python3
"""Schede di condivisione per le Top 8 dei locali (cartella l/) e per gli annunci della bacheca (cartella a/).
Ogni scheda e' una pagina leggera con titolo, descrizione e immagine 1200x630 per le anteprime di WhatsApp, Telegram,
Facebook, X, Discord ecc.; chi apre il link viene portato nel sito, gia' sulla Top 8 o sull'annuncio.
Gira dal flusso «Schede di condivisione» quando cambiano locali.json o annunci.json (o dopo i flussi che li modificano).
Crea solo le schede che mancano o che sono cambiate e cancella quelle di Top 8 e annunci tolti (il repo resta leggero).
Serve SITE_URL (indirizzo del sito) e Pillow. Solo grafica del sito: nessuna immagine ufficiale Pokemon."""
import html, json, os, re, textwrap
from PIL import Image, ImageDraw

import social_img as S

SITE = os.environ.get("SITE_URL", "").rstrip("/")
VERSIONE = "1"      # se cambia la grafica, aumentarla: le schede si rifanno tutte
W, H = 1200, 630
ROSSO, NERO, BIANCO, GIALLO, INK = (228, 30, 52), (16, 12, 12), (248, 246, 240), (255, 210, 31), (74, 54, 0)
f, adatta = S.f, S.adatta


def eh(u):
    """Stessa sigla di eh() nella pagina (JavaScript lavora sulle unita' UTF-16: qui si fa lo stesso)."""
    b = u.encode("utf-16-le")
    h = 5381
    for i in range(0, len(b), 2):
        h = (h * 33 + (b[i] | (b[i + 1] << 8))) & 0xFFFFFFFF
    d, n = "0123456789abcdefghijklmnopqrstuvwxyz", ""
    while h:
        n = d[h % 36] + n
        h //= 36
    return n or "0"


def lid(l):
    return eh("|".join(str(l.get(k) or "") for k in ("t", "s", "c", "d")))


def righe(testo, larghezza, quante):
    out = []
    # a capo scritti in modi diversi (\r\n di Windows, U+2028 dei testi copiati da X/Twitter) diventano tutti \n
    for par in re.sub(r"\r\n?|[\u2028\u2029\u0085]", "\n", str(testo or "")).split("\n"):
        out += textwrap.wrap(par, larghezza) or []
    return out[:quante]


def card_top8(l, out):
    im = Image.new("RGB", (W, H), BIANCO)
    d = ImageDraw.Draw(im)
    a_top, a_bot, b_top, b_bot = 470, 330, 1130, 990          # fasce oblique: rosso, nero, bianco
    d.polygon([(0, 0), (a_top, 0), (a_bot, H), (0, H)], fill=ROSSO)
    d.polygon([(a_top, 0), (b_top, 0), (b_bot, H), (a_bot, H)], fill=NERO)
    m = 44
    d.rounded_rectangle([m, 40, m + d.textlength("TOP 8", font=f(30, "ExtraBold")) + 44, 88], 24, fill=GIALLO)
    d.text((m + 22, 64), "TOP 8", font=f(30, "ExtraBold"), fill=INK, anchor="lm")
    y = 150
    for r in righe(l.get("t"), 16, 2):
        t, ft = adatta(d, r, 360, 64, "ExtraBold", 36)
        d.text((m, y), t, font=ft, fill=BIANCO, anchor="lm")
        y += 70
    t, ft = adatta(d, str(l.get("s") or ""), 320, 40, "Bold", 24)
    d.text((m, y + 10), t, font=ft, fill=GIALLO, anchor="lm")
    t, ft = adatta(d, str(l.get("c") or ""), 300, 32, "SemiBold", 22)
    d.text((m, y + 62), t, font=ft, fill=BIANCO, anchor="lm")
    t, ft = adatta(d, str(l.get("d") or ""), 280, 32, "SemiBold", 22)
    d.text((m, y + 104), t, font=ft, fill=BIANCO, anchor="lm")
    if l.get("n"):
        d.text((m, y + 150), "%s giocatori" % l["n"], font=f(30, "Bold"), fill=BIANCO, anchor="lm")
    nomi = [str(x or "").strip() or "—" for x in (l.get("top") or [])][:8]
    x0 = 520
    if nomi:
        d.text((x0, 70), "VINCITORE", font=f(30, "ExtraBold"), fill=GIALLO, anchor="lm")
        t, ft = adatta(d, nomi[0], 520, 64, "ExtraBold", 34)
        d.text((x0, 128), t, font=ft, fill=BIANCO, anchor="lm")
    y = 210
    for i, nm in enumerate(nomi[1:], start=2):
        xx = x0 - (y - 210) * 0.22                               # a scaletta lungo la diagonale
        d.text((xx, y), str(i), font=f(36, "ExtraBold"), fill=GIALLO if i <= 4 else (190, 180, 170), anchor="lm")
        t, ft = adatta(d, nm, 470, 36, "Bold", 22)
        d.text((xx + 56, y), t, font=ft, fill=BIANCO, anchor="lm")
        y += 54
    d.text((W - 30, H - 70), "rAKings", font=f(40, "ExtraBold"), fill=NERO, anchor="rm")
    d.text((W - 30, H - 30), "VGC", font=f(30, "ExtraBold"), fill=ROSSO, anchor="rm")
    im.save(out, "JPEG", quality=85, optimize=True)


def etichetta(a):
    if a.get("partner") == "pardini":
        return "FRANCESCO PARDINI", (124, 58, 237)
    if a.get("partner") == "rakings":
        return "rAKings VGC", ROSSO
    return "ANNUNCIO", ROSSO


def card_annuncio(a, out):
    lab, col = etichetta(a)
    im = Image.new("RGB", (W, H), (29, 11, 13))
    d = ImageDraw.Draw(im)
    d.polygon([(0, 0), (150, 0), (60, H), (0, H)], fill=col)    # diagonale come i post
    foto, s = a.get("img") or "", 470
    try:
        ph = Image.open(foto).convert("RGB") if foto.startswith("img/annunci/") and os.path.exists(foto) else None
    except Exception:
        ph = None
    if ph is None:                                               # senza foto: l'uovo di rAKings
        try:
            ph = Image.open("logo-egg.webp").convert("RGB")
        except Exception:
            ph = None
    if ph is not None:
        r = max(s / ph.width, H / ph.height)
        ph = ph.resize((int(ph.width * r) + 1, int(ph.height * r) + 1))
        x, y = (ph.width - s) // 2, (ph.height - H) // 2
        ph = ph.crop((x, y, x + s, y + H))
        mask = Image.new("L", (s, H), 0)
        ImageDraw.Draw(mask).polygon([(90, 0), (s, 0), (s, H), (0, H)], fill=255)
        im.paste(ph, (W - s, 0), mask)
    d = ImageDraw.Draw(im)
    m, maxw = 110, W - (s if ph is not None else 0) - 130
    lw = d.textlength(lab, font=f(28, "ExtraBold"))
    d.rounded_rectangle([m, 46, m + lw + 44, 92], 23, fill=col)
    d.text((m + 22, 69), lab, font=f(28, "ExtraBold"), fill=(255, 255, 255), anchor="lm")
    y = 160
    for r in righe(a.get("t"), 22, 3):
        t, ft = adatta(d, r, maxw, 60, "ExtraBold", 34)
        d.text((m, y), t, font=ft, fill=(255, 241, 239), anchor="lm")
        y += 68
    y += 10
    for r in righe(a.get("d"), 38, 4):
        t, ft = adatta(d, r, maxw, 34, "SemiBold", 22)
        d.text((m, y), t, font=ft, fill=(224, 170, 166), anchor="lm")
        y += 44
    d.line([(m, H - 90), (m + maxw, H - 90)], fill=(81, 37, 41), width=2)
    d.text((m, H - 52), "Bacheca di rAKings VGC", font=f(30, "Bold"), fill=GIALLO, anchor="lm")
    im.save(out, "JPEG", quality=76, optimize=True, progressive=True)


def pagina(url, titolo, descr, img, destinazione, alt):
    e = lambda s: html.escape(s, True)
    return """<!doctype html>
<html lang="it"><head><meta charset="utf-8"><title>%(t)s</title>
<!-- scheda di condivisione v%(v)s -->
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<meta name="description" content="%(d)s">
<meta property="og:type" content="website"><meta property="og:site_name" content="rAKings VGC"><meta property="og:locale" content="it_IT">
<meta property="og:title" content="%(t)s"><meta property="og:description" content="%(d)s">
<meta property="og:url" content="%(u)s"><meta property="og:image" content="%(i)s"><meta property="og:image:secure_url" content="%(i)s">
<meta property="og:image:type" content="image/jpeg"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:image:alt" content="%(a)s">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="%(t)s">
<meta name="twitter:description" content="%(d)s"><meta name="twitter:image" content="%(i)s"><meta name="twitter:image:alt" content="%(a)s">
<link rel="canonical" href="%(u)s">
<script>location.replace("%(g)s")</script></head>
<body style="font-family:system-ui,sans-serif;background:#1d0b0d;color:#fff;text-align:center;padding:40px 16px">
<p>Apro rAKings VGC…</p><p><a style="color:#ff6b78" href="%(g)s">Apri nel sito</a></p></body></html>
""" % {"t": e(titolo), "d": e(descr), "u": e(url), "i": e(img), "g": e(destinazione), "a": e(alt), "v": VERSIONE}


def scrivi(cartella, sigla, html_testo, disegna, tieni):
    p_html, p_jpg = "%s/%s.html" % (cartella, sigla), "%s/%s.jpg" % (cartella, sigla)
    tieni.update({sigla + ".html", sigla + ".jpg"})
    vecchio = open(p_html, encoding="utf-8").read() if os.path.exists(p_html) else ""
    if vecchio == html_testo and os.path.exists(p_jpg):
        return 0
    disegna(p_jpg)
    open(p_html, "w", encoding="utf-8").write(html_testo)
    return 1


def pulisci(cartella, tieni):
    for nome in os.listdir(cartella):
        if nome.endswith((".html", ".jpg")) and nome not in tieni:
            os.remove(os.path.join(cartella, nome))


def carica(nome, chiave):
    try:
        x = json.load(open(nome, encoding="utf-8"))
    except Exception:
        return None                                             # file illeggibile: non si tocca niente
    return x.get(chiave, []) if isinstance(x, dict) else (x if isinstance(x, list) else [])


def corto(s, n=180):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def main():
    if not SITE.startswith("http"):
        print("SITE_URL non impostato: schede non create")
        return
    fatte = 0
    loc = carica("locali.json", "locali")
    if loc is not None:
        os.makedirs("l", exist_ok=True)
        tieni = set()
        for l in loc:
            if not isinstance(l, dict) or not l.get("top") or not l.get("t"):
                continue
            s = lid(l)
            vinc = str(l["top"][0] or "").strip()
            titolo = "Top 8 · %s · %s" % (l.get("t"), l.get("s") or "")
            descr = corto(" · ".join(x for x in [str(l.get("c") or ""), str(l.get("d") or ""),
                                                 ("%s giocatori" % l["n"]) if l.get("n") else "",
                                                 ("Vincitore: " + vinc) if vinc else ""] if x) + ". Top 8 e squadre su rAKings VGC")
            pag = pagina("%s/l/%s.html" % (SITE, s), titolo + " · rAKings VGC", descr, "%s/l/%s.jpg" % (SITE, s),
                         "../index.html#locali-" + s, "Top 8 di %s" % l.get("t"))
            fatte += scrivi("l", s, pag, lambda p, l=l: card_top8(l, p), tieni)
        pulisci("l", tieni)
    ann = carica("annunci.json", "annunci")
    if ann is not None:
        os.makedirs("a", exist_ok=True)
        tieni = set()
        for a in ann:
            if not isinstance(a, dict) or not a.get("t") or not str(a.get("id") or "").isdigit():
                continue
            s = str(a["id"])
            lab = etichetta(a)[0]
            chi = "Francesco Pardini" if lab == "FRANCESCO PARDINI" else "rAKings VGC"
            # la scheda dipende anche dalla foto: se cambia la foto, cambia la pagina e si rifa' l'immagine
            impronta = str(os.path.getsize(a["img"])) if a.get("img") and os.path.exists(a["img"]) else "0"
            pag = pagina("%s/a/%s.html" % (SITE, s), "%s · %s" % (a["t"], chi), corto(a.get("d") or "Annuncio nella bacheca di rAKings VGC"),
                         "%s/a/%s.jpg?f=%s" % (SITE, s, impronta), "../index.html#annuncio-" + s, "Annuncio: %s" % a["t"])
            fatte += scrivi("a", s, pag, lambda p, a=a: card_annuncio(a, p), tieni)
        pulisci("a", tieni)
    print("Schede di condivisione create o aggiornate: %d" % fatte)


main()
