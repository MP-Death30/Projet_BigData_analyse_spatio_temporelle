#!/bin/bash
# A exécuter dans le conteneur 'namenode'

echo "⏳ Attente du Safe Mode..."
hdfs dfsadmin -safemode wait

echo "🏗️ Création de l'arborescence Data Lake..."
hdfs dfs -mkdir -p /user/mathis/datalake/raw/rte
hdfs dfs -mkdir -p /user/mathis/datalake/raw/noaa
hdfs dfs -mkdir -p /user/mathis/datalake/processed/dashboard

# Permissions larges
hdfs dfs -chmod -R 777 /user/mathis

echo "✅ HDFS est prêt."