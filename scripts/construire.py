#!/usr/bin/env python3
"""
Construit le site à publier sur GitHub Pages, dans le dossier « site/ » :
  - index.html : la webapp « Remplir une liseuse » (copiée depuis app/) ;
  - catalogue.json : la liste des livres pour la webapp ;
  - liseuse.html et une page par siècle, très légères (pour le navigateur
    des liseuses : pas de JavaScript, gros caractères) ;
  - kepub/ : versions KEPUB pour les Kobo (si l'outil kepubify est installé) ;
  - opds.xml : catalogue OPDS pour KOReader et les applis de lecture ;
  - packs/ : un ZIP par siècle + un ZIP complet, pour la copie par câble USB ;
  - epub/ : les livres eux-mêmes.
Met aussi à jour SOURCES.md à la racine du dépôt.

Utilisation : python3 scripts/construire.py
"""
import html
import json
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from urllib.parse import quote

from commun import RACINE, SIECLES, chemin_epub, lire_catalogue, nom_fichier

SITE = RACINE / "site"
TITRE = "Classiques libres"
SOUS_TITRE = "Grands textes de la littérature française, libres de droits — biblio.gironde"

STYLE = """<style>
body{font-family:Georgia,serif;font-size:1.3em;line-height:1.5;max-width:40em;margin:0 auto;padding:0 12px;color:#000;background:#fff}
h1{font-size:1.6em;margin:.6em 0 .2em}h2{font-size:1.3em;border-bottom:2px solid #000;margin-top:1.2em}
a{color:#000}li{margin:.7em 0}ul{padding-left:1.1em}
.livre a{font-weight:bold}.info{font-size:.8em;color:#333}.nav{margin:1em 0}
</style>"""


def taille(chemin):
    o = chemin.stat().st_size
    return f"{o / 1048576:.1f} Mo" if o >= 1048576 else f"{max(1, o // 1024)} Ko"


def page_html(titre, corps, retour=True):
    nav = '<p class="nav"><a href="liseuse.html">&lt; Retour au sommaire</a></p>' if retour else ""
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(titre)}</title>{STYLE}</head>
<body>{nav}<h1>{html.escape(titre)}</h1>
{corps}
{nav}</body></html>
"""


def lien_epub(l):
    return f"epub/{l['siecle']}/{quote(nom_fichier(l))}"


def construire_pages(par_siecle, packs):
    # Sommaire
    items = []
    for s, livres in par_siecle.items():
        items.append(f'<li><a href="{s}.html">{html.escape(SIECLES[s])}</a> '
                     f'<span class="info">({len(livres)} livres)</span></li>')
    items_packs = "".join(
        f'<li><a href="packs/{quote(n)}">{html.escape(n)}</a> <span class="info">{t}</span></li>'
        for n, t in packs)
    corps = f"""<p>{html.escape(SOUS_TITRE)}</p>
<h2>Choisir un siècle</h2><ul>{''.join(items)}</ul>
<p class="info">Touchez le titre d'un livre pour le télécharger directement sur la liseuse.</p>
<h2>Packs pour copie par câble</h2>
<p class="info">À télécharger sur un ordinateur, à décompresser, puis à copier sur la liseuse.</p>
<ul>{items_packs}</ul>
<h2>Catalogue OPDS</h2>
<p class="info">Pour KOReader et les applis de lecture : <a href="opds.xml">opds.xml</a></p>
<p class="info">Textes issus de Wikisource (licence CC BY-SA) et d'autres sources libres — voir le fichier SOURCES du dépôt.</p>"""
    (SITE / "liseuse.html").write_text(page_html(TITRE, corps, retour=False), encoding="utf-8")

    # Une page par siècle
    for s, livres in par_siecle.items():
        lis = "".join(
            f'<li class="livre"><a href="{lien_epub(l)}">{html.escape(l["titre"])}</a><br>'
            f'{html.escape(l["auteur"])} <span class="info">— {l["annee"]} — {taille(chemin_epub(l))}</span></li>'
            for l in livres)
        (SITE / f"{s}.html").write_text(page_html(SIECLES[s], f"<ul>{lis}</ul>"), encoding="utf-8")


def construire_packs(par_siecle):
    dossier = SITE / "packs"
    dossier.mkdir()
    packs = []

    def faire_zip(nom, livres, sous_dossiers):
        chemin = dossier / nom
        with zipfile.ZipFile(chemin, "w", zipfile.ZIP_STORED) as z:  # EPUB déjà compressés
            for l in livres:
                arc = f"Classiques libres/{SIECLES[l['siecle']].split(' —')[0]}/{nom_fichier(l)}" \
                    if sous_dossiers else f"Classiques libres/{nom_fichier(l)}"
                z.write(chemin_epub(l), arc)
        packs.append((nom, taille(chemin)))

    for s, livres in par_siecle.items():
        faire_zip(f"classiques-{s}e-siecle.zip", livres, False)
    tous = [l for livres in par_siecle.values() for l in livres]
    if tous:
        faire_zip("classiques-tous.zip", tous, True)
    return packs


def construire_opds(par_siecle):
    maj = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nav_type = "application/atom+xml;profile=opds-catalog;kind=navigation"
    acq_type = "application/atom+xml;profile=opds-catalog;kind=acquisition"

    def entete(id_, titre, kind):
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/terms/" xmlns:opds="http://opds-spec.org/2010/catalog">
<id>urn:classiques-libres:{id_}</id><title>{html.escape(titre)}</title><updated>{maj}</updated>
<author><name>biblio.gironde</name></author>
<link rel="self" href="{'opds.xml' if id_ == 'racine' else f'opds-{id_}.xml'}" type="{kind}"/>
<link rel="start" href="opds.xml" type="{nav_type}"/>
"""

    racine = entete("racine", TITRE, nav_type)
    for s, livres in par_siecle.items():
        racine += f"""<entry><title>{html.escape(SIECLES[s])}</title><id>urn:classiques-libres:{s}</id>
<updated>{maj}</updated><content type="text">{len(livres)} livres</content>
<link rel="subsection" href="opds-{s}.xml" type="{acq_type}"/></entry>
"""
        flux = entete(s, SIECLES[s], acq_type)
        for l in livres:
            flux += f"""<entry><title>{html.escape(l['titre'])}</title>
<id>urn:classiques-libres:{s}:{quote(nom_fichier(l))}</id><updated>{maj}</updated>
<author><name>{html.escape(l['auteur'])}</name></author><dc:language>fr</dc:language>
<dc:issued>{l['annee']}</dc:issued>
<link rel="http://opds-spec.org/acquisition/open-access" href="{lien_epub(l)}" type="application/epub+zip"/>
</entry>
"""
        (SITE / f"opds-{s}.xml").write_text(flux + "</feed>\n", encoding="utf-8")
    (SITE / "opds.xml").write_text(racine + "</feed>\n", encoding="utf-8")


def est_bnr(l):
    return l.get("source") == "bnr" or "ebooks-bnr.com" in l.get("url", "")


def ecrire_sources(par_siecle):
    lignes = ["# Sources et licences", "",
              "Toutes les œuvres sont dans le domaine public. Les fichiers EPUB proviennent de :", "",
              "- **[Bibliothèque numérique romande](https://ebooks-bnr.com)** (BNR) : éditions réalisées par des",
              "  bénévoles de l'association Les Bourlapapey. Elles peuvent être utilisées librement, **sans",
              "  modification**, en indiquant la source ; leur partie éditoriale (notes, présentation, maquette)",
              "  ne peut pas être utilisée à des fins commerciales sans leur accord. Ces fichiers sont donc",
              "  diffusés ici tels quels (pas de conversion KEPUB).",
              "- **[Wikisource](https://fr.wikisource.org)** : licence",
              "  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.fr)",
              "  (transcriptions et mise en forme des contributeurs de Wikisource).", "",
              "| Siècle | Auteur | Titre | Source |", "|---|---|---|---|"]
    for s, livres in par_siecle.items():
        for l in livres:
            page = l.get("page") or ""
            if est_bnr(l):
                src = f"[BNR]({page or l['url']})"
            elif l.get("source") == "wikisource" or (not l["url"] and l["wikisource"]):
                if not page:
                    page = "https://fr.wikisource.org/wiki/" + quote(l["wikisource"].replace(" ", "_"))
                src = f"[Wikisource]({page})"
            else:
                src = f"[lien]({page or l['url']})"
            lignes.append(f"| {s}e | {l['auteur']} | {l['titre']} | {src} |")
    (RACINE / "SOURCES.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")


def nom_kepub(l):
    return nom_fichier(l)[:-5] + ".kepub.epub"


def construire_kepub(par_siecle):
    """Convertit les EPUB en KEPUB (format natif Kobo) avec kepubify, s'il est installé."""
    outil = shutil.which("kepubify")
    if not outil:
        print("kepubify non trouvé : pas de versions KEPUB (les Kobo recevront l'EPUB standard).")
        return
    for s, livres in par_siecle.items():
        dest = SITE / "kepub" / s
        dest.mkdir(parents=True)
        for l in livres:
            if est_bnr(l):
                continue  # la BNR demande de diffuser ses fichiers sans modification
            r = subprocess.run([outil, "--output", str(dest), str(chemin_epub(l))],
                               capture_output=True, text=True)
            if r.returncode != 0 or not (dest / nom_kepub(l)).exists():
                print(f"  KEPUB impossible pour {nom_fichier(l)} : {r.stderr.strip()[:200]}")


def construire_json(par_siecle):
    livres = []
    for s, liste in par_siecle.items():
        for l in liste:
            k = SITE / "kepub" / s / nom_kepub(l)
            livres.append({
                "siecle": s, "auteur": l["auteur"], "titre": l["titre"], "annee": l["annee"],
                "fichier": nom_fichier(l), "epub": lien_epub(l),
                "taille": chemin_epub(l).stat().st_size,
                "fichierKepub": nom_kepub(l) if k.exists() else None,
                "kepub": f"kepub/{s}/{quote(nom_kepub(l))}" if k.exists() else None,
                "tailleKepub": k.stat().st_size if k.exists() else None,
            })
    donnees = {"siecles": {s: SIECLES[s] for s in par_siecle}, "livres": livres,
               "maj": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
    (SITE / "catalogue.json").write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()

    par_siecle = {}
    manquants = 0
    for l in lire_catalogue():
        if chemin_epub(l).exists():
            par_siecle.setdefault(l["siecle"], []).append(l)
        else:
            manquants += 1
    par_siecle = {s: sorted(v, key=lambda l: (l["annee"], l["auteur"]))
                  for s, v in sorted(par_siecle.items())}
    if not par_siecle:
        print("Aucun EPUB dans epub/ pour l'instant : la webapp sera publiée avec un catalogue vide.")

    for s, livres in par_siecle.items():
        (SITE / "epub" / s).mkdir(parents=True)
        for l in livres:
            shutil.copy2(chemin_epub(l), SITE / "epub" / s / nom_fichier(l))

    packs = construire_packs(par_siecle)
    construire_pages(par_siecle, packs)
    construire_opds(par_siecle)
    construire_kepub(par_siecle)
    construire_json(par_siecle)
    shutil.copy2(RACINE / "app" / "index.html", SITE / "index.html")
    ecrire_sources(par_siecle)
    (SITE / ".nojekyll").touch()

    total = sum(len(v) for v in par_siecle.values())
    print(f"Site construit dans site/ : {total} livres, {len(packs)} packs ZIP.")
    if manquants:
        print(f"{manquants} titres du catalogue n'ont pas encore d'EPUB (ignorés).")


if __name__ == "__main__":
    main()
