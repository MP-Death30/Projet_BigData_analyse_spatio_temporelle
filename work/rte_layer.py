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
LOCAL_FILE = "rte_datalake.parquet"

def download_and_clean():
    print(f"--- DL: {DATA_URL} ---")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(DATA_URL, headers=headers, timeout=60, verify=False)
        r.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            target = [f for f in z.namelist() if 'xls' in f.lower() or 'csv' in f.lower()][0]
            with z.open(target) as f:
                try:
                    df = pd.read_csv(f, sep=None, engine='python', encoding='cp1252', skipfooter=1, na_values=['ND', 'Nd', 'nd', '-', ''], dtype=str)
                except:
                    f.seek(0)
                    df = pd.read_csv(f, sep='\t', encoding='cp1252', skipfooter=1, engine='python', na_values=['ND', 'Nd', 'nd', '-', ''], dtype=str)

        df.columns = df.columns.str.strip()
        # Réalignement colonnes
        if 'Nature' in df.columns:
            sample_val = df['Nature'].dropna().iloc[0] if not df['Nature'].dropna().empty else ""
            if re.match(r'^\d{4}-\d{2}-\d{2}$', str(sample_val)):
                cols = df.columns.tolist()
                new_columns = [cols[0]] + cols[2:] + ['_TRASH_COLUMN']
                if len(new_columns) == len(df.columns):
                    df.columns = new_columns
                    df = df.drop(columns=['_TRASH_COLUMN'], errors='ignore')

        if 'Date' not in df.columns or 'Heures' not in df.columns:
            return pd.DataFrame(), "ERREUR STRUCTURE"

        df = df.dropna(subset=['Date', 'Heures'])
        df['Datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Heures'], format='%Y-%m-%d %H:%M', errors='coerce')
        df = df.dropna(subset=['Datetime']).set_index('Datetime').sort_index()

        cols_metadata = ['Date', 'Heures', 'Nature', 'Périmètre']
        cols_to_convert = [c for c in df.columns if c not in cols_metadata]
        for col in cols_to_convert:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        final_df = df.select_dtypes(include=[np.number])
        final_df = final_df[~final_df.index.duplicated(keep='last')]
        
        if 'Consommation' in final_df.columns:
            final_df = final_df[final_df['Consommation'] >= 1]
            
        final_df = final_df.fillna(0)
        return final_df, None

    except Exception as e:
        return pd.DataFrame(), f"Exception : {str(e)}"

def get_latest_data():
    """Télécharge et renvoie le DataFrame Pandas nettoyé."""
    df, msg = download_and_clean()
    return df, msg