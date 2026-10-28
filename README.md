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
scripts/telecharger.py téléchargement en lot (BNR d'abord, puis Wikisource)
scripts/construire.py  génère le site : webapp, catalogue.json, KEPUB, OPDS, ZIP
SOURCES.md             provenance et licence de chaque titre (généré)
```

## Ajouter ou mettre à jour des livres

Il faut Python 3.8 ou plus récent, sans bibliothèque à installer.

Le script cherche chaque titre dans cet ordre :

1. **lien direct** déjà indiqué dans la colonne `url` de `catalogue.csv` ;
2. **[Bibliothèque numérique romande](https://ebooks-bnr.com)** (BNR), dont les EPUB sont relus
   et soignés. Quand la BNR publie une œuvre en plusieurs tomes (*Les Misérables*…), chaque
   tome devient une ligne du catalogue et un fichier séparé ;
3. **Wikisource**, en dernier recours.

```bash
python3 scripts/telecharger.py --verifier            # cherche les sources sans rien télécharger
python3 scripts/telecharger.py                       # télécharge tous les EPUB manquants
python3 scripts/telecharger.py --siecle 19           # un seul siècle
python3 scripts/telecharger.py --forcer              # retélécharge tout (et retente la BNR
                                                     #  pour les titres venus de Wikisource)
python3 scripts/telecharger.py --source wikisource   # sans la BNR
```

Le script remplit lui-même les colonnes `source`, `page` et `url` du catalogue et
affiche un bilan. Pour chaque titre signalé « à vérifier », mettez le lien direct de
l'EPUB dans la colonne `url` (sur la BNR : clic droit sur le bouton EPUB › copier
l'adresse du lien) ou le titre exact de la page Wikisource dans la colonne
`wikisource`, puis relancez avec `--forcer --siecle XX`.

Il suffit ensuite de pousser sur `main` : l'action GitHub convertit les livres au
format Kobo (avec [kepubify](https://github.com/pgaskin/kepubify)), reconstruit et
publie la webapp. Les livres de la BNR ne sont pas convertis : ses conditions
demandent de les diffuser sans modification, les Kobo reçoivent donc l'EPUB d'origine.

Tester en local :

```bash
python3 scripts/construire.py
cd site && python3 -m http.server 8000   # puis ouvrir http://localhost:8000 dans Chrome
```

(La conversion KEPUB n'a lieu en local que si `kepubify` est installé.)

## Sources de livres numériques libres

Pour compléter le catalogue ou trouver d'autres textes du domaine public :

* [Bibliothèque numérique romande](https://ebooks-bnr.com) propose des EPUB soignés et relus. C’est le meilleur choix pour les liseuses.
* [Ebooks libres et gratuits](https://www.ebooksgratuits.com) a un très gros catalogue classique, en EPUB, PDF et Mobi.
* [Wikisource](https://fr.wikisource.org) a des textes établis d’après les éditions originales et permet un export EPUB à la volée.
* [Gallica (BnF)](https://gallica.bnf.fr) donne accès aux éditions originales numérisées. C’est idéal pour la médiation, par exemple pour montrer la première édition de *Madame Bovary*.
* [Bibebook](https://www.bibebook.com) et [Project Gutenberg](https://www.gutenberg.org/browse/languages/fr) sont deux bons compléments.
* [Littérature audio](https://www.litteratureaudio.com) propose des versions lues gratuitement, utiles pour l’accessibilité.
* [Bibliothèque électronique du Québec](https://beq.ebooksgratuits.com) propose environ 2 800 volumes en EPUB, PDF (dont une version pour liseuses) et MOBI.
  ⚠️ Elle suit le droit canadien, où une œuvre devenait libre 50 ans après la mort de l'auteur (70 ans en France) :
  **vérifiez que l'auteur est mort avant 1956**. Aucune licence de redistribution n'est affichée : à utiliser
  pour la lecture, et à ne pas ajouter au dépôt sans l'accord du site.

Avant d'ajouter au dépôt un EPUB venant d'un autre site que Wikisource, vérifiez sa
licence : certains sites autorisent la redistribution seulement sans modification
ou sans usage commercial. Indiquez le lien direct dans la colonne `url` de
`catalogue.csv` pour que la source apparaisse dans `SOURCES.md`.

## Droits

- Les œuvres sont dans le domaine public en France (auteurs morts depuis plus de 70 ans).
- Les EPUB de la **BNR** peuvent être utilisés librement, **sans modification**, en indiquant
  la source ; leur partie éditoriale (notes, présentation, maquette) ne peut pas servir à
  des fins commerciales sans l'accord de l'association Les Bourlapapey. Ils sont diffusés
  tels quels, avec leur source dans `SOURCES.md`.
- Les EPUB issus de **Wikisource** sont sous licence CC BY-SA 4.0 : la source est indiquée
  dans `SOURCES.md` et dans chaque fichier.
- GitHub étant hébergé aux États-Unis, le catalogue se limite aux œuvres publiées
  avant 1931, libres aussi là-bas.
- Ne pas ajouter de traduction ou de version modernisée récente : elle serait protégée.

## Activer GitHub Pages (une seule fois)

Dans le dépôt : *Settings → Pages → Build and deployment → Source : GitHub Actions*.
