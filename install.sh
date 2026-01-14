#!/bin/bash

echo "=================================================="
echo "🚀 INITIALISATION DU DATALAKE & INGESTION (ETL)"
echo "=================================================="

# 1. Initialisation de l'infrastructure HDFS (Dossiers & Droits)
echo ""
echo "🏗️  [1/3] Configuration HDFS (Namenode)..."
docker exec -it namenode bash /myhadoop/work/init_datalake.sh

# 2. Lancement du gros ETL Batch (Météo + Air)
echo ""
echo "🌤️  [2/3] Exécution de l'ETL Batch (Météo & Air Quality)..."
echo "      Cela peut prendre quelques minutes selon votre connexion..."
docker exec -it pyspark_notebook python work/etl_batch.py

# 3. Ingestion Initiale RTE
echo ""
echo "⚡ [3/3] Bootstrap des données RTE..."
docker exec -it pyspark_notebook python work/bootstrap_data.py

echo ""
echo "=================================================="
echo "✅ INSTALLATION TERMINÉE"
echo "=================================================="
echo "Vous pouvez maintenant lancer le dashboard :"
echo "👉 docker exec -it pyspark_notebook streamlit run work/app.py"
echo "=================================================="