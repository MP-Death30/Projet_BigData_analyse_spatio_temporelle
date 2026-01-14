Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "🚀 INITIALISATION DU DATALAKE & INGESTION (ETL)" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Initialisation de l'infrastructure HDFS
Write-Host ""
Write-Host "🏗️  [1/3] Configuration HDFS (Namenode)..." -ForegroundColor Yellow
docker exec -it namenode bash /myhadoop/work/init_datalake.sh

# 2. ETL Batch (Météo + Air)
Write-Host ""
Write-Host "🌤️  [2/3] Exécution de l'ETL Batch (Météo & Air)..." -ForegroundColor Yellow
docker exec -it pyspark_notebook python work/etl_batch.py

# 3. Bootstrap RTE
Write-Host ""
Write-Host "⚡ [3/3] Bootstrap des données RTE..." -ForegroundColor Yellow
docker exec -it pyspark_notebook python work/bootstrap_data.py

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host "✅ INSTALLATION TERMINÉE" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host "Lancement :"
Write-Host "👉 docker exec -it pyspark_notebook streamlit run work/app.py" -ForegroundColor Cyan