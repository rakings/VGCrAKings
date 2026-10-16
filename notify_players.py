#!/usr/bin/env python3
"""Avviso "Player in evidenza": quando in news.json compare un nuovo italiano in evidenza
(top 16 di un grande torneo) manda una notifica sul canale "player".
Manda anche l'avviso "Vincitore di un Regionale" (canale "winner"): primo posto, di qualsiasi nazionalità.
Manda anche "Vincitore Victory Road" (canale "vrwin"): legge il banner "X is the VR ... Champion!" della home di victoryroad.pro.
Si lancia DOPO update_news.py. Riusa l'invio di update_events.py (OneSignal o ntfy).
Il primo giro non manda nulla: memorizza solo lo stato. Poi avvisa soltanto per i tornei
più recenti di quelli già noti, così il caricamento a ritroso dello storico non genera avvisi."""
import html, json, os, re, signal, sys, time, urllib.request
import update_events as ue

STATE = "notify_players_state.json"
TOPIC = "player"

def place(p):
    return "Vincitore" if p == 1 else "%d° posto" % p

RE_CHAMP = re.compile(r"^\W*([^!\n]{2,60}?)\s+is the\s+(VR [^!\n]{3,60}?)\s+Champion\b", re.I)

def fetch_limited(url, total=45):
    """Legge una pagina con un tempo massimo COMPLESSIVO: anche se il sito risponde a gocce non si resta appesi."""
    end = time.monotonic() + total
    req = urllib.request.Request(url, headers={"User-Agent": ue.UA})
    buf = []
    with urllib.request.urlopen(req, timeout=10) as r:
        while True:
            if time.monotonic() > end:
                raise TimeoutError("risposta troppo lenta (oltre %d secondi)" % total)
            ch = r.read1(65536)  # restituisce subito quello che è arrivato
            if not ch:
                break
            buf.append(ch)
    return b"".join(buf).decode("utf-8", "replace")

def vr_champions():
    """Banner della home di Victory Road: "Kiran Singh is the VR October Challenge #2 Champion!".
    Solo i tornei VR (i Regionali sono già coperti dall'avviso del vincitore). Dà [(giocatore, torneo, link)] oppure None se la home non si legge."""
    try:
        t0 = time.monotonic()
        page = fetch_limited(ue.VR)
        log("notify_players: home VR scaricata in %.1f secondi" % (time.monotonic() - t0))
    except Exception as ex:
        print("Home di Victory Road non letta:", ex)
        return None
    out, seen = [], set()
    pre = re.sub(r"<br\s*/?>", " ", page, flags=re.I)  # il banner va a capo dopo il nome: "Kiran Singh<br>is the VR ..."
    pre = re.sub(r"</?(?:b|strong|em|i|u|span)\b[^>]*>", "", pre)  # il nome può stare in un grassetto (il link accanto resta separato)
    pre = re.sub(r"<(script|style)\b.*?</\1>", " ", pre, flags=re.S | re.I)  # niente codice: pagine enormi e lente da leggere
    for piece in re.split(r"<[^>]*>", pre):  # un banner = un pezzo di testo tra due tag (ricerca lineare, non può bloccarsi)
        if "Champion" not in piece:
            continue
        txt = html.unescape(re.sub(r"\s+", " ", piece)).strip()
        r = RE_CHAMP.match(txt)
        if not r or (r[1], r[2]) in seen:
            continue
        seen.add((r[1], r[2]))
        pos = page.find(r[1].split()[-1])
        link = re.search(r'href=["\'](https://victoryroad\.pro/vr[a-z0-9-]+/?)["\']', page[max(pos, 0):max(pos, 0) + 1500])
        out.append((r[1].strip(), r[2].strip(), link[1] if link else ue.VR))
    if not out and re.search(r"is the [^<>]{3,80} Champion", html.unescape(page)):
        print("Victory Road: c'è un banner 'Champion' ma non è stato riconosciuto (formato diverso dal previsto)")
    return out

def reg_top8(news, tid):
    """Top 8 di un Regionale dai dati di news.json: righe '1. Nome (PAESE)'."""
    for n in news.get("news") or []:
        if n.get("t") == "Regionale" and str(n.get("src", "")).rstrip("/").endswith("/tournaments/%s" % tid):
            return ["%d. %s%s" % (i + 1, r["pl"], (" (%s)" % r["cc"]) if r.get("cc") else "") for i, r in enumerate((n.get("rows") or [])[:8])]
    return []

def vr_top8(link):
    """Top 8 di un torneo VR dalla tabella 'Top cut' della pagina dell'evento (colonne: posto, Swiss, bandiera, giocatore, premio...).
    Se la tabella non si legge si torna senza la lista: l'avviso parte lo stesso, solo col vincitore."""
    if not link or link.rstrip("/") == ue.VR.rstrip("/"):
        return []
    try:
        page = fetch_limited(link)
        m = re.search(r"Top cut", page, re.I)
        t = re.search(r"<table.*?</table>", page[m.end():] if m else page, re.S | re.I)
        if not t:
            return []
        txt = lambda c: html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c))).strip()
        out = []
        for tr in re.findall(r"<tr.*?</tr>", t.group(0), re.S | re.I):
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
            if len(cells) < 4 or not txt(cells[0]).isdigit() or int(txt(cells[0])) > 8:
                continue
            b = re.search(r"<(?:strong|b)\b[^>]*>(.*?)</(?:strong|b)>", cells[3], re.S | re.I)
            name = txt(b.group(1)) if b else re.sub(r"\s*\(.*$", "", txt(cells[3]))
            fl = txt(cells[2])
            if not re.fullmatch(r"[A-Za-z]{2,3}", fl):
                g = re.search(r'(?:alt|title)=["\']([A-Za-z]{2,3})["\']|/([A-Za-z]{2,3})\.(?:png|svg|webp|gif)', cells[2])
                fl = (g[1] or g[2]) if g else ""
            pr = re.search(r"\$\s?[\d.,]+", txt(cells[4])) if len(cells) > 4 else None
            out.append("%d. %s%s%s" % (int(txt(cells[0])), name, (" (%s)" % fl.upper()) if fl else "", (" - " + pr[0].replace(" ", "")) if pr else ""))
        return out[:8]
    except Exception as ex:
        print("Top 8 VR non letta:", ex)
        return []

def log(*a):
    print(*a)
    sys.stdout.flush()

def main():
    if hasattr(signal, "SIGALRM"):
        signal.alarm(150)  # rete di sicurezza: dopo 150 secondi il sistema chiude lo script, qualunque cosa lo blocchi
    if not (os.environ.get("NTFY_PREFIX") or ue.os_on()):
        return
    log("notify_players: avvio")
    try:
        news = json.load(open("news.json", encoding="utf-8"))
    except Exception as ex:
        print("news.json non letto:", ex)
        return
    ita = [x for x in news.get("ita") or [] if x.get("pl") and x.get("id") is not None]
    all_ids = [int(x["id"]) for x in ita] + [int(r[3]) for r in news.get("bp") or [] if len(r) > 3]
    st = ue.load(STATE, None)
    if not isinstance(st, dict):  # primo giro: si ricorda tutto, senza avvisi
        champs = vr_champions()
        sent = ["%s|%s" % (x["pl"], x["id"]) for x in ita] + ["V|%s|%s" % (p, e) for p, e, _ in champs or []]
        json.dump({"min_id": max(all_ids or [0]), "sent": sorted(sent), "vr_init": champs is not None},
                  open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
        print("Player in evidenza: stato iniziale salvato, nessun avviso")
        return
    sent, min_id = set(st.get("sent") or []), int(st.get("min_id") or 0)
    vr_new = []
    vr_ready = bool(st.get("vr_init")) and any(k.startswith("V|") for k in sent)  # stato valido solo se ha già registrato un vincitore VR
    log("notify_players: leggo la home di Victory Road")
    champs = vr_champions()
    log("notify_players: home VR letta" if champs is not None else "notify_players: home VR non letta")
    if champs is not None:
        for pl, ev, link in champs:
            key = "V|%s|%s" % (pl, ev)
            if key not in sent:
                sent.add(key)
                if vr_ready:  # la prima volta si memorizza soltanto
                    vr_new.append((pl, ev, link))
    wins = []  # vincitori dei Regionali (bp: [giocatore, paese, torneo, id, posizione])
    for r in news.get("bp") or []:
        if len(r) > 4 and r[4] == 1 and ("W|%s" % r[3]) not in sent:
            sent.add("W|%s" % r[3])
            if int(r[3]) > min_id:
                wins.append(r)
    new = []
    for x in ita:
        key = "%s|%s" % (x["pl"], x["id"])
        if key in sent:
            continue
        sent.add(key)
        if int(x["id"]) > min_id:
            new.append(x)
    site = os.environ.get("SITE_URL", "")
    log("notify_players: da inviare: %d player, %d vincitori, %d VR" % (len(new), len(wins), len(vr_new)))
    try:
        if len(new) > 5:
            ue.deliver(TOPIC, "Player in evidenza", "\n".join("%s - %s" % (x["pl"], x["t"]) for x in new[:5]) + "\ne altri %d" % (len(new) - 5), site)
        else:
            for x in new:
                ue.deliver(TOPIC, "Player in evidenza: %s" % x["pl"], "%s a %s%s" % (place(x["p"]), x["t"], (" (%s)" % x["d"]) if x.get("d") else ""),
                           "https://limitlessvgc.com/tournaments/%s" % x["id"])
        for pl, ev, link in vr_new:
            ue.deliver("vrwin", "Vincitore Victory Road: %s" % pl, "\n".join([ev] + vr_top8(link)), link)
        for r in wins:
            ue.deliver("winner", "Vincitore Regionale: %s" % r[0],
                       "\n".join(["Regional %s%s" % (r[2], (" (%s)" % r[1]) if r[1] else "")] + reg_top8(news, r[3])),
                       "https://limitlessvgc.com/tournaments/%s" % r[3])
        print("Avvisi inviati: %d player, %d vincitori, %d VR" % (len(new), len(wins), len(vr_new)))
    except Exception as ex:
        print("Avviso player non inviato:", ex)
        return  # lo stato non si aggiorna: si riprova al giro dopo
    json.dump({"min_id": min_id, "sent": sorted(sent), "vr_init": bool(st.get("vr_init") or champs)},
              open(STATE, "w", encoding="utf-8"), ensure_ascii=False)

if __name__ == "__main__":
    main()
