# ============================================================================
# Makefile - Projet Big Data RTE Dashboard
# ============================================================================
# Gestion complète du projet : build, démarrage, tests, nettoyage
# ============================================================================

.PHONY: help build start stop restart clean logs status test-hdfs test-regional \
        load-national load-regional dashboard init clean-hdfs clean-all \
        check-containers backup restore

# Couleurs pour l'affichage
GREEN  := \033[0;32m
YELLOW := \033[0;33m
RED    := \033[0;31m
BLUE   := \033[0;34m
NC     := \033[0m # No Color

# Variables
COMPOSE_FILE := docker-compose.yml
DASHBOARD_URL := http://localhost:8501
HDFS_NAMENODE := namenode
HDFS_PATH_NATIONAL := /user/mathis/datalake/raw/rte/rte_datalake.parquet
HDFS_PATH_REGIONAL := /user/mathis/datalake/raw/rte/rte_regional.parquet
BACKUP_DIR := ./backups

# ============================================================================
# COMMANDES PRINCIPALES
# ============================================================================

## help: Afficher l'aide
help:
	@echo ""
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║         Projet Big Data - Dashboard RTE - Makefile            ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(GREEN)DÉMARRAGE RAPIDE:$(NC)"
	@echo "  make init              - Initialisation complète du projet"
	@echo "  make start             - Démarrer tous les services"
	@echo "  make dashboard         - Ouvrir le dashboard"
	@echo ""
	@echo "$(GREEN)GESTION DES SERVICES:$(NC)"
	@echo "  make build             - Construire les images Docker"
	@echo "  make start             - Démarrer les containers"
	@echo "  make stop              - Arrêter les containers"
	@echo "  make restart           - Redémarrer les containers"
	@echo "  make status            - Voir le status des containers"
	@echo "  make logs              - Afficher les logs"
	@echo ""
	@echo "$(GREEN)DONNÉES:$(NC)"
	@echo "  make load-national     - Charger données nationales RTE"
	@echo "  make load-regional     - Charger données régionales RTE"
	@echo "  make test-hdfs         - Tester HDFS (national)"
	@echo "  make test-regional     - Tester persistance régionale"
	@echo ""
	@echo "$(GREEN)MAINTENANCE:$(NC)"
	@echo "  make clean             - Nettoyer les containers"
	@echo "  make clean-hdfs        - Nettoyer les données HDFS"
	@echo "  make clean-all         - Nettoyer complètement"
	@echo "  make backup            - Sauvegarder les données HDFS"
	@echo "  make restore           - Restaurer les données HDFS"
	@echo ""
	@echo "$(YELLOW)Exemple d'utilisation:$(NC)"
	@echo "  make init && make dashboard"
	@echo ""

## init: Initialisation complète du projet
init:
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║           Initialisation du Projet Big Data                   ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(GREEN)1️⃣  Vérification de Docker...$(NC)"
	@docker --version || (echo "$(RED)❌ Docker non installé$(NC)" && exit 1)
	@docker-compose --version || (echo "$(RED)❌ Docker Compose non installé$(NC)" && exit 1)
	@echo "$(GREEN)   ✅ Docker OK$(NC)"
	@echo ""
	@echo "$(GREEN)2️⃣  Construction des images...$(NC)"
	@$(MAKE) build
	@echo ""
	@echo "$(GREEN)3️⃣  Démarrage des services...$(NC)"
	@$(MAKE) start
	@echo ""
	@echo "$(GREEN)4️⃣  Attente de l'initialisation (30 secondes)...$(NC)"
	@sleep 30
	@echo ""
	@echo "$(GREEN)5️⃣  Vérification des services...$(NC)"
	@$(MAKE) status
	@echo ""
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║                  ✅ Initialisation Terminée                     ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(YELLOW)📊 Dashboard disponible à:$(NC) $(DASHBOARD_URL)"
	@echo "$(YELLOW)🚀 Commande suivante:$(NC) make dashboard"
	@echo ""

# ============================================================================
# GESTION DES SERVICES
# ============================================================================

## build: Construire les images Docker
build:
	@echo "$(BLUE)🔨 Construction des images Docker...$(NC)"
	@docker-compose -f $(COMPOSE_FILE) build
	@echo "$(GREEN)✅ Images construites avec succès$(NC)"

## start: Démarrer les containers
start:
	@echo "$(BLUE)🚀 Démarrage des containers...$(NC)"
	@docker-compose -f $(COMPOSE_FILE) up -d
	@echo "$(GREEN)✅ Containers démarrés$(NC)"
	@echo "$(YELLOW)⏳ Attendre 30 secondes pour l'initialisation complète$(NC)"

## stop: Arrêter les containers
stop:
	@echo "$(BLUE)🛑 Arrêt des containers...$(NC)"
	@docker-compose -f $(COMPOSE_FILE) stop
	@echo "$(GREEN)✅ Containers arrêtés$(NC)"

## restart: Redémarrer les containers
restart:
	@echo "$(BLUE)🔄 Redémarrage des containers...$(NC)"
	@$(MAKE) stop
	@sleep 2
	@$(MAKE) start
	@echo "$(GREEN)✅ Containers redémarrés$(NC)"

## status: Afficher le statut des containers
status:
	@echo "$(BLUE)📊 Statut des containers:$(NC)"
	@echo ""
	@docker-compose -f $(COMPOSE_FILE) ps
	@echo ""
	@echo "$(BLUE)🔍 Santé des services:$(NC)"
	@echo ""
	@docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "namenode|datanode|spark|pyspark_notebook|resourcemanager|nodemanager|historyserver|postgres" || echo "Aucun container en cours d'exécution"

## logs: Afficher les logs
logs:
	@echo "$(BLUE)📜 Logs des containers (Ctrl+C pour quitter):$(NC)"
	@docker-compose -f $(COMPOSE_FILE) logs -f --tail=100

## dashboard: Ouvrir le dashboard dans le navigateur
dashboard:
	@echo "$(BLUE)🌐 Ouverture du dashboard...$(NC)"
	@echo "$(YELLOW)Dashboard URL:$(NC) $(DASHBOARD_URL)"
	@sleep 2
	@if command -v xdg-open > /dev/null; then \
		xdg-open $(DASHBOARD_URL); \
	elif command -v open > /dev/null; then \
		open $(DASHBOARD_URL); \
	elif command -v start > /dev/null; then \
		start $(DASHBOARD_URL); \
	else \
		echo "$(YELLOW)⚠️  Ouvrez manuellement: $(DASHBOARD_URL)$(NC)"; \
	fi

# ============================================================================
# GESTION DES DONNÉES
# ============================================================================

## load-national: Charger les données nationales
load-national:
	@echo "$(BLUE)📥 Chargement des données nationales RTE...$(NC)"
	@echo "$(YELLOW)⚠️  Cette opération se fait via le dashboard$(NC)"
	@echo ""
	@echo "$(GREEN)Instructions:$(NC)"
	@echo "  1. Ouvrir le dashboard: make dashboard"
	@echo "  2. Aller dans 'RTE Production'"
	@echo "  3. Cliquer sur '🔄 Actualiser depuis RTE (National)'"
	@echo "  4. Attendre la synchronisation HDFS"
	@echo ""
	@$(MAKE) dashboard

## load-regional: Charger les données régionales
load-regional:
	@echo "$(BLUE)📥 Chargement des données régionales RTE...$(NC)"
	@echo "$(YELLOW)⚠️  Cette opération se fait via le dashboard$(NC)"
	@echo ""
	@echo "$(GREEN)Instructions:$(NC)"
	@echo "  1. Ouvrir le dashboard: make dashboard"
	@echo "  2. Aller dans 'RTE Production'"
	@echo "  3. Cliquer sur '🗺️ Charger Données Régionales'"
	@echo "  4. Attendre la sauvegarde HDFS"
	@echo ""
	@$(MAKE) dashboard

## test-hdfs: Tester la connexion HDFS et les données nationales
test-hdfs:
	@echo "$(BLUE)🧪 Test HDFS - Données Nationales$(NC)"
	@echo ""
	@echo "$(YELLOW)1️⃣  Vérification du container namenode...$(NC)"
	@docker ps | grep namenode > /dev/null && echo "   $(GREEN)✅ Namenode actif$(NC)" || (echo "   $(RED)❌ Namenode non actif$(NC)" && exit 1)
	@echo ""
	@echo "$(YELLOW)2️⃣  Vérification de HDFS...$(NC)"
	@docker exec $(HDFS_NAMENODE) hdfs dfsadmin -report > /dev/null 2>&1 && echo "   $(GREEN)✅ HDFS opérationnel$(NC)" || echo "   $(RED)❌ HDFS non accessible$(NC)"
	@echo ""
	@echo "$(YELLOW)3️⃣  Fichiers dans /user/mathis/datalake/raw/rte/ :$(NC)"
	@docker exec $(HDFS_NAMENODE) hdfs dfs -ls /user/mathis/datalake/raw/rte/ 2>/dev/null || echo "   $(RED)❌ Répertoire non trouvé$(NC)"
	@echo ""
	@echo "$(YELLOW)4️⃣  Test du fichier national :$(NC)"
	@if docker exec $(HDFS_NAMENODE) hdfs dfs -test -e $(HDFS_PATH_NATIONAL) 2>/dev/null; then \
		echo "   $(GREEN)✅ Fichier rte_datalake.parquet existe$(NC)"; \
		echo ""; \
		echo "   Taille du fichier :"; \
		docker exec $(HDFS_NAMENODE) hdfs dfs -du -h $(HDFS_PATH_NATIONAL); \
	else \
		echo "   $(YELLOW)⚠️  Fichier rte_datalake.parquet n'existe pas$(NC)"; \
		echo "   $(YELLOW)→ Chargez les données avec: make load-national$(NC)"; \
	fi
	@echo ""

## test-regional: Tester la persistance des données régionales
test-regional:
	@echo "$(BLUE)🧪 Test HDFS - Données Régionales$(NC)"
	@echo ""
	@echo "$(YELLOW)1️⃣  Vérification du container namenode...$(NC)"
	@docker ps | grep namenode > /dev/null && echo "   $(GREEN)✅ Namenode actif$(NC)" || (echo "   $(RED)❌ Namenode non actif$(NC)" && exit 1)
	@echo ""
	@echo "$(YELLOW)2️⃣  Test du fichier régional :$(NC)"
	@if docker exec $(HDFS_NAMENODE) hdfs dfs -test -e $(HDFS_PATH_REGIONAL) 2>/dev/null; then \
		echo "   $(GREEN)✅ Fichier rte_regional.parquet existe$(NC)"; \
		echo ""; \
		echo "   Taille du fichier :"; \
		docker exec $(HDFS_NAMENODE) hdfs dfs -du -h $(HDFS_PATH_REGIONAL); \
		echo ""; \
		echo "   $(GREEN)✅ Persistance HDFS des données régionales : ACTIVE$(NC)"; \
	else \
		echo "   $(YELLOW)⚠️  Fichier rte_regional.parquet n'existe pas$(NC)"; \
		echo "   $(YELLOW)→ Chargez les données avec: make load-regional$(NC)"; \
	fi
	@echo ""
	@echo "$(YELLOW)3️⃣  Comparaison National vs Régional :$(NC)"
	@if docker exec $(HDFS_NAMENODE) hdfs dfs -test -e $(HDFS_PATH_NATIONAL) 2>/dev/null && \
	   docker exec $(HDFS_NAMENODE) hdfs dfs -test -e $(HDFS_PATH_REGIONAL) 2>/dev/null; then \
		echo "   National :"; \
		docker exec $(HDFS_NAMENODE) hdfs dfs -du -h $(HDFS_PATH_NATIONAL); \
		echo ""; \
		echo "   Régional :"; \
		docker exec $(HDFS_NAMENODE) hdfs dfs -du -h $(HDFS_PATH_REGIONAL); \
	fi
	@echo ""

# ============================================================================
# MAINTENANCE ET NETTOYAGE
# ============================================================================

## clean: Arrêter et supprimer les containers
clean:
	@echo "$(BLUE)🧹 Nettoyage des containers...$(NC)"
	@docker-compose -f $(COMPOSE_FILE) down
	@echo "$(GREEN)✅ Containers supprimés$(NC)"

## clean-hdfs: Nettoyer les données HDFS
clean-hdfs:
	@echo "$(RED)⚠️  ATTENTION: Cette action va supprimer TOUTES les données HDFS$(NC)"
	@echo "$(YELLOW)Voulez-vous continuer? [y/N]$(NC)"
	@read -r REPLY; \
	if [ "$$REPLY" = "y" ] || [ "$$REPLY" = "Y" ]; then \
		echo "$(BLUE)🧹 Nettoyage des données HDFS...$(NC)"; \
		docker exec $(HDFS_NAMENODE) hdfs dfs -rm -r /user/mathis/datalake/raw/rte/* 2>/dev/null || true; \
		echo "$(GREEN)✅ Données HDFS supprimées$(NC)"; \
	else \
		echo "$(YELLOW)Opération annulée$(NC)"; \
	fi

## clean-all: Nettoyage complet (containers + volumes + images)
clean-all:
	@echo "$(RED)⚠️  ATTENTION: Cette action va tout supprimer (containers, volumes, images)$(NC)"
	@echo "$(YELLOW)Voulez-vous continuer? [y/N]$(NC)"
	@read -r REPLY; \
	if [ "$$REPLY" = "y" ] || [ "$$REPLY" = "Y" ]; then \
		echo "$(BLUE)🧹 Nettoyage complet...$(NC)"; \
		docker-compose -f $(COMPOSE_FILE) down -v --rmi all; \
		echo "$(GREEN)✅ Nettoyage complet terminé$(NC)"; \
	else \
		echo "$(YELLOW)Opération annulée$(NC)"; \
	fi

## backup: Sauvegarder les données HDFS
backup:
	@echo "$(BLUE)💾 Sauvegarde des données HDFS...$(NC)"
	@mkdir -p $(BACKUP_DIR)
	@TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	echo "$(YELLOW)Création du backup: $(BACKUP_DIR)/hdfs_backup_$$TIMESTAMP.tar$(NC)"; \
	docker exec $(HDFS_NAMENODE) hdfs dfs -get /user/mathis/datalake/raw/rte /tmp/rte_backup 2>/dev/null || true; \
	docker cp $(HDFS_NAMENODE):/tmp/rte_backup $(BACKUP_DIR)/hdfs_backup_$$TIMESTAMP 2>/dev/null || true; \
	if [ -d "$(BACKUP_DIR)/hdfs_backup_$$TIMESTAMP" ]; then \
		cd $(BACKUP_DIR) && tar -czf hdfs_backup_$$TIMESTAMP.tar.gz hdfs_backup_$$TIMESTAMP && rm -rf hdfs_backup_$$TIMESTAMP; \
		echo "$(GREEN)✅ Backup créé: $(BACKUP_DIR)/hdfs_backup_$$TIMESTAMP.tar.gz$(NC)"; \
	else \
		echo "$(RED)❌ Erreur lors de la création du backup$(NC)"; \
	fi

## restore: Restaurer les données HDFS depuis un backup
restore:
	@echo "$(BLUE)📥 Restauration des données HDFS...$(NC)"
	@echo "$(YELLOW)Backups disponibles:$(NC)"
	@ls -lh $(BACKUP_DIR)/*.tar.gz 2>/dev/null || echo "$(RED)Aucun backup trouvé$(NC)"
	@echo ""
	@echo "$(YELLOW)Entrez le nom du fichier de backup (sans le chemin):$(NC)"
	@read -r BACKUP_FILE; \
	if [ -f "$(BACKUP_DIR)/$$BACKUP_FILE" ]; then \
		echo "$(BLUE)Restauration de $$BACKUP_FILE...$(NC)"; \
		cd $(BACKUP_DIR) && tar -xzf $$BACKUP_FILE; \
		docker cp $$(basename $$BACKUP_FILE .tar.gz) $(HDFS_NAMENODE):/tmp/; \
		docker exec $(HDFS_NAMENODE) hdfs dfs -put -f /tmp/$$(basename $$BACKUP_FILE .tar.gz)/* /user/mathis/datalake/raw/rte/; \
		echo "$(GREEN)✅ Restauration terminée$(NC)"; \
	else \
		echo "$(RED)❌ Fichier de backup non trouvé$(NC)"; \
	fi

# ============================================================================
# UTILITAIRES
# ============================================================================

## check-containers: Vérifier l'état des containers requis
check-containers:
	@echo "$(BLUE)🔍 Vérification des containers requis...$(NC)"
	@echo ""
	@REQUIRED="namenode datanode spark-master spark-worker pyspark_notebook"; \
	for container in $$REQUIRED; do \
		if docker ps | grep -q $$container; then \
			echo "$(GREEN)✅ $$container$(NC)"; \
		else \
			echo "$(RED)❌ $$container$(NC)"; \
		fi \
	done

## shell-namenode: Ouvrir un shell dans le namenode
shell-namenode:
	@echo "$(BLUE)🐚 Connexion au namenode...$(NC)"
	@docker exec -it $(HDFS_NAMENODE) bash

## shell-spark: Ouvrir un shell dans le notebook PySpark
shell-spark:
	@echo "$(BLUE)🐚 Connexion au notebook PySpark...$(NC)"
	@docker exec -it pyspark_notebook bash

## hdfs-report: Afficher le rapport HDFS
hdfs-report:
	@echo "$(BLUE)📊 Rapport HDFS:$(NC)"
	@echo ""
	@docker exec $(HDFS_NAMENODE) hdfs dfsadmin -report

## hdfs-browse: Parcourir les fichiers HDFS
hdfs-browse:
	@echo "$(BLUE)📁 Fichiers HDFS dans /user/mathis/:$(NC)"
	@echo ""
	@docker exec $(HDFS_NAMENODE) hdfs dfs -ls -R /user/mathis/

# ============================================================================
# RACCOURCIS UTILES
# ============================================================================

## dev: Démarrage rapide pour développement
dev: start
	@sleep 30
	@$(MAKE) dashboard

## prod: Démarrage en mode production avec tests
prod: init test-hdfs
	@echo "$(GREEN)✅ Environnement de production prêt$(NC)"

## quick-restart: Redémarrage rapide du dashboard uniquement
quick-restart:
	@echo "$(BLUE)🔄 Redémarrage rapide du dashboard...$(NC)"
	@docker-compose restart pyspark_notebook
	@echo "$(GREEN)✅ Dashboard redémarré$(NC)"
	@echo "$(YELLOW)⏳ Attendre 5 secondes...$(NC)"
	@sleep 5
	@$(MAKE) dashboard

## full-test: Test complet du système
full-test:
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║                    Test Complet du Système                    ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@$(MAKE) status
	@echo ""
	@$(MAKE) check-containers
	@echo ""
	@$(MAKE) test-hdfs
	@echo ""
	@$(MAKE) test-regional
	@echo ""
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║                     Test Complet Terminé                      ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════════╝$(NC)"

# Par défaut, afficher l'aide
.DEFAULT_GOAL := help
