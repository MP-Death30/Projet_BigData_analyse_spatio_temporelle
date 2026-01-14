# Bibliothèques standard
import os
import glob
import json
import time
from math import radians, cos, sin, asin, sqrt

# Bibliothèques tierces
import requests
import pandas as pd
import geopandas as gpd
from IPython.display import display

# PySpark
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.functions import to_date, col, lit, substring, regexp_replace
from pyspark.sql.types import StructType, StructField, StringType, DoubleType
from pyspark.sql.window import Window


# --- 1. Configuration et Initialisation de Spark ---
# Augmentation des timeouts et allocation de mémoire stricte pour éviter les crashs JVM
spark = SparkSession.builder \
    .appName("DataLake_NOAA_NYC_Prep") \
    .config("spark.executor.memory", "3g") \
    .config("spark.driver.memory", "2g") \
    .config("spark.network.timeout", "800s") \
    .config("spark.rpc.askTimeout", "800s") \
    .getOrCreate()

# --- 2. Définition des Paramètres Géographiques et HDFS ---
# Boîte englobante de la région de NYC afin de restreindre l'import des données NOAA
MIN_LAT, MAX_LAT = 40.0, 41.5
MIN_LON, MAX_LON = -75.0, -73.0

# Chemin HDFS BRUT
RAW_OUTPUT_PATH = "hdfs://namenode:9000/user/mathis/datalake/noaa_gsod_nyc_raw_2005_2023.parquet"

# Plage d'années pour le test
START_YEAR = 2022 #2005
END_YEAR = 2022 #2023

print("✅ Session Spark configurée et initialisée.")



# --- 1. Téléchargement des Métadonnées des Stations ---
stations_url = "https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv"
pdf_stations = pd.read_csv(stations_url,
                         dtype={'USAF': str, 'WBAN': str})

pdf_stations['STN_ID'] = pdf_stations['USAF'].str.strip() + pdf_stations['WBAN'].str.strip()
pdf_stations = pdf_stations.rename(columns={'LAT': 'LATITUDE', 'LON': 'LONGITUDE'})
pdf_stations = pdf_stations.dropna(subset=['LATITUDE', 'LONGITUDE', 'STATION NAME'])
spark_stations_df = spark.createDataFrame(pdf_stations)

# --- 2. Filtrage Géographique ---
nyc_stations_spark = spark_stations_df.filter(
    (F.col('LATITUDE') >= MIN_LAT) & (F.col('LATITUDE') <= MAX_LAT) &
    (F.col('LONGITUDE') >= MIN_LON) & (F.col('LONGITUDE') <= MAX_LON)
)

# Récupération de la liste des IDs pertinents (pour filtrage par nom de fichier)
relevant_station_ids = [row.STN_ID for row in nyc_stations_spark.select("STN_ID").collect()]

print(f"\n✅ {nyc_stations_spark.count()} Stations NOAA pertinentes trouvées près de New York.")
# Gardons ce DataFrame pour la jointure des coordonnées plus tard



BASE_URL = "https://www.ncei.noaa.gov/data/global-summary-of-the-day/access"
LOCAL_BASE_DIR = "/home/jovyan/work/data/noaa_gsod"
START_YEAR = 2005
END_YEAR = 2023

# --- IDs des stations à télécharger ---
if 'relevant_station_ids' not in locals():
    print("⚠️ ATTENTION: La liste 'relevant_station_ids' n'est pas définie. Veuillez exécuter la Phase 2 en premier.")
    exit()

# Démarrage du processus
print(f"Démarrage du téléchargement pour {len(relevant_station_ids)} stations de {START_YEAR} à {END_YEAR}.")

downloaded_count = 0

# --- Boucle principale (sans barre de progression) ---
for year in range(START_YEAR, END_YEAR + 1):
    year_dir = os.path.join(LOCAL_BASE_DIR, str(year))
    
    # Petit print pour savoir où on en est (optionnel, mais utile sans barre de progression)
    print(f"Traitement de l'année : {year}...")

    # Crée le répertoire de l'année s'il n'existe pas
    os.makedirs(year_dir, exist_ok=True)

    for station_id in relevant_station_ids:
        file_name = f"{station_id}.csv"
        local_path = os.path.join(year_dir, file_name)
        remote_url = f"{BASE_URL}/{year}/{file_name}"

        # Vérifie si le fichier existe déjà
        if os.path.exists(local_path):
            downloaded_count += 1
            continue

        try:
            # Requête HTTP GET
            response = requests.get(remote_url, timeout=10)
            response.raise_for_status()

            # Écrit le contenu dans le fichier local
            with open(local_path, 'wb') as f:
                f.write(response.content)

            downloaded_count += 1
            
            # Pause pour être poli avec le serveur NOAA
            time.sleep(0.05) 

        except requests.exceptions.HTTPError as errh:
            # Fichier 404/Not Found
            if response.status_code == 404:
                pass 
            else:
                print(f"\n❌ Erreur HTTP pour {remote_url}: {errh}")
        except requests.exceptions.RequestException as e:
            print(f"\n❌ Erreur de Connexion/Timeout pour {remote_url}: {e}")

print(f"\n✅ Téléchargement terminé. {downloaded_count} fichiers GSOD traités (téléchargés ou existants).")





# --- Configuration des Chemins ---
LOCAL_BASE_DIR = "/home/jovyan/work/data/noaa_gsod" 
RAW_OUTPUT_PATH = "hdfs://namenode:9000/user/mathis/datalake/noaa_gsod_nyc_raw_2005_2023.parquet"
START_YEAR = 2005
END_YEAR = 2023

# --- 1. Définition des Chemins Ciblés ---
# Nous recréons la liste, mais cette fois en utilisant 'glob' ou une vérification OS
# pour ne pas inclure les chemins qui n'existent pas.

existing_targeted_paths = []
for year in range(START_YEAR, END_YEAR + 1):
    for station_id in relevant_station_ids:
        # Chemin absolu corrigé : /home/jovyan/work/data/noaa_gsod/2005/XXXXX.csv
        path = f"{LOCAL_BASE_DIR}/{year}/{station_id}.csv"
        
        # Vérifie si le fichier existe vraiment avant de l'ajouter à la liste de lecture de Spark
        if os.path.exists(path):
            existing_targeted_paths.append(path)

# Si aucun chemin n'existe, nous aurons une erreur, mais au moins nous savons pourquoi.
if not existing_targeted_paths:
    raise FileNotFoundError("Aucun fichier GSOD cible n'a été trouvé dans le répertoire local.")

gsod_data_paths = existing_targeted_paths
print(f"Total de {len(gsod_data_paths)} fichiers existants seront lus par Spark.")

# --- 2. Schéma et Lecture ---
gsod_schema = StructType([
    StructField("STATION", StringType(), True),
    StructField("DATE", StringType(), True),
    StructField("LATITUDE", DoubleType(), True), 
    StructField("LONGITUDE", DoubleType(), True),
    StructField("ELEVATION", DoubleType(), True),
    StructField("NAME", StringType(), True),
    StructField("TEMP", DoubleType(), True),
    StructField("TEMP_ATTRIBUTES", StringType(), True),
    StructField("DEWP", DoubleType(), True),
    StructField("DEWP_ATTRIBUTES", StringType(), True),
    StructField("SLP", DoubleType(), True),
    StructField("SLP_ATTRIBUTES", StringType(), True),
    StructField("STP", DoubleType(), True),
    StructField("STP_ATTRIBUTES", StringType(), True),
    StructField("VISIB", DoubleType(), True),
    StructField("VISIB_ATTRIBUTES", StringType(), True),
    StructField("WDSP", DoubleType(), True),
    StructField("WDSP_ATTRIBUTES", StringType(), True),
    StructField("MXSPD", DoubleType(), True),
    StructField("GUST", DoubleType(), True),
    StructField("MAX", DoubleType(), True),
    StructField("MAX_ATTRIBUTES", StringType(), True),
    StructField("MIN", DoubleType(), True),
    StructField("MIN_ATTRIBUTES", StringType(), True),
    StructField("PRCP", DoubleType(), True),
    StructField("PRCP_ATTRIBUTES", StringType(), True),
    StructField("SNDP", DoubleType(), True),
    StructField("FRSHHT", StringType(), True),
])

# Lecture distribuée des données GSOD (seulement les fichiers ciblés)
all_gsod_data = spark.read.csv(
    gsod_data_paths,
    header=True,
    schema=gsod_schema,
    sep=','
)

# Renommage de la colonne ID
nyc_gsod_data = all_gsod_data.withColumnRenamed("STATION", "ID_STATION")


# --- 3. Persistance de la Couche Brute sur HDFS ---
print(f"\nSauvegarde de la copie BRUTE filtrée (2005-2023) dans : {RAW_OUTPUT_PATH}...")
# Cette étape transfère les données du disque local du conteneur vers HDFS
nyc_gsod_data.write.mode("overwrite").parquet(RAW_OUTPUT_PATH)
print("✅ Copie brute sauvegardée sur HDFS. Le traitement peut se poursuivre.")






# --- Configuration des Chemins ---
LOCAL_BASE_DIR = "/home/jovyan/work/data/air_quality"
LOCAL_JSON_PATH = os.path.join(LOCAL_BASE_DIR, "nyc_air_quality_raw.json")
AIR_QUALITY_URL = "https://data.cityofnewyork.us/api/views/c3uy-2p5r/rows.json?accessType=DOWNLOAD"

# Crée le répertoire local si nécessaire
os.makedirs(LOCAL_BASE_DIR, exist_ok=True)

# --- 1. Téléchargement et Nettoyage de la structure JSON Socrata ---
print(f"⬇️ Téléchargement du JSON Socrata depuis l'API de NYC...")
try:
    response = requests.get(AIR_QUALITY_URL, timeout=300) # Timeout de 5 minutes
    response.raise_for_status()
    data = response.json()
    
    # La clé 'data' contient le tableau des enregistrements bruts que Spark doit lire.
    raw_records = data.get('data', [])

    if not raw_records:
        print("❌ Erreur : La clé 'data' est vide dans le JSON téléchargé. Arrêt du processus.")
        exit()
    
    # Écriture du tableau de données brutes SEULEMENT dans le nouveau fichier JSON.
    # Ceci est essentiel pour que le RDD/toDF fonctionne correctement.
    with open(LOCAL_JSON_PATH, 'w') as f:
        json.dump(raw_records, f)

    print(f"✅ Fichier JSON brut sauvegardé et nettoyé structurellement à : {LOCAL_JSON_PATH}")
    
except Exception as e:
    print(f"❌ Erreur lors du téléchargement/nettoyage : {e}")
    exit()





# ==============================================================================
# 💾 SAUVEGARDE FINALE DANS HDFS (Datalake)
# ==============================================================================
from pyspark.sql import SparkSession
import os

# 1. Configuration de la session Spark pour HDFS
spark = SparkSession.builder \
    .appName("ETL_NYC_Weather_Air") \
    .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
    .getOrCreate()

print("🚀 Démarrage de l'écriture HDFS...")

# 2. Sauvegarde Météo (Weather)
# Assurez-vous que votre DataFrame final s'appelle 'df_final_weather'
if 'df_final_weather' in locals() and not df_final_weather.empty:
    # Conversion Pandas -> Spark
    # On reset l'index pour garder la date si elle est en index
    df_w_clean = df_final_weather.reset_index()
    # Conversion des types objets en string pour éviter les erreurs Spark
    for col in df_w_clean.select_dtypes(include=['object']).columns:
        df_w_clean[col] = df_w_clean[col].astype(str)
        
    sdf_weather = spark.createDataFrame(df_w_clean)
    
    # Écriture HDFS
    hdfs_path_weather = "/user/mathis/datalake/processed/dashboard/weather.parquet"
    sdf_weather.write.mode("overwrite").parquet(hdfs_path_weather)
    print(f"✅ Météo sauvegardée : {hdfs_path_weather}")
else:
    print("⚠️ Attention : df_final_weather introuvable ou vide.")

# 3. Sauvegarde Qualité de l'Air
# Assurez-vous que votre DataFrame final s'appelle 'df_final_air'
if 'df_final_air' in locals() and not df_final_air.empty:
    # Conversion Pandas -> Spark
    df_a_clean = df_final_air.reset_index()
    for col in df_a_clean.select_dtypes(include=['object']).columns:
        df_a_clean[col] = df_a_clean[col].astype(str)

    sdf_air = spark.createDataFrame(df_a_clean)
    
    # Écriture HDFS
    hdfs_path_air = "/user/mathis/datalake/processed/dashboard/air_quality.parquet"
    sdf_air.write.mode("overwrite").parquet(hdfs_path_air)
    print(f"✅ Qualité Air sauvegardée : {hdfs_path_air}")
else:
    print("⚠️ Attention : df_final_air introuvable ou vide.")

print("🎉 ETL terminé.")






































