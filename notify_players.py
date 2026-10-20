#!/usr/bin/env python3
"""Avviso "Player in evidenza": quando in news.json compare un nuovo italiano in evidenza
(top 16 di un grande torneo) manda una notifica sul canale "player".
Manda anche l'avviso "Vincitore di un Regionale" (canale "winner"): primo posto, di qualsiasi nazionalità.
Manda anche "Vincitore Victory Road" (canale "vrwin"): legge il banner "X is the VR ... Champion!" della home di victoryroad.pro.
Si lancia DOPO update_news.py. Riusa l'invio di update_events.py (OneSignal o ntfy).
Il primo giro non manda nulla: memorizza solo lo stato. Poi avvisa soltanto per i tornei
più recenti di quelli già noti, così il caricamento a ritroso dello storico non genera avvisi."""
import html, json, os, re, signal, sys, time, urllib.request
from datetime import datetime, timedelta
import update_events as ue

STATE = "notify_players_state.json"
TOPIC = "player"

def place(p):
    return "Vincitore" if p == 1 else "%d° posto" % p

RE_CHAMP = re.compile(r"^\W*([^!\n]{2,60}?)\s+(?:is|are) the\s+((?:VR|Victory Road) [^!\n]{3,60}?)\s+Champions?\b", re.I)

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

VR_HOME = {"html": None}
RE_ANN = re.compile(r"(VR [A-Za-z]+ Challenge #\d+)\b[^.!?]{0,60}?\bannounced\b[^.!?]{0,40}?\bsign-?ups? (?:are )?open", re.I)

def vr_annunci(page, oggi=None):
    """Articoli del sito VR tipo "The VR October Challenge #4 has been announced, and sign-ups are open!".
    Dà [(nome torneo, link articolo, {date, end})] solo per tornei non ancora finiti."""
    oggi = oggi or datetime.now(ue.ROME).date()
    out, visti = [], set()
    for m in re.finditer(r"[^<>]+", page):  # pezzi di testo tra due tag (ricerca lineare); il titolo può stare dentro un link o accanto a "Read more"
        titolo = html.unescape(re.sub(r"\s+", " ", m[0])).strip()
        if "announced" not in titolo:
            continue
        r = RE_ANN.search(titolo)
        if not r or r[1].lower() in visti:
            continue
        visti.add(r[1].lower())
        pr = re.search(r'href=["\'](https://victoryroad\.pro/[^"\'#]+)["\'][^>]*>\s*(?:<[^>]+>\s*)*$', page[max(0, m.start() - 500):m.start()])
        po = re.search(r'href=["\'](https://victoryroad\.pro/[^"\'#]+)["\']', page[m.end():m.end() + 2500])
        link = (pr or po).group(1) if (pr or po) else ue.VR
        dopo = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1>", " ", page[m.end():m.end() + 4000], flags=re.S | re.I))))
        d = re.search(r"held online on (\d{1,2})(?:\s*[–—-]\s*(\d{1,2}))?\s+([A-Za-z]+)\s+(\d{4})", dopo) or re.search(r"\bon (\d{1,2})(?:\s*[–—-]\s*(\d{1,2}))?\s+([A-Za-z]+)\s+(\d{4})", dopo)
        if not d or d[3].lower() not in ue.MESI:
            log("notify_players: annuncio VR senza data riconoscibile: %s" % r[1])
            continue
        mese, anno = ue.MESI.index(d[3].lower()) + 1, int(d[4])
        inizio, fine = "%04d-%02d-%02d" % (anno, mese, int(d[1])), "%04d-%02d-%02d" % (anno, mese, int(d[2] or d[1]))
        if datetime.fromisoformat(fine).date() < oggi:
            continue  # torneo già finito: niente avviso su un annuncio vecchio
        out.append((r[1].strip(), link, {"date": inizio, "end": fine if fine != inizio else None}))
    # seconda fonte: la slide della home "VR October Challenge #4 - The next VR event is held online on 24-25 October. Sign up, ..."
    txt = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1>", " ", page, flags=re.S | re.I))))
    for m in re.finditer(r"(VR [A-Za-z]+ Challenge #\d+)\s+The next VR event is held online on (\d{1,2})(?:\s*[–—-]\s*(\d{1,2}))?\s+([A-Za-z]+)\b[^.!?]{0,15}[.!]?\s*Sign[- ]?up", txt, re.I):
        nome = m[1].strip()
        if nome.lower() in visti or m[4].lower() not in ue.MESI:
            continue
        visti.add(nome.lower())
        mese, anno = ue.MESI.index(m[4].lower()) + 1, oggi.year
        inizio, fine = "%04d-%02d-%02d" % (anno, mese, int(m[2])), "%04d-%02d-%02d" % (anno, mese, int(m[3] or m[2]))
        if (oggi - datetime.fromisoformat(fine).date()).days > 180:  # la slide non scrive l'anno: se la data sembra molto passata è dell'anno dopo
            inizio, fine = inizio.replace(str(anno), str(anno + 1), 1), fine.replace(str(anno), str(anno + 1), 1)
        if datetime.fromisoformat(fine).date() < oggi:
            continue
        pos = page.find("The next VR event is held online")
        lk = re.search(r'href=["\'](https://victoryroad\.pro/[^"\'#]+)["\']', page[pos:pos + 2500]) if pos >= 0 else None
        out.append((nome, lk[1] if lk else ue.VR, {"date": inizio, "end": fine if fine != inizio else None}))
    return out

def vr_champions():
    """Banner della home di Victory Road: "Kiran Singh is the VR October Challenge #2 Champion!".
    Solo i tornei VR (i Regionali sono già coperti dall'avviso del vincitore). Dà [(giocatore, torneo, link)] oppure None se la home non si legge."""
    try:
        t0 = time.monotonic()
        page = fetch_limited(ue.VR)
        VR_HOME["html"] = page
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
        evname = re.sub(r"^Victory Road ", "VR ", r[2].strip(), flags=re.I)  # stesso nome che usa la scheda del torneo
        pos = page.find(r[1].split()[-1])
        link = re.search(r'href=["\'](https://victoryroad\.pro/vr[a-z0-9-]+/?)["\']', page[max(pos, 0):max(pos, 0) + 1500])
        out.append((r[1].strip(), evname, link[1] if link else ue.VR))
    for pl, ev, link in vr_finished(page, {e for _, e, _ in out}):
        log("notify_players: vincitore preso dalla pagina del torneo (banner assente o diverso): %s - %s" % (pl, ev))
        out.append((pl, ev, link))
    log("notify_players: vincitori VR trovati: %s" % (", ".join("%s (%s)" % (p, e) for p, e, _ in out) or "nessuno"))
    if not out and re.search(r"is the [^<>]{3,80} Champion", html.unescape(page)):
        print("Victory Road: c'è un banner 'Champion' ma non è stato riconosciuto (formato diverso dal previsto)")
    return out

def vr_finished(home, known):
    """Rete di sicurezza: se il banner della home manca o ha un formato nuovo, guarda le pagine dei VR finiti negli
    ultimi 3 giorni e prende il 1° posto dalla tabella 'Top cut'. Dà [(giocatore, torneo, link)]."""
    out = []
    try:
        today = datetime.now(ue.ROME).date()
        slugs = []
        for s in re.findall(r'href=["\']https://victoryroad\.pro/(vr[a-z0-9-]+)/?["\']', home):
            if s not in slugs:
                slugs.append(s)
        sigle = [m[:3] for m in ue.MESI]
        for back in (0, 1):  # mese corrente e precedente: vr-oct26, vr-oct26-2, vr-oct26-3...
            i = today.month - 1 - back
            for suf in ("", "-2", "-3", "-4", "-5", "-6"):
                sl = "vr-%s%02d%s" % (sigle[i % 12], (today.year + i // 12) % 100, suf)
                if sl not in slugs:
                    slugs.append(sl)
        t0 = time.monotonic()
        for slug in slugs[:14]:
            if time.monotonic() - t0 > 60:
                break
            link = ue.VR + slug + "/"
            try:
                page = fetch_limited(link, total=15)
                ev = ue.vr_parse(slug, page)
            except Exception:
                continue  # pagina inesistente o non leggibile: si passa oltre
            if not ev or ev["name"] in known:
                continue
            try:
                last = datetime.fromisoformat(ev.get("end") or ev["date"]).date()
            except Exception:
                continue
            if not today - timedelta(days=3) <= last <= today:
                continue
            top = vr_top8(link)
            m = re.match(r"1\.\s+(.*?)(?:\s+\([A-Za-z]{2,3}\))?(?:\s+-\s+\$.*)?$", top[0]) if top else None
            if m and m[1].strip():
                out.append((m[1].strip(), ev["name"], link))
                known.add(ev["name"])  # uno stesso torneo non si conta due volte
            time.sleep(0.5)
    except Exception as ex:
        print("Controllo pagine VR non riuscito:", ex)
    return out

def reg_top8(news, tid):
    """Top 8 di un Regionale dai dati di news.json: righe '1. Nome (PAESE)'."""
    for n in news.get("news") or []:
        if n.get("t") == "Regionale" and str(n.get("src", "")).rstrip("/").endswith("/tournaments/%s" % tid):
            return ["%d. %s%s" % (i + 1, r["pl"], (" (%s)" % r["cc"]) if r.get("cc") else "") for i, r in enumerate((n.get("rows") or [])[:8])]
    return []

MESI_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
VR_JSON = "news_vr.json"

def vr_page(link):
    """Legge la pagina di un torneo VR: top 8 dalla tabella 'Top cut' (posto, Swiss, bandiera, giocatore, premio, squadra)
    e le info (date, giocatori, formato, regolamento). Se qualcosa non si legge, torna ciò che c'è."""
    out = {"rows": [], "ev": None, "players": None, "fmt": None}
    if not link or link.rstrip("/") == ue.VR.rstrip("/"):
        return out
    try:
        page = fetch_limited(link)
    except Exception as ex:
        print("Pagina VR non letta:", ex)
        return out
    try:
        slug = link.rstrip("/").split("/")[-1]
        out["ev"] = ue.vr_parse(slug, page)
        text = re.sub(r"<(script|style).*?</\1>", " ", page, flags=re.S | re.I)
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text)).replace("\xa0", " "))
        p = re.search(r"Attendance\W{0,5}(\d[\d.,]*)\s*players?", text, re.I)
        out["players"] = re.sub(r"\D", "", p[1]) if p else None
        f = re.search(r"Format\W{0,3}(.{3,120}?)\s+Organi[sz]er", text)
        out["fmt"] = f[1].strip() if f else None
    except Exception as ex:
        print("Info VR non lette:", ex)
    try:
        m = re.search(r"Top cut", page, re.I)
        t = re.search(r"<table.*?</table>", page[m.end():] if m else page, re.S | re.I)
        if not t:
            return out
        txt = lambda c: html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c))).strip()
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
            pz, ex = "", ""
            if len(cells) > 4:
                cp = txt(cells[4])
                pr = re.search(r"\$\s?[\d.,]+", cp)
                pz = pr[0].replace(" ", "") if pr else ""
                ex = re.sub(r"\$\s?[\d.,]+", "", cp).strip()  # es. "VRtSG": invito o premio extra scritto accanto
            mons = []
            if len(cells) > 5:  # nomi dei Pokémon dalle immagini della squadra (alt/title), se ci sono
                for g in re.findall(r'<img[^>]+?(?:alt|title)=["\']([^"\']{3,25})["\']', cells[5], re.I):
                    g = html.unescape(g).strip()
                    if re.fullmatch(r"[A-Za-zÀ-ÿ' .:\-]+", g) and g not in mons:
                        mons.append(g)
            out["rows"].append({"pos": int(txt(cells[0])), "pl": name, "cc": fl.upper(), "pz": pz, "ex": ex, "mons": mons[:6]})
        out["rows"] = out["rows"][:8]
    except Exception as ex:
        print("Top 8 VR non letta:", ex)
    return out

def vr_top8(link, data=None):
    """Righe di testo per la notifica: '1. Nome (US) - $785'."""
    d = data or vr_page(link)
    return ["%d. %s%s%s" % (r["pos"], r["pl"], (" (%s)" % r["cc"]) if r["cc"] else "", (" - " + r["pz"]) if r["pz"] else "") for r in d["rows"]]

def dataita(ev):
    try:
        a = datetime.fromisoformat(ev["date"]); b = datetime.fromisoformat(ev["end"]) if ev.get("end") else None
    except Exception:
        return ""
    if b and b != a:
        return ("%d–%d %s %d" % (a.day, b.day, MESI_IT[b.month - 1], b.year)) if a.month == b.month else ("%d %s – %d %s %d" % (a.day, MESI_IT[a.month - 1], b.day, MESI_IT[b.month - 1], b.year))
    return "%d %s %d" % (a.day, MESI_IT[a.month - 1], a.year)

def vr_article(name, link, data):
    """Articolo per la sezione Grandi tornei del sito (news_vr.json): top 8, premi, giocatori, formato, regolamento."""
    if not data["rows"]:
        return None
    ev = data["ev"] or {}
    parts = [x for x in (dataita(ev), ("%s giocatori" % data["players"]) if data["players"] else "", ("Regolamento %s" % ev["reg"]) if ev.get("reg") else "") if x]
    fmt = data["fmt"] or ""
    for en, it in (("2-phase Swiss rounds", "round svizzeri in 2 fasi"), ("Swiss rounds", "round svizzeri"), ("top cut", "top cut"), ("Open team lists", "· team list aperte"), ("Closed team lists", "· team list chiuse")):
        fmt = re.sub(en, it, fmt, flags=re.I)
    rows = []
    for r in data["rows"]:
        x = {"pl": r["pl"], "cc": r["cc"], "pz": " · ".join(v for v in (r["pz"], r["ex"]) if v)}
        if r["mons"]:
            x["mons"] = r["mons"]
        rows.append(x)
    return {"t": "Victory Road", "n": name, "d": " · ".join(parts), "top": len(rows), "real": True, "src": link, "srcn": "Victory Road",
            "fmt": fmt, "ts": (ev.get("end") or ev.get("date") or ""), "rows": rows}

def vr_salva(art):
    try:
        try:
            lst = json.load(open(VR_JSON, encoding="utf-8"))
        except Exception:
            lst = []
        lst = [art] + [x for x in lst if x.get("n") != art["n"]]
        json.dump(lst[:8], open(VR_JSON, "w", encoding="utf-8"), ensure_ascii=False)
        return True
    except Exception as ex:
        print("Articolo VR non salvato:", ex)
        return False

def vr_backfill(champs):
    """Crea l'articolo (news_vr.json) dei vincitori VR che ne sono ancora privi, senza mandare notifiche:
    serve per i tornei già avvisati prima che esistesse l'articolo."""
    try:
        try:
            have = {x.get("n") for x in json.load(open(VR_JSON, encoding="utf-8"))}
        except Exception:
            have = set()
        for pl, ev, link in champs[:3]:
            if ev in have:
                continue
            links = [link] if link and link.rstrip("/") != ue.VR.rstrip("/") else []
            m = re.search(r"VR (\w+) Challenge #(\d+)", ev)  # banner senza link: si prova l'indirizzo vr-oct26-3
            if m and not links:
                yy = datetime.now(ue.ROME).year % 100
                n = int(m[2])
                links = [ue.VR + "vr-%s%02d%s/" % (m[1][:3].lower(), yy, "" if n == 1 else "-%d" % n)]
            for lk in links:
                art = vr_article(ev, lk, vr_page(lk))
                if art and vr_salva(art):
                    log("notify_players: articolo VR creato: %s" % ev)
                    break
            else:
                log("notify_players: articolo VR non creato (pagina o top 8 non leggibili): %s" % ev)
    except Exception as ex:
        print("Articoli VR non creati:", ex)

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
        vr_backfill(champs)
        done = {k.split("|", 2)[2] for k in sent if k.startswith("V|") and k.count("|") >= 2}  # tornei VR già registrati
        for pl, ev, link in champs:
            key = "V|%s|%s" % (pl, ev)
            if key not in sent and ev not in done:
                done.add(ev)
                sent.add(key)
                if vr_ready:  # la prima volta si memorizza soltanto
                    vr_new.append((pl, ev, link))
    ann = []  # annunci Victory Road con iscrizioni aperte (avviso "vrreg")
    for nome, link, ev in vr_annunci(VR_HOME["html"] or ""):
        if ("R|%s" % nome) not in sent:
            sent.add("R|%s" % nome)
            ann.append((nome, link, ev))
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
    log("notify_players: da inviare: %d player, %d vincitori, %d VR, %d iscrizioni VR" % (len(new), len(wins), len(vr_new), len(ann)))
    try:
        if len(new) > 5:
            ue.deliver(TOPIC, "Player in evidenza", "\n".join("%s - %s" % (x["pl"], x["t"]) for x in new[:5]) + "\ne altri %d" % (len(new) - 5), ue.sito_url(TOPIC))
        else:
            for x in new:
                ue.deliver(TOPIC, "Player in evidenza: %s" % x["pl"], "%s a %s%s" % (place(x["p"]), x["t"], (" (%s)" % x["d"]) if x.get("d") else ""),
                           "https://limitlessvgc.com/tournaments/%s" % x["id"])
        for nome, link, ev in ann:
            ue.deliver_multi(["vrreg", "vr"], "Victory Road: iscrizioni aperte", "%s\n%s" % (nome, dataita(ev)), link)  # chi ha attivo "Victory Road" o la casella dedicata: un solo avviso
        for pl, ev, link in vr_new:
            data = vr_page(link)
            art = vr_article(ev, link, data)
            click = link  # senza articolo si apre la pagina di Victory Road
            if art and vr_salva(art):  # con l'articolo: il sito si apre su quel torneo, già aperto (poi l'articolo rimanda a Victory Road)
                click = ue.sito_url("vrwin").split("#")[0] + "#vr-" + re.sub(r"^vr-", "", link.rstrip("/").split("/")[-1])
            ue.deliver("vrwin", "Vincitore Victory Road: %s" % pl, "\n".join([ev] + vr_top8(link, data)), click)
        for r in wins:
            ue.deliver("winner", "Vincitore Regionale: %s" % r[0],
                       "\n".join(["Regional %s%s" % (r[2], (" (%s)" % r[1]) if r[1] else "")] + reg_top8(news, r[3])),
                       "https://limitlessvgc.com/tournaments/%s" % r[3])
        print("Avvisi inviati: %d player, %d vincitori, %d VR, %d iscrizioni VR" % (len(new), len(wins), len(vr_new), len(ann)))
    except Exception as ex:
        print("Avviso player non inviato:", ex)
        return  # lo stato non si aggiorna: si riprova al giro dopo
    json.dump({"min_id": min_id, "sent": sorted(sent), "vr_init": bool(st.get("vr_init") or champs)},
              open(STATE, "w", encoding="utf-8"), ensure_ascii=False)

if __name__ == "__main__":
    main()
