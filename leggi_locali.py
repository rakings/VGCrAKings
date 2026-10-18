#!/usr/bin/env python3
"""Legge Gmail (IMAP, sola lettura) e crea una Issue su GitHub per ogni nuova richiesta:
  - "Risultati locale: ..."  -> report Top 8 di un torneo locale (da chiunque)
  - "Annuncio: titolo"       -> annuncio per il sito (SOLO se la mail arriva dal tuo stesso indirizzo Gmail)
Gira nel repository PRIVATO delle richieste: la Issue contiene tutti i dati, così li leggi e approvi da GitHub.
Nel sito pubblico non arriva nulla finché non metti l'etichetta "approvato" (vedi locali_azione.py).
Segreti richiesti: GMAIL_ADDRESS, GMAIL_APP_PASSWORD (password per le app). Stato in locali_state.json."""
import email, hashlib, imaplib, io, json, os, re, sys, urllib.error
from datetime import date, datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

from locali_comune import (ANNUNCI_MAX, ETICHETTE, RETENTION_GIORNI, carica_stato, data_it, gh, log, parse_team, pulisci,
                           salva_stato, sigla)

GIORNI_MAIL = 30      # si guardano solo le mail degli ultimi 30 giorni
MAX_NUOVE = 15        # tetto di richieste nuove per giro (anti-spam): il resto al giro dopo
TIPI = ("Sfida di Lega", "Coppa di Lega", "Altro")
MESI_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
RE_GIOC = re.compile(r"^\s*([1-8])\s*°\s*[·•\-.:]*\s*(.*)$")
RE_FINE = re.compile(r"^\s*(Link|Contatto|Consenso[^:]*)\s*:", re.I)


class Scarta(Exception):
    """Mail non valida: si registra il motivo e non si riprova."""


def campo(body, nome):
    m = re.search(r"^[ \t]*%s[ \t]*:[ \t]*(.*)$" % nome, body, re.I | re.M)
    return m.group(1).strip() if m else ""


def parse_report(body, data_mail):
    if len(body) > 30000:
        raise Scarta("messaggio troppo lungo")
    oggi = datetime.now(timezone.utc).date()
    avvisi = []
    negozio, citta = pulisci(campo(body, "Negozio"), 80), pulisci(campo(body, r"Citt[aà]"), 80)
    if not negozio or not citta:
        raise Scarta("mancano Negozio e/o Città")
    tipo = pulisci(campo(body, "Tipo"), 30)
    if tipo not in TIPI:
        avvisi.append("Tipo non riconosciuto: verrà usato \"Altro\"")
        tipo = "Altro"
    try:
        dt = date.fromisoformat(campo(body, "Data"))
    except ValueError:
        dt = data_mail
        avvisi.append("Data mancante o non valida: usata la data della mail (%s)" % data_it(dt.isoformat()))
    if dt > oggi + timedelta(days=1):
        raise Scarta("data nel futuro (%s)" % dt.isoformat())
    if (oggi - dt).days > RETENTION_GIORNI:
        raise Scarta("data troppo vecchia (%s): verrebbe subito eliminata dalla pulizia" % dt.isoformat())
    m = re.search(r"\d+", campo(body, "Giocatori"))
    n = int(m.group()) if m and int(m.group()) <= 5000 else None
    link = campo(body, "Link")
    link = link[:200] if re.match(r"^https?://\S+$", link) else ""

    righe = body.replace("\r", "").split("\n")
    inizio = next((k + 1 for k, r in enumerate(righe) if re.match(r"^\s*TOP\s*8\s*$", r, re.I)), None)
    if inizio is None:
        raise Scarta("manca la sezione TOP 8")
    blocchi = []
    for r in righe[inizio:]:
        if RE_FINE.match(r):
            break
        g = RE_GIOC.match(r)
        if g:
            blocchi.append([int(g.group(1)), g.group(2), []])
        elif blocchi:
            blocchi[-1][2].append(r)
    giocatori, visti = [], set()
    for p, nome, resto in blocchi:
        if p in visti:
            continue
        visti.add(p)
        nome = pulisci(nome, 60)
        if nome.lower() in ("(anonimo)", "anonimo"):
            nome = ""
        if re.search(r"https?:|www\.|@", nome):
            raise Scarta("nome del giocatore %d° sospetto (link o indirizzo)" % p)
        rt, team = "", []
        for l in resto:
            mm = re.match(r"^\s*Rental team:\s*(.*)$", l, re.I)
            if mm:
                rt = re.sub(r"[^A-Za-z0-9]", "", mm.group(1))[:12]
            else:
                team.append(l)
        tm = parse_team("\n".join(team))
        if tm and len(tm) != 6:
            avvisi.append("%d°: la squadra ha %d Pokémon invece di 6" % (p, len(tm)))
        giocatori.append({"p": p, "nome": nome, "rt": rt, "tm": tm[:6]})
    if not giocatori:
        raise Scarta("nessun giocatore nella TOP 8")
    giocatori.sort(key=lambda g: g["p"])
    cons = campo(body, "Consenso dei giocatori confermato")
    if any(g["nome"] for g in giocatori) and not cons.lower().startswith("s"):
        avvisi.append("Ci sono nomi ma il consenso/minorenni NON risulta confermato: verifica prima di approvare")
    return {"tipo": tipo, "negozio": negozio, "citta": citta, "iso": dt.isoformat(), "n": n,
            "link": link, "giocatori": giocatori, "avvisi": avvisi}


RE_ANN = re.compile(r"^\s*annuncio\s*[:\-\u2013\u2014]\s*(.+?)\s*$", re.I)


def parse_annuncio(oggetto, body, da):
    """Oggetto "Annuncio: titolo", corpo = descrizione. Accettato solo se scritto dal tuo indirizzo."""
    ind = os.environ.get("GMAIL_ADDRESS", "").strip().lower()
    if not ind or (da or "").strip().lower() != ind:
        raise Scarta("annuncio da un mittente non autorizzato")
    m = RE_ANN.match(oggetto or "")
    titolo = pulisci(m.group(1), 100) if m else ""
    if not titolo:
        raise Scarta("manca il titolo (l'oggetto deve essere \"Annuncio: titolo\")")
    righe = []
    for r_ in (body or "").replace("\r", "").split("\n"):
        if r_.strip() == "--" or r_.startswith("-- "):   # da qui in poi c'è la firma
            break
        if r_.lstrip().startswith(">"):                  # citazioni di altre mail
            continue
        righe.append(pulisci(r_, 400))
    testo = re.sub(r"\n{3,}", "\n\n", "\n".join(righe)).strip()[:800]
    return {"titolo": titolo, "testo": testo}


def corpo_annuncio(a):
    r_ = ["Annuncio arrivato via mail. **Non è pubblicato**: questo repository è privato.", "",
          "**Titolo:** " + a["titolo"], "", a["testo"] or "_(nessuna descrizione)_", ""]
    if a.get("img"):
        r_ += ["Foto allegata: ![foto](https://github.com/%s/blob/main/%s?raw=true)" % (os.environ.get("GITHUB_REPOSITORY", ""), a["img"]), ""]
    r_ += ["La **notifica a tutti gli iscritti** parte dopo 3 minuti dalla pubblicazione.", "---",
          "**Per pubblicare** metti l'etichetta `approvato`: entra nell'archivio della sezione Info (massimo %d annunci: quando si supera il limite si tolgono i più vecchi non fissati)." % ANNUNCI_MAX,
          "**Per fissarlo in cima** metti `fissato` (anche dopo la pubblicazione; togli l'etichetta per rimetterlo nell'archivio).",
          "**Per scartare** metti `rifiutato`. **Per toglierlo dal sito** metti `rimosso`.",
          "", "<!-- ANNUNCIO-DATA", json.dumps(a, ensure_ascii=True), "-->"]
    return "\n".join(r_)


def corpo_issue(p):
    r = ["Richiesta arrivata via mail. **Non è pubblicata**: questo repository è privato.", ""]
    if p["avvisi"]:
        r += ["⚠️ **Da controllare**"] + ["- " + a for a in p["avvisi"]] + [""]
    r += ["**%s** · %s · %s" % (p["tipo"], p["negozio"], p["citta"]),
          "Data: %s · Giocatori: %s" % (data_it(p["iso"]), p["n"] if p["n"] is not None else "n.d.")]
    if p["link"]:
        r.append("Link indicato (per verifica): " + p["link"])
    r.append("")
    for g in p["giocatori"]:
        r.append("**%d°** %s" % (g["p"], g["nome"] or "_anonimo_") + ("  · rental `%s`" % g["rt"] if g["rt"] else ""))
        for x in g["tm"]:
            r.append("- %s%s%s" % (x["n"], " @ " + x["i"] if x["i"] else "", " · " + x["a"] if x["a"] else "") +
                     (" · " + ", ".join(x["m"]) if x["m"] else ""))
    r += ["", "---",
          "**Per pubblicare** metti l'etichetta `approvato` (la notifica parte dopo 3 minuti).",
          "**Per scartare** metti `rifiutato`. **Per togliere un report già pubblicato** metti `rimosso`.",
          "", "<!-- LOCALI-DATA", json.dumps(p, ensure_ascii=True), "-->"]
    return "\n".join(r)


def riduci_immagine(dati):
    """JPEG leggero (max 1200 px). Senza Pillow si accetta solo un JPEG già piccolo."""
    try:
        from PIL import Image, ImageOps
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(dati)))
        im.thumbnail((1200, 1200))
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            fondo = Image.new("RGB", im.size, (255, 255, 255))
            fondo.paste(im, mask=im.split()[-1])
            im = fondo
        elif im.mode != "RGB":
            im = im.convert("RGB")
        out = io.BytesIO()
        im.save(out, "JPEG", quality=82, optimize=True)
        return out.getvalue()
    except Exception as ex:
        log("[AVVISO] immagine non ridotta (%s)" % type(ex).__name__)
        return dati if dati[:3] == b"\xff\xd8\xff" and len(dati) <= 1200000 else None


def immagine_mail(msg):
    """Prima immagine allegata (almeno 5 KB, per saltare le icone delle firme): JPEG pronto da salvare, oppure None."""
    for part in msg.walk():
        if part.get_content_maintype() != "image":
            continue
        dati = part.get_payload(decode=True) or b""
        if 5000 <= len(dati) <= 15000000:
            return riduci_immagine(dati)
    return None


def testo_mail(msg):
    plain = html = None
    for part in msg.walk():
        if part.get_content_maintype() != "text" or part.get_filename():
            continue
        try:
            t = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
        except Exception:
            continue
        if part.get_content_subtype() == "plain" and plain is None:
            plain = t
        elif part.get_content_subtype() == "html" and html is None:
            html = t
    if plain is not None:
        return plain
    if html is not None:
        return re.sub(r"<[^>]+>", "\n", re.sub(r"<br\s*/?>|</p>|</div>", "\n", html, flags=re.I))
    return ""


def leggi_mail(giorni=GIORNI_MAIL):
    ind = os.environ.get("GMAIL_ADDRESS", "").strip()
    pw = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    if not ind or not pw:
        raise RuntimeError("Mancano i segreti GMAIL_ADDRESS e/o GMAIL_APP_PASSWORD (Settings > Secrets and variables > Actions).")
    M = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=60)
    try:
        M.login(ind, pw)
    except imaplib.IMAP4.error:
        raise RuntimeError("Gmail ha rifiutato l'accesso: controlla l'indirizzo, la password per le app (16 caratteri) e che IMAP sia attivo.")
    M.select("INBOX", readonly=True)
    da = datetime.now(timezone.utc) - timedelta(days=giorni)
    nums = []
    for sogg in ("Risultati locale", "Annuncio"):
        typ, dati = M.search(None, "SINCE", "%02d-%s-%d" % (da.day, MESI_EN[da.month - 1], da.year),
                             "SUBJECT", '"%s"' % sogg)
        if typ != "OK":
            raise RuntimeError("Ricerca in Gmail non riuscita: %s" % typ)
        nums += [n for n in (dati[0] or b"").split() if n not in nums]
    out = []
    for num in nums:
        typ, d = M.fetch(num, "(BODY.PEEK[])")
        if typ != "OK" or not d or not isinstance(d[0], tuple):
            continue
        raw = d[0][1]
        msg = email.message_from_bytes(raw)
        oggetto = str(make_header(decode_header(msg.get("Subject", ""))))
        if not oggetto.lower().lstrip().startswith(("risultati locale", "annuncio")):
            continue
        try:
            dm = parsedate_to_datetime(msg.get("Date")).astimezone(timezone.utc)
        except Exception:
            dm = datetime.now(timezone.utc)
        mid = (msg.get("Message-ID") or "").strip() or "sha1:" + hashlib.sha1(raw).hexdigest()
        da = parseaddr(msg.get("From", ""))[1]
        # l'immagine si legge solo per gli annunci scritti da te
        img = immagine_mail(msg) if oggetto.lower().lstrip().startswith("annuncio") and da.lower() == ind.lower() else None
        out.append((mid, oggetto, dm, testo_mail(msg), da, img))
    M.logout()
    return out


def assicura_etichette():
    for nome, colore in ETICHETTE:
        try:
            gh("POST", "/labels", {"name": nome, "color": colore})
        except urllib.error.HTTPError as e:
            if e.code != 422:   # 422 = esiste già
                raise


def main():
    stato = carica_stato()
    try:
        assicura_etichette()   # così nel repository ci sono sempre tutte le etichette (anche quelle aggiunte dopo)
    except Exception as ex:
        log("[AVVISO] etichette non verificate:", type(ex).__name__)
    try:
        mails = leggi_mail()
    except RuntimeError as ex:
        log("[ERRORE]", ex)
        return 1
    except Exception as ex:
        log("[ERRORE] Lettura di Gmail non riuscita:", type(ex).__name__)
        return 1
    mails.sort(key=lambda m: m[2])
    log("Mail (risultati locali e annunci) trovate negli ultimi %d giorni: %d" % (GIORNI_MAIL, len(mails)))
    nuove = errori = 0
    etichette_ok = False
    visti = set()   # impronte dei contenuti già incontrati in questo giro (non si salvano: sono dati privati)
    for mid, oggetto, dm, body, mittente, img in mails:
        k = sigla(mid)
        try:
            if oggetto.lower().lstrip().startswith("annuncio"):
                p = parse_annuncio(oggetto, body, mittente)
                if img:
                    os.makedirs("annunci_img", exist_ok=True)
                    with open("annunci_img/%s.jpg" % k, "wb") as f:
                        f.write(img)
                    p["img"] = "annunci_img/%s.jpg" % k
                titolo_issue, corpo, etichetta = "Annuncio: %s" % p["titolo"], corpo_annuncio(p), "annuncio-da-approvare"
                h = sigla("ann|%s|%s" % (p["titolo"].lower(), p["testo"].lower()))
            else:
                p = parse_report(body, dm.date())
                titolo_issue = "Locale: %s – %s (%s)" % (p["negozio"], p["citta"], data_it(p["iso"]))
                corpo, etichetta = corpo_issue(p), "locali-da-approvare"
                h = sigla("|".join([p["negozio"].lower(), p["iso"]] + [g["nome"].lower() for g in p["giocatori"]]))
        except Scarta as ex:
            if k not in stato["msgs"]:
                log("[SCARTATA] mail %s: %s" % (k[:6], ex))
                stato["msgs"][k] = "scartata: %s" % ex
                salva_stato(stato)
            continue
        doppia = h in visti
        visti.add(h)
        if k in stato["msgs"]:
            continue
        if doppia:
            log("[DUPLICATA] mail %s: stessi dati di una richiesta precedente" % k[:6])
            stato["msgs"][k] = "duplicata"
            salva_stato(stato)
            continue
        if nuove >= MAX_NUOVE:
            log("Raggiunto il tetto di %d richieste per giro: le altre al prossimo." % MAX_NUOVE)
            break
        try:
            if not etichette_ok:
                assicura_etichette()
                etichette_ok = True
            iss = gh("POST", "/issues", {"title": titolo_issue, "body": corpo, "labels": [etichetta]})
        except Exception as ex:
            log("[ERRORE] Issue non creata per la mail %s (si riprova al prossimo giro): %s" % (k[:6], type(ex).__name__))
            errori += 1
            continue
        nuove += 1
        stato["msgs"][k] = "issue #%d" % iss["number"]
        salva_stato(stato)
        log("[NUOVA] mail %s -> Issue #%d" % (k[:6], iss["number"]))
    log("Fatto: %d nuove richieste, %d errori." % (nuove, errori))
    return 1 if errori else 0


if __name__ == "__main__":
    sys.exit(main())
