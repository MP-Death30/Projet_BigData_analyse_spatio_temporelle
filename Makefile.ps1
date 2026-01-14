# ============================================================================
# Makefile.ps1 - Projet Big Data RTE Dashboard (Windows PowerShell)
# ============================================================================
# Alternative au Makefile pour Windows
# Usage: .\Makefile.ps1 <commande>
# ============================================================================

param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

# Couleurs
$Green = "Green"
$Yellow = "Yellow"
$Red = "Red"
$Blue = "Cyan"

# Variables
$ComposeFile = "docker-compose.yml"
$DashboardURL = "http://localhost:8501"
$HDFSNamenode = "namenode"
$HDFSPathNational = "/user/mathis/datalake/raw/rte/rte_datalake.parquet"
$HDFSPathRegional = "/user/mathis/datalake/raw/rte/rte_regional.parquet"
$BackupDir = "./backups"

# ============================================================================
# FONCTIONS
# ============================================================================

function Show-Help {
    Write-Host ""
    Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor $Blue
    Write-Host "║         Projet Big Data - Dashboard RTE - PowerShell          ║" -ForegroundColor $Blue
    Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor $Blue
    Write-Host ""
    Write-Host "DÉMARRAGE RAPIDE:" -ForegroundColor $Green
    Write-Host "  .\Makefile.ps1 init              - Initialisation complète"
    Write-Host "  .\Makefile.ps1 start             - Démarrer tous les services"
    Write-Host "  .\Makefile.ps1 dashboard         - Ouvrir le dashboard"
    Write-Host ""
    Write-Host "GESTION DES SERVICES:" -ForegroundColor $Green
    Write-Host "  .\Makefile.ps1 build             - Construire les images Docker"
    Write-Host "  .\Makefile.ps1 start             - Démarrer les containers"
    Write-Host "  .\Makefile.ps1 stop              - Arrêter les containers"
    Write-Host "  .\Makefile.ps1 restart           - Redémarrer les containers"
    Write-Host "  .\Makefile.ps1 status            - Voir le statut"
    Write-Host "  .\Makefile.ps1 logs              - Afficher les logs"
    Write-Host ""
    Write-Host "DONNÉES:" -ForegroundColor $Green
    Write-Host "  .\Makefile.ps1 load-national     - Charger données nationales"
    Write-Host "  .\Makefile.ps1 load-regional     - Charger données régionales"
    Write-Host "  .\Makefile.ps1 test-hdfs         - Tester HDFS"
    Write-Host "  .\Makefile.ps1 test-regional     - Tester persistance régionale"
    Write-Host ""
    Write-Host "MAINTENANCE:" -ForegroundColor $Green
    Write-Host "  .\Makefile.ps1 clean             - Nettoyer les containers"
    Write-Host "  .\Makefile.ps1 clean-all         - Nettoyage complet"
    Write-Host "  .\Makefile.ps1 backup            - Sauvegarder HDFS"
    Write-Host ""
    Write-Host "EXEMPLE:" -ForegroundColor $Yellow
    Write-Host "  .\Makefile.ps1 init"
    Write-Host "  .\Makefile.ps1 dashboard"
    Write-Host ""
}

function Initialize-Project {
    Write-Host ""
    Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor $Blue
    Write-Host "║           Initialisation du Projet Big Data                   ║" -ForegroundColor $Blue
    Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor $Blue
    Write-Host ""
    
    Write-Host "1️⃣  Vérification de Docker..." -ForegroundColor $Green
    try {
        docker --version | Out-Null
        docker-compose --version | Out-Null
        Write-Host "   ✅ Docker OK" -ForegroundColor $Green
    } catch {
        Write-Host "   ❌ Docker non installé ou non démarré" -ForegroundColor $Red
        exit 1
    }
    
    Write-Host ""
    Write-Host "2️⃣  Construction des images..." -ForegroundColor $Green
    Build-Images
    
    Write-Host ""
    Write-Host "3️⃣  Démarrage des services..." -ForegroundColor $Green
    Start-Services
    
    Write-Host ""
    Write-Host "4️⃣  Attente de l'initialisation (30 secondes)..." -ForegroundColor $Green
    Start-Sleep -Seconds 30
    
    Write-Host ""
    Write-Host "5️⃣  Vérification des services..." -ForegroundColor $Green
    Show-Status
    
    Write-Host ""
    Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor $Blue
    Write-Host "║                  ✅ Initialisation Terminée                     ║" -ForegroundColor $Blue
    Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor $Blue
    Write-Host ""
    Write-Host "📊 Dashboard disponible à: $DashboardURL" -ForegroundColor $Yellow
    Write-Host "🚀 Commande suivante: .\Makefile.ps1 dashboard" -ForegroundColor $Yellow
    Write-Host ""
}

function Build-Images {
    Write-Host "🔨 Construction des images Docker..." -ForegroundColor $Blue
    docker-compose -f $ComposeFile build
    Write-Host "✅ Images construites avec succès" -ForegroundColor $Green
}

function Start-Services {
    Write-Host "🚀 Démarrage des containers..." -ForegroundColor $Blue
    docker-compose -f $ComposeFile up -d
    Write-Host "✅ Containers démarrés" -ForegroundColor $Green
    Write-Host "⏳ Attendre 30 secondes pour l'initialisation complète" -ForegroundColor $Yellow
}

function Stop-Services {
    Write-Host "🛑 Arrêt des containers..." -ForegroundColor $Blue
    docker-compose -f $ComposeFile stop
    Write-Host "✅ Containers arrêtés" -ForegroundColor $Green
}

function Restart-Services {
    Write-Host "🔄 Redémarrage des containers..." -ForegroundColor $Blue
    Stop-Services
    Start-Sleep -Seconds 2
    Start-Services
    Write-Host "✅ Containers redémarrés" -ForegroundColor $Green
}

function Show-Status {
    Write-Host "📊 Statut des containers:" -ForegroundColor $Blue
    Write-Host ""
    docker-compose -f $ComposeFile ps
    Write-Host ""
}

function Show-Logs {
    Write-Host "📜 Logs des containers (Ctrl+C pour quitter):" -ForegroundColor $Blue
    docker-compose -f $ComposeFile logs -f --tail=100
}

function Open-Dashboard {
    Write-Host "🌐 Ouverture du dashboard..." -ForegroundColor $Blue
    Write-Host "Dashboard URL: $DashboardURL" -ForegroundColor $Yellow
    Start-Sleep -Seconds 2
    Start-Process $DashboardURL
}

function Load-National {
    Write-Host "📥 Chargement des données nationales RTE..." -ForegroundColor $Blue
    Write-Host "⚠️  Cette opération se fait via le dashboard" -ForegroundColor $Yellow
    Write-Host ""
    Write-Host "Instructions:" -ForegroundColor $Green
    Write-Host "  1. Ouvrir le dashboard"
    Write-Host "  2. Aller dans 'RTE Production'"
    Write-Host "  3. Cliquer sur '🔄 Actualiser depuis RTE (National)'"
    Write-Host "  4. Attendre la synchronisation HDFS"
    Write-Host ""
    Open-Dashboard
}

function Load-Regional {
    Write-Host "📥 Chargement des données régionales RTE..." -ForegroundColor $Blue
    Write-Host "⚠️  Cette opération se fait via le dashboard" -ForegroundColor $Yellow
    Write-Host ""
    Write-Host "Instructions:" -ForegroundColor $Green
    Write-Host "  1. Ouvrir le dashboard"
    Write-Host "  2. Aller dans 'RTE Production'"
    Write-Host "  3. Cliquer sur '🗺️ Charger Données Régionales'"
    Write-Host "  4. Attendre la sauvegarde HDFS"
    Write-Host ""
    Open-Dashboard
}

function Test-HDFS {
    Write-Host "🧪 Test HDFS - Données Nationales" -ForegroundColor $Blue
    Write-Host ""
    
    Write-Host "1️⃣  Vérification du container namenode..." -ForegroundColor $Yellow
    $namenode = docker ps | Select-String "namenode"
    if ($namenode) {
        Write-Host "   ✅ Namenode actif" -ForegroundColor $Green
    } else {
        Write-Host "   ❌ Namenode non actif" -ForegroundColor $Red
        return
    }
    
    Write-Host ""
    Write-Host "2️⃣  Fichiers dans /user/mathis/datalake/raw/rte/ :" -ForegroundColor $Yellow
    docker exec $HDFSNamenode hdfs dfs -ls /user/mathis/datalake/raw/rte/ 2>$null
    
    Write-Host ""
    Write-Host "3️⃣  Test du fichier national :" -ForegroundColor $Yellow
    docker exec $HDFSNamenode hdfs dfs -test -e $HDFSPathNational 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ Fichier rte_datalake.parquet existe" -ForegroundColor $Green
        Write-Host ""
        Write-Host "   Taille du fichier :"
        docker exec $HDFSNamenode hdfs dfs -du -h $HDFSPathNational
    } else {
        Write-Host "   ⚠️  Fichier rte_datalake.parquet n'existe pas" -ForegroundColor $Yellow
        Write-Host "   → Chargez les données avec: .\Makefile.ps1 load-national" -ForegroundColor $Yellow
    }
    Write-Host ""
}

function Test-Regional {
    Write-Host "🧪 Test HDFS - Données Régionales" -ForegroundColor $Blue
    Write-Host ""
    
    Write-Host "1️⃣  Vérification du container namenode..." -ForegroundColor $Yellow
    $namenode = docker ps | Select-String "namenode"
    if ($namenode) {
        Write-Host "   ✅ Namenode actif" -ForegroundColor $Green
    } else {
        Write-Host "   ❌ Namenode non actif" -ForegroundColor $Red
        return
    }
    
    Write-Host ""
    Write-Host "2️⃣  Test du fichier régional :" -ForegroundColor $Yellow
    docker exec $HDFSNamenode hdfs dfs -test -e $HDFSPathRegional 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ Fichier rte_regional.parquet existe" -ForegroundColor $Green
        Write-Host ""
        Write-Host "   Taille du fichier :"
        docker exec $HDFSNamenode hdfs dfs -du -h $HDFSPathRegional
        Write-Host ""
        Write-Host "   ✅ Persistance HDFS des données régionales : ACTIVE" -ForegroundColor $Green
    } else {
        Write-Host "   ⚠️  Fichier rte_regional.parquet n'existe pas" -ForegroundColor $Yellow
        Write-Host "   → Chargez les données avec: .\Makefile.ps1 load-regional" -ForegroundColor $Yellow
    }
    Write-Host ""
}

function Clean-Containers {
    Write-Host "🧹 Nettoyage des containers..." -ForegroundColor $Blue
    docker-compose -f $ComposeFile down
    Write-Host "✅ Containers supprimés" -ForegroundColor $Green
}

function Clean-All {
    Write-Host "⚠️  ATTENTION: Cette action va tout supprimer" -ForegroundColor $Red
    $confirm = Read-Host "Voulez-vous continuer? [y/N]"
    if ($confirm -eq "y" -or $confirm -eq "Y") {
        Write-Host "🧹 Nettoyage complet..." -ForegroundColor $Blue
        docker-compose -f $ComposeFile down -v --rmi all
        Write-Host "✅ Nettoyage complet terminé" -ForegroundColor $Green
    } else {
        Write-Host "Opération annulée" -ForegroundColor $Yellow
    }
}

function Backup-Data {
    Write-Host "💾 Sauvegarde des données HDFS..." -ForegroundColor $Blue
    if (!(Test-Path $BackupDir)) {
        New-Item -ItemType Directory -Path $BackupDir | Out-Null
    }
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupName = "hdfs_backup_$timestamp"
    
    Write-Host "Création du backup: $BackupDir/$backupName.tar.gz" -ForegroundColor $Yellow
    
    docker exec $HDFSNamenode hdfs dfs -get /user/mathis/datalake/raw/rte /tmp/rte_backup 2>$null
    docker cp "${HDFSNamenode}:/tmp/rte_backup" "$BackupDir/$backupName" 2>$null
    
    if (Test-Path "$BackupDir/$backupName") {
        Compress-Archive -Path "$BackupDir/$backupName" -DestinationPath "$BackupDir/$backupName.zip"
        Remove-Item -Path "$BackupDir/$backupName" -Recurse
        Write-Host "✅ Backup créé: $BackupDir/$backupName.zip" -ForegroundColor $Green
    } else {
        Write-Host "❌ Erreur lors de la création du backup" -ForegroundColor $Red
    }
}

function Quick-Restart {
    Write-Host "🔄 Redémarrage rapide du dashboard..." -ForegroundColor $Blue
    docker-compose restart pyspark_notebook
    Write-Host "✅ Dashboard redémarré" -ForegroundColor $Green
    Write-Host "⏳ Attendre 5 secondes..." -ForegroundColor $Yellow
    Start-Sleep -Seconds 5
    Open-Dashboard
}

# ============================================================================
# ROUTEUR DE COMMANDES
# ============================================================================

switch ($Command.ToLower()) {
    "help"           { Show-Help }
    "init"           { Initialize-Project }
    "build"          { Build-Images }
    "start"          { Start-Services }
    "stop"           { Stop-Services }
    "restart"        { Restart-Services }
    "status"         { Show-Status }
    "logs"           { Show-Logs }
    "dashboard"      { Open-Dashboard }
    "load-national"  { Load-National }
    "load-regional"  { Load-Regional }
    "test-hdfs"      { Test-HDFS }
    "test-regional"  { Test-Regional }
    "clean"          { Clean-Containers }
    "clean-all"      { Clean-All }
    "backup"         { Backup-Data }
    "quick-restart"  { Quick-Restart }
    default          { 
        Write-Host "Commande inconnue: $Command" -ForegroundColor $Red
        Write-Host "Utilisez '.\Makefile.ps1 help' pour voir les commandes disponibles" -ForegroundColor $Yellow
    }
}
