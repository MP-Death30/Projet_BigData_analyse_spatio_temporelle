# 🌍 Dashboard Big Data : Analyse Spatio-Temporelle & Énergétique

Plateforme conteneurisée combinant HDFS (Stockage), Spark (Traitement distribué) et Streamlit (Visualisation).

## 🏗️ Architecture

| Composant | Technologie | Port | Rôle |
| :--- | :--- | :--- | :--- |
| **Frontend** | Streamlit | `8501` | Interface utilisateur interactive |
| **Processing** | Apache Spark 3.3 | `8080` | Calcul distribué (Master/Workers) |
| **Stockage** | Hadoop HDFS 3.2 | `9870` | Datalake (Raw & Processed Zones) |
| **Dev** | JupyterLab | `8888` | Environnement de prototypage |

---

## 🚀 Protocole de Démarrage

### 1. Prérequis
* **Docker Desktop** (Engine actif)
* **Make** (Standard sur Linux/Mac. Sur Windows : utiliser WSL ou installer Make pour Windows)
* **Git**

### 2. Installation & Lancement
L'intégralité du cycle de vie est gérée via le `Makefile`. Ne lancez pas de commandes `docker` manuellement.

**Initialisation complète (Build + Start + Wait) :**
``` bash
make init
```

*Cette commande construit les images, lance les conteneurs et attend la stabilisation des services.*

### 3. Ingestion des Données (ETL)

Le Dashboard nécessite des données initialisées dans HDFS pour fonctionner.

**A. Module NYC Air Quality (Batch processing)**
Initialise l'arborescence HDFS et lance le job Spark de traitement des historiques météo/pollution.
``` bash
make load-dashboard
```
*Sortie attendue : "✅ Données Batch disponibles dans /processed/dashboard/"*

**B. Module RTE (Énergie)**
Les données RTE se chargent directement depuis l'interface graphique pour garantir la fraîcheur.
1.  Ouvrir le Dashboard (voir section Accès).
2.  Aller dans le menu **RTE Production**.
3.  Cliquer sur **"🔄 Actualiser depuis RTE (National)"** pour initialiser le Datalake.
4.  (Optionnel) Cliquer sur **"🗺️ Charger Données Régionales"**.

---

## 🖥️ Accès aux Interfaces

| Service | URL |
| :--- | :--- |
| **Dashboard App** | [http://localhost:8501](http://localhost:8501) |
| **Spark Master** | [http://localhost:8080](http://localhost:8080) |
| **HDFS Explorer** | [http://localhost:9870](http://localhost:9870) |
| **Jupyter Lab** | [http://localhost:8888](http://localhost:8888) |

---

## 🛠️ Commandes de Maintenance

| Objectif | Commande | Description |
| :--- | :--- | :--- |
| **Arrêter** | ```` make stop ```` | Stoppe les conteneurs sans suppression |
| **Redémarrer** | ```` make restart ```` | Redémarrage complet des services |
| **Logs** | ```` make logs ```` | Affiche les logs en temps réel |
| **Shell Spark** | ```` make shell-spark ```` | Ouvre un terminal dans le conteneur de traitement |
| **Nettoyage HDFS** | ```` make clean-hdfs ```` | ⚠️ Supprime toutes les données du Datalake |
| **Reset Total** | ```` make clean-all ```` | ⚠️ Supprime conteneurs, images et volumes |

## 📂 Structure des Données HDFS

* `/user/mathis/datalake/raw/` : Données brutes (CSV, JSON RTE).
* `/user/mathis/datalake/processed/dashboard/` : Données optimisées (Parquet) pour l'affichage.
    * `air_quality.parquet`
    * `weather.parquet`