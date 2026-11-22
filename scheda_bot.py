#!/usr/bin/env python3
"""Bot Telegram @rakings_vgc_bot: i giocatori mandano la loro «scheda giocatore».

La parte «sempre accesa» del bot è su Google Apps Script (repo VGCbotAK, Codice.gs): ogni minuto legge Telegram,
risponde subito ai comandi, mette in coda moduli, foto e /cancella e avvia questo flusso, che legge la coda chiamando
l'app web dello script (indirizzo nella variabile SCHEDA_CODA_URL del repo, chiave ricavata dal token del bot).
Gira anche da solo 4 volte al giorno come riserva. Senza SCHEDA_CODA_URL legge i messaggi con getUpdates come prima.
A ogni giro:
  - legge i messaggi nuovi (coda di Apps Script, oppure getUpdates) e, solo senza Deno, risponde ai comandi /start, /scheda, /aiuto;
  - unisce i messaggi di ogni giocatore arrivati nel giro (testo con il modello + foto: prima l'avatar, poi il logo del team);
  - controlla la scheda (18 anni confermati, nome, almeno un profilo Instagram, Facebook o X, tipi validi, link Pokepaste);
  - legge le squadre dai link Pokepaste e Showdown psim.us/t/ (open teamsheet: Pokémon, strumento, abilità, tera, mosse; niente EV);
  - salva la scheda IN ATTESA in schede/attesa.json, CIFRATA con BACKUP_CHIAVE (il repo è pubblico: niente foto o
    link visibili prima dell'approvazione); l'approvazione si fa dalla pagina admin (scheda «Schede»), che lancia
    «python scheda_bot.py azione <id> approva|rifiuta [motivo]»: la scheda approvata va in schede/pubbliche.json
    (senza dati Telegram), l'avatar in schede/img/, il team in schede/team.json con il primo logo approvato;
  - /cancella elimina subito la scheda pubblica (senza bisogno di approvazione);
  - risponde al giocatore: ricevuta / cosa manca.
Chiavi: TELEGRAM_BOT_TOKEN e BACKUP_CHIAVE (segreti di GitHub). Nessuna chiave nel repo.
"""
import base64
import difflib
import unicodedata
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

CAMPI_S = None   # CAMPI con le chiavi senza accenti/punteggiatura (riempito dopo)

COLORI = {  # colore del nickname: lista fissa, tonalità leggibili sullo sfondo scuro della scheda
    "rosso": "#ff5a5f", "red": "#ff5a5f", "arancione": "#ff9f43", "orange": "#ff9f43", "giallo": "#ffd21f",
    "yellow": "#ffd21f", "verde": "#4cd97b", "green": "#4cd97b", "azzurro": "#5ad1ff", "light blue": "#5ad1ff",
    "cyan": "#5ad1ff", "blu": "#7b93ff", "blue": "#7b93ff", "viola": "#b57bff", "purple": "#b57bff",
    "bianco": "#ffffff", "white": "#ffffff", "oro": "#e8c060", "gold": "#e8c060",
}

TIPI_NOMI = {  # chiave -> modi in cui la gente lo scrive (IT, EN, ES, FR, DE e varianti comuni)
    "normal": "normale normal norm",
    "fire": "fuoco fire fuego feu feuer",
    "water": "acqua water agua eau wasser",
    "electric": "elettro elettrico elettrica electric electrico elettr elektro electrik electrique",
    "grass": "erba grass planta plante pflanze erbe",
    "ice": "ghiaccio ice hielo glace eis",
    "fighting": "lotta fighting fight combattimento lucha combat kampf",
    "poison": "veleno poison veneno gift velenoso",
    "ground": "terra ground tierra sol boden suolo",
    "flying": "volante flying volo volador vol flug",
    "psychic": "psico psichico psichica psychic psiquico psy psycho psycho",
    "bug": "coleottero insetto bug bicho insecte kafer",
    "rock": "roccia rock roca roche gestein",
    "ghost": "spettro fantasma ghost spectre geist",
    "dragon": "drago dragone dragon drache",
    "dark": "buio oscurita oscuro dark siniestro tenebres unlicht tenebre sinistro",
    "steel": "acciaio steel acero acier stahl metallo metal",
    "fairy": "folletto fata fairy hada fee",
}
TIPI = {nome: k for k, nomi in TIPI_NOMI.items() for nome in nomi.split()}

CAMPI = {  # chiave del modello (IT/EN) -> campo
    "nome": "nome", "name": "nome", "first name": "nome", "nome e cognome": "nome", "nome completo": "nome", "full name": "nome",
    "cognome": "cognome", "surname": "cognome", "last name": "cognome",
    "nickname": "nickname", "nick": "nickname",
    "nickname battlefy/vr": "nick_vr", "nickname battlefy / vr": "nick_vr", "nickname battlefy": "nick_vr",
    "nickname victory road": "nick_vr", "nickname vr": "nick_vr", "battlefy": "nick_vr", "victory road": "nick_vr",
    "nickname in game": "nick_gioco", "nickname in-game": "nick_gioco", "in game": "nick_gioco", "ign": "nick_gioco",
    "colore nickname": "colore", "colore": "colore", "nickname color": "colore", "nickname colour": "colore", "color": "colore",
    "paese": "paese", "country": "paese", "bandiera": "paese", "flag": "paese",
    "team": "team", "squadra team": "team",
    "tipi": "tipi", "tipi preferiti": "tipi", "types": "tipi", "favourite types": "tipi", "favorite types": "tipi",
    "instagram": "instagram", "facebook": "facebook", "x": "x", "twitter": "x", "twitch": "twitch",
    "youtube": "youtube", "tiktok": "tiktok",
    "squadre": "squadre", "teams": "squadre", "pokepaste": "squadre",
    "frase": "frase", "quote": "frase",
    "18 anni": "eta", "ho almeno 18 anni": "eta", "sono maggiorenne": "eta", "eta": "eta", "età": "eta", "age": "eta",
    "i am 18 or older": "eta", "18+": "eta",
}
SOCIAL_HOST = {
    "instagram": ("instagram.com",), "facebook": ("facebook.com", "fb.com"), "x": ("x.com", "twitter.com"),
    "twitch": ("twitch.tv",), "youtube": ("youtube.com", "youtu.be"), "tiktok": ("tiktok.com",),
}

BENVENUTO = "👋 Ciao! Con questo bot crei la tua *scheda giocatore* su rAKings VGC.\n\n⚠️ *LEGGI PRIMA DI INIZIARE* ⚠️\n\n⚠️🔴 *Non sbagliare il logo del team!*\nIl logo vale per tutti i membri del team e si può cambiare solo con il permesso dell'admin di rAKings.\n\n⚠️ *Il tuo team è già iscritto?*\nSe un tuo compagno ha già mandato il logo del team, tu *non mandarlo di nuovo*: scrivi solo il nome del team nel modulo, altrimenti rischi di cambiarlo per tutti.\n\n⚠️ *Serve un profilo social aperto*\nCi vuole almeno un profilo Instagram, Facebook o X pubblico: è l'unico modo che abbiamo per verificare che sei davvero tu. Senza, la scheda non può essere approvata e non comparirà sull'app.\n\n📋 *Come funziona*\n1. Copia il modulo che trovi qui sotto, compilalo e mandalo.\n2. Manda le foto: prima l'avatar, poi (se serve) il logo del team.\n3. Ti rispondo in un paio di minuti; poi l'admin controlla la scheda e la pubblica.\n\n✏️ Per modificare la scheda rimanda il modulo con /scheda · 🗑 Per eliminarla scrivi /cancella\n\nInviando la scheda confermi di avere *almeno 18 anni* e che dati, foto e profili social sono tuoi. Se invii il logo di un team dichiari di avere il diritto di usarlo e accetti che venga mostrato su rAKings VGC: la responsabilità del logo è tua.\n\n🇬🇧 Copy the template below, fill it in and send it with your avatar. ⚠️ Double-check your team logo: it is shared by the whole team and only the rAKings admin can change it. If a teammate already sent it, do not send it again. An open Instagram, Facebook or X profile is required to verify it is really you. You must be at least 18. /cancella deletes your card."   # stesso testo dello script Google (Codice.gs)
MODELLO = (
    "Copia questo modello, compilalo e mandalo con le foto (prima avatar, poi logo del team) — "
    "copy, fill in and send it with your photos:\n\n"
    "Nome: \n"
    "Cognome: \n"
    "Nickname: \n"
    "Nickname Battlefy/VR (facoltativo): \n"
    "Nickname in game (facoltativo): \n"
    "Colore nickname: (rosso, arancione, giallo, verde, azzurro, blu, viola, bianco, oro)\n"
    "Paese: (es. Italia / Italy)\n"
    "Team: (facoltativo / optional)\n"
    "Tipi preferiti: (2 tipi, es. Fuoco, Acqua)\n"
    "Instagram: https://instagram.com/...\n"
    "Facebook: (facoltativo)\n"
    "X: (facoltativo)\n"
    "Twitch: (facoltativo)\n"
    "YouTube: (facoltativo)\n"
    "TikTok: (facoltativo)\n"
    "Squadre (fino a 6, una per riga):\n"
    "Formato o nome squadra: \n"
    "Frase: (facoltativa, max 140 caratteri)\n"
    "Ho almeno 18 anni: SI"
)
AIUTO = (
    "ℹ️ /scheda modello da compilare · /cancella elimina la tua scheda · /start come funziona.\n"
    "Serve almeno un profilo Instagram, Facebook o X *pubblico*: lo usiamo per verificare che sei tu.\n"
    "Le squadre vanno messe come link di pokepast.es o di Showdown (psim.us/t/…)."
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
        return
    except Exception as ex:
        log("Risposta con formattazione rifiutata, la rimando senza:", ex)
    try:                      # es. un «_» o un «*» scritto dal giocatore o nel motivo del rifiuto
        tg("sendMessage", chat_id=chat, text=testo, disable_web_page_preview="true")
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


def semplice(t):
    """minuscolo, senza accenti, solo lettere e numeri separati da uno spazio: «Acciàio,ACQUA» -> «acciaio acqua»"""
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", t))


def simile(parola, scelte, soglia=0.8):
    """la parola giusta anche con un errore di battitura («aciaio» -> «acciaio»), oppure None"""
    if parola in scelte:
        return parola
    m = difflib.get_close_matches(parola, list(scelte), n=1, cutoff=soglia)
    return m[0] if m else None


def squadra_da_riga(riga):
    """(formato, link) da una riga con un link Pokepaste, anche scritto come [Nome](link) o con altro testo intorno."""
    m = re.search(r"pokepast\.es/([0-9a-z]{6,32})", riga or "", re.I)
    sd = None if m else re.search(r"(?:psim\.us/t/|pokemonshowdown\.com/(?:t/|view/))(\d{3,12})", riga or "", re.I)
    if sd:                                            # squadre salvate su Showdown: https://psim.us/t/2091236
        m = sd
    if not m:
        return None
    prima = re.sub(r"(https?://)?(www\.|play\.|teams\.)?$", "", riga[:m.start()], flags=re.I)
    md = re.search(r"\[([^\]]*)\]\(\s*$", prima)              # [Untitled 1 (OTS)](https://pokepast.es/...)
    if md:
        etichetta = prima[:md.start()].strip(" :-\t") or md.group(1).strip()
    else:
        etichetta = prima.strip(" :-\t[]()")
    if ":" in etichetta and etichetta.split(":", 1)[0].strip():   # «Reg M-C: Untitled 1» -> «Reg M-C»
        etichetta = etichetta.split(":", 1)[0].strip()
    if norm(etichetta) in ("formato o nome squadra", "formato", "nome squadra", "squadra"):   # etichetta del modulo lasciata così
        etichetta = ""
    return etichetta, ("https://psim.us/t/" + m.group(1)) if sd else ("https://pokepast.es/" + m.group(1).lower())


def con_link(msg):
    """Testo del messaggio con i link «nascosti» di Telegram (testo cliccabile) scritti dopo il testo."""
    t = msg.get("text") or msg.get("caption") or ""
    ents = [e for e in (msg.get("entities") or msg.get("caption_entities") or []) if e.get("type") == "text_link" and e.get("url")]
    if not ents:
        return t
    u = t.encode("utf-16-le")                       # Telegram conta le posizioni in unità UTF-16
    for e in sorted(ents, key=lambda e: -e.get("offset", 0)):
        fine = (e.get("offset", 0) + e.get("length", 0)) * 2
        u = u[:fine] + (" " + e["url"]).encode("utf-16-le") + u[fine:]
    return u.decode("utf-16-le", "replace")


def leggi_modello(testo):
    """'Chiave: valore' riga per riga; le righe senza chiave nota dopo «Squadre:» sono altre squadre."""
    global CAMPI_S
    if CAMPI_S is None:
        CAMPI_S = {semplice(k): v for k, v in CAMPI.items()}
    campi, squadre, ultimo = {}, [], None
    for riga in (testo or "").splitlines():
        if not riga.strip():
            continue
        m = re.match(r"^\s*([^:=]{1,50}?)\s*[:=]\s*(.*)$", riga)
        chiave = None
        if m and not re.match(r"^\s*https?$", m.group(1), re.I):
            etichetta = re.sub(r"\(.*?\)", "", m.group(1))                 # «(facoltativo)» nell'etichetta non conta
            chiave = CAMPI.get(norm(etichetta)) or CAMPI_S.get(semplice(etichetta))
            if not chiave and len(semplice(etichetta)) >= 4:                # «Instragram», «Nikname»…
                vicina = simile(semplice(etichetta), CAMPI_S, 0.85)
                chiave = CAMPI_S.get(vicina) if vicina else None
        if chiave:
            ultimo = chiave
            val = m.group(2).strip()
            if chiave == "squadre":
                sq = squadra_da_riga(val)
                if sq:
                    squadre.append(sq)
            else:
                campi[chiave] = val
        elif ultimo == "squadre":
            sq = squadra_da_riga(riga)
            if sq:
                squadre.append(sq)
    campi["squadre"] = squadre
    return campi


def link_social(campo, val):
    val = (val or "").strip()
    if not val or val.startswith("("):
        return ""
    nome = re.match(r"^@?([\w.\-]{1,40})$", val)
    if nome:                                             # solo il nome utente («@mario.rossi»): si costruisce il link
        base = {"instagram": "instagram.com/", "facebook": "facebook.com/", "x": "x.com/", "twitch": "twitch.tv/",
                "youtube": "youtube.com/@", "tiktok": "tiktok.com/@"}[campo]
        val = "https://" + base + nome.group(1)
    elif not re.match(r"^https?://", val, re.I):
        val = "https://" + val.lstrip("@/")
    u = urllib.parse.urlparse(val)
    host = u.netloc.lower().removeprefix("www.").removeprefix("m.")
    if not any(host == h or host.endswith("." + h) for h in SOCIAL_HOST[campo]):
        return ""
    return "https://%s%s" % (host, u.path.rstrip("/"))


NOMI_SD = None


def nomi_showdown():
    """id -> nome di mosse, strumenti e abilità dai dati di Showdown (una volta per giro). Vuoto se non raggiungibile."""
    global NOMI_SD
    if NOMI_SD is not None:
        return NOMI_SD
    NOMI_SD = {}
    for f in ("moves", "items", "abilities"):
        try:
            with urllib.request.urlopen(urllib.request.Request("https://play.pokemonshowdown.com/data/%s.js" % f,
                                                               headers={"User-Agent": "rakings-bot (+https://rakings.github.io)"}), timeout=30) as r:
                t = r.read().decode("utf-8", "replace")
        except Exception as ex:
            log("Dati Showdown non letti:", f, ex)
            continue
        i, prof, chiave = t.find("{"), 0, None            # oggetto {id:{...,name:"Nome",...}, ...}: si contano le graffe
        for m in re.finditer(r'[{}]|([a-z0-9]+):\{|name:"([^"]+)"', t[i:]):
            tok = m.group(0)
            if m.group(1) is not None:
                if prof == 1:
                    chiave = m.group(1)
                prof += 1
            elif tok == "{":
                prof += 1
            elif tok == "}":
                prof -= 1
            elif m.group(2) is not None and prof == 2 and chiave:
                NOMI_SD.setdefault(chiave, m.group(2))
                chiave = None
    return NOMI_SD


def nome_sd(v):
    k = re.sub(r"[^a-z0-9]", "", (v or "").lower())
    if not k:
        return ""
    return nomi_showdown().get(k) or re.sub(r"(?<=[a-z])(?=[A-Z])", " ", v)


def leggi_showdown(url):
    """Squadra salvata su Showdown (psim.us/t/ID): formato «packed» -> stessa lista di leggi_pokepaste."""
    m = re.search(r"(\d{3,12})\s*$", url or "")
    if not m:
        return None
    try:
        req = urllib.request.Request("https://teams.pokemonshowdown.com/api/getteam?teamid=" + m.group(1),
                                     headers={"User-Agent": "rakings-bot (+https://rakings.github.io)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            dati = json.loads(r.read().decode("utf-8", "replace").lstrip("]"))
    except Exception as ex:
        log("Squadra Showdown non letta:", url, ex)
        return None
    squadra = []
    for pk in (dati.get("team") or "").split("]"):
        c = pk.split("|")
        if len(c) < 5:
            continue
        specie = c[1] or c[0]
        extra = c[11].split(",") if len(c) > 11 else []
        squadra.append({"pokemon": specie.strip(), "strumento": nome_sd(c[2]), "abilita": nome_sd(c[3]),
                        "tera": extra[5].strip() if len(extra) > 5 else "",
                        "mosse": [nome_sd(x) for x in c[4].split(",") if x][:4]})
    return squadra[:6] or None


TITOLO_PASTE = ""   # titolo dell'ultimo Pokepaste letto (le squadre di Showdown non hanno un titolo leggibile)


def leggi_pokepaste(url):
    """Pokepaste in formato Showdown -> lista di 6 {pokemon, strumento, abilita, tera, mosse}. Niente EV/IV/natura."""
    global TITOLO_PASTE
    TITOLO_PASTE = ""
    if "psim.us/t/" in (url or ""):
        return leggi_showdown(url)
    m = re.search(r"pokepast\.es/([0-9a-f]{6,32})", url or "", re.I)
    if not m:
        return None
    try:                                              # /json: testo del paste + titolo (es. «Team pioggia»)
        req = urllib.request.Request("https://pokepast.es/%s/json" % m.group(1), headers={"User-Agent": "rakings-bot (+https://rakings.github.io)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            dati = json.loads(r.read().decode("utf-8", "replace"))
        testo = dati.get("paste") or ""
        TITOLO_PASTE = (dati.get("title") or "").strip()[:40]
    except Exception:
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


def pn_norm(v):
    return " ".join(norm(v).split())


def costruisci(campi, foto, utente):
    """Ritorna (scheda, errori, avvisi)."""
    errori, avvisi = [], []
    eta_scritta = campi.get("eta") or ""
    eta = semplice(eta_scritta)
    confermata = (eta.split()[:1] in (["si"], ["s"], ["yes"], ["y"], ["ok"], ["true"], ["confermo"], ["certo"], ["vero"], ["x"])
                  or any(c in eta_scritta for c in "✅✔☑👍") or (eta.isdigit() and 18 <= int(eta) <= 99))
    if not confermata:
        errori.append("manca la conferma «Ho almeno 18 anni: SI»: la scheda è solo per maggiorenni / missing «I am 18 or older: YES»")
    nome = (campi.get("nome") or "").strip()
    cognome = (campi.get("cognome") or "").strip()
    if nome.startswith("("):
        nome = ""
    if cognome.startswith("("):
        cognome = ""
    if cognome and pn_norm(cognome) not in pn_norm(nome):     # nome completo come nei risultati: «Nome Cognome»
        nome = (nome + " " + cognome).strip()
    if not nome:
        errori.append("manca il Nome / missing Name")
    elif not cognome and len(nome.split()) < 2:
        errori.append("manca il Cognome (serve per collegare la scheda ai tuoi risultati) / missing Surname")
    social = {}
    for c in SOCIAL_HOST:
        v = link_social(c, campi.get(c))
        if campi.get(c) and not campi.get(c, "").startswith("(") and not v:
            avvisi.append("link %s non valido, ignorato / invalid %s link, ignored" % (c, c))
        if v:
            social[c] = v
    if not (social.get("instagram") or social.get("facebook") or social.get("x")):
        errori.append("⚠️ serve un profilo Instagram, Facebook o X pubblico: senza non possiamo verificare che sei davvero tu "
                      "e la scheda non può essere approvata / an open Instagram, Facebook or X profile is required to verify it is you")
    tipi = []
    scritto = campi.get("tipi") or ""
    if not scritto.strip().startswith("("):
        for parola in semplice(scritto).split():         # qualsiasi separatore: spazio, virgola, /, -, +, «e», «and»…
            if parola in ("e", "ed", "and", "y", "et", "und", "o", "or", "tipo", "tipi", "type", "types"):
                continue
            trovati = []
            vicino = simile(parola, TIPI, 0.75) if len(parola) >= 3 else (parola if parola in TIPI else None)
            if vicino:
                trovati = [TIPI[vicino]]
            elif len(parola) >= 6:                       # due tipi attaccati: «acciaioacqua», «fuocoerba»
                for i in range(3, len(parola) - 2):
                    a1, a2 = simile(parola[:i], TIPI, 0.85), simile(parola[i:], TIPI, 0.85)
                    if a1 and a2:
                        trovati = [TIPI[a1], TIPI[a2]]
                        break
            if not trovati:
                avvisi.append("tipo «%s» non riconosciuto / unknown type" % parola)
            for k in trovati:
                if k not in tipi:
                    tipi.append(k)
    tipi = tipi[:2]
    if len(tipi) == 1:
        tipi = tipi * 2
    squadre = []
    if len(campi.get("squadre", [])) > MAX_SQUADRE:
        avvisi.append("hai messo più di %d squadre: tengo le prime %d / more than %d teams: only the first %d are kept" % ((MAX_SQUADRE,) * 4))
    for formato, url in campi.get("squadre", [])[:MAX_SQUADRE]:
        s = leggi_pokepaste(url)
        if s:   # nome della squadra: il titolo del paste; il formato scritto dal giocatore resta come sottotitolo
            squadre.append({"nome": TITOLO_PASTE, "formato": formato[:30], "link": url, "pokemon": s})
        else:
            avvisi.append("squadra non letta (serve un link pokepast.es valido): %s" % url[:60])
    colore_scritto = semplice(campi.get("colore") or "")
    nome_c = simile(colore_scritto, COLORI, 0.75) if colore_scritto else None
    colore = COLORI.get(nome_c, "") if nome_c else ""
    if colore_scritto and not colore and not colore_scritto.startswith("("):
        avvisi.append("colore del nickname «%s» non in lista: resta bianco / unknown nickname colour, white is used" % campi.get("colore", "").strip()[:20])
    frase = (campi.get("frase") or "").strip()
    frase = "" if frase.startswith("(") else frase[:MAX_FRASE]
    team = (campi.get("team") or "").strip()
    team = "" if team.startswith("(") else team[:40]
    scheda = {
        "nome": nome[:60], "nickname": (campi.get("nickname") or "").strip()[:30],
        "nick_vr": (campi.get("nick_vr") or "").strip()[:40], "nick_gioco": (campi.get("nick_gioco") or "").strip()[:20],
        "paese": (campi.get("paese") or "").strip()[:30], "team": team, "tipi": tipi, "social": social,
        "squadre": squadre, "colore": colore, "frase": frase,
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
    pub[pid] = {k: sch.get(k) for k in ("nome", "nickname", "nick_vr", "nick_gioco", "colore", "paese", "tipi", "social", "squadre", "frase")}
    pub[pid].update({"team": ts, "avatar": avatar, "aggiornata": int(time.time())})
    mappa[chiave] = pid
    salva(PUBBLICHE, pub)
    salva(TEAM, team)
    salva(MAPPA, cifra(mappa))
    salva(ATTESA, cifra(attesa))
    rispondi(chat, "🎉 La tua scheda è stata approvata ed è visibile su rAKings VGC! / Your card is approved and live on rAKings VGC!\n\n"
                   "✏️ Per modificarla rimanda il modulo completo con /scheda (le foto solo se vuoi cambiarle): la nuova versione "
                   "sostituisce questa dopo l'approvazione. / To edit it, send the full template again with /scheda."
                   + ("\n\n🛡 Il logo del team non è stato cambiato: resta quello già approvato per il tuo team. "
                      "/ The team logo was not changed: the one already approved for your team stays." if senza_logo else ""))
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
        testo = con_link(msg)
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
