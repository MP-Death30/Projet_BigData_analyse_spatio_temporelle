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
AIR_FILE = os.path.join(LOCAL_DATA_DIR, "air_quality", "nyc_air_quality_raw.json")

# URLs (au cas où les fichiers locaux manquent)
URL_AIR_NYC = "https://data.cityofnewyork.us/resource/c3uy-2p5r.json?$limit=50000"

# Initialisation Spark (Optimisée pour HDFS)
spark = SparkSession.builder \
    .appName("ETL_Batch_NYC_Weather") \
    .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
    .config("spark.executor.memory", "2g") \
    .getOrCreate()

print("✅ Session Spark initialisée.")

# ==============================================================================
# 0. SAUVEGARDE DES DONNÉES BRUTES (RAW)
# ==============================================================================
def upload_raw_folder_to_hdfs(local_dir, hdfs_target_dir):
    """
    Copie le dossier local complet vers HDFS (Zone Raw)
    """
    print(f"\n📦 Vérification et Upload des données brutes : {local_dir} -> {hdfs_target_dir}")
    
    if not os.path.exists(local_dir):
        print(f"⚠️  Le dossier local source {local_dir} n'existe pas. Upload ignoré.")
        return

    # Accès au système de fichiers Hadoop via la JVM Spark
    try:
        sc = spark.sparkContext
        jvm = sc._gateway.jvm
        conf = sc._jsc.hadoopConfiguration()
        fs = jvm.org.apache.hadoop.fs.FileSystem.get(conf)
        Path = jvm.org.apache.hadoop.fs.Path
        
        src_path = Path(local_dir)
        dst_path = Path(hdfs_target_dir)
        
        # Copie (overwrite=True pour s'assurer que les données sont à jour)
        fs.copyFromLocalFile(False, True, src_path, dst_path)
        print("✅ Dossier 'data' (Raw) synchronisé dans HDFS.")
        
    except Exception as e:
        print(f"❌ Erreur lors de l'upload Raw : {e}")

# ==============================================================================
# 2. TRAITEMENT MÉTÉO (NOAA)
# ==============================================================================
def process_weather(years):
    print(f"\n🌤️  Traitement des données Météo (NOAA) pour {len(years)} années...")
    
    dfs = []
    
    for year in years:
        # Construction dynamique du chemin pour l'année
        year_dir = os.path.join(LOCAL_DATA_DIR, "noaa_gsod", str(year))
        
        # --- VERIFICATION CRITIQUE ---
        if not os.path.exists(year_dir):
            # Message informatif simple, pas d'erreur
            print(f"⚠️  Année {year} non trouvée (Dossier absent).")
            continue
        # -----------------------------

        # Récupération des fichiers CSV locaux
        files = glob.glob(os.path.join(year_dir, "*.csv"))
        
        if not files:
            print(f"⚠️  Dossier vide pour l'année {year}.")
            continue

        print(f"   -> Année {year} : {len(files)} stations trouvées.")
        
        # Lecture
        for filename in files:
            try:
                # Lecture en String pour éviter les erreurs de schéma initiales
                df = pd.read_csv(filename, dtype=str)
                dfs.append(df)
            except Exception as e:
                print(f"   [Erreur lecture] {os.path.basename(filename)}: {e}")

    if not dfs:
        print("⚠️  Aucune donnée météo valide n'a été chargée sur toute la période.")
        return pd.DataFrame()

    print("⏳ Concatenation des données météo...")
    df_weather = pd.concat(dfs, ignore_index=True)
    
    # Nettoyage Rapide : Sélection des colonnes
    cols_to_keep = ['STATION', 'DATE', 'LATITUDE', 'LONGITUDE', 'NAME', 'TEMP', 'DEWP', 'WDSP']
    cols_exist = [c for c in cols_to_keep if c in df_weather.columns]
    df_weather = df_weather[cols_exist]

    # Standardisation ID
    if 'STATION' in df_weather.columns:
        df_weather['ID_STATION'] = df_weather['STATION']
    
    print(f"✅ Météo consolidée (2005-2023) : {len(df_weather)} enregistrements.")
    return df_weather

# ==============================================================================
# 3. TRAITEMENT QUALITÉ DE L'AIR (NYC)
# ==============================================================================
def process_air_quality():
    print("\n💨 Traitement Qualité de l'Air (NYC OpenData)...")
    
    # Vérification fichier local, sinon téléchargement
    if not os.path.exists(AIR_FILE):
        print("   -> Fichier local absent. Téléchargement...")
        try:
            os.makedirs(os.path.dirname(AIR_FILE), exist_ok=True)
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
        print("❌ Erreur lecture JSON Air Quality (Format invalide).")
        return pd.DataFrame()
        
    # Nettoyage & Mapping (Gestion du format List of Lists)
    mapping = {
        8: 'GEOJOIN_ID',
        9: 'INDICATOR_ID',
        10: 'NOM_POLLUANT',
        11: 'MESURE',
        12: 'UNITÉ',
        13: 'TYPE_ZONE',
        14: 'GEOCODE',
        15: 'GEONAME',
        16: 'PERIODE',
        17: 'DATE_OBSERVATION',
        18: 'VALEUR'
    }
    
    # Renommage
    df_air = df_air.rename(columns=mapping)
    
    # Sélection (Unicité des colonnes pour éviter l'erreur "already used")
    cols_final = list(set(mapping.values()))
    
    # Filtrer pour ne garder que les colonnes qui existent vraiment dans le DF
    cols_final = [c for c in cols_final if c in df_air.columns]
    
    df_air = df_air[cols_final]
    
    print(f"✅ Qualité Air traitée : {len(df_air)} enregistrements.")
    return df_air

# ==============================================================================
# 4. EXPORT VERS HDFS (DATALAKE PROCESSED)
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
    
    # 0. Upload des Raw Data (Backup)
    upload_raw_folder_to_hdfs(LOCAL_DATA_DIR, "/user/mathis/datalake/raw")

    # 1. Pipeline Météo (Plage dynamique 2005-2023)
    # Génération automatique de la liste ['2005', '2006', ..., '2023']
    target_years = [str(year) for year in range(2005, 2024)]
    
    df_w = process_weather(years=target_years) 
    save_to_hdfs(df_w, "weather.parquet")
    
    # 2. Pipeline Air
    df_a = process_air_quality()
    save_to_hdfs(df_a, "air_quality.parquet")
    
    print("\n🎉 ETL Batch terminé avec succès.")
    spark.stop()