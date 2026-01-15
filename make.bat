@echo off
SETLOCAL EnableDelayedExpansion

REM ============================================================================
REM  PROJET BIG DATA - COMMANDES WINDOWS
REM ============================================================================

REM --- CONFIGURATION ---
SET COMPOSE_FILE=docker-compose.yml
SET URL_DASHBOARD=http://localhost:8501
SET URL_JUPYTER=http://localhost:8888
SET NAMENODE=namenode
SET SPARK_NOTEBOOK=pyspark_notebook

REM --- ROUTEUR ---
IF "%1"=="" GOTO help
IF "%1"=="help" GOTO help
IF "%1"=="init" GOTO init
IF "%1"=="run" GOTO run
IF "%1"=="stop" GOTO stop
IF "%1"=="restart" GOTO restart
IF "%1"=="status" GOTO status
IF "%1"=="logs" GOTO logs
IF "%1"=="clean" GOTO clean
IF "%1"=="clean-all" GOTO clean_all
IF "%1"=="load-dashboard" GOTO load_dashboard
IF "%1"=="shell" GOTO shell

echo [ERREUR] Commande inconnue : %1
GOTO help

REM ============================================================================
REM  COMMANDES PRINCIPALES
REM ============================================================================

:help
echo.
echo  USAGE : make.bat [COMMANDE]
echo.
echo  --- DEMARRAGE (Ordre Chronologique) ---
echo  init            1. Construire et demarrer l'infrastructure (1ere fois)
echo  load-dashboard  2. Charger les donnees dans HDFS (Indispensable)
echo  run             3. LANCER L'APPLICATION (Ouvre le navigateur + Serveur)
echo.
echo  --- MAINTENANCE ---
echo  stop            Mettre en pause les conteneurs
echo  restart         Redemarrer les conteneurs
echo  status          Voir l'etat des services
echo  clean           Supprimer les conteneurs (garde les donnees)
echo  clean-all       Tout supprimer (Images + Volumes + Conteneurs)
echo  logs            Afficher les logs
echo  shell           Ouvrir un terminal dans le conteneur Spark
echo.
GOTO end

:init
echo [INFO] Verification de Docker...
docker --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERREUR] Docker n'est pas lance ou installe.
    GOTO end
)
echo [INFO] Construction et demarrage de la stack...
docker compose -f %COMPOSE_FILE% up -d --build
echo [INFO] Attente de stabilisation des services (30s)...
timeout /t 30 /nobreak
echo [OK] Infrastructure prete.
echo [SUITE] Lancez 'make load-dashboard' pour injecter les donnees.
GOTO end

:run
echo [INFO] Ouverture du navigateur...
start %URL_DASHBOARD%
echo [INFO] Demarrage du serveur Streamlit...
echo [IMPORTANT] Laissez cette fenetre ouverte tant que vous utilisez l'app !
echo.
docker exec -it %SPARK_NOTEBOOK% streamlit run work/app.py
GOTO end

:stop
docker compose -f %COMPOSE_FILE% stop
echo [OK] Services arretes.
GOTO end

:restart
CALL :stop
timeout /t 2 /nobreak >nul
docker compose -f %COMPOSE_FILE% up -d
echo [OK] Services redemarres.
GOTO end

:status
docker compose -f %COMPOSE_FILE% ps
GOTO end

:clean
docker compose -f %COMPOSE_FILE% down
echo [OK] Conteneurs supprimes.
GOTO end

:clean-all
echo [ATTENTION] Suppression totale (Volumes + Images)...
docker compose -f %COMPOSE_FILE% down -v --rmi all
echo [OK] Nettoyage complet effectue.
GOTO end

:logs
docker compose -f %COMPOSE_FILE% logs -f --tail=100
GOTO end

:shell
docker exec -it %SPARK_NOTEBOOK% bash
GOTO end

REM ============================================================================
REM  GESTION DES DONNEES
REM ============================================================================

:load_dashboard
echo [INFO] 1/3 Copie du script d'init HDFS...
docker cp work/init_datalake.sh %NAMENODE%:/tmp/init_datalake.sh
docker exec %NAMENODE% chmod +x /tmp/init_datalake.sh

echo [INFO] 2/3 Creation de l'arborescence HDFS...
docker exec %NAMENODE% /tmp/init_datalake.sh

echo [INFO] 3/3 Execution de l'ETL Batch (Spark)...
docker exec %SPARK_NOTEBOOK% python /home/jovyan/work/etl_batch.py

echo [OK] Donnees chargees. Vous pouvez faire 'make run'.
GOTO end

:end
ENDLOCAL