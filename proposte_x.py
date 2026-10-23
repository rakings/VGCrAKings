#!/usr/bin/env python3
"""Ogni avviso del bot diventa una Issue del repository con un link 'Pubblica su X'.
Tu ricevi la notifica di GitHub (app o mail), apri la Issue, tocchi il link: X si apre con il post già scritto,
premi Pubblica. Quelli che non vuoi li ignori. Gratuito: nessuna API di X, solo il link ufficiale x.com/intent/post.

Di default le Issue nascono nel repo del sito (basta  permissions: issues: write  e GITHUB_TOKEN automatico).
Per metterle nel repo PRIVATO: variabile X_REPO = utente/repo-privato e segreto X_TOKEN (token con permesso Issues: lettura e scrittura su quel repo).
Pausa/ripresa: workflow 'X - Pausa' e 'X - Riprendi' (file x_stato.json). I post sono in INGLESE (variabile X_LINGUA=it per l'italiano).
Per limitare le categorie: variabile X_CATEGORIE (es. regionali,winner,vrwin,money). Per spegnere: X_ISSUES=0.
Le Issue non pubblicate si chiudono da sole dopo 2 giorni e 8 ore (56 ore).

  python3 proposte_x.py   -> crea una Issue di prova (workflow 'Proposta X di prova')
"""
import json, os, re, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

ETICHETTA = "da-pubblicare-x"
TAGS = "#VGC #PokemonVGC #PokemonChampions"
TAGS_TOPIC = {"regionali": "#VGC #VGCItalia #PokemonChampions", "player": "#VGC #VGCItalia #PokemonChampions"}
LIMITE, LINK_LEN, ORE_MAX = 280, 23, 56   # 56 ore = 2 giorni e 8 ore
_pronto = {"v": False}


def _repo():
    return (os.environ.get("X_REPO") or os.environ.get("GITHUB_REPOSITORY") or "").strip()   # repo privato se impostato


def _token():
    return (os.environ.get("X_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()      # token per il repo privato, altrimenti quello automatico


STATO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "x_stato.json")


def in_pausa():
    """True se hai premuto 'X - Pausa' (file x_stato.json con "attivo": false). Senza il file il servizio è acceso."""
    if os.environ.get("X_PROVA") == "1":
        return False   # la prova da Actions funziona anche in pausa
    try:
        return json.load(open(STATO, encoding="utf-8")).get("attivo") is False
    except Exception:
        return False


def attivo():
    return bool(_token() and _repo()) and os.environ.get("X_ISSUES", "1") != "0" and not in_pausa()


CTA_EN = ["🔔 Not every alert is posted here. Get them all in the free app: link in bio",
          "📲 Want every alert, not just these? Free app, link in bio",
          "🔔 There's more! All alerts, filters & reminders in the free app (link in bio)",
          "📲 Never miss an event: get all alerts in the free app, link in bio",
          "🔔 More alerts in the free app → link in bio"]
CTA_IT = ["🔔 Qui non c'è tutto. Ricevi ogni avviso nell'app gratuita: link in bio",
          "📲 Vuoi ogni avviso, non solo questi? App gratuita, link in bio",
          "🔔 C'è di più! Tutti gli avvisi e i promemoria nell'app gratuita (link in bio)",
          "📲 Non perdere nessun torneo: tutti gli avvisi nell'app gratuita, link in bio",
          "🔔 Più avvisi nell'app gratuita → link in bio"]
CTA_CORTA = {"en": "📲 All alerts in the free app: link in bio", "it": "📲 Tutti gli avvisi nell'app: link in bio"}


def scegli_cta(title, lingua="en"):
    """Una frase diversa a rotazione (stabile per lo stesso titolo): X non ama i post tutti identici."""
    lst = CTA_IT if lingua == "it" else CTA_EN
    return lst[sum(ord(c) for c in title) % len(lst)]


def testo_post(topic, title, body, click, lingua="en"):
    """Titolo, dettagli (accorciati se servono), link, invito a scaricare l'app, hashtag: sempre entro 280 caratteri.
    L'invito c'è SEMPRE: se manca spazio si accorcia prima il dettaglio, poi l'invito (versione corta), poi il titolo."""
    tags = TAGS_TOPIC.get(topic, TAGS)
    link = click if (click or "").startswith("http") else ""
    corpo = " · ".join(x.strip() for x in (body or "").splitlines() if x.strip())
    cta = scegli_cta(title, lingua)

    def spazio_con(c):
        return LIMITE - (len(title) + len(tags) + len(c) + (LINK_LEN if link else 0) + 7)
    if spazio_con(cta) < 20:
        cta = CTA_CORTA["it" if lingua == "it" else "en"]
    spazio = spazio_con(cta)
    if spazio < 0:
        title = title[:max(10, len(title) + spazio - 1)].rstrip() + "…"
        corpo = ""
    elif len(corpo) > spazio:
        corpo = (corpo[:spazio - 1].rstrip() + "…") if spazio > 20 else ""
    return "\n".join([title] + ([corpo] if corpo else []) + ([link] if link else []) + [cta, tags])


# ---------- inglese: l'account X pubblica sempre in inglese (X_LINGUA=it per lasciare l'italiano) ----------
SOLO_ITALIANI = {"locali", "locali8", "annunci"}   # testo originale in italiano: la Issue avvisa di controllare prima di pubblicare
_visti = set()   # (testo, link) già proposti in questa esecuzione: evita il doppione money / money33 dello stesso torneo
MESI_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
MESI_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
TITOLI = {
    "Money tournament": "New money tournament",
    "Money tournament (oltre 33 iscritti)": "Money tournament (33+ players)",
    "Global Challenge": "New Global Challenge",
    "Regionali: nuovo evento": "New Regional Championship announced",
    "Regionali: iscrizioni aperte": "Regional registration is open",
    "Regionali: iscrizioni in chiusura": "Regional registration closing soon",
    "Regionali: orario iscrizioni aggiornato": "Regional registration time updated",
    "Regionali: iscrizioni annunciate": "Regional registration date announced",
    "Victory Road: iscrizioni aperte": "Victory Road: registration is open",
    "Iscrizioni aperte ora": "Registration is open now",
    "Nuovi avvisi VGC": "New VGC events",
    "Player in evidenza": "Players to watch",
    "Maddos Cup: torneo annunciato": "Maddos Cup announced",
    "Maddos Cup: iscrizioni aperte": "Maddos Cup: registration is open",
}
PREFISSI = (("Vincitore Victory Road: ", "Victory Road winner: "), ("Vincitore Regionale: ", "Regional winner: "),
            ("Player in evidenza: ", "Player to watch: "), ("Nuova top 8: ", "New top 8: "), ("Annuncio: ", "Announcement: "))


def _it_to_en(t):
    mesi = "|".join(MESI_IT)
    t = re.sub(r"(\d{1,2})\s*[–-]\s*(\d{1,2}) (%s)(?: (\d{4}))?" % mesi,
                            lambda m: "%s %s–%s%s" % (MESI_EN[MESI_IT.index(m.group(3))], m.group(1), m.group(2), (", " + m.group(4)) if m.group(4) else ""), t)
    t = re.sub(r"(\d{1,2}) (%s) (\d{4})" % mesi, lambda m: "%s %s, %s" % (MESI_EN[MESI_IT.index(m.group(2))], m.group(1), m.group(3)), t)
    t = re.sub(r"(\d{1,2}) (%s)" % mesi, lambda m: "%s %s" % (MESI_EN[MESI_IT.index(m.group(2))], m.group(1)), t)
    t = re.sub(r"(20\d\d)-(\d\d)-(\d\d)", lambda m: "%s %d, %s" % (MESI_EN[int(m.group(2)) - 1], int(m.group(3)), m.group(1)), t)
    return t


def in_inglese(title, body):
    """Ritorna (titolo, corpo, sicuro). sicuro=False se qualche frase non è nota: la Issue lo segnala da controllare."""
    sicuro = True
    if title in TITOLI:
        t = TITOLI[title]
    else:
        m = re.match(r"Iscrizioni tra (\d+) minuti$", title)
        t = None
        if m:
            t = "Registration opens in %s minute%s" % (m.group(1), "" if m.group(1) == "1" else "s")
        for it, en in PREFISSI:
            if t is None and title.startswith(it):
                t = en + title[len(it):]
        if t is None:
            t, sicuro = title, False
    b = body or ""
    b = re.sub(r"\be altri (\d+)\b", r"and \1 more", b)
    b = re.sub(r"Apertura iscrizioni: (.+?) alle (\d\d:\d\d) \(ora italiana\)", r"Registration opens: \1 at \2 (Italian time)", b)
    b = re.sub(r"Si aprono alle (\d\d:\d\d) \(ora italiana\)", r"Opens at \1 (Italian time)", b)
    b = re.sub(r"Apertura prevista alle (\d\d:\d\d) \(ora italiana\)", r"Expected opening: \1 (Italian time)", b)
    b = re.sub(r"^Vincitore a ", "Winner at ", b, flags=re.M)
    b = re.sub(r"^(\d+)° posto a ", lambda m: "%s place at " % _ord(int(m.group(1))), b, flags=re.M)
    b = b.replace(" - iscrizioni fino al ", " · registration until ").replace("data sul link", "date on the link")
    b = _it_to_en(b)
    if re.search(r"\b(iscrizioni|iscritti|aperte|chiusura|vincitore|posto|torneo)\b", t + " " + b, re.I):
        sicuro = False
    return t, b, sicuro


def _ord(n):
    return "%d%s" % (n, "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))



def link_x(testo):
    return "https://x.com/intent/post?text=" + urllib.parse.quote(testo, safe="")


def _gh(metodo, percorso, dati=None):
    req = urllib.request.Request("https://api.github.com/repos/%s%s" % (_repo(), percorso),
                                 data=json.dumps(dati).encode("utf-8") if dati is not None else None, method=metodo,
                                 headers={"Authorization": "Bearer " + _token(), "Accept": "application/vnd.github+json",
                                          "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8") or "{}")


def _prepara():
    """Una volta per esecuzione: crea l'etichetta e chiude le proposte vecchie."""
    if _pronto["v"]:
        return
    _pronto["v"] = True
    try:
        _gh("POST", "/labels", {"name": ETICHETTA, "color": "1d9bf0", "description": "Avviso pronto da pubblicare su X"})
    except Exception:
        pass  # esiste già
    try:
        limite = datetime.now(timezone.utc) - timedelta(hours=ORE_MAX)
        for it in _gh("GET", "/issues?labels=%s&state=open&per_page=100" % ETICHETTA):
            if "pull_request" in it:
                continue
            if datetime.strptime(it["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) < limite:
                _gh("PATCH", "/issues/%d" % it["number"], {"state": "closed", "state_reason": "not_planned"})
    except Exception as ex:
        print("Pulizia proposte X saltata:", ex)


def proponi(topic, title, body, click):
    """Crea la Issue. Non solleva mai errori: non deve mai bloccare le notifiche vere."""
    solo = [x.strip() for x in os.environ.get("X_CATEGORIE", "").split(",") if x.strip()]   # facoltativo: es. regionali,winner,vrwin
    if not attivo() or (solo and topic not in solo):
        return False
    try:
        _prepara()
        chiave = (body or "", click or "")
        if chiave in _visti:
            return False   # stesso torneo già proposto in questo giro (es. money e money33)
        _visti.add(chiave)
        sicuro = True
        lingua = "it" if os.environ.get("X_LINGUA", "en") == "it" else "en"
        if lingua == "en":
            title, body, sicuro = in_inglese(title, body)
            if topic in SOLO_ITALIANI:
                sicuro = False
        post = testo_post(topic, title, body, click, lingua)
        corpo = ("## [🐦 Pubblica su X](%s)\n\n"
                 "Tocca il titolo qui sopra: X si apre con il post già scritto, premi **Pubblica**.\n"
                 "Non ti interessa? Ignora questa Issue (si chiude da sola dopo 2 giorni e 8 ore).\n\n"
                 "**Anteprima del post** (%d caratteri):\n\n```\n%s\n```\n\n"
                 "Categoria: `%s`%s%s") % (link_x(post), len(post) - (len(click) - LINK_LEN if (click or "").startswith("http") else 0),
                                         post, topic, ("\nPagina: " + click) if (click or "").startswith("http") else "",
                                         "" if sicuro else "\n\n⚠️ **Controlla la traduzione**: c'è una frase che non conosco, modificala prima di pubblicare.")
        _gh("POST", "/issues", {"title": "🐦 " + title[:120], "body": corpo, "labels": [ETICHETTA]})
        return True
    except Exception as ex:
        print("Proposta X non creata:", ex)
        return False


if __name__ == "__main__":
    os.environ["X_PROVA"] = "1"
    ok = proponi("regionali", "Prova rAKings VGC", "Se tocchi il link, X si apre con questo testo.", "https://example.com/")
    print("OK: Issue creata, controlla la scheda Issues." if ok else "ERRORE: Issue non creata (controlla permissions: issues: write e GITHUB_TOKEN).")
    sys.exit(0 if ok else 1)
