import sys
import os
import findspark
findspark.init()

from pyspark.sql import SparkSession
import rte_layer

HDFS_RTE_PATH = "hdfs://namenode:9000/user/mathis/datalake/raw/rte/rte_datalake.parquet"

def init_spark():
    return SparkSession.builder \
        .appName("Bootstrap_RTE") \
        .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
        .getOrCreate()

def main():
    print("🚀 Démarrage de l'ingestion RTE...")
    
    # 1. Téléchargement via Pandas (Mémoire RAM)
    print("⬇️ Téléchargement des données RTE...")
    df_pandas, msg = rte_layer.get_latest_data()
    
    if df_pandas.empty:
        print(f"❌ Erreur : {msg}")
        return

    print(f"✅ Données en mémoire : {len(df_pandas)} lignes.")

    # 2. Écriture HDFS via Spark
    print("💾 Sauvegarde vers HDFS...")
    spark = init_spark()
    df_spark = spark.createDataFrame(df_pandas.reset_index())
    df_spark.write.mode("overwrite").parquet(HDFS_RTE_PATH)
    
    print(f"✅ Succès ! Données écrites sur : {HDFS_RTE_PATH}")

if __name__ == "__main__":
    main()