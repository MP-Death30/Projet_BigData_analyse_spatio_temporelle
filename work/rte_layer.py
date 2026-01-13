import pandas as pd
import requests
import zipfile
import io
import os
import numpy as np
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DATA_URL = "https://eco2mix.rte-france.com/download/eco2mix/eCO2mix_RTE_En-cours-TR.zip"
DATALAKE_PATH = "rte_datalake.parquet"

# Mapping aligné sur les colonnes RÉELLES
COLUMNS_MAPPING = {
    'Nucléaire': 'Nucléaire',
    'Gaz': 'Gaz',
    'Charbon': 'Charbon', 
    'Fioul': 'Fioul',
    'Hydraulique': 'Hydraulique',
    'Pompage': 'Pompage',
    'Eolien': 'Eolien',
    'Solaire': 'Solaire',
    'Bioénergies': 'Bioénergies',
    'Consommation': 'Consommation'
}

def download_and_clean():
    print(f"--- DL: {DATA_URL} ---")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(DATA_URL, headers=headers, timeout=60, verify=False)
        r.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            target = [f for f in z.namelist() if 'xls' in f.lower()][0]
            with z.open(target) as f:
                # Lecture brute pour sécuriser le typage
                df = pd.read_csv(
                    f, 
                    sep='\t', 
                    encoding='cp1252', 
                    skipfooter=1, 
                    engine='python',
                    na_values=['ND', 'Nd', 'nd', '-', ''],
                    dtype=str
                )

        # Nettoyage des noms de colonnes
        df.columns = df.columns.str.strip()

        # --- 1. LOGIQUE DE RÉALIGNEMENT (Si décalage détecté) ---
        if 'Nature' in df.columns:
            sample_val = df['Nature'].dropna().iloc[0] if not df['Nature'].dropna().empty else ""
            if re.match(r'^\d{4}-\d{2}-\d{2}$', str(sample_val)):
                print("⚠️ DÉCALAGE DÉTECTÉ : Réalignement des colonnes...")
                cols = df.columns.tolist()
                # On saute la colonne 'Nature' (vide) et on décale tout vers la gauche
                new_columns = [cols[0]] + cols[2:] + ['_TRASH_COLUMN']
                
                if len(new_columns) == len(df.columns):
                    df.columns = new_columns
                    df = df.drop(columns=['_TRASH_COLUMN'], errors='ignore')

        # --- 2. CONVERSION TEMPORELLE ---
        df = df.dropna(subset=['Date', 'Heures'])
        df['Datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Heures'], format='%Y-%m-%d %H:%M', errors='coerce')
        df = df.dropna(subset=['Datetime']).set_index('Datetime').sort_index()

        # --- 3. CONVERSION NUMÉRIQUE & MAPPING ---
        final_df = pd.DataFrame(index=df.index)
        found_cols = []
        
        for src, dest in COLUMNS_MAPPING.items():
            if src in df.columns:
                final_df[dest] = pd.to_numeric(df[src], errors='coerce')
                found_cols.append(dest)
        
        if not found_cols:
            return pd.DataFrame(), "ERREUR MAPPING: Aucune colonne d'énergie trouvée."

        # Nettoyage doublons index
        final_df = final_df[~final_df.index.duplicated(keep='last')]

        # --- 4. FILTRAGE ---
        # A. On ne garde que le passé (pour éviter les ND prévisionnels futurs)
        now = pd.Timestamp.now()
        final_df = final_df[final_df.index <= now]

        # B. Filtre de qualité sur la Consommation
        if 'Consommation' in final_df.columns:
            # On supprime les lignes où la conso est NaN (ND)
            final_df = final_df.dropna(subset=['Consommation'])
            # On supprime les lignes où la conso est < 1 (Valeurs aberrantes ou nulles)
            final_df = final_df[final_df['Consommation'] >= 1]
            
        # C. Remplissage des trous restants (sur les autres colonnes)
        final_df = final_df.fillna(0)

        return final_df, None

    except Exception as e:
        return pd.DataFrame(), f"Exception Technique : {str(e)}"

def update_datalake():
    df_new, error = download_and_clean()
    if df_new.empty: 
        return pd.DataFrame(), f"❌ Echec DL : {error}"

    if os.path.exists(DATALAKE_PATH):
        try:
            df_old = pd.read_parquet(DATALAKE_PATH)
            # Fusion : df_new écrase df_old sur les périodes communes
            df_final = df_new.combine_first(df_old)
        except:
            df_final = df_new
    else:
        df_final = df_new

    # --- SÉCURITÉ PARQUET ---
    # Filtrage strict des colonnes pour éviter les crashs PyArrow (types mixtes)
    allowed_cols = list(COLUMNS_MAPPING.values())
    df_final = df_final[df_final.columns.intersection(allowed_cols)]

    # Nettoyage final
    if 'Consommation' in df_final.columns:
        df_final = df_final[df_final['Consommation'] >= 1]
        
    df_final = df_final.fillna(0)
    df_final = df_final[~df_final.index.duplicated(keep='last')]
    
    # Sauvegarde
    df_final.sort_index().to_parquet(DATALAKE_PATH)
    
    last_date = df_final.index.max()
    return df_final, f"✅ OK ({len(df_final)} lignes). Dernier point : {last_date}"

def get_data():
    if os.path.exists(DATALAKE_PATH):
        return pd.read_parquet(DATALAKE_PATH)
    return pd.DataFrame()