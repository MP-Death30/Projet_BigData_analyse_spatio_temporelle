# 🔌 Projet Big Data - Analyse Spatio-Temporelle
## Modifications du Module RTE Production

---

## 📋 Modifications Apportées

### 1. **Graphique Amélioré** ✅
Le graphique dans `app.py` affiche maintenant **toutes les sources d'énergie** :

**Avant :**
- Affichait uniquement la consommation générale
- Graphique simple avec `px.area`

**Après :**
- ⚛️ **Nucléaire** (Jaune or)
- 💧 **Hydraulique** (Bleu)
- 🌀 **Éolien** (Vert lime)
- ☀️ **Solaire** (Orange foncé)
- 🔥 **Gaz** (Rouge tomate)
- 🌱 **Bioénergies** (Marron)
- ⚫ **Charbon** (Gris foncé)
- 🛢️ **Fioul** (Rouge foncé)
- ⚡ **Pompage** (Bleu royal)
- 📈 **Consommation** (Ligne noire en surimpression)

### 2. **Statistiques Détaillées** 📊
Ajout d'une section complète avec :
- Production moyenne par source
- Production maximale par source
- Part de chaque source dans le mix (%)
- Distinction énergies renouvelables vs fossiles

### 3. **Palette de Couleurs Optimisée** 🎨
Couleurs plus vives et contrastées pour une meilleure lisibilité du graphique empilé.

### 4. **Script de Chargement** 🔧
Nouveau script `load_excel_to_datalake.py` pour charger facilement les données depuis Excel.

---

## 🚀 Utilisation

### Démarrer l'Application Streamlit

```bash
cd work/
streamlit run app.py
```

L'application propose 2 modes :
1. **NYC Air Quality** - Analyse de la qualité de l'air à New York
2. **RTE Production** - Analyse de la production électrique en France ⚡

### Charger de Nouvelles Données

Si vous avez un nouveau fichier Excel RTE :

```bash
# 1. Placer le fichier Excel dans le dossier work/
cp /chemin/vers/fichier.xlsx work/Electricité_consommation__production__CO2_et_échanges.xlsx

# 2. Exécuter le script de chargement
cd work/
python3 load_excel_to_datalake.py
```

Le script va :
- ✅ Charger le fichier Excel
- ✅ Extraire toutes les colonnes d'énergie
- ✅ Créer/mettre à jour le datalake (`rte_datalake.parquet`)
- ✅ Afficher les statistiques

---

## 📊 Données Disponibles

### Format du Fichier Excel Attendu

Le fichier doit contenir les colonnes suivantes :
- `Date` : Date au format JJ/MM/AAAA
- `Heures` : Heure au format HH:MM
- `Consommation` : Consommation totale (MW)
- `Nucléaire` : Production nucléaire (MW)
- `Hydraulique` : Production hydraulique (MW)
- `Eolien` : Production éolienne (MW)
- `Solaire` : Production solaire (MW)
- `Gaz` : Production au gaz (MW)
- `Charbon` : Production au charbon (MW)
- `Fioul` : Production au fioul (MW)
- `Bioénergies` : Production bioénergies (MW)
- `Pompage` : Stockage par pompage (MW, négatif)

### Données Actuelles

**Période :** 01/01/2025 - 01/12/2026  
**Points de données :** 14,976 lignes (mesures toutes les 15 minutes)

**Production moyenne :**
- Nucléaire : 42,321 MW (83.9%)
- Hydraulique : 6,842 MW (13.6%)
- Éolien : 5,757 MW (11.4%)
- Solaire : 3,304 MW (6.6%)
- Gaz : 2,014 MW (4.0%)
- Bioénergies : 944 MW (1.9%)

**Énergies renouvelables :** 27.9% du mix  
**Énergies fossiles :** 3.6% du mix

---

## 📁 Structure des Fichiers

```
work/
├── app.py                                    # Application Streamlit (MODIFIÉ)
├── rte_layer.py                              # Module de gestion RTE
├── load_excel_to_datalake.py                 # Script de chargement (NOUVEAU)
├── rte_datalake.parquet                      # Datalake RTE
├── Electricité_consommation_...xlsx          # Fichier Excel source
├── dashboard_data_air.parquet                # Données NYC Air
├── dashboard_data_weather.parquet            # Données NYC Weather
└── dashboard_map.geojson                     # Carte NYC
```

---

## 🎯 Fonctionnalités du Dashboard RTE

### Vue Principale
- **KPIs en temps réel** : Production totale, Consommation, Nucléaire
- **Graphique interactif** : Mix énergétique avec toutes les sources empilées
- **Ligne de consommation** : En noir, superposée sur la production

### Statistiques Détaillées
- **Production moyenne** par source d'énergie
- **Production maximale** atteinte pour chaque source
- **Part dans le mix** (pourcentage) pour chaque source

### Analyse Énergétique
- 🌱 **Énergies Renouvelables** : Production et part du mix
- 🏭 **Énergies Fossiles** : Production et part du mix

### Graphique Circulaire (Donut)
- Répartition instantanée du mix énergétique
- Visible dans la barre latérale

---

## 🔧 Dépendances

```bash
# Déjà installées dans l'environnement Docker
streamlit
pandas
geopandas
folium
streamlit-folium
plotly
numpy
pyarrow  # Pour lire les fichiers Parquet
openpyxl  # Pour lire les fichiers Excel
```

---

## 💡 Conseils d'Utilisation

### Navigation
- Utilisez la **barre latérale** pour basculer entre NYC et RTE
- Le bouton **"Forcer Mise à jour"** télécharge les dernières données RTE

### Interaction avec le Graphique
- **Zoom** : Sélectionnez une zone avec la souris
- **Pan** : Déplacez-vous dans le graphique
- **Légende** : Cliquez sur une source pour la masquer/afficher
- **Hover** : Survolez pour voir les valeurs exactes

### Performance
- L'application charge **~15,000 points** : temps de chargement ~2-3 secondes
- Le graphique interactif Plotly permet une navigation fluide
- Les données sont mises en cache par Streamlit

---

## 🐛 Résolution de Problèmes

### Le graphique n'affiche aucune donnée
```bash
# Vérifier l'existence du datalake
ls -lh rte_datalake.parquet

# Recharger les données depuis Excel
python3 load_excel_to_datalake.py
```

### Erreur "Unable to find a usable engine"
```bash
# Installer pyarrow
pip install pyarrow --break-system-packages
```

### Le fichier Excel n'est pas reconnu
- Vérifiez que le fichier contient les colonnes `Date` et `Heures`
- Vérifiez que les colonnes d'énergie sont nommées correctement
- Le script affiche les colonnes trouvées pour diagnostic

---

## 📈 Améliorations Futures Possibles

- [ ] Export des graphiques en PDF/PNG
- [ ] Comparaison multi-périodes
- [ ] Prévisions avec Machine Learning
- [ ] Alertes sur seuils de production/consommation
- [ ] Analyse de la corrélation météo/production
- [ ] Calcul automatique des émissions CO2
- [ ] API REST pour accès aux données

---

## 📝 Changelog

### Version 2.0 (Janvier 2026)
- ✅ Graphique avec toutes les sources d'énergie
- ✅ Statistiques détaillées par source
- ✅ Distinction renouvelables vs fossiles
- ✅ Palette de couleurs optimisée
- ✅ Script de chargement depuis Excel
- ✅ Documentation complète

### Version 1.0 (Original)
- Graphique simple avec consommation uniquement
- Application NYC Air Quality

---

## 👥 Support

Pour toute question ou problème :
1. Vérifiez ce README
2. Consultez les logs de Streamlit
3. Vérifiez le contenu du datalake avec le script de test

---

**🎉 Profitez de votre tableau de bord énergétique amélioré !**
