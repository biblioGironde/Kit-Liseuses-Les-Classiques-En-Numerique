#!/usr/bin/env python3
"""
Téléchargement en lot des EPUB du catalogue.

Ordre de priorité des sources, pour chaque titre :
  1. un lien direct déjà connu (colonne « url » de catalogue.csv) ;
  2. la Bibliothèque numérique romande (ebooks-bnr.com) : EPUB soignés et relus ;
  3. Wikisource, via le service d'export officiel WS Export.

Quand la BNR publie une œuvre en plusieurs tomes (Les Misérables…), chaque tome
devient une ligne du catalogue et un fichier séparé.

Utilisation :
    python3 scripts/telecharger.py               # télécharge tout ce qui manque
    python3 scripts/telecharger.py --siecle 19   # un seul siècle
    python3 scripts/telecharger.py --verifier    # cherche les sources sans rien télécharger
    python3 scripts/telecharger.py --forcer      # retélécharge même si le fichier existe
    python3 scripts/telecharger.py --source wikisource   # ignorer la BNR

Aucune dépendance : Python 3.8+ suffit.
"""
import argparse
import html
import io
import json
import re
import sys
import time
import zipfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from commun import chemin_epub, ecrire_catalogue, lire_catalogue, sans_accents

BNR = "https://ebooks-bnr.com/"
API_WS = "https://fr.wikisource.org/w/api.php"
WSEXPORT = "https://ws-export.wmcloud.org/"
UA = "Kit-Les-Classiques-En-Numerique/1.0 (biblio.gironde ; https://github.com/biblioGironde/Kit-Les-Classiques-En-Numerique)"
TAILLE_MIN = 15_000   # en dessous : probablement une page d'homonymie ou un sommaire vide
PAUSE = 3             # secondes entre deux téléchargements, par politesse envers les sites


def requete(url, timeout=180):
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=timeout) as r:
        return r.read()


def norm(texte):
    return re.sub(r"[^a-z0-9]+", " ", sans_accents(texte).lower()).strip()


def sans_article(texte):
    """« le tartuffe » → « tartuffe », « l avare » → « avare »."""
    return re.sub(r"^(le|la|les|l|un|une) ", "", texte)


def nom_auteur(auteur):
    """Dernier mot du nom : « Victor Hugo » → « hugo »."""
    return norm(auteur).split(" ")[-1]


# ---------------------------------------------------------------- BNR
# Deux façons de trouver un livre sur la BNR :
#  1. l'index alphabétique des titres (ebooks-bnr.com/par/titres/), le plus fiable ;
#  2. la recherche du site, qui trouve aussi les œuvres publiées en plusieurs tomes.

RE_EPUB = r'https://ebooks-bnr\.com/\?fdsb_dl=ebooks/[a-z0-9]+/[^"]+?\.epub'
PAGES_HORS_LIVRES = ("par", "nuage", "nos-ebooks", "informations", "contact", "categories",
                     "recherche", "coups-de-coeur", "donation", "politique", "wp-")
SUITES_ADMISES = ("ou ", "et ", "a la recherche")  # « Candide ou l'Optimisme », « Zadig et autres contes »
_index_bnr = None


def cle_titre(titre):
    """Clé de comparaison : sans tome, sans article (même placé à la fin : « Avare (L') »)."""
    t = re.sub(r"\(\s*tome[^)]*\)", " ", titre, flags=re.I)
    t = re.sub(r"\(\s*(le|la|les|l[’']|un|une)\s*\)", " ", t, flags=re.I)
    t = t.split(" – ")[0]  # « Du Côté de chez Swann – À la recherche du temps perdu 1 »
    return sans_article(norm(t))


def titre_correspond(cible, candidat):
    if candidat == cible:
        return True
    return candidat.startswith(cible + " ") and candidat[len(cible) + 1:].startswith(SUITES_ADMISES)


def tome_de(titre):
    m = re.search(r"tome\s*(\d+)", titre, re.I)
    return int(m.group(1)) if m else 0


def bnr_index():
    """Index des titres de la BNR : liste de (titre, page). Chargé une seule fois."""
    global _index_bnr
    if _index_bnr is None:
        page = requete(BNR + "par/titres/", timeout=120).decode("utf-8", "replace")
        page = page.split("<article", 1)[-1]
        _index_bnr = []
        for url, slug, texte in re.findall(r'<a href="(https://ebooks-bnr\.com/([a-z0-9-]+)/)"[^>]*>(.*?)</a>', page, re.S):
            if not slug.startswith(PAGES_HORS_LIVRES):
                _index_bnr.append((html.unescape(re.sub(r"<[^>]+>", "", texte)).strip(), url))
        print(f"      (index BNR : {len(_index_bnr)} titres)")
    return _index_bnr


def bnr_epub_de_page(url):
    page = requete(url, timeout=60).decode("utf-8", "replace")
    m = re.search(RE_EPUB, page.split("<article", 1)[-1])
    return html.unescape(m.group(0)) if m else None


def bnr_chercher(requete_texte):
    """Résultats de la recherche BNR : liste de (titre affiché, page, lien EPUB)."""
    page = requete(BNR + "?" + urlencode({"s": requete_texte}), timeout=60).decode("utf-8", "replace")
    resultats = []
    for bloc in page.split("<article")[1:]:
        t = re.search(r'class="entry-title[^"]*"[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', bloc, re.S)
        e = re.search(RE_EPUB, bloc)
        if t and e:
            titre = html.unescape(re.sub(r"<[^>]+>", "", t.group(2))).strip()
            resultats.append((titre, t.group(1), html.unescape(e.group(0))))
    return resultats


def bnr_trouver(ligne):
    """Renvoie la liste des (tome, titre BNR, page, epub) correspondant au titre."""
    cible = sans_article(norm(ligne["titre"]))
    nom = nom_auteur(ligne["auteur"])
    anonyme = ligne["auteur"] == "Anonyme"

    # 1. Index des titres : l'auteur est vérifié dans l'adresse de la page (« balzac-honore-de-… »)
    trouves = []
    for titre, page in bnr_index():
        if titre_correspond(cible, cle_titre(titre)) and (anonyme or nom.replace(" ", "-") in page):
            epub = bnr_epub_de_page(page)
            if epub:
                trouves.append((tome_de(titre), titre, page, epub))
    if trouves:
        return sorted(set(trouves))

    # 2. Recherche du site (titres de la forme « Hugo Victor – Les Misérables (tome 1) »)
    mots = [m for m in norm(ligne["titre"]).split() if len(m) > 3]
    for q in [ligne["titre"]] + ([f"{nom} {mots[-1]}"] if mots else []):
        vus = set()
        for titre, page, epub in bnr_chercher(q):
            if " – " not in titre or epub in vus:
                continue
            auteur_bnr, titre_bnr = titre.split(" – ", 1)
            if (anonyme or nom in norm(auteur_bnr)) and titre_correspond(cible, cle_titre(titre_bnr)):
                vus.add(epub)
                trouves.append((tome_de(titre_bnr), titre, page, epub))
        if trouves:
            return sorted(trouves)
        time.sleep(1)
    return []


# ---------------------------------------------------------- Wikisource

def ws_api(**params):
    params.update(format="json", formatversion="2")
    return json.loads(requete(API_WS + "?" + urlencode(params), timeout=60))


def ws_trouver(ligne):
    """Renvoie (titre de page, statut)."""
    if ligne["wikisource"]:
        d = ws_api(action="query", titles=ligne["wikisource"], redirects=1, prop="pageprops")
        p = d["query"]["pages"][0]
        if not p.get("missing"):
            if "disambiguation" in p.get("pageprops", {}):
                return p["title"], "homonymie Wikisource : choisir une édition"
            return p["title"], "ok"
    d = ws_api(action="query", list="search", srnamespace=0, srlimit=3,
               srsearch=f'intitle:"{ligne["titre"]}" {ligne["auteur"]}')
    res = d["query"]["search"]
    if res:
        return res[0]["title"], "trouvé par recherche Wikisource : à vérifier"
    return None, "introuvable"


def ws_url(page, fmt):
    return WSEXPORT + "?" + urlencode({"lang": "fr", "page": page, "format": fmt})


# ------------------------------------------------------------ Commun

def epub_valide(donnees):
    try:
        with zipfile.ZipFile(io.BytesIO(donnees)) as z:
            return z.read("mimetype").strip() == b"application/epub+zip"
    except Exception:
        return False


def telecharger(url):
    for essai in range(3):
        try:
            return requete(url)
        except (HTTPError, URLError, TimeoutError) as e:
            if essai == 2:
                raise
            print(f"      nouvelle tentative ({e})")
            time.sleep(10)


def resoudre(ligne, args):
    """Complète source/page/url de la ligne. Renvoie la liste des lignes (plusieurs si tomes)."""
    if ligne["url"]:
        ligne["statut"] = ligne["statut"] or "lien direct"
        return [ligne]
    if args.source in ("auto", "bnr"):
        try:
            trouves = bnr_trouver(ligne)
        except Exception as e:
            trouves = []
            print(f"      BNR injoignable ({e})")
        if trouves:
            if len(trouves) == 1:
                _, titre, page, epub = trouves[0]
                ligne.update(source="bnr", page=page, url=epub, statut="ok")
                print(f"      BNR : {titre}")
                return [ligne]
            print(f"      BNR : {len(trouves)} tomes")
            tomes = []
            for tome, titre, page, epub in trouves:
                l = dict(ligne)
                l.update(titre=f"{ligne['titre']} (tome {tome})" if tome else ligne["titre"],
                         source="bnr", page=page, url=epub, statut="ok")
                tomes.append(l)
                print(f"        • {titre}")
            return tomes
        if args.source == "bnr":
            ligne["statut"] = "absent de la BNR"
            return [ligne]
    page, statut = ws_trouver(ligne)
    if page:
        ligne.update(source="wikisource", wikisource=page, statut=statut,
                     page="https://fr.wikisource.org/wiki/" + quote(page.replace(" ", "_")),
                     url=ws_url(page, args.format))
        print(f"      Wikisource : {page}" + ("" if statut == "ok" else f"  ({statut})"))
    else:
        ligne["statut"] = "introuvable (BNR et Wikisource)"
    return [ligne]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--siecle", help="ne traiter qu'un siècle (15 à 20)")
    p.add_argument("--verifier", action="store_true", help="chercher les sources sans télécharger")
    p.add_argument("--forcer", action="store_true", help="retélécharger les fichiers existants")
    p.add_argument("--source", choices=["auto", "bnr", "wikisource"], default="auto",
                   help="auto (BNR puis Wikisource, par défaut), bnr seule, ou wikisource seule")
    p.add_argument("--format", default="epub-3", help="format WS Export (epub-3, ou epub-2 pour les très vieilles liseuses)")
    args = p.parse_args()

    catalogue = lire_catalogue()
    nouveau, problemes, traitees = [], [], []
    compte = {"ok": 0, "deja": 0}
    a_traiter = [l for l in catalogue if not args.siecle or l["siecle"] == args.siecle]

    for i, l in enumerate(catalogue):
        if l not in a_traiter:
            nouveau.append(l)
            continue
        n = a_traiter.index(l) + 1
        print(f"[{n}/{len(a_traiter)}] {l['auteur']} — {l['titre']}")
        if chemin_epub(l).exists() and not args.forcer and not args.verifier:
            print("      déjà présent")
            compte["deja"] += 1
            nouveau.append(l)
            continue
        if args.forcer and l["source"] == "wikisource":
            l["url"] = ""  # on retente la BNR en priorité
        try:
            lignes = resoudre(l, args)
        except Exception as e:
            l["statut"] = f"erreur réseau : {e}"
            lignes = [l]
        nouveau.extend(lignes)
        traitees.extend(lignes)

        for x in lignes:
            if not x["url"]:
                problemes.append((x, x["statut"]))
                print(f"      ✗ {x['statut']}")
                continue
            if x["statut"] not in ("ok", "lien direct"):
                problemes.append((x, x["statut"]))
            if args.verifier:
                continue
            cible = chemin_epub(x)
            if cible.exists() and not args.forcer:
                compte["deja"] += 1
                continue
            try:
                donnees = telecharger(x["url"])
            except Exception as e:
                x["statut"] = f"échec du téléchargement : {e}"
                problemes.append((x, x["statut"]))
                print(f"      ✗ {x['statut']}")
                continue
            if not epub_valide(donnees):
                x["statut"] = "fichier reçu invalide"
                problemes.append((x, x["statut"]))
                print("      ✗ le fichier reçu n'est pas un EPUB")
                continue
            if len(donnees) < TAILLE_MIN:
                x["statut"] = "EPUB très petit : vérifier la source (sommaire ou homonymie ?)"
                problemes.append((x, x["statut"]))
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_bytes(donnees)
            compte["ok"] += 1
            print(f"      ✓ {cible.name} ({len(donnees) // 1024} Ko, {x['source']})")
            time.sleep(PAUSE)

    ecrire_catalogue(nouveau)

    sources = {}
    for x in traitees:
        cle = x["source"] or "aucune"
        sources[cle] = sources.get(cle, 0) + 1
    print("\n=== Bilan ===")
    print(f"Téléchargés : {compte['ok']}   Déjà présents : {compte['deja']}   À vérifier : {len(problemes)}")
    print("Sources : " + ", ".join(f"{k} {v}" for k, v in sorted(sources.items())))
    for x, statut in problemes:
        print(f"  • {x['auteur']} — {x['titre']} : {statut}")
    if problemes:
        print("\nPour corriger : mettez dans catalogue.csv le lien direct de l'EPUB (colonne « url »)")
        print("ou le titre exact de la page Wikisource (colonne « wikisource »), puis relancez")
        print("avec --forcer --siecle XX.")
    return 1 if problemes else 0


if __name__ == "__main__":
    sys.exit(main())
