# Projet d'examen — Data Collection

Application Streamlit permettant de scraper (Selenium), stocker (SQLite),
visualiser et évaluer des données issues de deux sources :

- **Books to Scrape** (https://books.toscrape.com)
- **Gaaraas** — annonces auto Dakar (https://www.gaaraas.com)

## Structure du projet

Application **single-page** : toute la navigation se fait via la sidebar
("User Input Features" → nombre de pages, menu déroulant "Options", et choix
de la source de données), sans dossier `pages/` multipage.

```
.
├── app.py                     # Appli Streamlit complète (sidebar + routage interne)
├── scrapers/
│   ├── driver_factory.py      # Création du driver Selenium (local + cloud)
│   ├── books_scraper.py       # Scraper Selenium — Books to Scrape
│   └── gaaraas_scraper.py     # Scraper Selenium — Gaaraas
├── database/
│   └── db.py                  # Init / lecture / écriture SQLite
├── data/
│   ├── raw/                   # Exports CSV bruts (extension Web Scraper)
│   └── clean/                 # (optionnel) exports CSV nettoyés locaux
├── requirements.txt
└── packages.txt                # paquets apt pour Streamlit Cloud (chromium)
```

## Installation locale

```bash
python -m venv venv
source venv/bin/activate      # Windows : venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Selenium 4.24+ télécharge automatiquement le bon chromedriver en local
(Selenium Manager) — aucune installation manuelle de driver n'est requise,
à condition d'avoir Google Chrome (ou Chromium) installé sur la machine.

## Déploiement sur Streamlit Community Cloud

1. Poussez ce dossier sur un repo GitHub.
2. Sur https://share.streamlit.io, créez une nouvelle app pointant vers `app.py`.
3. Le fichier `packages.txt` (chromium + chromium-driver) est installé
   automatiquement par Streamlit Cloud : le scraping Selenium fonctionnera
   directement dans l'appli déployée.
4. Le scraping de 100 pages peut être lent sur l'infrastructure gratuite :
   pensez à limiter le nombre de pages pendant les démonstrations, ou à
   scraper une fois puis à conserver les données dans `data/app.db`
   (committé dans le repo) pour que le dashboard fonctionne sans re-scraper.

## Scraping no-code (Web Scraper)

1. Installer l'extension Chrome **Web Scraper**.
2. Créer un sitemap pour chaque source (Books to Scrape / Gaaraas) avec
   pagination, puis lancer le scraping (données volontairement **non nettoyées**).
3. Exporter les résultats en CSV.
4. Déposer ces CSV dans l'application, page **Scraping → onglet "Scraping
   no-code Web Scraper"** : ils seront stockés dans `data/raw/` et
   téléchargeables depuis l'app.

## ⚠️ À vérifier avant la remise

- **Gaaraas** : le site n'expose pas de classes CSS stables documentées ici.
  Le scraper `gaaraas_scraper.py` extrait le texte visible de chaque carte
  d'annonce puis le parse par expressions régulières (marque, modèle, année,
  prix, kilométrage, boîte, région). **Inspectez le site avec F12** avant la
  remise et ajustez les regex si la structure a changé.
- **Formulaires** : remplacez `KOBO_FORM_URL` et `GOOGLE_FORM_URL` en haut de
  `app.py` par vos liens réels une fois les formulaires créés à partir du
  document de spécification fourni séparément.
- **Base de données** : `data/app.db` (SQLite) est créée automatiquement au
  premier lancement, avec une table `books` et une table `cars`.

## Livrables attendus

- Lien de l'application déployée
- Lien du repo GitHub
- Vidéo de 10 min (8 min explication du code + 2 min démo)
