# ============================================================================
# Makefile - Projet Big Data (Linux / Mac)
# ============================================================================

.PHONY: help init run stop restart clean clean-all logs status load-dashboard shell

# Variables
COMPOSE_FILE := docker-compose.yml
NAMENODE := namenode
SPARK_NOTEBOOK := pyspark_notebook

# --- AIDE ---
help:
	@echo ""
	@echo " USAGE : make [COMMANDE]"
	@echo ""
	@echo " --- DÉMARRAGE ---"
	@echo " init            1. Initialisation complète (Build + Start)"
	@echo " load-dashboard  2. Charger les données HDFS"
	@echo " run             3. LANCER L'APPLICATION (Browser + Server)"
	@echo ""
	@echo " --- MAINTENANCE ---"
	@echo " stop            Arrêter les services"
	@echo " restart         Redémarrer"
	@echo " clean           Supprimer les conteneurs"
	@echo " clean-all       Reset total (Volumes inclus)"
	@echo " logs            Logs temps réel"
	@echo " shell           Terminal Spark"
	@echo ""

# --- COMMANDES PRINCIPALES ---
init:
	@echo "[INFO] Construction et démarrage..."
	@docker compose -f $(COMPOSE_FILE) up -d --build
	@echo "[INFO] Attente de stabilisation (30s)..."
	@sleep 30
	@echo "[OK] Prêt. Lancez 'make load-dashboard'."

run:
	@echo "[INFO] Ouverture du navigateur..."
	@xdg-open http://localhost:8501 2>/dev/null || open http://localhost:8501 2>/dev/null &
	@echo "[INFO] Démarrage de Streamlit (Ctrl+C pour arrêter)..."
	@docker exec -it $(SPARK_NOTEBOOK) streamlit run work/app.py

stop:
	@docker compose -f $(COMPOSE_FILE) stop

restart: stop
	@docker compose -f $(COMPOSE_FILE) up -d

status:
	@docker compose -f $(COMPOSE_FILE) ps

clean:
	@docker compose -f $(COMPOSE_FILE) down

clean-all:
	@echo "[ATTENTION] Suppression totale..."
	@docker compose -f $(COMPOSE_FILE) down -v --rmi all

logs:
	@docker compose -f $(COMPOSE_FILE) logs -f --tail=100

shell:
	@docker exec -it $(SPARK_NOTEBOOK) bash

# --- DONNÉES ---
load-dashboard:
	@echo "[INFO] Configuration HDFS..."
	@docker exec -u root $(SPARK_NOTEBOOK) chmod +x /home/jovyan/work/init_datalake.sh
	@docker exec $(SPARK_NOTEBOOK) /home/jovyan/work/init_datalake.sh
	@echo "[INFO] Lancement ETL..."
	@docker exec $(SPARK_NOTEBOOK) python /home/jovyan/work/etl_batch.py
	@echo "[OK] Données chargées."