#!/usr/bin/env python3
"""YouTube Shorts di rAKings VGC: dalle stesse immagini dei post (money tournament, VR, Regionali, Top 8 dei locali,
storie dei vincitori) crea un video verticale 1080x1920 e, quando lo approvi nella scheda YouTube della pagina admin,
lo carica sul canale del sito con l'API ufficiale di YouTube.

Segreti su GitHub (Settings > Secrets and variables > Actions):
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN   (vedi GUIDA_YOUTUBE.txt)
Finche' Google non approva il progetto (audit), YouTube rende PRIVATI i video caricati dall'API: e' normale.
Solo libreria standard + Pillow + ffmpeg."""
import json, os, shutil, subprocess, tempfile, time, urllib.error, urllib.parse, urllib.request

W, H, FPS = 1080, 1920, 30
SITO = "https://rakings.github.io/VGCrAKings/"
APERTE = ("da approvare", "errore")
TAGS = ["Pokemon VGC", "Pokemon Champions", "VGC", "Pokemon", "Victory Road", "Pokemon tournament", "rAKings VGC"]


def titolo_da(r):
    """Titolo inglese dalla prima riga della didascalia di Instagram (gia' in inglese), con #Shorts."""
    t = ((r.get("ig") or {}).get("testo") or r.get("titolo") or "rAKings VGC").strip().split("\n")[0].strip()
    t = t[:88].rstrip(" ·-:") + " #Shorts"
    return t[:100]


def descrizione_da(r):
    t = ((r.get("ig") or {}).get("testo") or "").replace("link in bio", "link below").strip()
    t += "\n\n📲 rAKings VGC app: " + SITO
    t += "\nrAKings VGC is a fan-made community project, not affiliated with Nintendo, The Pokémon Company or Game Freak."
    return t[:4900]


def aggiungi(d):
    """Ogni richiesta ancora aperta su Instagram riceve anche la sua voce YouTube (una volta sola)."""
    n = 0
    for r in d.get("richieste", []):
        if "yt" in r:
            continue
        ig = r.get("ig") or {}
        if ig.get("stato") in APERTE:
            r["yt"] = {"stato": "da approvare", "testo": titolo_da(r)}
            n += 1
    d.setdefault("yt_dal", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    return n


# ---------------------------------------------------------------- video
def _fotogramma(src, dst):
    """Immagine del post al centro, sopra la stessa immagine sfocata a tutto schermo (niente bande nere)."""
    from PIL import Image, ImageFilter, ImageEnhance
    im = Image.open(src).convert("RGB")
    s = max(W / im.width, H / im.height)
    bg = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(40))).enhance(0.45)
    if abs(im.width / im.height - W / H) < 0.02:      # storia gia' verticale: a tutto schermo
        fg = im.resize((W, H), Image.LANCZOS)
        bg.paste(fg, (0, 0))
    else:
        fw = W - 60
        fg = im.resize((fw, int(im.height * fw / im.width)), Image.LANCZOS)
        if fg.height > H - 200:
            fh = H - 200
            fg = im.resize((int(im.width * fh / im.height), fh), Image.LANCZOS)
        bg.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
    bg.save(dst, quality=95)


def crea_video(immagini, out):
    """Short: 4 secondi per immagine (6 se e' una sola), leggero zoom e dissolvenza tra le immagini, al massimo 60 secondi."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg non trovato")
    immagini = [x for x in immagini if os.path.exists(x)][:14]
    if not immagini:
        raise RuntimeError("immagini del post non trovate")
    tmp = tempfile.mkdtemp()
    dur = 6.0 if len(immagini) == 1 else 4.0
    fd = 0.5
    ins, fil = [], []
    for i, src in enumerate(immagini):
        f = os.path.join(tmp, "f%02d.jpg" % i)
        _fotogramma(src, f)
        ins += ["-loop", "1", "-t", "%.2f" % dur, "-i", f]
        n = int(dur * FPS)
        fil.append("[%d:v]scale=%d:%d,zoompan=z='1+0.04*on/%d':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=%d:s=%dx%d:fps=%d,setsar=1,format=yuv420p[v%d]"
                   % (i, W * 2, H * 2, n, n, W, H, FPS, i))
    if len(immagini) == 1:
        last = "v0"
    else:
        last, t = "v0", dur - fd
        for i in range(1, len(immagini)):
            fil.append("[%s][v%d]xfade=transition=fade:duration=%.2f:offset=%.2f[x%d]" % (last, i, fd, t, i))
            last, t = "x%d" % i, t + dur - fd
    totale = len(immagini) * dur - (len(immagini) - 1) * fd
    cmd = ["ffmpeg", "-y", "-loglevel", "error"] + ins + [
        "-f", "lavfi", "-t", "%.2f" % totale, "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-filter_complex", ";".join(fil), "-map", "[%s]" % last, "-map", "%d:a" % len(immagini), "-t", "%.2f" % totale,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return out


# ---------------------------------------------------------------- API di YouTube (chiavi mai scritte nei log)
def _token():
    q = urllib.parse.urlencode({"client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
                                "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=q), timeout=30) as r:
            return json.load(r)["access_token"]
    except urllib.error.HTTPError as e:
        try:
            m = json.load(e).get("error_description") or "accesso rifiutato"
        except ValueError:
            m = "errore %s" % e.code
        raise RuntimeError("Google non da' l'accesso al canale (%s): rifai il collegamento (GUIDA_YOUTUBE.txt)" % m)


def carica(video, titolo, descrizione):
    tok = _token()
    meta = {"snippet": {"title": titolo, "description": descrizione, "tags": TAGS, "categoryId": "20"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    try:
        return _invia(video, meta, tok)
    except ValueError:
        # YouTube ha rifiutato un campo facoltativo: riprova con i soli dati essenziali
        minimo = {"snippet": {"title": titolo, "description": descrizione, "categoryId": "20"},
                  "status": {"privacyStatus": "public"}}
        try:
            return _invia(video, minimo, tok)
        except ValueError as e:
            raise RuntimeError(str(e))


def _invia(video, meta, tok):
    size = os.path.getsize(video)
    req = urllib.request.Request("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                                 data=json.dumps(meta).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json; charset=UTF-8",
                                          "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            dove = r.headers["Location"]
        with open(video, "rb") as f:
            put = urllib.request.Request(dove, data=f.read(), method="PUT",
                                         headers={"Authorization": "Bearer " + tok, "Content-Type": "video/mp4"})
        with urllib.request.urlopen(put, timeout=600) as r:
            j = json.load(r)
    except urllib.error.HTTPError as e:
        try:
            err = json.load(e).get("error", {})
        except ValueError:
            err = {}
        dett = "; ".join(x.get("reason", "") for x in err.get("errors", []) if x.get("reason"))
        msg = "YouTube: %s%s" % (err.get("message") or e.code, " (%s)" % dett if dett else "")
        if e.code == 400:
            raise ValueError(msg)
        raise RuntimeError(msg)
    vid = j.get("id")
    if not vid:
        raise RuntimeError("YouTube non ha confermato il caricamento")
    stato = (j.get("status") or {}).get("privacyStatus", "")
    return "https://youtube.com/shorts/" + vid, stato


def pubblica(r, titolo):
    """Crea lo Short dalle immagini della richiesta e lo carica. Ritorna (link, nota)."""
    for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        if not os.environ.get(k):
            raise RuntimeError("YouTube non e' ancora collegato (mancano i segreti YT_... su GitHub)")
    imgs = r.get("imgs") or [r["img"]]
    out = os.path.join(tempfile.mkdtemp(), "short.mp4")
    crea_video(imgs, out)
    link, stato = carica(out, (titolo or titolo_da(r))[:100], descrizione_da(r))
    nota = "" if stato == "public" else "caricato come %s: normale finche' Google non approva il progetto (audit)" % (stato or "privato")
    return link, nota


if __name__ == "__main__":
    # prova locale: python3 youtube.py prova img1.jpg img2.jpg  -> crea prova_short.mp4 senza caricarlo
    import sys
    if sys.argv[1:2] == ["prova"]:
        print(crea_video(sys.argv[2:], "prova_short.mp4"))
