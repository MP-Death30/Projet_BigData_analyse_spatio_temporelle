# Projet Big Data : Analyse Spatio-Temporelle (NYC & RTE)

Ce projet propose une architecture hybride de traitement de données :
1.  **Batch Processing (NYC)** : Analyse historique de la qualité de l'air et de la météo à New York (Spark/Hadoop).
2.  **Speed Layer (RTE)** : Monitoring quasi-temps réel du mix électrique français et des échanges transfrontaliers (Pandas/Streamlit).

## Architecture & Fonctionnalités

### 1. Module NYC (Air Quality & Weather)
Pipeline ETL distribué utilisant **PySpark** sur Docker.
* **Sources** : NOAA GSOD (Météo) & Socrata (Air Quality NYC).
* **Traitements** : Nettoyage, jointures spatiales (lat/lon), agrégations temporelles.
* **Sortie** : Fichiers Parquet optimisés pour le dashboard.

### 2. Module RTE (Mix Électrique France)
Pipeline léger et incrémental pour le suivi énergétique.
* **Source** : API RTE éCO2mix (Zip/CSV).
* **Logique** :
    * Récupération incrémentale des données (Datalake Parquet local).
    * Détection automatique des structures de fichiers (TSV/CSV).
    * Visualisation des flux d'énergie (Production par filière, Solde Import/Export).
* **Nouveauté** : Carte interactive des échanges commerciaux avec les pays frontaliers (Flèches Import/Export).

## Structure du dépôt

* `work/`
    * `Projet_BigData_analyse_spatio_temporelle.ipynb` : Orchestrateur principal (ETL Spark).
    * `app.py` : Application **Streamlit** (Dashboard unique pour les deux modules).
    * `rte_layer.py` : Script de gestion des données RTE (Téléchargement, Nettoyage, Stockage).
    * `dashboard_*.parquet/geojson` : Données traitées prêtes à l'emploi.
* `docker/` : Configuration des conteneurs (Spark Master, Worker, Jupyter).
* `docker-compose.yml` : Définition de la stack complète.

## Installation & Démarrage

### Pré-requis
* Docker & Docker Compose installés.

### Lancement Rapide
1.  **Construire et lancer la stack** :
    ```bash
    sh build-images.sh
    docker-compose up -d
    ```

2.  **Générer les données (Si première utilisation)** :
    * Accédez au notebook via `http://localhost:8888` (token dans les logs).
    * Exécutez le notebook pour générer les fichiers Parquet de NYC.
    * *Note : Le module RTE se mettra à jour automatiquement depuis l'interface Streamlit.*

3.  **Lancer le Dashboard** :
    ```bash
    # Accès au conteneur
    docker exec -it pyspark_notebook bash
    
    # Dans le conteneur :
    cd work
    streamlit run app.py
    ```
    * Accédez ensuite à `http://localhost:8501`.

## Guide d'Utilisation du Dashboard

* **Navigation** : Utilisez la barre latérale pour basculer entre "NYC Air Quality" et "RTE Production".
* **Module RTE** :
    * Cliquez sur le bouton **"Forcer Mise à jour"** pour télécharger les dernières données temps réel.
    * Visualisez la carte des échanges : Les flèches **Vertes** indiquent un Import (France acheteuse), les flèches **Rouges/Bleues** un Export (France vendeuse).

## Maintenance
* **RTE Layer** : Le script `rte_layer.py` gère les changements de format de l'API RTE. En cas de colonne manquante, vérifiez le mapping dans ce fichier.
* **Spark** : Ajustez la mémoire dans `docker-compose.yml` si le traitement NYC échoue (OOM).