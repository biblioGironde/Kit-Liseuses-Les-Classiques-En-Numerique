#!/usr/bin/env python3
"""
Téléchargement en lot des EPUB du catalogue.

Source par défaut : Wikisource (licence CC BY-SA), via le service d'export
officiel WS Export. Pour un titre, on peut aussi donner une URL directe
d'EPUB dans la colonne « url » du catalogue (Bibliothèque numérique romande…).

Utilisation :
    python3 scripts/telecharger.py              # télécharge tout ce qui manque
    python3 scripts/telecharger.py --siecle 19  # un seul siècle
    python3 scripts/telecharger.py --verifier   # vérifie les pages sans télécharger
    python3 scripts/telecharger.py --forcer     # retélécharge même si le fichier existe

Aucune dépendance : Python 3.8+ suffit.
"""
import argparse
import json
import sys
import time
import zipfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from commun import chemin_epub, ecrire_catalogue, lire_catalogue

API = "https://fr.wikisource.org/w/api.php"
WSEXPORT = "https://ws-export.wmcloud.org/"
UA = "Kit-Les-Classiques-En-Numerique/1.0 (biblio.gironde ; https://github.com/biblioGironde/Kit-Les-Classiques-En-Numerique)"
TAILLE_MIN = 15_000   # en dessous : probablement une page d'homonymie ou un sommaire vide
PAUSE = 3             # secondes entre deux téléchargements, par politesse


def requete(url, timeout=180):
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=timeout) as r:
        return r.read()


def api(**params):
    params.update(format="json", formatversion="2")
    return json.loads(requete(API + "?" + urlencode(params), timeout=60))


def resoudre(ligne):
    """Trouve la page Wikisource. Renvoie (titre_de_page, statut)."""
    titre_ws = ligne["wikisource"]
    if titre_ws:
        d = api(action="query", titles=titre_ws, redirects=1, prop="pageprops")
        page = d["query"]["pages"][0]
        if not page.get("missing"):
            if "disambiguation" in page.get("pageprops", {}):
                return page["title"], "homonymie : choisir une édition"
            return page["title"], "ok"
    # Repli : recherche plein texte « titre auteur »
    d = api(action="query", list="search", srnamespace=0, srlimit=3,
            srsearch=f'intitle:"{ligne["titre"]}" {ligne["auteur"]}')
    res = d["query"]["search"]
    if res:
        return res[0]["title"], "trouvé par recherche : à vérifier"
    return None, "introuvable sur Wikisource"


def epub_valide(donnees):
    """Vérifie qu'on a bien reçu un EPUB (archive ZIP avec le bon mimetype)."""
    import io
    try:
        with zipfile.ZipFile(io.BytesIO(donnees)) as z:
            return z.read("mimetype").strip() == b"application/epub+zip"
    except Exception:
        return False


def telecharger(ligne, page, fmt):
    if ligne["url"]:
        url = ligne["url"]
    else:
        url = WSEXPORT + "?" + urlencode({"lang": "fr", "page": page, "format": fmt})
    for essai in range(3):
        try:
            return requete(url)
        except (HTTPError, URLError, TimeoutError) as e:
            if essai == 2:
                raise
            print(f"      nouvelle tentative ({e})")
            time.sleep(10)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--siecle", help="ne traiter qu'un siècle (15 à 20)")
    p.add_argument("--verifier", action="store_true", help="vérifier les pages sans télécharger")
    p.add_argument("--forcer", action="store_true", help="retélécharger les fichiers existants")
    p.add_argument("--format", default="epub-3", help="format WS Export (epub-3 par défaut, epub-2 pour les très vieilles liseuses)")
    args = p.parse_args()

    lignes = lire_catalogue()
    a_traiter = [l for l in lignes if not args.siecle or l["siecle"] == args.siecle]
    bilan = {"ok": 0, "deja": 0, "probleme": []}

    for i, l in enumerate(a_traiter, 1):
        cible = chemin_epub(l)
        print(f"[{i}/{len(a_traiter)}] {l['auteur']} — {l['titre']}")
        if cible.exists() and not args.forcer and not args.verifier:
            print("      déjà présent")
            bilan["deja"] += 1
            continue
        try:
            page, statut = (None, "url directe") if l["url"] else resoudre(l)
        except Exception as e:
            page, statut = None, f"erreur réseau : {e}"
        if page:
            print(f"      page Wikisource : {page}  ({statut})")
            l["wikisource"] = page
        l["statut"] = statut
        if page is None and not l["url"]:
            print(f"      ✗ {statut}")
            bilan["probleme"].append((l, statut))
            continue
        if args.verifier:
            if statut != "ok":
                bilan["probleme"].append((l, statut))
            continue
        try:
            donnees = telecharger(l, page, args.format)
        except Exception as e:
            l["statut"] = f"échec du téléchargement : {e}"
            print(f"      ✗ {l['statut']}")
            bilan["probleme"].append((l, l["statut"]))
            continue
        if not epub_valide(donnees):
            l["statut"] = "fichier reçu invalide"
            print("      ✗ le fichier reçu n'est pas un EPUB")
            bilan["probleme"].append((l, l["statut"]))
            continue
        if len(donnees) < TAILLE_MIN:
            l["statut"] = "EPUB très petit : vérifier la page (sommaire ou homonymie ?)"
            bilan["probleme"].append((l, l["statut"]))
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(donnees)
        print(f"      ✓ {cible.name} ({len(donnees) // 1024} Ko)")
        if l["statut"] in ("ok", "url directe"):
            bilan["ok"] += 1
        elif len(donnees) >= TAILLE_MIN:
            bilan["probleme"].append((l, "téléchargé, " + l["statut"]))
        time.sleep(PAUSE)

    ecrire_catalogue(lignes)

    print("\n=== Bilan ===")
    print(f"Téléchargés : {bilan['ok']}   Déjà présents : {bilan['deja']}   À vérifier : {len(bilan['probleme'])}")
    for l, statut in bilan["probleme"]:
        print(f"  • {l['auteur']} — {l['titre']} : {statut}")
    if bilan["probleme"]:
        print("\nCorrigez la colonne « wikisource » (titre exact de la page) ou « url » dans catalogue.csv,")
        print("puis relancez avec --forcer --siecle XX.")
    return 1 if bilan["probleme"] else 0


if __name__ == "__main__":
    sys.exit(main())
