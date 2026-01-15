# 🌍 Dashboard Big Data : Analyse Spatio-Temporelle

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Spark](https://img.shields.io/badge/Apache%20Spark-3.5-orange)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30-red)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)

Ce projet est une plateforme d'analyse de données Big Data combinant traitement distribué (Spark) et visualisation interactive (Streamlit). Il démontre l'intégration d'un Datalake (HDFS) avec une application front-end pour l'analyse de données environnementales et énergétiques.

## 🚀 Fonctionnalités

Le dashboard propose deux modules d'analyse distincts :

### 1. 🗽 NYC Air Quality (Batch Processing)
Analyse historique de la qualité de l'air à New York croisée avec les données météorologiques.
* **Cartographie interactive** : Visualisation des niveaux de pollution par quartier (Choropleth map).
* **Croisement de données** : Corrélation entre polluants (Ozone, PM2.5, etc.) et météo (Vent, Température).
* **Calcul distribué** : Agrégations spatiales complexes réalisées via PySpark.

### 2. ⚡ RTE Production (Speed Layer / Ingestion)
Suivi en quasi-temps réel du mix énergétique français (données éCO2mix).
* **Pipeline ETL** : Ingestion automatique depuis l'API RTE vers HDFS (format Parquet).
* **Visualisation** : Graphiques de production par filière, échanges frontaliers et mix énergétique.
* **Architecture** : Mise à jour incrémentale du Datalake.

---

## 🛠️ Architecture Technique

Le projet repose sur une stack conteneurisée via Docker :

| Service | Rôle | Port Accessible |
| :--- | :--- | :--- |
| **Spark Master** | Gestionnaire de cluster Spark | `8080` (Web UI) |
| **Spark Worker** | Exécution des tâches distribuées | `8081` |
| **HDFS (Namenode)** | Stockage distribué (Datalake) | `9870` |
| **Jupyter/App** | Environnement de dév & Streamlit | `8888` (Lab) / `8501` (App) |

---

## 📋 Prérequis

Avant de lancer le projet, assurez-vous d'avoir installé :
* **Docker Desktop** (avec le moteur Docker en cours d'exécution).
* **Git**.

---

## ⚙️ Installation et Démarrage

Nous utilisons un `Makefile` pour simplifier les commandes Docker.

### 1. Cloner le projet
``` bash
git clone [https://github.com/VOTRE_UTILISATEUR/projet_bigdata_analyse_spatio_temporelle.git](https://github.com/VOTRE_UTILISATEUR/projet_bigdata_analyse_spatio_temporelle.git)
cd projet_bigdata_analyse_spatio_temporelle
```

### 2. Installation Automatisée
Cette commande construit les images Docker, lance les conteneurs et initialise les données (ETL).
* **Sous Linux / Mac :**
    ``` bash
    make init
    ```
* **Sous Windows (PowerShell) :**
    ``` powershell
    .\make init
    ```
    *(Cela va exécuter `build-images.sh`, lancer `docker-compose up`, et exécuter les scripts d'initialisation dans le conteneur)*

### 3. Accéder à l'application
Une fois l'installation terminée (message "✅ INSTALLATION TERMINÉE"), ouvrez votre navigateur :

* 📊 **Dashboard Streamlit :** [http://localhost:8501](http://localhost:8501)
* 📓 **Jupyter Lab :** [http://localhost:8888](http://localhost:8888)
* 🐘 **Spark Master UI :** [http://localhost:8080](http://localhost:8080)

---

## 🕹️ Commandes Utiles

| Action | Commande (Linux/Mac) | Commande (Windows) |
| :--- | :--- | :--- |
| **Démarrer** (sans réinstaller) | `make start` | `.\make start` |
| **Arrêter** les services | `make stop` | `.\make stop` |
| **Redémarrer** (Reset rapide) | `make restart` | `.\make restart` |
| **Nettoyer** (Suppr. conteneurs) | `make clean` | `.\make clean` |
| **Shell** (Entrer dans le container) | `make shell` | `docker exec -it pyspark_notebook bash` |

---

## 📂 Structure du Projet

```
📦 projet_bigdata
 ┣ 📂 docker             # Fichiers de configuration des images Docker
 ┣ 📂 work               # Code source (monté dans le conteneur)
 ┃ ┣ 📜 app.py           # Point d'entrée de l'application Streamlit
 ┃ ┣ 📜 etl_batch.py     # Script ETL pour les données Batch
 ┃ ┣ 📜 rte_layer.py     # Connecteur API RTE
 ┃ ┗ 📂 data             # Données brutes (CSV/JSON)
 ┣ 📜 docker-compose.yml # Orchestration des services
 ┣ 📜 Makefile           # Automatisation des commandes
 ┗ 📜 README.md          # Documentation
```

---

## ⚠️ Dépannage (Troubleshooting)

**Erreur : `JavaPackage object is not callable` ou `ConnectionRefused`**
* Cela arrive si la session Spark est corrompue.
* **Solution :** Cliquez sur le bouton **"🛑 Arrêter le Dashboard"** dans la barre latérale de l'application, ou lancez `make restart`. L'application redémarrera proprement la JVM.

**Erreur : `Hadoop/HDFS connection refused`**
* Assurez-vous que le conteneur `namenode` est bien en cours d'exécution via `docker ps`.
