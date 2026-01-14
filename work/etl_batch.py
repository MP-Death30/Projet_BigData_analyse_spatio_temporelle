import os
import glob
import json
import requests
import pandas as pd
import geopandas as gpd
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, DoubleType
import warnings

# On ignore les warnings Pandas pour la propreté des logs
warnings.filterwarnings('ignore')

# ==============================================================================
# 1. CONFIGURATION & SPARK SESSION
# ==============================================================================
print("🚀 Démarrage du Script ETL Batch...")

# Définition des Chemins
LOCAL_DATA_DIR = "/home/jovyan/work/data"
NOAA_DIR = os.path.join(LOCAL_DATA_DIR, "noaa_gsod", "2022")
AIR_FILE = os.path.join(LOCAL_DATA_DIR, "air_quality", "nyc_air_quality_raw.json")

# URLs (au cas où les fichiers locaux manquent)
URL_AIR_NYC = "https://data.cityofnewyork.us/resource/c3uy-2p5r.json?$limit=50000"

# Initialisation Spark (Optimisée)
spark = SparkSession.builder \
    .appName("ETL_Batch_NYC_Weather") \
    .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
    .config("spark.executor.memory", "2g") \
    .getOrCreate()

print("✅ Session Spark initialisée.")

# ==============================================================================
# 2. TRAITEMENT MÉTÉO (NOAA)
# ==============================================================================
def process_weather():
    print("\n🌤️  Traitement des données Météo (NOAA 2022)...")
    
    # Récupération des fichiers CSV locaux
    all_files = glob.glob(os.path.join(NOAA_DIR, "*.csv"))
    
    if not all_files:
        print("⚠️  Aucun fichier CSV trouvé dans work/data/noaa_gsod/2022/")
        print("   -> Assurez-vous d'avoir téléchargé les données ou lancez le script de scraping.")
        return pd.DataFrame()

    print(f"   -> {len(all_files)} stations trouvées localement.")
    
    # Lecture et Concatenation avec Pandas
    dfs = []
    for filename in all_files:
        try:
            # On lit en forçant tout en string pour éviter les erreurs de typage initiales
            df = pd.read_csv(filename, dtype=str)
            dfs.append(df)
        except Exception as e:
            print(f"   [Erreur lecture] {os.path.basename(filename)}: {e}")

    if not dfs:
        return pd.DataFrame()

    df_weather = pd.concat(dfs, ignore_index=True)
    
    # Nettoyage Rapide
    # On garde les colonnes utiles
    cols_to_keep = ['STATION', 'DATE', 'LATITUDE', 'LONGITUDE', 'NAME', 'TEMP', 'DEWP', 'WDSP']
    # On filtre celles qui existent vraiment
    cols_exist = [c for c in cols_to_keep if c in df_weather.columns]
    df_weather = df_weather[cols_exist]

    # Standardisation
    df_weather['ID_STATION'] = df_weather['STATION']
    
    # Note : Les conversions (Fahrenheit->Celsius) sont faites dans app.py à la lecture.
    # Ici on stocke la donnée brute consolidée.
    
    print(f"✅ Météo consolidée : {len(df_weather)} enregistrements.")
    return df_weather

# ==============================================================================
# 3. TRAITEMENT QUALITÉ DE L'AIR (NYC)
# ==============================================================================
def process_air_quality():
    print("\nmask️  Traitement Qualité de l'Air (NYC OpenData)...")
    
    # Vérification fichier local, sinon téléchargement
    if not os.path.exists(AIR_FILE):
        print("   -> Fichier local absent. Téléchargement...")
        os.makedirs(os.path.dirname(AIR_FILE), exist_ok=True)
        try:
            r = requests.get(URL_AIR_NYC, timeout=30)
            with open(AIR_FILE, 'wb') as f:
                f.write(r.content)
        except Exception as e:
            print(f"❌ Erreur téléchargement Air Quality : {e}")
            return pd.DataFrame()

    # Lecture
    try:
        df_air = pd.read_json(AIR_FILE)
    except ValueError:
        print("❌ Erreur lecture JSON Air Quality.")
        return pd.DataFrame()
        
    # Nettoyage simple
    # Renommage pour cohérence
    mapping = {
        'unique_id': 'GEOJOIN_ID',
        'indicator_id': 'INDICATOR_ID',
        'name': 'NOM_POLLUANT',
        'measure': 'MESURE',
        'measure_info': 'UNITÉ',
        'geo_type_name': 'TYPE_ZONE',
        'geo_join_id': 'GEOCODE',
        'geo_place_name': 'GEONAME',
        'time_period': 'PERIODE',
        'start_date': 'DATE_OBSERVATION',
        'data_value': 'VALEUR'
    }
    df_air = df_air.rename(columns=mapping)
    
    # On ne garde que les colonnes renommées qui existent
    cols_final = [c for c in mapping.values() if c in df_air.columns]
    df_air = df_air[cols_final]
    
    print(f"✅ Qualité Air traitée : {len(df_air)} enregistrements.")
    return df_air

# ==============================================================================
# 4. EXPORT VERS HDFS (DATALAKE)
# ==============================================================================
def save_to_hdfs(pandas_df, hdfs_filename):
    if pandas_df.empty:
        print(f"⚠️  Skipping {hdfs_filename} (DataFrame vide)")
        return

    full_path = f"/user/mathis/datalake/processed/dashboard/{hdfs_filename}"
    
    try:
        # Conversion Pandas -> Spark
        # Astuce : Convertir en string les objets pour éviter les erreurs de schéma Spark
        df_clean = pandas_df.copy()
        if isinstance(df_clean.index, pd.DatetimeIndex):
            df_clean = df_clean.reset_index()
            
        for col in df_clean.select_dtypes(include=['object']).columns:
            df_clean[col] = df_clean[col].astype(str)

        spark_df = spark.createDataFrame(df_clean)
        
        # Écriture Parquet
        spark_df.write.mode("overwrite").parquet(full_path)
        print(f"💾 Sauvegardé sur HDFS : {full_path}")
        
    except Exception as e:
        print(f"❌ Erreur écriture HDFS pour {hdfs_filename} : {e}")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    
    # 1. Pipeline Météo
    df_w = process_weather()
    save_to_hdfs(df_w, "weather.parquet")
    
    # 2. Pipeline Air
    df_a = process_air_quality()
    save_to_hdfs(df_a, "air_quality.parquet")
    
    print("\n🎉 ETL Batch terminé avec succès.")
    spark.stop()