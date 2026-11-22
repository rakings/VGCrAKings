#!/usr/bin/env python3
"""Bot Telegram @rakings_vgc_bot: i giocatori mandano la loro «scheda giocatore».

La parte «sempre accesa» del bot è su Google Apps Script (repo VGCbotAK, Codice.gs): ogni minuto legge Telegram,
risponde subito ai comandi, mette in coda moduli, foto e /cancella e avvia questo flusso, che legge la coda chiamando
l'app web dello script (indirizzo nella variabile SCHEDA_CODA_URL del repo, chiave ricavata dal token del bot).
Gira anche da solo 4 volte al giorno come riserva. Senza SCHEDA_CODA_URL legge i messaggi con getUpdates come prima.
A ogni giro:
  - legge i messaggi nuovi (coda di Apps Script, oppure getUpdates) e, solo senza Deno, risponde ai comandi /start, /scheda, /aiuto;
  - unisce i messaggi di ogni giocatore arrivati nel giro (testo con il modello + foto: prima l'avatar, poi il logo del team);
  - controlla la scheda (14 anni confermati, nome, almeno un profilo Instagram o Facebook, tipi validi, link Pokepaste);
  - legge le squadre dai link Pokepaste (open teamsheet: Pokémon, strumento, abilità, tera, mosse; niente EV);
  - salva la scheda IN ATTESA in schede/attesa.json, CIFRATA con BACKUP_CHIAVE (il repo è pubblico: niente foto o
    link visibili prima dell'approvazione); l'approvazione si fa dalla pagina admin (scheda «Schede»), che lancia
    «python scheda_bot.py azione <id> approva|rifiuta [motivo]»: la scheda approvata va in schede/pubbliche.json
    (senza dati Telegram), l'avatar in schede/img/, il team in schede/team.json con il primo logo approvato;
  - /cancella elimina subito la scheda pubblica (senza bisogno di approvazione);
  - risponde al giocatore: ricevuta / cosa manca.
Chiavi: TELEGRAM_BOT_TOKEN e BACKUP_CHIAVE (segreti di GitHub). Nessuna chiave nel repo.
"""
import base64
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

CARTELLA = "schede"
STATO = os.path.join(CARTELLA, "bot_stato.json")      # solo l'ultimo messaggio letto (niente dati personali)
ATTESA = os.path.join(CARTELLA, "attesa.json")        # schede in attesa di approvazione, cifrate
MAPPA = os.path.join(CARTELLA, "mappa.json")          # giocatore Telegram -> codice pubblico della scheda, cifrata
PUBBLICHE = os.path.join(CARTELLA, "pubbliche.json")  # schede approvate (pubbliche, senza dati Telegram)
TEAM = os.path.join(CARTELLA, "team.json")            # team: nome, logo, membri
IMG = os.path.join(CARTELLA, "img")                   # avatar approvati: img/<codice>.webp
LOGHI = os.path.join(CARTELLA, "team")                # loghi dei team: team/<nome-team>.webp
MAX_SQUADRE = 6
MAX_FRASE = 140
MAX_RISULTATI = 10
LATO_FOTO = 256

TIPI = {  # nome italiano / inglese -> chiave
    "normale": "normal", "normal": "normal", "fuoco": "fire", "fire": "fire", "acqua": "water", "water": "water",
    "elettro": "electric", "electric": "electric", "erba": "grass", "grass": "grass", "ghiaccio": "ice", "ice": "ice",
    "lotta": "fighting", "fighting": "fighting", "veleno": "poison", "poison": "poison", "terra": "ground", "ground": "ground",
    "volante": "flying", "flying": "flying", "psico": "psychic", "psychic": "psychic", "coleottero": "bug", "bug": "bug",
    "roccia": "rock", "rock": "rock", "spettro": "ghost", "ghost": "ghost", "drago": "dragon", "dragon": "dragon",
    "buio": "dark", "dark": "dark", "acciaio": "steel", "steel": "steel", "folletto": "fairy", "fairy": "fairy",
}

CAMPI = {  # chiave del modello (IT/EN) -> campo
    "nome": "nome", "name": "nome",
    "nickname": "nickname", "nick": "nickname",
    "paese": "paese", "country": "paese", "bandiera": "paese", "flag": "paese",
    "team": "team", "squadra team": "team",
    "tipi": "tipi", "tipi preferiti": "tipi", "types": "tipi", "favourite types": "tipi", "favorite types": "tipi",
    "instagram": "instagram", "facebook": "facebook", "x": "x", "twitter": "x", "twitch": "twitch",
    "youtube": "youtube", "tiktok": "tiktok",
    "squadre": "squadre", "teams": "squadre", "pokepaste": "squadre",
    "risultati": "risultati", "results": "risultati",
    "frase": "frase", "quote": "frase",
    "14 anni": "eta", "ho almeno 14 anni": "eta", "eta": "eta", "età": "eta", "age": "eta",
    "i am 14 or older": "eta", "14+": "eta",
}
SOCIAL_HOST = {
    "instagram": ("instagram.com",), "facebook": ("facebook.com", "fb.com"), "x": ("x.com", "twitter.com"),
    "twitch": ("twitch.tv",), "youtube": ("youtube.com", "youtu.be"), "tiktok": ("tiktok.com",),
}

BENVENUTO = "👋 Ciao! Con questo bot crei la tua *scheda giocatore* su rAKings VGC.\n\n⚠️ *LEGGI PRIMA DI INIZIARE* ⚠️\n\n⚠️🔴 *Non sbagliare il logo del team!*\nIl logo vale per tutti i membri del team e si può cambiare solo con il permesso dell'admin di rAKings.\n\n⚠️ *Il tuo team è già iscritto?*\nSe un tuo compagno ha già mandato il logo del team, tu *non mandarlo di nuovo*: scrivi solo il nome del team nel modulo, altrimenti rischi di cambiarlo per tutti.\n\n⚠️ *Serve un profilo social aperto*\nCi vuole almeno un profilo Instagram o Facebook pubblico: è l'unico modo che abbiamo per verificare che sei davvero tu. Senza, la scheda non può essere approvata e non comparirà sull'app.\n\n📋 *Come funziona*\n1. Copia il modulo che trovi qui sotto, compilalo e mandalo.\n2. Manda le foto: prima l'avatar, poi (se serve) il logo del team.\n3. Ti rispondo in un paio di minuti; poi l'admin controlla la scheda e la pubblica.\n\n✏️ Per modificare la scheda rimanda il modulo con /scheda · 🗑 Per eliminarla scrivi /cancella\n\nInviando la scheda confermi di avere *almeno 14 anni* e che dati, foto e profili social sono tuoi. Se invii il logo di un team dichiari di avere il diritto di usarlo e accetti che venga mostrato su rAKings VGC: la responsabilità del logo è tua.\n\n🇬🇧 Copy the template below, fill it in and send it with your avatar. ⚠️ Double-check your team logo: it is shared by the whole team and only the rAKings admin can change it. If a teammate already sent it, do not send it again. An open Instagram or Facebook profile is required to verify it is really you. You must be at least 14. /cancella deletes your card."   # stesso testo dello script Google (Codice.gs)
MODELLO = (
    "Copia questo modello, compilalo e mandalo con le foto (prima avatar, poi logo del team) — "
    "copy, fill in and send it with your photos:\n\n"
    "Nome: (come nei risultati / as in the standings)\n"
    "Nickname: \n"
    "Paese: (es. Italia / Italy)\n"
    "Team: (facoltativo / optional)\n"
    "Tipi preferiti: (2 tipi, es. Fuoco, Acqua)\n"
    "Instagram: https://instagram.com/...\n"
    "Facebook: (facoltativo)\n"
    "X: (facoltativo)\n"
    "Twitch: (facoltativo)\n"
    "YouTube: (facoltativo)\n"
    "TikTok: (facoltativo)\n"
    "Squadre: (fino a 6 link Pokepaste, uno per riga, con il formato davanti)\n"
    "Reg M-C: https://pokepast.es/...\n"
    "Risultati: (facoltativo, tornei non presenti su rAKings, separati da virgola)\n"
    "Frase: (facoltativa, max 140 caratteri)\n"
    "Ho almeno 14 anni: SI"
)
AIUTO = (
    "ℹ️ /scheda modello da compilare · /cancella elimina la tua scheda · /start come funziona.\n"
    "Serve almeno un profilo Instagram o Facebook *pubblico*: lo usiamo per verificare che sei tu.\n"
    "Le squadre vanno messe come link di pokepast.es."
)


def log(*a):
    print(*a, flush=True)


# ---------------- cifratura (stessa di social.py: l'admin decifra nel browser con il suo codice) ----------------
def _openssl(args, dati):
    r = subprocess.run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-md", "sha256", "-a", "-A",
                        "-pass", "env:BACKUP_CHIAVE"] + args, input=dati, capture_output=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError("openssl: %s" % r.stderr.decode("utf-8", "replace").strip()[:120])
    return r.stdout


def cifra(d):
    return {"formato": "aes-256-cbc pbkdf2 sha256 200000",
            "dati": _openssl(["-salt"], json.dumps(d, ensure_ascii=False).encode("utf-8")).decode("ascii")}


def decifra(f):
    if not isinstance(f, dict) or "dati" not in f:
        return {}
    return json.loads(_openssl(["-d"], f["dati"].encode("ascii") + b"\n").decode("utf-8"))


def carica(path, vuoto):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return vuoto


def salva(path, dati):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


# ---------------- Telegram ----------------
def tg(metodo, **param):
    tok = os.environ["TELEGRAM_BOT_TOKEN"]
    dati = urllib.parse.urlencode({k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in param.items()}).encode()
    req = urllib.request.Request("https://api.telegram.org/bot%s/%s" % (tok, metodo), data=dati)
    with urllib.request.urlopen(req, timeout=40) as r:
        out = json.loads(r.read().decode("utf-8"))
    if not out.get("ok"):
        raise RuntimeError("Telegram %s: %s" % (metodo, str(out.get("description"))[:120]))
    return out["result"]


def scarica_file(file_id):
    tok = os.environ["TELEGRAM_BOT_TOKEN"]
    info = tg("getFile", file_id=file_id)
    with urllib.request.urlopen("https://api.telegram.org/file/bot%s/%s" % (tok, info["file_path"]), timeout=40) as r:
        return r.read()


def rispondi(chat, testo):
    try:
        tg("sendMessage", chat_id=chat, text=testo, parse_mode="Markdown", disable_web_page_preview="true")
    except Exception as ex:   # un giocatore che ha bloccato il bot non deve fermare il giro
        log("Risposta non inviata a", chat, ":", ex)


def foto_quadrata(dati):
    """Avatar o logo: ritaglio quadrato al centro, 256x256, WebP leggero (pochi KB). Ritorna base64."""
    from PIL import Image
    im = Image.open(io.BytesIO(dati))
    im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
    w, h = im.size
    lato = min(w, h)
    im = im.crop(((w - lato) // 2, (h - lato) // 2, (w - lato) // 2 + lato, (h - lato) // 2 + lato))
    im = im.resize((LATO_FOTO, LATO_FOTO), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "WEBP", quality=80, method=6)
    return base64.b64encode(out.getvalue()).decode("ascii")


# ---------------- lettura della scheda ----------------
def norm(t):
    return re.sub(r"\s+", " ", (t or "").strip().lower())


def leggi_modello(testo):
    """'Chiave: valore' riga per riga; le righe senza chiave nota dopo «Squadre:» sono altre squadre."""
    campi, squadre, ultimo = {}, [], None
    for riga in (testo or "").splitlines():
        if not riga.strip():
            continue
        m = re.match(r"^\s*([^:]{1,30}?)\s*:\s*(.*)$", riga)
        chiave = CAMPI.get(norm(m.group(1))) if m else None
        if chiave:
            ultimo = chiave
            val = m.group(2).strip()
            if chiave == "squadre":
                if val:
                    squadre.append(("", val))
            else:
                campi[chiave] = val
        elif ultimo == "squadre":
            m2 = re.match(r"^\s*(.*?)\s*:?\s*(https?://\S+)\s*$", riga)
            if m2:
                squadre.append((m2.group(1).strip(" :-"), m2.group(2)))
    campi["squadre"] = squadre
    return campi


def link_social(campo, val):
    val = (val or "").strip()
    if not val or val.startswith("("):
        return ""
    if not re.match(r"^https?://", val, re.I):
        val = "https://" + val.lstrip("@/")
        if campo == "instagram" and "instagram.com" not in val:
            val = "https://instagram.com/" + val.split("//", 1)[1]
    u = urllib.parse.urlparse(val)
    host = u.netloc.lower().removeprefix("www.").removeprefix("m.")
    if not any(host == h or host.endswith("." + h) for h in SOCIAL_HOST[campo]):
        return ""
    return "https://%s%s" % (host, u.path.rstrip("/"))


def leggi_pokepaste(url):
    """Pokepaste in formato Showdown -> lista di 6 {pokemon, strumento, abilita, tera, mosse}. Niente EV/IV/natura."""
    m = re.search(r"pokepast\.es/([0-9a-f]{6,32})", url or "", re.I)
    if not m:
        return None
    try:
        with urllib.request.urlopen("https://pokepast.es/%s/raw" % m.group(1), timeout=20) as r:
            testo = r.read().decode("utf-8", "replace")
    except Exception as ex:
        log("Pokepaste non letto:", url, ex)
        return None
    squadra = []
    for blocco in re.split(r"\n\s*\n", testo.replace("\r", "").strip()):
        righe = [x.strip() for x in blocco.split("\n") if x.strip()]
        if not righe:
            continue
        testa = righe[0]
        strumento = ""
        if " @ " in testa:
            testa, strumento = testa.split(" @ ", 1)
        testa = re.sub(r"\s*\((M|F)\)\s*$", "", testa.strip())
        mm = re.match(r"^.*\((.+)\)$", testa)          # «Soprannome (Specie)»
        specie = mm.group(1) if mm else testa
        p = {"pokemon": specie.strip(), "strumento": strumento.strip(), "abilita": "", "tera": "", "mosse": []}
        for x in righe[1:]:
            if x.lower().startswith("ability:"):
                p["abilita"] = x.split(":", 1)[1].strip()
            elif x.lower().startswith("tera type:"):
                p["tera"] = x.split(":", 1)[1].strip()
            elif x.startswith("-"):
                p["mosse"].append(x.lstrip("- ").strip())
        p["mosse"] = p["mosse"][:4]
        if p["pokemon"]:
            squadra.append(p)
    return squadra[:6] or None


def costruisci(campi, foto, utente):
    """Ritorna (scheda, errori, avvisi)."""
    errori, avvisi = [], []
    eta = norm(campi.get("eta"))
    if eta not in ("si", "sì", "yes", "y", "s", "ok", "true"):
        errori.append("manca la conferma «Ho almeno 14 anni: SI» / missing «I am 14 or older: YES»")
    nome = (campi.get("nome") or "").strip()
    if not nome or nome.startswith("("):
        errori.append("manca il Nome / missing Name")
    social = {}
    for c in SOCIAL_HOST:
        v = link_social(c, campi.get(c))
        if campi.get(c) and not campi.get(c, "").startswith("(") and not v:
            avvisi.append("link %s non valido, ignorato / invalid %s link, ignored" % (c, c))
        if v:
            social[c] = v
    if not (social.get("instagram") or social.get("facebook")):
        errori.append("⚠️ serve un profilo Instagram o Facebook pubblico: senza non possiamo verificare che sei davvero tu "
                      "e la scheda non può essere approvata / an open Instagram or Facebook profile is required to verify it is you")
    tipi = []
    for t in re.split(r"[,/;]| e | and ", campi.get("tipi") or ""):
        k = TIPI.get(norm(t))
        if k and k not in tipi:
            tipi.append(k)
        elif norm(t) and not norm(t).startswith("("):
            avvisi.append("tipo «%s» non riconosciuto / unknown type" % t.strip())
    tipi = tipi[:2]
    if len(tipi) == 1:
        tipi = tipi * 2
    squadre = []
    for formato, url in campi.get("squadre", [])[:MAX_SQUADRE]:
        s = leggi_pokepaste(url)
        if s:
            squadre.append({"formato": formato[:30] or "Squadra %d" % (len(squadre) + 1), "link": url, "pokemon": s})
        else:
            avvisi.append("squadra non letta (serve un link pokepast.es valido): %s" % url[:60])
    risultati = [r.strip()[:80] for r in re.split(r"[,;]", campi.get("risultati") or "") if r.strip() and not r.strip().startswith("(")]
    frase = (campi.get("frase") or "").strip()
    frase = "" if frase.startswith("(") else frase[:MAX_FRASE]
    team = (campi.get("team") or "").strip()
    team = "" if team.startswith("(") else team[:40]
    scheda = {
        "nome": nome[:60], "nickname": (campi.get("nickname") or "").strip()[:30],
        "paese": (campi.get("paese") or "").strip()[:30], "team": team, "tipi": tipi, "social": social,
        "squadre": squadre, "risultati": risultati[:MAX_RISULTATI], "frase": frase,
        "avatar": foto[0] if foto else "", "logo_team": foto[1] if (len(foto) > 1 and team) else "",
        "telegram": {"id": utente.get("id"), "username": utente.get("username") or "", "nome": utente.get("first_name") or ""},
        "ricevuta": int(time.time()),
    }
    if not foto:
        avvisi.append("nessuna foto: verrà usato un avatar con le iniziali / no photo: initials avatar will be used")
    return scheda, errori, avvisi


# ---------------- schede pubbliche (approvate dall'admin) ----------------
def slug_team(nome):
    """«Team Aurora», «team aurora», «TEAM  AURORA» -> «team-aurora» (stesso team)."""
    import unicodedata
    t = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40]


def scrivi_img(path, b64):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64))


def togli_da_team(team, pid, tranne=""):
    for k in list(team):
        if k == tranne:                         # stesso team della scheda nuova: il giocatore resta, logo compreso
            continue
        m = team[k].get("membri", [])
        if pid in m:
            m.remove(pid)
        if not m:                               # team rimasto senza giocatori: sparisce con il suo logo
            try:
                os.remove(os.path.join(LOGHI, k + ".webp"))
            except OSError:
                pass
            del team[k]


def elimina_pubblica(chiave):
    """Toglie la scheda pubblica del giocatore (comando /cancella o richiesta sua). True se c'era."""
    mappa = decifra(carica(MAPPA, {})) if os.path.exists(MAPPA) else {}
    pid = mappa.pop(chiave, None)
    if not pid:
        return False
    pub, team = carica(PUBBLICHE, {}), carica(TEAM, {})
    pub.pop(pid, None)
    togli_da_team(team, pid)
    try:
        os.remove(os.path.join(IMG, pid + ".webp"))
    except OSError:
        pass
    salva(PUBBLICHE, pub)
    salva(TEAM, team)
    salva(MAPPA, cifra(mappa))
    return True


def azione(chiave, az, motivo=""):
    """Dall'admin: approva o rifiuta la scheda in attesa del giocatore (chiave = id Telegram)."""
    attesa = decifra(carica(ATTESA, {})) if os.path.exists(ATTESA) else {}
    sch = attesa.pop(chiave, None)
    if not sch:
        log("Nessuna scheda in attesa per", chiave)
        return 0
    senza_logo = az == "approva" and motivo == "senza_logo"     # «Approva senza logo»: entra nel team, il logo resta quello di prima
    if senza_logo:
        sch["logo_team"] = ""
    chat = (sch.get("telegram") or {}).get("id") or chiave
    if az == "rifiuta":
        salva(ATTESA, cifra(attesa))
        rispondi(chat, "❌ La tua scheda non è stata approvata. / Your card was not approved." +
                 ("\nMotivo / Reason: %s" % motivo[:200] if motivo else "") +
                 "\nPuoi correggerla e rimandarla con /scheda. / You can fix it and send it again.")
        log("Scheda rifiutata:", sch.get("nome"))
        return 0
    mappa = decifra(carica(MAPPA, {})) if os.path.exists(MAPPA) else {}
    pid = mappa.get(chiave) or os.urandom(6).hex()
    pub, team = carica(PUBBLICHE, {}), carica(TEAM, {})
    togli_da_team(team, pid, slug_team(sch.get("team") or ""))
    ts = ""
    if sch.get("team"):
        ts = slug_team(sch["team"])
        t = team.setdefault(ts, {"nome": sch["team"], "logo": False, "membri": []})
        if pid not in t["membri"]:
            t["membri"].append(pid)
        if sch.get("logo_team"):          # il logo vale per tutto il team; lo cambia solo chi approva (l'admin vede l'avviso)
            scrivi_img(os.path.join(LOGHI, ts + ".webp"), sch["logo_team"])
            t["logo"] = True
    avatar = bool(sch.get("avatar"))
    if avatar:
        scrivi_img(os.path.join(IMG, pid + ".webp"), sch["avatar"])
    elif (pub.get(pid) or {}).get("avatar") and os.path.exists(os.path.join(IMG, pid + ".webp")):
        avatar = True                     # scheda modificata senza foto nuova: resta l'avatar di prima
    pub[pid] = {k: sch.get(k) for k in ("nome", "nickname", "paese", "tipi", "social", "squadre", "risultati", "frase")}
    pub[pid].update({"team": ts, "avatar": avatar, "aggiornata": int(time.time())})
    mappa[chiave] = pid
    salva(PUBBLICHE, pub)
    salva(TEAM, team)
    salva(MAPPA, cifra(mappa))
    salva(ATTESA, cifra(attesa))
    rispondi(chat, "🎉 La tua scheda è stata approvata ed è visibile su rAKings VGC! / Your card is approved and live on rAKings VGC!\n\n"
                   "✏️ Per modificarla rimanda il modulo completo con /scheda (le foto solo se vuoi cambiarle): la nuova versione "
                   "sostituisce questa dopo l'approvazione. / To edit it, send the full template again with /scheda.")
    log("Scheda approvata%s:" % (" (senza logo)" if senza_logo else ""), sch.get("nome"), "->", pid)
    return 0


# ---------------- giro ----------------
def elabora(aggiornamenti, attesa):
    """Unisce i messaggi di ogni giocatore e aggiorna le schede in attesa. Ritorna (cambiate, giocatori da tenere in coda)."""
    per_utente = {}
    for u in aggiornamenti:
        msg = u.get("message") or {}
        chat = msg.get("chat") or {}
        if chat.get("type") != "private" or not msg.get("from") or msg["from"].get("is_bot"):
            continue
        d = per_utente.setdefault(msg["from"]["id"], {"utente": msg["from"], "chat": chat["id"], "testi": [], "foto": [], "loghi": [], "comandi": []})
        testo = msg.get("text") or msg.get("caption") or ""
        fid = ""
        if msg.get("photo"):
            fid = sorted(msg["photo"], key=lambda p: p.get("file_size") or 0)[-1]["file_id"]
        elif (msg.get("document") or {}).get("mime_type", "").startswith("image/"):
            fid = msg["document"]["file_id"]
        # foto con «logo» nella didascalia (e non il modulo): è il logo del team, anche senza avatar
        logo = bool(fid) and bool(re.search(r"\blogo\b", testo, re.I)) and not re.search(r"^\s*(nome|name)\s*:", testo, re.I | re.M)
        if logo:
            d["loghi"].append(fid)
            continue
        if testo.strip().startswith("/"):
            d["comandi"].append(testo.strip().split()[0].split("@")[0].lower())
        elif testo.strip():
            d["testi"].append(testo)
        if fid:
            d["foto"].append(fid)

    cambiate = False
    tenuti = set()
    for uid, d in per_utente.items():
        chiave = str(uid)
        for c in d["comandi"]:
            if c == "/start":
                rispondi(d["chat"], BENVENUTO)
            elif c == "/scheda":
                rispondi(d["chat"], MODELLO)
            elif c == "/aiuto":
                rispondi(d["chat"], AIUTO)
            elif c == "/cancella":
                attesa.pop(chiave, None)
                cambiate = True
                tolta = elimina_pubblica(chiave)
                rispondi(d["chat"], "🗑 Fatto: la tua scheda è stata eliminata%s. / Your card has been deleted." %
                         ("" if tolta else " (non era ancora pubblicata)"))
        modello = next((t for t in reversed(d["testi"]) if re.search(r"^\s*(nome|name)\s*:", t, re.I | re.M)), "")
        if not modello:
            if d["loghi"] and chiave in attesa and attesa[chiave].get("team"):   # logo mandato dopo il modulo
                try:
                    attesa[chiave]["logo_team"] = foto_quadrata(scarica_file(d["loghi"][-1]))
                    cambiate = True
                    rispondi(d["chat"], "🛡 Logo del team aggiunto alla tua scheda in attesa: vale dopo l'approvazione dell'admin. / Team logo added, pending approval.")
                except Exception as ex:
                    log("Logo non letto:", ex)
            if d["foto"] and chiave in attesa:              # foto mandate dopo il modulo: vanno nella scheda in attesa
                sch, nuove = attesa[chiave], 0
                for fid in d["foto"][:2]:
                    try:
                        f = foto_quadrata(scarica_file(fid))
                    except Exception as ex:
                        log("Foto non letta:", ex)
                        continue
                    if not sch.get("avatar"):
                        sch["avatar"] = f
                    elif sch.get("team") and not sch.get("logo_team"):
                        sch["logo_team"] = f
                    else:
                        sch["avatar"] = f
                    nuove += 1
                if nuove:
                    cambiate = True
                    rispondi(d["chat"], "📸 Foto aggiunta alla tua scheda in attesa. / Photo added to your pending card.")
                continue
            if (d["foto"] or d["loghi"]) and chiave in attesa:
                continue
            if (d["foto"] or d["loghi"]) and not d["testi"] and not d["comandi"]:
                tenuti.add(uid)                             # foto arrivate prima del modulo: restano in coda
                continue
            if d["testi"] and not d["comandi"]:
                rispondi(d["chat"], "Non ho trovato il modello compilato. Scrivi /scheda per riceverlo. / Template not found: send /scheda.")
            continue
        foto = []
        for fid in d["foto"][:1 if d["loghi"] else 2]:
            try:
                foto.append(foto_quadrata(scarica_file(fid)))
            except Exception as ex:
                log("Foto non letta:", ex)
        if d["loghi"]:                                      # logo indicato con la didascalia: avatar facoltativo
            try:
                foto = [foto[0] if foto else "", foto_quadrata(scarica_file(d["loghi"][-1]))]
            except Exception as ex:
                log("Logo non letto:", ex)
        scheda, errori, avvisi = costruisci(leggi_modello(modello), foto, d["utente"])
        if errori:
            rispondi(d["chat"], "❌ Scheda non accettata / Card not accepted:\n- " + "\n- ".join(errori) +
                     "\n\nCorreggi e rimanda il modello. / Fix it and send the template again.")
            continue
        attesa[chiave] = scheda
        cambiate = True
        extra = ("\n\nNote:\n- " + "\n- ".join(avvisi)) if avvisi else ""
        rispondi(d["chat"], "✅ Scheda ricevuta, ora è in attesa di approvazione. / Card received, waiting for approval." + extra)
        log("Scheda in attesa:", scheda["nome"], "| squadre", len(scheda["squadre"]), "| foto", len(foto))

    return cambiate, tenuti


def coda_deno(base, chiave, ids=None):
    """Legge (ids=None) o svuota la coda dei messaggi dell'app web di Apps Script (POST; Google risponde con un rimando, seguito da urllib)."""
    corpo = {"k": chiave, "op": "leggi"} if ids is None else {"k": chiave, "op": "fatti", "ids": ids}
    req = urllib.request.Request(base, data=json.dumps(corpo).encode(), headers={"User-Agent": "rakings-bot", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.loads(r.read().decode("utf-8"))
    if not out.get("ok"):
        raise RuntimeError("coda: %s" % out.get("errore", "risposta non valida"))
    return out


def giro_deno(base, attesa):
    chiave = hashlib.sha256(("rakings-coda:" + os.environ["TELEGRAM_BOT_TOKEN"]).encode()).hexdigest()
    cambiate, visti = False, set()
    for _ in range(4):                                   # rilegge: i messaggi arrivati mentre lavorava vanno nello stesso giro
        coda = coda_deno(base, chiave)["coda"]
        if coda:                                         # aspetta 30 secondi dall'ultimo messaggio: le foto arrivano dopo il testo
            eta = time.time() - max(c["t"] for c in coda) / 1000
            if eta < 30:
                time.sleep(31 - eta)
                coda = coda_deno(base, chiave)["coda"]
        nuovi = [c for c in coda if c["id"] not in visti]
        log("Messaggi in coda:", len(nuovi))
        if not nuovi:
            break
        visti.update(c["id"] for c in nuovi)
        c2, tenuti = elabora([c["u"] for c in nuovi], attesa)
        cambiate = cambiate or c2
        if c2:
            salva(ATTESA, cifra(attesa))
        vecchi = time.time() * 1000 - 86400000          # foto senza modulo da più di un giorno: si buttano
        fatti = [c["id"] for c in nuovi if ((c["u"].get("message") or {}).get("from") or {}).get("id") not in tenuti or c["t"] < vecchi]
        if fatti:
            coda_deno(base, chiave, fatti)
    log("Fatto. Schede in attesa:", len(attesa))
    return 0


def giro():
    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        log("TELEGRAM_BOT_TOKEN mancante: niente da fare.")
        return 0
    if not os.environ.get("BACKUP_CHIAVE"):
        log("BACKUP_CHIAVE mancante: non posso salvare le schede cifrate, mi fermo.")
        return 1
    attesa = decifra(carica(ATTESA, {})) if os.path.exists(ATTESA) else {}
    coda_url = (os.environ.get("SCHEDA_CODA_URL") or "").strip()
    if coda_url.startswith("https://script.google.com/"):   # bot su Apps Script: si legge la sua coda (mai getUpdates)
        return giro_deno(coda_url, attesa)
    stato = carica(STATO, {})
    offset = int(stato.get("offset") or 0)
    aggiornamenti = tg("getUpdates", offset=offset, timeout=0, allowed_updates=["message"])
    log("Messaggi nuovi:", len(aggiornamenti))
    if not aggiornamenti:
        return 0
    for u in aggiornamenti:
        offset = max(offset, u["update_id"] + 1)
    cambiate, _ = elabora(aggiornamenti, attesa)
    if cambiate:
        salva(ATTESA, cifra(attesa))
    salva(STATO, {"offset": offset, "letto": int(time.time())})
    tg("getUpdates", offset=offset, timeout=0)     # conferma a Telegram: i messaggi letti non tornano più
    log("Fatto. Schede in attesa:", len(attesa))
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "azione":          # dalla pagina admin (flusso scheda-azione)
        if not os.environ.get("BACKUP_CHIAVE"):
            sys.exit("BACKUP_CHIAVE mancante")
        if not re.fullmatch(r"\d{3,15}", sys.argv[2]) or sys.argv[3] not in ("approva", "rifiuta"):
            sys.exit("richiesta non valida")
        sys.exit(azione(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else ""))
    sys.exit(giro())
