@echo off
REM ============================================================================
REM make.bat - Projet Big Data RTE Dashboard (Windows Batch)
REM ============================================================================
REM Alternative au Makefile pour Windows (cmd.exe)
REM Usage: make.bat <commande>
REM ============================================================================

SETLOCAL EnableDelayedExpansion

REM Variables
SET COMPOSE_FILE=docker-compose.yml
SET DASHBOARD_URL=http://localhost:8501
SET HDFS_NAMENODE=namenode
SET BACKUP_DIR=backups

REM ============================================================================
REM ROUTEUR DE COMMANDES
REM ============================================================================

IF "%1"=="" GOTO help
IF "%1"=="help" GOTO help
IF "%1"=="init" GOTO init
IF "%1"=="build" GOTO build
IF "%1"=="up" GOTO up
IF "%1"=="start" GOTO up
IF "%1"=="down" GOTO down
IF "%1"=="stop" GOTO down
IF "%1"=="restart" GOTO restart
IF "%1"=="status" GOTO status
IF "%1"=="logs" GOTO logs
IF "%1"=="dashboard" GOTO dashboard
IF "%1"=="run" GOTO run
IF "%1"=="load-national" GOTO load_national
IF "%1"=="load-regional" GOTO load_regional
IF "%1"=="test-hdfs" GOTO test_hdfs
IF "%1"=="test-regional" GOTO test_regional
IF "%1"=="clean" GOTO clean
IF "%1"=="clean-hdfs" GOTO clean_hdfs
IF "%1"=="clean-all" GOTO clean_all
IF "%1"=="backup" GOTO backup
IF "%1"=="quick-restart" GOTO quick_restart
IF "%1"=="shell-namenode" GOTO shell_namenode
IF "%1"=="shell-spark" GOTO shell_spark
IF "%1"=="dev" GOTO dev
GOTO unknown

REM ============================================================================
REM AIDE
REM ============================================================================

:help
echo.
echo ================================================================
echo          Projet Big Data - Dashboard RTE - Windows
echo ================================================================
echo.
echo DEMARRAGE RAPIDE:
echo   make init              - Initialisation complete
echo   make start             - Demarrer tous les services
echo   make run               - Lancer le dashboard dans le container
echo   make dashboard         - Ouvrir le dashboard
echo.
echo GESTION DES SERVICES:
echo   make build             - Construire les images Docker
echo   make up / start        - Demarrer les containers
echo   make down / stop       - Arreter les containers
echo   make restart           - Redemarrer les containers
echo   make status            - Voir le statut
echo   make logs              - Afficher les logs
echo   make run               - Lancer le dashboard dans le container
echo.
echo DONNEES:
echo   make load-national     - Charger donnees nationales
echo   make load-regional     - Charger donnees regionales
echo   make test-hdfs         - Tester HDFS
echo   make test-regional     - Tester persistance regionale
echo.
echo MAINTENANCE:
echo   make clean             - Nettoyer les containers
echo   make clean-hdfs        - Nettoyer donnees HDFS
echo   make clean-all         - Nettoyage complet
echo   make backup            - Sauvegarder HDFS
echo.
echo UTILITAIRES:
echo   make quick-restart     - Redemarrage rapide
echo   make shell-namenode    - Shell dans namenode
echo   make shell-spark       - Shell dans PySpark
echo   make dev               - Mode developpement
echo.
GOTO end

REM ============================================================================
REM INITIALISATION COMPLETE
REM ============================================================================

:init
echo.
echo ================================================================
echo           Initialisation du Projet Big Data
echo ================================================================
echo.
echo [1/5] Verification de Docker...
docker --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERREUR] Docker non installe ou non demarre
    echo Installez Docker Desktop: https://www.docker.com/products/docker-desktop
    GOTO end
)
docker-compose --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERREUR] Docker Compose non installe
    GOTO end
)
echo [OK] Docker OK
echo.
echo [2/5] Construction des images...
CALL :build
echo.
echo [3/5] Demarrage des services...
CALL :up
echo.
echo [4/5] Attente de l'initialisation (30 secondes)...
timeout /t 30 /nobreak >nul
echo.
echo [5/5] Verification des services...
CALL :status
echo.
echo ================================================================
echo           Initialisation Terminee
echo ================================================================
echo.
echo Dashboard disponible: %DASHBOARD_URL%
echo Commande suivante: make dashboard
echo.
GOTO end

REM ============================================================================
REM GESTION DES SERVICES
REM ============================================================================

:build
echo Construction des images Docker...
docker-compose -f %COMPOSE_FILE% build
IF ERRORLEVEL 1 (
    echo [ERREUR] Echec de la construction
    GOTO end
)
echo [OK] Images construites
GOTO end

:up
echo Demarrage des containers...
docker-compose -f %COMPOSE_FILE% up -d
IF ERRORLEVEL 1 (
    echo [ERREUR] Echec du demarrage
    GOTO end
)
echo [OK] Containers demarres
echo [INFO] Attendre 30 secondes pour l'initialisation complete
GOTO end

:down
echo Arret des containers...
docker-compose -f %COMPOSE_FILE% stop
IF ERRORLEVEL 1 (
    echo [ERREUR] Echec de l'arret
    GOTO end
)
echo [OK] Containers arretes
GOTO end

:restart
echo Redemarrage des containers...
CALL :clean
timeout /t 2 /nobreak >nul
CALL :up
echo [OK] Containers redemarres
GOTO end

:status
echo.
echo Status des containers:
echo ================================================================
docker-compose -f %COMPOSE_FILE% ps
echo.
GOTO end

:logs
echo.
echo Logs des containers (Ctrl+C pour quitter):
echo ================================================================
docker-compose -f %COMPOSE_FILE% logs -f --tail=100
GOTO end

:dashboard
echo Ouverture du dashboard...
echo URL: %DASHBOARD_URL%
timeout /t 2 /nobreak >nul
start %DASHBOARD_URL%
GOTO end

:run
echo Lancement du dashboard dans le container...
docker exec -it pyspark_notebook streamlit run work/app.py
GOTO end

REM ============================================================================
REM GESTION DES DONNEES
REM ============================================================================

:load_national
echo.
echo Chargement des donnees nationales RTE...
echo [INFO] Cette operation se fait via le dashboard
echo.
echo Instructions:
echo   1. Ouvrir le dashboard
echo   2. Aller dans 'RTE Production'
echo   3. Cliquer sur 'Actualiser depuis RTE (National)'
echo   4. Attendre la synchronisation HDFS
echo.
CALL :dashboard
GOTO end

:load_regional
echo.
echo Chargement des donnees regionales RTE...
echo [INFO] Cette operation se fait via le dashboard
echo.
echo Instructions:
echo   1. Ouvrir le dashboard
echo   2. Aller dans 'RTE Production'
echo   3. Cliquer sur 'Charger Donnees Regionales'
echo   4. Attendre la sauvegarde HDFS
echo.
CALL :dashboard
GOTO end

REM ============================================================================
REM TESTS
REM ============================================================================

:test_hdfs
echo.
echo ================================================================
echo    Test HDFS - Donnees Nationales
echo ================================================================
echo.
echo [1] Verification du container namenode...
docker ps | findstr namenode >nul
IF ERRORLEVEL 1 (
    echo [ERREUR] Namenode non actif
    GOTO end
)
echo [OK] Namenode actif
echo.
echo [2] Verification de HDFS...
docker exec %HDFS_NAMENODE% hdfs dfsadmin -report >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERREUR] HDFS non accessible
) ELSE (
    echo [OK] HDFS operationnel
)
echo.
echo [3] Fichiers dans /user/mathis/datalake/raw/rte/ :
docker exec %HDFS_NAMENODE% hdfs dfs -ls /user/mathis/datalake/raw/rte/ 2>nul
echo.
echo [4] Test du fichier national:
docker exec %HDFS_NAMENODE% hdfs dfs -test -e /user/mathis/datalake/raw/rte/rte_datalake.parquet 2>nul
IF ERRORLEVEL 1 (
    echo [ATTENTION] Fichier rte_datalake.parquet n'existe pas
    echo Chargez les donnees avec: make load-national
) ELSE (
    echo [OK] Fichier rte_datalake.parquet existe
    echo.
    echo Taille du fichier:
    docker exec %HDFS_NAMENODE% hdfs dfs -du -h /user/mathis/datalake/raw/rte/rte_datalake.parquet
)
echo.
GOTO end

:test_regional
echo.
echo ================================================================
echo    Test HDFS - Donnees Regionales
echo ================================================================
echo.
echo [1] Verification du container namenode...
docker ps | findstr namenode >nul
IF ERRORLEVEL 1 (
    echo [ERREUR] Namenode non actif
    GOTO end
)
echo [OK] Namenode actif
echo.
echo [2] Test du fichier regional:
docker exec %HDFS_NAMENODE% hdfs dfs -test -e /user/mathis/datalake/raw/rte/rte_regional.parquet 2>nul
IF ERRORLEVEL 1 (
    echo [ATTENTION] Fichier rte_regional.parquet n'existe pas
    echo Chargez les donnees avec: make load-regional
) ELSE (
    echo [OK] Fichier rte_regional.parquet existe
    echo.
    echo Taille du fichier:
    docker exec %HDFS_NAMENODE% hdfs dfs -du -h /user/mathis/datalake/raw/rte/rte_regional.parquet
    echo.
    echo [OK] Persistance HDFS des donnees regionales: ACTIVE
)
echo.
echo [3] Comparaison National vs Regional:
docker exec %HDFS_NAMENODE% hdfs dfs -test -e /user/mathis/datalake/raw/rte/rte_datalake.parquet 2>nul
IF NOT ERRORLEVEL 1 (
    docker exec %HDFS_NAMENODE% hdfs dfs -test -e /user/mathis/datalake/raw/rte/rte_regional.parquet 2>nul
    IF NOT ERRORLEVEL 1 (
        echo National:
        docker exec %HDFS_NAMENODE% hdfs dfs -du -h /user/mathis/datalake/raw/rte/rte_datalake.parquet
        echo.
        echo Regional:
        docker exec %HDFS_NAMENODE% hdfs dfs -du -h /user/mathis/datalake/raw/rte/rte_regional.parquet
    )
)
echo.
GOTO end

REM ============================================================================
REM MAINTENANCE
REM ============================================================================

:clean
echo Nettoyage des containers...
docker-compose -f %COMPOSE_FILE% down
echo [OK] Containers supprimes
GOTO end

:clean_hdfs
echo.
echo [ATTENTION] Cette action va supprimer TOUTES les donnees HDFS
set /p confirm="Voulez-vous continuer? [y/N]: "
IF /I "%confirm%"=="y" (
    echo Nettoyage des donnees HDFS...
    docker exec %HDFS_NAMENODE% hdfs dfs -rm -r /user/mathis/datalake/raw/rte/* 2>nul
    echo [OK] Donnees HDFS supprimees
) ELSE (
    echo Operation annulee
)
GOTO end

:clean_all
echo.
echo [ATTENTION] Cette action va tout supprimer (containers + volumes + images)
set /p confirm="Voulez-vous continuer? [y/N]: "
IF /I "%confirm%"=="y" (
    echo Nettoyage complet...
    docker-compose -f %COMPOSE_FILE% down -v --rmi all
    echo [OK] Nettoyage complet termine
) ELSE (
    echo Operation annulee
)
GOTO end

:backup
echo.
echo Sauvegarde des donnees HDFS...
IF NOT EXIST "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

REM Generer timestamp
FOR /f "tokens=2-4 delims=/ " %%a IN ('date /t') DO (SET mydate=%%c%%a%%b)
FOR /f "tokens=1-2 delims=/: " %%a IN ('time /t') DO (SET mytime=%%a%%b)
SET timestamp=%mydate%_%mytime%
SET backup_name=hdfs_backup_%timestamp%

echo Creation du backup: %BACKUP_DIR%\%backup_name%

docker exec %HDFS_NAMENODE% hdfs dfs -get /user/mathis/datalake/raw/rte /tmp/rte_backup 2>nul
docker cp %HDFS_NAMENODE%:/tmp/rte_backup %BACKUP_DIR%\%backup_name% 2>nul

IF EXIST "%BACKUP_DIR%\%backup_name%" (
    echo [OK] Backup cree: %BACKUP_DIR%\%backup_name%
) ELSE (
    echo [ERREUR] Erreur lors de la creation du backup
)
GOTO end

REM ============================================================================
REM UTILITAIRES
REM ============================================================================

:quick_restart
echo Redemarrage rapide du dashboard...
docker-compose restart pyspark_notebook
echo [OK] Dashboard redemarre
echo Attente de 5 secondes...
timeout /t 5 /nobreak >nul
CALL :dashboard
GOTO end

:shell_namenode
echo Connexion au namenode...
docker exec -it %HDFS_NAMENODE% bash
GOTO end

:shell_spark
echo Connexion au notebook PySpark...
docker exec -it pyspark_notebook bash
GOTO end

:dev
echo Mode developpement...
CALL :up
timeout /t 30 /nobreak >nul
CALL :dashboard
GOTO end

REM ============================================================================
REM ERREUR
REM ============================================================================

:unknown
echo [ERREUR] Commande inconnue: %1
echo Utilisez 'make help' pour voir les commandes disponibles
GOTO end

:end
ENDLOCAL
