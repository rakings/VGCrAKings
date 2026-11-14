"""Immagini per Instagram e X (1080x1350, formato 4:5 del feed) generate in automatico.
Solo grafica del sito: testo, colori e logo rAKings. Nessuna immagine ufficiale Pokemon."""
import os
from PIL import Image, ImageDraw, ImageFont

QUI = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(QUI, "bric.ttf")   # carattere del sito (Bricolage Grotesque, licenza libera OFL)
W, H = 1080, 1350
BG, CARD, LINE = (20, 18, 10), (33, 29, 12), (70, 62, 30)
GIALLO, INK, BIANCO, GRIGIO = (255, 210, 31), (74, 54, 0), (245, 243, 235), (170, 165, 150)
ORO, ARGENTO, BRONZO = (255, 210, 31), (205, 210, 220), (214, 150, 90)


def f(size, peso="Bold"):
    ft = ImageFont.truetype(FONT, size)
    try:
        ft.set_variation_by_name(peso)
    except Exception:
        pass
    return ft


def adatta(d, testo, maxw, size, peso="Bold", minimo=26):
    """Rimpicciolisce il testo finche' entra; se non entra neanche al minimo, lo taglia con «…»."""
    while size > minimo and d.textlength(testo, font=f(size, peso)) > maxw:
        size -= 2
    ft = f(size, peso)
    while d.textlength(testo, font=ft) > maxw and len(testo) > 2:
        testo = testo[:-2].rstrip() + "…"
    return testo, ft


def base(etichetta, piede="Top 8 e squadre su rAKings VGC"):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    for i in range(0, W + H, 46):                       # trama leggera a righe diagonali
        d.line([(i, 0), (i - H, H)], fill=(26, 23, 12), width=14)
    d.rounded_rectangle([60, 64, 60 + d.textlength(etichetta, font=f(34, "ExtraBold")) + 56, 124], 30, fill=GIALLO)
    d.text((88, 94), etichetta, font=f(34, "ExtraBold"), fill=INK, anchor="lm")
    d.text((W - 60, 94), "rAKings VGC", font=f(40, "ExtraBold"), fill=GIALLO, anchor="rm")
    d.line([(60, H - 120), (W - 60, H - 120)], fill=LINE, width=3)
    d.text((60, H - 72), piede, font=f(30, "SemiBold"), fill=GRIGIO, anchor="lm")
    return im, d


def top8(titolo, negozio, citta, data, nomi, out):
    """titolo: tipo di torneo; nomi: dal 1° all'8° (gli stessi gia' pubblicati sul sito). Se sono meno di 8 si mostrano solo quelli."""
    im, d = base("TOP 8")
    t, ft = adatta(d, titolo, W - 120, 84, "ExtraBold")
    d.text((60, 200), t, font=ft, fill=BIANCO, anchor="lm")
    t, ft = adatta(d, negozio, W - 120, 50, "Bold")
    d.text((60, 284), t, font=ft, fill=GIALLO, anchor="lm")
    d.text((60, 344), "%s · %s" % (citta, data), font=f(36, "Medium"), fill=GRIGIO, anchor="lm")
    y = 392
    nomi = [str(n or "").strip() or "—" for n in nomi][:8]
    for i, n in enumerate(nomi):
        h = 136 if i == 0 else 80
        d.rounded_rectangle([60, y, W - 60, y + h], 22, fill=CARD, outline=GIALLO if i == 0 else LINE, width=4 if i == 0 else 2)
        col = [ORO, ARGENTO, BRONZO, BRONZO][i] if i < 4 else GRIGIO
        cx, cy = 60 + 70, y + h // 2
        r = 44 if i == 0 else 30
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
        d.text((cx, cy + 2), str(i + 1), font=f(52 if i == 0 else 36, "ExtraBold"), fill=BG, anchor="mm")
        if i == 0:
            d.text((200, cy - 28), "VINCITORE", font=f(28, "ExtraBold"), fill=GIALLO, anchor="lm")
            t, ft = adatta(d, n or "—", W - 300, 60, "ExtraBold")
            d.text((200, cy + 22), t, font=ft, fill=BIANCO, anchor="lm")
        else:
            t, ft = adatta(d, n or "—", W - 300, 44, "Bold")
            d.text((200, cy + 2), t, font=ft, fill=BIANCO, anchor="lm")
        y += h + 12
    im.save(out, "JPEG", quality=92)


def money(nome, premio, quando, dove, out):
    """Torneo con premio in denaro: nome, premio (es. "500 €"), data/ora e piattaforma."""
    im, d = base("MONEY TOURNAMENT", "Tutti i tornei su rAKings VGC")
    d.text((60, 250), "Montepremi", font=f(44, "SemiBold"), fill=GRIGIO, anchor="lm")
    t, ft = adatta(d, premio, W - 120, 220, "ExtraBold", 80)
    d.text((54, 410), t, font=ft, fill=GIALLO, anchor="lm")
    d.line([(60, 560), (W - 60, 560)], fill=LINE, width=3)
    righe, parole = [], nome.split()
    while parole and len(righe) < 3:                    # nome del torneo su massimo 3 righe
        r = parole.pop(0)
        while parole and d.textlength(r + " " + parole[0], font=f(76, "ExtraBold")) <= W - 120:
            r += " " + parole.pop(0)
        righe.append(r)
    if parole:
        righe[-1] = adatta(d, righe[-1] + " " + " ".join(parole), W - 120, 76, "ExtraBold", 76)[0]
    y = 650
    for r in righe:
        d.text((60, y), r, font=f(76, "ExtraBold"), fill=BIANCO, anchor="lm")
        y += 92
    y += 40
    for ic, txt in (("Quando", quando), ("Dove", dove)):
        d.rounded_rectangle([60, y, W - 60, y + 110], 22, fill=CARD, outline=LINE, width=2)
        d.text((96, y + 55), ic, font=f(32, "SemiBold"), fill=GRIGIO, anchor="lm")
        t, ft = adatta(d, txt, W - 400, 42, "Bold")
        d.text((W - 96, y + 55), t, font=ft, fill=BIANCO, anchor="rm")
        y += 130
    im.save(out, "JPEG", quality=92)


if __name__ == "__main__":   # prova: python3 social_img.py  -> crea prova_top8.jpg e prova_money.jpg
    top8("Sfida di Lega", "Games Academy Roma", "Roma", "14 novembre 2026",
         ["Marco Rossi", "Giulia B.", "Luca Bianchi", "Shadow", "Andrea Verdi", "F.M.", "Paolo Ferrari", "Sara Colombo"], "prova_top8.jpg")
    money("VGC Italia Winter Cup Reg H", "500 €", "Sabato 21 novembre · 15:00", "Limitless", "prova_money.jpg")
