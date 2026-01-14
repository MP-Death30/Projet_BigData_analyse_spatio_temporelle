import pandas as pd
import requests
import urllib3
import json
from datetime import datetime, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# API Open Data RTE - Données régionales
REGIONAL_DATA_URL = "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-regional-tr/records"
LOCAL_REGIONAL_FILE = "rte_datalake_regional.parquet"

# Liste des régions françaises
REGIONS = [
    'Auvergne-Rhône-Alpes',
    'Bourgogne-Franche-Comté',
    'Bretagne',
    'Centre-Val de Loire',
    'Corse',
    'Grand Est',
    'Hauts-de-France',
    'Île-de-France',
    'Normandie',
    'Nouvelle-Aquitaine',
    'Occitanie',
    'Pays de la Loire',
    "Provence-Alpes-Côte d'Azur"
]

def download_and_clean_regional():
    """
    Télécharge et nettoie les données régionales depuis l'API Open Data RTE
    Suit la même logique que download_and_clean() de rte_layer.py
    """
    print(f"--- DL Regional: {REGIONAL_DATA_URL} ---")
    try:
        # Paramètres de requête (derniers 7 jours, limite augmentée)
        params = {
            'limit': 100,  # Maximum par requête
            'offset': 0,
            'order_by': 'date_heure DESC',
            'timezone': 'Europe/Paris'
        }
        
        all_records = []
        max_requests = 50  # Limiter à ~5000 enregistrements (50 x 100)
        
        print(f"Récupération des données régionales...")
        
        # Pagination pour récupérer plus de données
        for i in range(max_requests):
            params['offset'] = i * 100
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            r = requests.get(REGIONAL_DATA_URL, params=params, headers=headers, timeout=30, verify=False)
            r.raise_for_status()
            
            data = r.json()
            
            if 'results' not in data or len(data['results']) == 0:
                break  # Plus de données
            
            all_records.extend(data['results'])
            
            # Afficher progression
            if (i + 1) % 10 == 0:
                print(f"  Récupérés: {len(all_records)} enregistrements...")
            
            # Si on a moins de 100 résultats, c'est la dernière page
            if len(data['results']) < 100:
                break
        
        print(f"Total récupéré: {len(all_records)} enregistrements")
        
        if not all_records:
            return pd.DataFrame(), "Aucune donnée disponible"
        
        # Normaliser les données JSON en DataFrame
        df = pd.json_normalize(all_records)
        
        # Identifier les colonnes importantes
        # Structure typique: date_heure, libelle_region, code_insee_region, 
        # nucleaire, eolien, solaire, hydraulique, pompage, bioenergies, 
        # thermique, gaz, charbon, fioul, consommation, etc.
        
        # Renommer les colonnes pour cohérence avec le format national
        column_mapping = {
            'date_heure': 'Datetime',
            'libelle_region': 'Region',
            'code_insee_region': 'Code_Region',
            'nucleaire': 'Nucléaire',
            'eolien': 'Eolien',
            'solaire': 'Solaire',
            'hydraulique': 'Hydraulique',
            'pompage': 'Pompage',
            'bioenergies': 'Bioénergies',
            'gaz': 'Gaz',
            'charbon': 'Charbon',
            'fioul': 'Fioul',
            'consommation': 'Consommation',
            'ech_physiques': 'Ech. physiques',
            'stockage_batterie': 'Stockage batterie',
            'destockage_batterie': 'Déstockage batterie',
            'eolien_terrestre': 'Eolien terrestre',
            'eolien_offshore': 'Eolien offshore',
            'tco_thermique': 'Taux de Co2',
            'tch_thermique': 'Taux de CH4',
            'tso2_thermique': 'Taux de SO2'
        }
        
        # Appliquer le mapping (seulement pour les colonnes qui existent)
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
        
        # Convertir Datetime
        if 'Datetime' in df.columns:
            df['Datetime'] = pd.to_datetime(df['Datetime'], errors='coerce')
            df = df.dropna(subset=['Datetime'])
            df = df.set_index('Datetime').sort_index()
        else:
            return pd.DataFrame(), "ERREUR: Colonne date_heure manquante"
        
        # Garder uniquement les colonnes numériques + Region
        cols_to_keep = ['Region', 'Code_Region']
        numeric_cols = []
        
        for col in df.columns:
            if col in cols_to_keep:
                continue
            try:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                numeric_cols.append(col)
            except:
                pass
        
        # Sélectionner colonnes finales
        final_cols = [c for c in cols_to_keep if c in df.columns] + numeric_cols
        final_df = df[final_cols]
        
        # Supprimer les doublons (garder le plus récent)
        final_df = final_df[~final_df.index.duplicated(keep='last')]
        
        # Remplir les NaN avec 0 pour les colonnes numériques
        for col in numeric_cols:
            final_df[col] = final_df[col].fillna(0)
        
        print(f"✓ Données nettoyées: {len(final_df)} lignes, {len(final_df.columns)} colonnes")
        print(f"  Période: {final_df.index.min()} → {final_df.index.max()}")
        print(f"  Régions: {final_df['Region'].nunique() if 'Region' in final_df.columns else 'N/A'}")
        
        return final_df, None
        
    except Exception as e:
        print(f"ERREUR: {str(e)}")
        return pd.DataFrame(), f"Exception : {str(e)}"

def get_latest_regional_data():
    """
    Télécharge et renvoie le DataFrame Pandas des données régionales
    Équivalent à get_latest_data() de rte_layer.py
    """
    df, msg = download_and_clean_regional()
    return df, msg

def get_available_regions(df):
    """
    Retourne la liste des régions disponibles dans le DataFrame
    """
    if df.empty or 'Region' not in df.columns:
        return []
    return sorted(df['Region'].unique().tolist())

def filter_by_region(df, region_name):
    """
    Filtre le DataFrame pour une région spécifique
    """
    if df.empty or 'Region' not in df.columns:
        return pd.DataFrame()
    
    if region_name == "France entière":
        # Agréger toutes les régions
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        aggregated = df.groupby(df.index)[numeric_cols].sum()
        return aggregated
    else:
        # Filtrer par région
        return df[df['Region'] == region_name]

def get_regional_summary(df):
    """
    Génère un résumé par région (dernière valeur)
    Retourne un DataFrame avec une ligne par région
    """
    if df.empty or 'Region' not in df.columns:
        return pd.DataFrame()
    
    # Prendre la dernière valeur pour chaque région
    latest_data = []
    
    for region in df['Region'].unique():
        region_data = df[df['Region'] == region]
        if not region_data.empty:
            last_row = region_data.iloc[-1]
            latest_data.append(last_row)
    
    summary_df = pd.DataFrame(latest_data)
    return summary_df.reset_index(drop=True)
