#!/usr/bin/env python3
"""Copia di sicurezza settimanale degli iscritti alle notifiche (archivio KV del Worker su Cloudflare).

Legge l'elenco completo dal Worker (stessa lettura a pagine che usano gli avvisi), lo comprime e lo CIFRA con la chiave
segreta BACKUP_CHIAVE (AES-256, solo Andrea la conosce). Il file cifrato va in una «Release» della repo (copia-iscritti),
sostituendo quella vecchia: niente storico che si accumula, la repo resta leggera. Senza la chiave il file e' illeggibile.

Per leggerlo (solo se servisse un ripristino), su un PC con openssl:
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in iscritti.enc -out iscritti.json.gz -pass env:BACKUP_CHIAVE
Il ripristino nel Worker si prepara solo se un giorno servira'."""
import gzip, json, os, subprocess, sys, time, urllib.parse, urllib.request

UA = "rakings-copia-iscritti"

def leggi_tutti():
    base = os.environ["SUBS_URL"].rstrip("/") + "/list"
    hdr = {"Authorization": "Bearer " + os.environ["SUBS_TOKEN"], "User-Agent": UA}
    subs, cursor, pagine = [], None, 0
    while True:
        q = [("kind", "all"), ("limit", "1000")]
        if cursor:
            q.append(("cursor", cursor))
        req = urllib.request.Request(base + "?" + urllib.parse.urlencode(q), headers=hdr)
        data = json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
        subs += data.get("subs") or []
        cursor = data.get("cursor")
        pagine += 1
        if not cursor:
            return subs, pagine
        if pagine >= 2000:
            raise RuntimeError("troppe pagine")
        time.sleep(0.2)

def main():
    chiave = os.environ.get("BACKUP_CHIAVE", "")
    if len(chiave) < 16:
        print("::warning::Copia degli iscritti NON fatta: manca il segreto BACKUP_CHIAVE (almeno 16 caratteri) su GitHub.")
        return 0
    subs, pagine = leggi_tutti()
    if not subs:
        print("::warning::Il Worker ha restituito 0 iscritti: la copia vecchia NON viene sostituita.")
        return 0
    dati = {"v": 1, "quando": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "n": len(subs), "subs": subs}
    with gzip.open("iscritti.json.gz", "wb") as f:
        f.write(json.dumps(dati, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    subprocess.run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-salt",
                    "-in", "iscritti.json.gz", "-out", "iscritti.enc", "-pass", "env:BACKUP_CHIAVE"], check=True)
    os.remove("iscritti.json.gz")
    with open("copia_info.txt", "w") as f:
        f.write("%s %d\n" % (dati["quando"], len(subs)))
    print("Copia degli iscritti: %d iscrizioni (%d pagine), file cifrato %d byte" % (len(subs), pagine, os.path.getsize("iscritti.enc")))
    return 0

if __name__ == "__main__":
    sys.exit(main())
