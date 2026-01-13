import pandas as pd
import requests
import zipfile
import io
import os
import numpy as np
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DATA_URL = "https://eco2mix.rte-france.com/download/eco2mix/eCO2mix_RTE_En-cours-TR.zip"
DATALAKE_PATH = "rte_datalake.parquet"

COLUMNS_MAPPING = {
    'Nucléaire': 'Nucléaire', 'Gaz': 'Gaz', 'Charbon': 'Charbon', 
    'Fioul': 'Fioul', 'Hydraulique': 'Hydraulique', 'Pompage': 'Pompage',
    'Eolien': 'Eolien', 'Solaire': 'Solaire', 'Bioénergies': 'Bioénergies',
    'Consommation': 'Consommation'
}

def download_and_clean():
    print(f"--- DL: {DATA_URL} ---")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36'}
        r = requests.get(DATA_URL, headers=headers, timeout=60, verify=False)
        r.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            target = [f for f in z.namelist() if 'xls' in f.lower() or 'txt' in f.lower()][0]
            with z.open(target) as f:
                # LECTURE INTELLIGENTE (sep=None permet l'autodétection)
                df = pd.read_csv(f, sep=None, encoding='latin-1', skipfooter=1, engine='python')

        df.columns = df.columns.str.strip()
        print(f"Colonnes brutes trouvées : {list(df.columns)}")

        # Construction Date
        if 'Date' in df.columns and 'Heures' in df.columns:
            df['Datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Heures'], dayfirst=True, errors='coerce')
            df = df.dropna(subset=['Datetime']).set_index('Datetime')
        else:
            return pd.DataFrame(), f"ERREUR STRUCTURE: Colonnes Date/Heures introuvables. Colonnes vues: {list(df.columns)}"

        # Nettoyage
        df = df.replace(['ND', 'Nd', 'nd', '-', ''], np.nan)

        # Mapping
        final_df = pd.DataFrame(index=df.index)
        found_cols = []
        for src, dest in COLUMNS_MAPPING.items():
            if src in df.columns:
                final_df[dest] = pd.to_numeric(df[src], errors='coerce')
                found_cols.append(dest)
        
        # LOGIQUE DE SURVIE
        # Si on a trouvé très peu de colonnes, c'est suspect
        if len(found_cols) == 0:
            return pd.DataFrame(), "ERREUR MAPPING: Aucune colonne d'énergie reconnue."

        # Filtrage Consommation (SEULEMENT SI ELLE EXISTE)
        if 'Consommation' in final_df.columns:
            final_df = final_df.dropna(subset=['Consommation'])
        
        final_df = final_df.fillna(0)
        final_df = final_df[~final_df.index.duplicated(keep='last')]

        return final_df.sort_index(), None

    except Exception as e:
        return pd.DataFrame(), f"Exception Technique : {str(e)}"

def update_datalake():
    df_new, error = download_and_clean()
    if df_new.empty: 
        return pd.DataFrame(), f"❌ Echec DL : {error}"

    if os.path.exists(DATALAKE_PATH):
        try:
            df_old = pd.read_parquet(DATALAKE_PATH)
            # Fusion
            df_final = df_new.combine_first(df_old)
        except:
            df_final = df_new
    else:
        df_final = df_new

    # Nettoyage final
    if 'Consommation' in df_final.columns:
        df_final = df_final.dropna(subset=['Consommation'])
        
    df_final = df_final.fillna(0)
    df_final = df_final[~df_final.index.duplicated(keep='last')]
    
    df_final.sort_index().to_parquet(DATALAKE_PATH)
    return df_final, f"✅ OK ({len(df_final)} lignes). Dernier point: {df_final.index.max()}"

def get_data():
    if os.path.exists(DATALAKE_PATH):
        return pd.read_parquet(DATALAKE_PATH)
    return pd.DataFrame()