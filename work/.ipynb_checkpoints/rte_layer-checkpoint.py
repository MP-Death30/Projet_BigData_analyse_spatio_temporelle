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

def download_and_clean():
    print(f"--- DL: {DATA_URL} ---")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(DATA_URL, headers=headers, timeout=60, verify=False)
        r.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            target = [f for f in z.namelist() if 'xls' in f.lower() or 'csv' in f.lower()][0]
            with z.open(target) as f:
                # Tentative de lecture flexible (séparateur auto ou tab)
                try:
                    df = pd.read_csv(
                        f, 
                        sep=None, 
                        engine='python',
                        encoding='cp1252', 
                        skipfooter=1, 
                        na_values=['ND', 'Nd', 'nd', '-', ''],
                        dtype=str
                    )
                except:
                    f.seek(0)
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

        # --- LOGIQUE DE RÉALIGNEMENT (Si colonne Nature décale tout) ---
        if 'Nature' in df.columns:
            sample_val = df['Nature'].dropna().iloc[0] if not df['Nature'].dropna().empty else ""
            if re.match(r'^\d{4}-\d{2}-\d{2}$', str(sample_val)):
                cols = df.columns.tolist()
                new_columns = [cols[0]] + cols[2:] + ['_TRASH_COLUMN']
                if len(new_columns) == len(df.columns):
                    df.columns = new_columns
                    df = df.drop(columns=['_TRASH_COLUMN'], errors='ignore')

        # --- CONVERSION TEMPORELLE ---
        if 'Date' not in df.columns or 'Heures' not in df.columns:
            return pd.DataFrame(), "ERREUR STRUCTURE: Colonnes Date/Heures manquantes."

        df = df.dropna(subset=['Date', 'Heures'])
        df['Datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Heures'], format='%Y-%m-%d %H:%M', errors='coerce')
        df = df.dropna(subset=['Datetime']).set_index('Datetime').sort_index()

        # --- CONVERSION NUMÉRIQUE (TOUTES COLONNES) ---
        # On ne filtre plus via une liste blanche restreinte. On garde tout ce qui est numérique.
        cols_metadata = ['Date', 'Heures', 'Nature', 'Périmètre']
        cols_to_convert = [c for c in df.columns if c not in cols_metadata]
        
        for col in cols_to_convert:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        final_df = df.select_dtypes(include=[np.number])

        # Nettoyage doublons index
        final_df = final_df[~final_df.index.duplicated(keep='last')]

        # --- FILTRAGE ---
        if 'Consommation' in final_df.columns:
            final_df = final_df.dropna(subset=['Consommation'])
            final_df = final_df[final_df['Consommation'] >= 1]
            
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
            # Fusion intelligente : on garde les colonnes existantes et nouvelles
            df_final = df_new.combine_first(df_old)
        except:
            df_final = df_new
    else:
        df_final = df_new

    # Nettoyage final
    if 'Consommation' in df_final.columns:
        df_final = df_final[df_final['Consommation'] >= 1]
        
    df_final = df_final.fillna(0)
    df_final = df_final[~df_final.index.duplicated(keep='last')]
    
    # Sauvegarde
    df_final.sort_index().to_parquet(DATALAKE_PATH)
    
    last_date = df_final.index.max()
    nb_cols = len(df_final.columns)
    return df_final, f"✅ OK ({len(df_final)} lignes, {nb_cols} cols). Dernier point : {last_date}"

def get_data():
    if os.path.exists(DATALAKE_PATH):
        return pd.read_parquet(DATALAKE_PATH)
    return pd.DataFrame()