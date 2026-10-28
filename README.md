# Kit Les Classiques en numérique

Une sélection de grands textes de la littérature française du XVe au XXe siècle,
libres de droits, et une webapp pour les copier en quelques clics sur les liseuses
du réseau (Kobo, Cybook…).

**Webapp :** https://bibliogironde.github.io/Kit-Les-Classiques-En-Numerique/

## Remplir une liseuse (mode d'emploi express)

1. Ouvrir la webapp avec **Chrome** ou **Edge** sur un ordinateur.
2. Brancher la liseuse (Kobo : toucher « Connecter » sur l'écran).
3. Cliquer sur « J'ai branché la liseuse », choisir la liseuse dans la fenêtre, autoriser la modification.
4. Cocher les livres, cliquer sur « Copier ».
5. Éjecter la liseuse, débrancher.

La webapp reconnaît la liseuse et envoie le bon format :

| Liseuse | Détection | Format copié |
|---|---|---|
| Kobo | dossier système `.kobo` | KEPUB (format natif Kobo, plus fluide) |
| Cybook | nom du disque, dossiers Bookeen | EPUB |
| Autre / non reconnue | choix manuel | EPUB |

Les livres sont copiés dans un dossier `Classiques libres` sur la liseuse. Ceux qui
y sont déjà sont signalés et ne sont pas recopiés.

Également publiés :

- `liseuse.html` : version très légère à ouvrir dans le navigateur d'une liseuse
  (téléchargement à l'unité, sans ordinateur) ;
- `opds.xml` : catalogue OPDS pour KOReader et les applis de lecture ;
- `packs/` : un ZIP par siècle et un ZIP complet.

## Organisation du dépôt

```
catalogue.csv          la liste des titres (à modifier pour ajouter un livre)
epub/15 … epub/20      les fichiers EPUB, rangés par siècle
app/index.html         la webapp
scripts/telecharger.py téléchargement en lot depuis Wikisource
scripts/construire.py  génère le site : webapp, catalogue.json, KEPUB, OPDS, ZIP
SOURCES.md             provenance et licence de chaque titre (généré)
```

## Ajouter ou mettre à jour des livres

Il faut Python 3.8 ou plus récent, sans bibliothèque à installer.

```bash
python3 scripts/telecharger.py --verifier   # contrôle les titres Wikisource, sans rien télécharger
python3 scripts/telecharger.py              # télécharge tous les EPUB manquants
python3 scripts/telecharger.py --siecle 19  # un seul siècle
```

Pour chaque titre signalé « à vérifier », ouvrez la page sur https://fr.wikisource.org,
copiez son titre exact dans la colonne `wikisource` de `catalogue.csv` (ou mettez un
lien direct vers un EPUB dans la colonne `url`), puis relancez avec `--forcer --siecle XX`.

Il suffit ensuite de pousser sur `main` : l'action GitHub convertit les livres au
format Kobo (avec [kepubify](https://github.com/pgaskin/kepubify)), reconstruit et
publie la webapp.

Tester en local :

```bash
python3 scripts/construire.py
cd site && python3 -m http.server 8000   # puis ouvrir http://localhost:8000 dans Chrome
```

(La conversion KEPUB n'a lieu en local que si `kepubify` est installé.)

## Droits

- Les œuvres sont dans le domaine public en France (auteurs morts depuis plus de 70 ans).
- Les EPUB issus de Wikisource sont sous licence CC BY-SA 4.0 : la source est indiquée
  dans `SOURCES.md` et dans chaque fichier.
- GitHub étant hébergé aux États-Unis, le catalogue se limite aux œuvres publiées
  avant 1931, libres aussi là-bas.
- Ne pas ajouter de traduction ou de version modernisée récente : elle serait protégée.

## Activer GitHub Pages (une seule fois)

Dans le dépôt : *Settings → Pages → Build and deployment → Source : GitHub Actions*.
