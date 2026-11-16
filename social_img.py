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


def base(etichetta, piede="Top 8 and teams on rAKings VGC"):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    passo, strisce = 54, [(228, 30, 52), (16, 12, 12), (248, 246, 240)]   # righe oblique: rosso, nero, bianco a giro
    for k, x in enumerate(range(-H, W + passo, passo)):
        d.polygon([(x, H), (x + passo, H), (x + passo + H, 0), (x + H, 0)], fill=strisce[k % 3])
    velo = Image.new("RGBA", (W, H), (0, 0, 0, 0))     # riquadro scuro (un po' trasparente) dove sta il testo: si legge sempre
    ImageDraw.Draw(velo).rounded_rectangle([34, 152, W - 34, H - 34], 40, fill=BG + (232,))
    im = Image.alpha_composite(im.convert("RGBA"), velo).convert("RGB")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([60, 64, 60 + d.textlength(etichetta, font=f(34, "ExtraBold")) + 56, 124], 30, fill=GIALLO)
    d.text((88, 94), etichetta, font=f(34, "ExtraBold"), fill=INK, anchor="lm")
    lw = d.textlength("rAKings VGC", font=f(36, "ExtraBold"))
    d.rounded_rectangle([W - 60 - lw - 56, 64, W - 60, 124], 30, fill=BG)
    d.text((W - 60 - 28, 94), "rAKings VGC", font=f(36, "ExtraBold"), fill=GIALLO, anchor="rm")
    d.line([(60, H - 120), (W - 60, H - 120)], fill=LINE, width=3)
    d.text((60, H - 72), piede, font=f(30, "SemiBold"), fill=GRIGIO, anchor="lm")
    return im, d


def top8_vecchio(titolo, negozio, citta, data, nomi, out):
    """titolo: tipo di torneo; nomi: dal 1° all'8° (gli stessi gia' pubblicati sul sito). Se sono meno di 8 si mostrano solo quelli."""
    im, d = base("TOP 8")
    t, ft = adatta(d, titolo, W - 120, 84, "ExtraBold")
    d.text((70, 214), t, font=ft, fill=BIANCO, anchor="lm")
    t, ft = adatta(d, negozio, W - 120, 50, "Bold")
    d.text((70, 292), t, font=ft, fill=GIALLO, anchor="lm")
    d.text((70, 346), "%s · %s" % (citta, data), font=f(36, "Medium"), fill=GRIGIO, anchor="lm")
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
            d.text((200, cy - 28), "WINNER", font=f(28, "ExtraBold"), fill=GIALLO, anchor="lm")
            t, ft = adatta(d, n or "—", W - 300, 60, "ExtraBold")
            d.text((200, cy + 22), t, font=ft, fill=BIANCO, anchor="lm")
        else:
            t, ft = adatta(d, n or "—", W - 300, 44, "Bold")
            d.text((200, cy + 2), t, font=ft, fill=BIANCO, anchor="lm")
        y += h + 12
    im.save(out, "JPEG", quality=92)


def money(nome, premio, quando, dove, out):
    """Torneo con premio in denaro: nome, premio (es. "500 €"), data/ora e piattaforma."""
    im, d = base("MONEY TOURNAMENT", "Every tournament on rAKings VGC")
    d.text((60, 250), "Prize pool", font=f(44, "SemiBold"), fill=GRIGIO, anchor="lm")
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
    for ic, txt in (("When", quando), ("Where", dove)):
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


# ======================= MONEY TOURNAMENT DELLA SETTIMANA + REGIONALI E VR (2026-11-16) =======================
# Quadrato 1080x1080 diviso da una diagonale (da angolo ad angolo) in due triangoli con i colori del sito.
# Caratteri «da gioco» (licenza libera OFL), alternati una slide si' e una no: Russo One / Chakra Petch; titoli in Bungee.
import re as _re, glob as _glob, hashlib as _hl

# Caratteri «simpatici» (stile Halloween, tutti a licenza libera, cartella caratteri/): ogni torneo ne riceve uno a caso,
# sempre lo stesso per lo stesso torneo, e mai uguale a quello dell'altro torneo nella stessa slide.
DIVERTENTI = sorted(_glob.glob(os.path.join(QUI, "caratteri", "*.ttf")))


def carattere_per(nome, evita=None):
    if not DIVERTENTI:
        return None
    i = int(_hl.sha1(str(nome).encode("utf-8")).hexdigest()[:8], 16) % len(DIVERTENTI)
    if DIVERTENTI[i] == evita and len(DIVERTENTI) > 1:
        i = (i + 1) % len(DIVERTENTI)
    return DIVERTENTI[i]

Q = 1080
F_A = os.path.join(QUI, "RussoOne-Regular.ttf")
F_B = os.path.join(QUI, "ChakraPetch-Bold.ttf")
F_T = os.path.join(QUI, "Bungee-Regular.ttf")
MARRONE, ROSSO, ORO2, AZZURRO, GIALLO2 = (42, 17, 22), (214, 52, 70), (255, 200, 58), (134, 216, 240), (255, 210, 31)
NOTTE = (20, 10, 12)


def ft(path, size):
    return ImageFont.truetype(path, size)


def pulito(t):
    """Via emoji e simboli che i caratteri non hanno (resterebbero quadratini)."""
    t = _re.sub(r"[^\w\s\-.,:;!?'\"&()/#+€$£%@|·–—]", " ", str(t or ""), flags=_re.UNICODE)
    return _re.sub(r"\s+", " ", t).strip(" -|·") or "Torneo"


def a_capo(d, testo, font, larghezze, max_righe):
    """Divide il testo in righe; larghezze[i] = spazio disponibile per la riga i (nel triangolo si stringe)."""
    parole, righe = testo.split(), []
    while parole and len(righe) < max_righe:
        w = larghezze[min(len(righe), len(larghezze) - 1)]
        r = parole.pop(0)
        while parole and d.textlength(r + " " + parole[0], font=font) <= w:
            r += " " + parole.pop(0)
        while d.textlength(r, font=font) > w and len(r) > 3:
            r = r[:-2].rstrip() + "…"
        righe.append(r)
    if parole and righe:
        r = righe[-1]
        while d.textlength(r + "…", font=font) > larghezze[min(len(righe) - 1, len(larghezze) - 1)] and len(r) > 3:
            r = r[:-1]
        righe[-1] = r.rstrip() + "…"
    return righe


def _diagonale(colA, colB):
    im = Image.new("RGB", (Q, Q), colB)
    d = ImageDraw.Draw(im)
    d.polygon([(0, 0), (Q, 0), (0, Q)], fill=colA)              # triangolo in alto a sinistra
    d.line([(Q, 0), (0, Q)], fill=(255, 255, 255), width=10)   # la diagonale, da angolo ad angolo
    return im, d


def _alt(d, font, testo="ÀgHy"):
    """Altezza vera di una riga in quel carattere (i caratteri «simpatici» hanno misure molto diverse tra loro)."""
    l, t, r, b = d.textbbox((0, 0), testo, font=font)
    return b - t, t


def _blocco(d, t, font_path, alto, colore_testo, colore_premio, fondo=0, fun=None):
    """Un torneo dentro il suo triangolo. alto=True: triangolo in alto a sinistra (testo da sinistra, dall'alto);
    alto=False: triangolo in basso a destra (testo allineato a destra, dal basso). Le righe si stringono seguendo la diagonale."""
    m = 64
    fp = fun or font_path   # premio e nome nel carattere «simpatico» del torneo; posizione, data e piattaforma restano ben leggibili
    premio, nome, quando, dove, pos = t["premio"], pulito(t["nome"]), t["quando"], t.get("dove") or "", t["pos"]
    f_pos, f_in = ft(font_path, 34), ft(font_path, 32)
    f_pr = ft(fp, 100)
    while d.textlength(premio, font=f_pr) > 520 and f_pr.size > 46:
        f_pr = ft(fp, f_pr.size - 6)
    f_nm = ft(fp, 46)
    h_pr, o_pr = _alt(d, f_pr, premio)
    h_nm, o_nm = _alt(d, f_nm)
    h_in, o_in = _alt(d, f_in)
    gap_nm, gap = h_nm + 12, 14
    if alto:
        y = m
        d.text((m, y), "#%d" % pos, font=f_pos, fill=colore_testo); y += 50
        d.text((m, y - o_pr), premio, font=f_pr, fill=colore_premio); y += h_pr + 22
        larg = [max(200, Q - (y + i * gap_nm + h_nm) - m - 50) for i in range(3)]
        for r in a_capo(d, nome, f_nm, larg, 3):
            d.text((m, y - o_nm), r, font=f_nm, fill=colore_testo); y += gap_nm
        y += 8
        for r in (quando, dove):
            if r and Q - (y + h_in) - m - 50 > d.textlength(r, font=f_in):
                d.text((m, y - o_in), r, font=f_in, fill=colore_testo); y += h_in + 12
    else:
        y = Q - m - fondo
        for r in [r for r in (dove, quando) if r]:
            y -= h_in
            d.text((Q - m, y - o_in), r, font=f_in, fill=colore_testo, anchor="ra")
            y -= 12
        y -= 8
        righe = a_capo(d, nome, f_nm, [max(200, (y - (i + 1) * gap_nm) - m - 50) for i in range(3)], 3)
        for r in reversed(righe):
            y -= gap_nm
            d.text((Q - m, y - o_nm), r, font=f_nm, fill=colore_testo, anchor="ra")
        y -= h_pr + 22
        d.text((Q - m, y - o_pr), premio, font=f_pr, fill=colore_premio, anchor="ra")
        y -= 50
        d.text((Q - m, y), "#%d" % pos, font=f_pos, fill=colore_testo, anchor="ra")


# Colori del sito (i temi dell'app), scuri e chiari: ogni torneo ne riceve uno a caso, cosi' i post non sono tutti uguali.
# Colori accesi (2026-11-16): «forti» con testo bianco e «chiari» con testo scuro; niente rosa, al suo posto il viola.
FORTI = [(235, 28, 58), (124, 58, 237), (37, 99, 235), (5, 150, 105), (8, 145, 178)]
CHIARI = [(255, 210, 31), (125, 211, 252), (190, 242, 100), (196, 181, 253), (110, 231, 183), (255, 237, 74)]
TAVOLOZZA = FORTI + CHIARI


def chiaro(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2] > 150


def inchiostro(c):
    """Colori del testo leggibili su quello sfondo: (testo, premio)."""
    return ((29, 12, 16), (200, 20, 60)) if chiaro(c) else ((255, 246, 247), ORO2)


def assegna_caratteri(tornei, seme):
    """Un carattere «simpatico» diverso per ogni torneo del carosello: si mescolano tutti e si usano a giro,
    cosi' nello stesso post non si ripetono finche' non sono finiti (e i due tornei della stessa slide sono sempre diversi)."""
    import random as _r
    l = list(DIVERTENTI)
    if not l:
        return
    _r.Random(seme).shuffle(l)
    scuri = list(FORTI)
    chiari = list(CHIARI)
    _r.Random(seme + "s").shuffle(scuri)
    _r.Random(seme + "c").shuffle(chiari)
    ns = nc = 0
    for i, t in enumerate(tornei):
        t["fun"] = l[i % len(l)]
        # colore a caso per ogni torneo; nella stessa slide uno scuro e uno chiaro (o rosso), che si scambiano di posto
        # una slide si' e una no: le due meta' si distinguono sempre bene
        scuro = i == 0 and False or (((i - 1) // 2 + (i - 1) % 2) % 2 == 0 if i else False)
        if scuro:
            t["col"] = scuri[ns % len(scuri)]; ns += 1
        else:
            t["col"] = chiari[nc % len(chiari)]; nc += 1


def settimana_copertina(settimana, primo, totale, out):
    cb = primo.get("col") or NOTTE
    im, d = _diagonale(MARRONE, cb)
    d.text((64, 64), "MONEY", font=ft(F_T, 104), fill=ORO2)
    d.text((64, 176), "TOURNAMENT", font=ft(F_T, 64), fill=(255, 246, 247))
    d.text((64, 262), "OF THE WEEK", font=ft(F_B, 42), fill=(255, 246, 247))
    d.text((64, 312), settimana, font=ft(F_B, 42), fill=ORO2)
    d.text((64, 380), "rAKings VGC", font=ft(F_T, 32), fill=(255, 246, 247))
    tx, pr = inchiostro(cb)
    _blocco(d, primo, F_A, False, tx, pr, fondo=110 if totale > 1 else 0, fun=primo.get("fun") or carattere_per(primo["nome"]))
    if totale > 1:
        d.text((Q - 64, Q - 70), "swipe: %d more  >>" % (totale - 1), font=ft(F_B, 38), fill=pr, anchor="ra")
    im.save(out, "JPEG", quality=90)


def settimana_slide(n, coppia, out):
    """n = numero della slide (dalla 2): una si' e una no cambiano carattere e colori, per non essere monotoni."""
    pari = n % 2 == 0
    ca = coppia[0].get("col") or (MARRONE if pari else ROSSO)
    cb = coppia[1].get("col") if len(coppia) > 1 and coppia[1].get("col") else (ROSSO if pari else MARRONE)
    if cb == ca:
        cb = MARRONE if ca != MARRONE else ROSSO
    im, d = _diagonale(ca, cb)
    fnt = F_A if pari else F_B
    f1 = coppia[0].get("fun") or carattere_per(coppia[0]["nome"])
    _blocco(d, coppia[0], fnt, True, *inchiostro(ca), fun=f1)
    if len(coppia) > 1:
        _blocco(d, coppia[1], fnt, False, *inchiostro(cb), fun=coppia[1].get("fun") or carattere_per(coppia[1]["nome"], evita=f1))
    else:
        d.text((Q - 64, Q - 80), "rAKings VGC", font=ft(F_T, 40), fill=inchiostro(cb)[0], anchor="ra")
    im.save(out, "JPEG", quality=90)


def evento(tipo, nome, riga1, riga2, riga3, out):
    """Post singolo per un Regionale (giallo) o un VR (azzurro), con i colori delle sezioni dell'app.
    Il testo resta tutto nel triangolo scuro in alto a sinistra: ogni riga si stringe seguendo la diagonale."""
    col = GIALLO2 if tipo == "regionale" else AZZURRO
    im, d = _diagonale(NOTTE, col)
    m = 64
    def spazio(y, h):   # larghezza libera nel triangolo in alto a sinistra, per una riga alta h che parte a y
        return Q - (y + h) - m - 40
    etichetta = "REGIONAL" if tipo == "regionale" else "VICTORY ROAD"
    f_et = ft(F_T, 64)
    while d.textlength(etichetta, font=f_et) > spazio(64, f_et.size) and f_et.size > 30:
        f_et = ft(F_T, f_et.size - 4)
    d.text((m, 64), etichetta, font=f_et, fill=col)
    y = 64 + f_et.size + 40
    f_nm = ft(carattere_per(nome) or F_A, 62)
    for r in a_capo(d, pulito(nome), f_nm, [spazio(y + i * 72, 60) for i in range(3)], 3):
        d.text((m, y), r, font=f_nm, fill=(255, 246, 247)); y += 72
    y += 12
    for r in (riga1, riga2):
        if not r:
            continue
        f = ft(F_B, 42)
        for rr in a_capo(d, r, f, [spazio(y + i * 52, 42) for i in range(2)], 2):
            d.text((m, y), rr, font=f, fill=(255, 246, 247)); y += 52
    if riga3:
        d.text((Q - m, Q - 150), riga3, font=ft(F_B, 52), fill=NOTTE, anchor="ra")
    d.text((Q - m, Q - 80), "rAKings VGC", font=ft(F_T, 40), fill=NOTTE, anchor="ra")
    im.save(out, "JPEG", quality=90)


# ======================= STORIA: VINCITORE + SQUADRA + TOP 8 (Regionali e VR, 2026-11-16) =======================
# Verticale 1080x1920, diagonale da angolo ad angolo, colori della sezione (giallo Regionali, azzurro VR).
# Squadra del vincitore: nome dei 6 Pokemon + bollini dei tipi (stessi colori e sigle del sito), SENZA immagini ufficiali.
SW, SH = 1080, 1920
# tipi in inglese (pubblico internazionale), colori uguali al sito
TIPI = {k: (k.upper(), v) for k, v in {"Normal": "#A8A77A", "Fire": "#EE8130", "Water": "#6390F0", "Electric": "#F7D02C",
        "Grass": "#7AC74C", "Ice": "#96D9D6", "Fighting": "#C22E28", "Poison": "#A33EA1", "Ground": "#E2BF65", "Flying": "#A98FF3",
        "Psychic": "#F95587", "Bug": "#A6B91A", "Rock": "#B6A136", "Ghost": "#735797", "Dragon": "#6F35FC", "Dark": "#705746",
        "Steel": "#B7B7CE", "Fairy": "#D685AD"}.items()}


def ordinale(n):
    return "%d%s" % (n, "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))


def _hex(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def storia(tipo, evento, data, vincitore, paese, squadra, top8, out):
    """tipo: «regionale» o «vr»; squadra: [(nome, ["Fire", "Flying"]), ...] fino a 6; top8: [(pos, nome, paese), ...] dal 2° all'8°."""
    col = GIALLO2 if tipo == "regionale" else AZZURRO
    im = Image.new("RGB", (SW, SH), col)
    d = ImageDraw.Draw(im)
    d.polygon([(0, 0), (SW, 0), (0, SH)], fill=NOTTE)
    d.line([(SW, 0), (0, SH)], fill=(255, 255, 255), width=10)
    m = 70
    def spazio(y, h):   # larghezza libera nel triangolo scuro in alto a sinistra
        return SW * (1 - (y + h) / SH) - m - 30
    d.text((m, 80), "REGIONAL" if tipo == "regionale" else "VICTORY ROAD", font=ft(F_T, 64), fill=col)
    y = 180
    f_ev = ft(F_A, 48)
    for r in a_capo(d, pulito(evento), f_ev, [spazio(y + i * 60, 48) for i in range(2)], 2):
        d.text((m, y), r, font=f_ev, fill=(255, 246, 247)); y += 60
    d.text((m, y + 6), data, font=ft(F_B, 38), fill=(255, 246, 247)); y += 90
    d.text((m, y), "WINNER", font=ft(F_T, 46), fill=col); y += 70
    fun = carattere_per(vincitore) or F_A
    f_v = ft(fun, 86)
    righe = a_capo(d, pulito(vincitore), f_v, [spazio(y + i * 96, 86) for i in range(2)], 2)
    for r in righe:
        h, o = _alt(d, f_v, r)
        d.text((m, y - o), r, font=f_v, fill=(255, 246, 247)); y += max(h, 70) + 22
    if paese:
        d.text((m, y), paese, font=ft(F_B, 40), fill=col); y += 60
    # squadra: riquadro scuro sopra la diagonale, 2 colonne x 3 righe
    y = max(y + 10, 780)
    box = (m - 20, y, SW - m + 20, y + 3 * 128 + 40)
    d.rounded_rectangle(box, 30, fill=(31, 13, 16), outline=col, width=4)
    f_pk, f_ty = ft(F_B, 40), ft(F_B, 24)
    larg_col = (box[2] - box[0] - 60) // 2
    for i, (nome, tipi) in enumerate(squadra[:6]):
        cx = box[0] + 30 + (i % 2) * (larg_col + 20)
        cy = y + 30 + (i // 2) * 128
        n = nome
        while d.textlength(n, font=f_pk) > larg_col - 10 and len(n) > 3:
            n = n[:-2] + "…"
        d.text((cx, cy), n, font=f_pk, fill=(255, 246, 247))
        x = cx
        for t in tipi[:2]:
            sig, hx = TIPI.get(t, (t[:3].upper(), "#888888"))
            c = _hex(hx)
            w = d.textlength(sig, font=f_ty) + 24
            d.rounded_rectangle((x, cy + 52, x + w, cy + 88), 18, fill=c)
            d.text((x + w / 2, cy + 70), sig, font=f_ty, fill=(29, 12, 16) if chiaro(c) else (255, 255, 255), anchor="mm")
            x += w + 10
    # Top 8 dal 2° all'8°: nel triangolo colorato in basso a destra
    y = box[3] + 40
    d.text((SW - m, y), "TOP 8", font=ft(F_T, 50), fill=NOTTE, anchor="ra"); y += 72
    f_t8 = ft(F_A, 44)
    for pos, nome, pa in top8[:7]:
        t = "%s %s  %s" % (pulito(nome), "(%s)" % pa if pa else "", ordinale(pos))
        f_t8 = ft(F_A, 44)
        while d.textlength(t, font=f_t8) > SW * (y / SH) - m - 40 and f_t8.size > 36:   # prima rimpicciolisce, poi taglia
            f_t8 = ft(F_A, f_t8.size - 2)
        while d.textlength(t, font=f_t8) > SW * (y / SH) - m - 40 and len(t) > 8:
            nome = nome[:-2]
            t = "%s… %s  %s" % (pulito(nome), "(%s)" % pa if pa else "", ordinale(pos))
        d.text((SW - m, y), t, font=f_t8, fill=NOTTE, anchor="ra"); y += 60
    d.text((SW - m, SH - 118), "Full results in the app: link in bio", font=ft(F_B, 32), fill=NOTTE, anchor="ra")
    d.text((SW - m, SH - 70), "rAKings VGC", font=ft(F_T, 40), fill=NOTTE, anchor="ra")
    im.save(out, "JPEG", quality=90)


# ======================= TOP 8 DEI LOCALI (2026-11-16): tre fasce oblique rosso / nero / bianco =======================
def top8(titolo, negozio, citta, data, nomi, out):
    """Tre fasce oblique: in alto il rosso (torneo e negozio), al centro il nero (vincitore e Top 8, a scaletta lungo
    la diagonale), in basso il bianco (rAKings VGC)."""
    ROSSO_, NERO_, BIANCO_ = (228, 30, 52), (16, 12, 12), (248, 246, 240)
    a0, a1 = 340, 580          # linea rosso/nero: y a sinistra e a destra
    b0, b1 = 1020, 1260        # linea nero/bianco
    A = lambda x: a0 + (a1 - a0) * x / W
    B = lambda x: b0 + (b1 - b0) * x / W
    im = Image.new("RGB", (W, H), BIANCO_)
    d = ImageDraw.Draw(im)
    d.polygon([(0, 0), (W, 0), (W, a1), (0, a0)], fill=ROSSO_)
    d.polygon([(0, a0), (W, a1), (W, b1), (0, b0)], fill=NERO_)
    m = 64
    # fascia rossa
    d.rounded_rectangle([m, 52, m + d.textlength("TOP 8", font=f(34, "ExtraBold")) + 48, 104], 26, fill=GIALLO)
    d.text((m + 24, 78), "TOP 8", font=f(34, "ExtraBold"), fill=INK, anchor="lm")
    t, ft = adatta(d, titolo, 760, 92, "ExtraBold", 50)
    d.text((m, 168), t, font=ft, fill=BIANCO_, anchor="lm")
    t, ft = adatta(d, negozio, 620, 50, "Bold", 30)
    d.text((m, 238), t, font=ft, fill=GIALLO, anchor="lm")
    t, ft = adatta(d, "%s · %s" % (citta, data), 560, 36, "SemiBold", 24)
    d.text((m, 290), t, font=ft, fill=BIANCO_, anchor="lm")
    # fascia nera: vincitore grande, poi dal 2° all'8°
    nomi = [str(n or "").strip() or "—" for n in nomi][:8]
    y = 470
    if nomi:
        d.text((m, y), "WINNER", font=f(34, "ExtraBold"), fill=GIALLO, anchor="lm")
        t, ft = adatta(d, nomi[0], 640, 86, "ExtraBold", 44)
        d.text((m, y + 66), t, font=ft, fill=BIANCO_, anchor="lm")
        y += 156
    for i, n in enumerate(nomi[1:], start=2):
        h = 56
        x = m
        d.text((x, y + h / 2), "%d" % i, font=f(40, "ExtraBold"), fill=GIALLO if i <= 4 else (190, 180, 170), anchor="lm")
        t, ft = adatta(d, n, W - m - (x + 70), 42, "Bold", 26)
        d.text((x + 70, y + h / 2), t, font=ft, fill=BIANCO_, anchor="lm")
        y += h
    # fascia bianca
    d.text((m, H - 120), "rAKings VGC", font=f(64, "ExtraBold"), fill=NERO_, anchor="lm")
    d.text((m, H - 62), "Top 8 and teams in the app", font=f(32, "SemiBold"), fill=ROSSO_, anchor="lm")
    im.save(out, "JPEG", quality=92)
