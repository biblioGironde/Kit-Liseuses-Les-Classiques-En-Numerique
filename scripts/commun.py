"""Fonctions partagées par les scripts du Kit Les Classiques en numérique."""
import csv
import re
import unicodedata
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CATALOGUE = RACINE / "catalogue.csv"
DOSSIER_EPUB = RACINE / "epub"
COLONNES = ["siecle", "auteur", "titre", "annee", "wikisource", "url", "statut"]

SIECLES = {
    "15": "XVe siècle — fin du Moyen Âge",
    "16": "XVIe siècle — Renaissance",
    "17": "XVIIe siècle — classicisme",
    "18": "XVIIIe siècle — Lumières",
    "19": "XIXe siècle",
    "20": "XXe siècle",
}


def sans_accents(texte):
    """Supprime accents et caractères spéciaux (noms de fichiers sûrs pour les vieilles liseuses)."""
    texte = texte.replace("œ", "oe").replace("Œ", "Oe").replace("æ", "ae")
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    texte = re.sub(r"[’'`]", " ", texte)
    texte = re.sub(r"[^A-Za-z0-9 \-]", "", texte)
    return re.sub(r"\s+", " ", texte).strip()


def nom_fichier(ligne):
    """« Voltaire - Candide.epub »"""
    return f"{sans_accents(ligne['auteur'])} - {sans_accents(ligne['titre'])}.epub"


def chemin_epub(ligne):
    return DOSSIER_EPUB / ligne["siecle"] / nom_fichier(ligne)


def lire_catalogue():
    with open(CATALOGUE, newline="", encoding="utf-8") as f:
        lignes = list(csv.DictReader(f))
    for l in lignes:
        for c in COLONNES:
            l.setdefault(c, "")
            l[c] = (l[c] or "").strip()
    return lignes


def ecrire_catalogue(lignes):
    with open(CATALOGUE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES, extrasaction="ignore")
        w.writeheader()
        w.writerows(lignes)
