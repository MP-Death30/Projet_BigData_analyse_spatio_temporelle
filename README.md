Projet pédagogique d'analyse spatio-temporelle (NYC) utilisant PySpark, Docker et Streamlit.
 
## Description
Pipeline ETL Spark pour :
- Ingestion de données météo (NOAA GSOD) et qualité de l'air (Socrata).
- Nettoyage, enrichissement géographique (lat/lon), agrégations temporelles.
- Export en Parquet pour un dashboard Streamlit/folium.
 
## Structure du dépôt (principaux fichiers)
- work/Projet_BigData_analyse_spatio_temporelle.ipynb — Notebook principal qui orchestre l'ETL et génère l'application Streamlit.
- work/requirements.txt — Dépendances Python pour Jupyter / Streamlit.
- docker-compose.yml — Démarrage des services Spark (master/worker), notebook et services auxiliaires.
- build-images.sh — Script local de build des images Docker utilisées dans la stack.
- docker/ — Dockerfiles et scripts d'init (spark-master, spark-worker, pyspark_notebook, spark-submit).
- docker/spark-submit/ — Conteneur et script d'aide pour soumettre des jobs Spark depuis une image dédiée.
- app.py (généré par le notebook) — Dashboard Streamlit utilisant les Parquet produits.
 
## Comment exécuter (rapide)
1. Construire les images :
   docker-compose build
   ou
   sh build-images.sh
2. Démarrer la stack :
   docker-compose up -d
3. Soumettre le job Spark via le conteneur pyspark_notebook et exécuter les cellules du notebook dans le conteneur Jupyter.
4. Lancer le dashboard (si app.py généré) :
   1. ouvrer un terminale dans le container
   2. cd work
   3. streamlit run app.py
   
## Explication du code (ce qui est implémenté et où chercher)
- Notebook principal (work/Projet_BigData_analyse_spatio_temporelle.ipynb)
  - Étapes présentes : ingestion, nettoyage, transformation, jointures spatiales, agrégations temporelles, écriture en Parquet.
  - Utilise l'API PySpark DataFrame : lecture via spark.read (CSV / JSON), transformations avec select/withColumn/filter, agrégations avec groupBy/agg.
  - UDFs / fonctions utilitaires : conversion d'unités (°F → °C, mph → m/s), parsing de dates, calculs de distance basés sur lat/lon.
  - Optimisations : persist/cache des DataFrames lourds, repartition avant écriture, partitionnement par date/zone pour lecture efficace.
 
- Scripts de soumission (docker/spark-submit/)
  - Entrée pour spark-submit avec variables d'environnement (MASTER URL, path de l'application).
  - Exemple d'usage dans docker-compose pour exécuter des jobs batch vers le cluster Spark.
 
- Dockerfiles et scripts d'init (docker/)
  - Images contiennent Spark configuré (master/worker) et les dépendances Python pour exécuter le notebook et Streamlit.
  - Scripts start-master/start-worker configurent les paramètres réseau et options Spark.
 
- app.py (Streamlit)
  - Lecture des Parquet produits par l'ETL.
  - Visualisations : cartes (folium / pydeck), graphiques temporels (altair / matplotlib), filtres interactifs.
  - Utilise des caches (st.cache) pour éviter des relectures coûteuses.
 
## Points d'attention / conseils de maintenance
- Variables d'environnement Spark (mémoire, cores) sont configurable dans docker-compose et scripts d'init.
- Vérifier le partitionnement lors de l'écriture Parquet pour éviter trop de petits fichiers.
- Externaliser les secrets (API Socrata) hors du dépôt, utiliser des variables d'environnement.
- Tester les transformations critiques avec petits jeux de données et unit tests PyTest si nécessaire.
 
## Où regarder pour comprendre rapidement le code
1. work/Projet_BigData_analyse_spatio_temporelle.ipynb — lecture séquentielle des étapes ETL.
2. docker/spark-submit/ — comment le pipeline est lancé en production/containerisé.
3. app.py généré — comment sont consommés les résultats ETL pour le dashboard.
