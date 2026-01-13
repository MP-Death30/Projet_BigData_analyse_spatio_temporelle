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
    print(f"--- TÉLÉCHARGEMENT : {DATA_URL} ---")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36'}
        r = requests.get(DATA_URL, headers=headers, timeout=60, verify=False)
        r.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            target = [f for f in z.namelist() if 'xls' in f.lower() or 'txt' in f.lower()][0]
            with z.open(target) as f:
                df = pd.read_csv(f, sep='\t', encoding='latin-1', skipfooter=1, engine='python')

        df.columns = df.columns.str.strip()

        # Index Temporel
        if 'Date' in df.columns and 'Heures' in df.columns:
            df['Datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Heures'], dayfirst=True, errors='coerce')
            df = df.dropna(subset=['Datetime']).set_index('Datetime')
        else:
            return pd.DataFrame(), "Structure invalide (Pas de colonnes Date/Heures)."

        # 1. Remplacement ND -> NaN
        df = df.replace(['ND', 'Nd', 'nd', '-', ''], np.nan)

        # 2. Extraction et Conversion
        final_df = pd.DataFrame(index=df.index)
        for src, dest in COLUMNS_MAPPING.items():
            if src in df.columns:
                final_df[dest] = pd.to_numeric(df[src], errors='coerce')

        # 3. STRATÉGIE "ZÉRO DÉFAUT" (Au lieu de supprimer)
        # On remplit les trous par 0 pour permettre l'affichage graphique
        # On ne supprime la ligne que si TOUTES les valeurs sont vides
        final_df = final_df.dropna(how='all')
        final_df = final_df.fillna(0)
        
        print(f"Succès : {len(final_df)} lignes récupérées.")
        return final_df.sort_index(), None

    except Exception as e:
        import traceback
        traceback.print_exc()
        return pd.DataFrame(), f"Erreur Technique : {str(e)}"

def update_datalake():
    df_new, error = download_and_clean()
    if df_new.empty: return pd.DataFrame(), f"❌ Echec DL : {error}"

    if os.path.exists(DATALAKE_PATH):
        try:
            df_old = pd.read_parquet(DATALAKE_PATH)
        except:
            df_old = pd.DataFrame()
    else:
        df_old = pd.DataFrame()

    if not df_old.empty:
        df_final = df_new.combine_first(df_old)
    else:
        df_final = df_new

    # Nettoyage final avant sauvegarde
    df_final = df_final.fillna(0)
    df_final.sort_index().to_parquet(DATALAKE_PATH)
    
    return df_final, f"✅ Données chargées ({len(df_final)} lignes)."

def get_data():
    if os.path.exists(DATALAKE_PATH):
        return pd.read_parquet(DATALAKE_PATH)
    return pd.DataFrame()