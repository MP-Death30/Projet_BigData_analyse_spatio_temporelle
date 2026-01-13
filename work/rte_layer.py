import pandas as pd
import requests
import zipfile
import io
import os
import base64
from datetime import datetime, timedelta

# Configuration
HISTORICAL_URL = "https://www.data.gouv.fr/api/1/datasets/r/1ae6c731-991f-4441-9663-adc99005fac5"
API_TOKEN_URL = "https://digital.iservices.rte-france.com/token/oauth/"
API_DATA_URL = "https://digital.iservices.rte-france.com/open_api/actual_generation/v1/actual_generations_per_production_type"

# --- 1. HISTORIQUE (DATALAKE) ---
def read_csv_flexible(file_obj):
    separators = ['\t', ',', ';']
    content = file_obj.read()
    for sep in separators:
        try:
            file_obj.seek(0)
            df = pd.read_csv(io.BytesIO(content), sep=sep, encoding='latin-1', skipfooter=1, engine='python')
            if 'Nucléaire' in df.columns or 'Nuclear' in df.columns: return df
        except: continue
    return pd.DataFrame()

def get_historical_data():
    try:
        r = requests.get(HISTORICAL_URL, timeout=30, verify=False)
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            target = [f for f in z.namelist() if 'xls' in f.lower() or 'txt' in f.lower()][0]
            with z.open(target) as f:
                df = read_csv_flexible(f)

        df.columns = df.columns.str.strip()
        df['Datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Heures'], format='%Y-%m-%d %H:%M', errors='coerce')
        df = df.dropna(subset=['Datetime']).set_index('Datetime')
        
        cols_map = {'Fioul': 'Fioul', 'Charbon': 'Charbon', 'Gaz': 'Gaz', 'Nucléaire': 'Nucléaire', 
                    'Eolien': 'Eolien', 'Solaire': 'Solaire', 'Hydraulique': 'Hydraulique', 'Bioénergies': 'Bioénergies'}
        available_cols = [c for c in cols_map.keys() if c in df.columns]
        return df[available_cols].replace('ND', 0).fillna(0).astype(float).sort_index(), None
    except Exception as e:
        return pd.DataFrame(), f"Erreur Historique : {str(e)}"

# --- 2. TEMPS RÉEL (API) ---
def get_realtime_data(base64_key):
    if not base64_key: return pd.DataFrame(), "Clé API non générée."
    try:
        # Auth
        headers_auth = {"Authorization": f"Basic {base64_key}", "Content-Type": "application/x-www-form-urlencoded"}
        res_auth = requests.post(API_TOKEN_URL, headers=headers_auth, timeout=10)
        
        if res_auth.status_code == 401:
            return pd.DataFrame(), "Erreur 401 : Identifiants refusés par RTE."
        res_auth.raise_for_status()
        
        token = res_auth.json().get("access_token")

        # Data
        headers_data = {"Authorization": f"Bearer {token}"}
        res_data = requests.get(API_DATA_URL, headers=headers_data, timeout=10)
        res_data.raise_for_status()
        
        records = []
        for prod in res_data.json().get('actual_generations_per_production_type', []):
            ptype = prod['production_type']
            for val in prod['values']:
                records.append({'Datetime': val['start_date'], 'Type': ptype, 'Value': val['value']})
        
        if not records: return pd.DataFrame(), "API connectée mais aucune donnée."

        df = pd.DataFrame(records)
        df['Datetime'] = pd.to_datetime(df['Datetime'], utc=True).dt.tz_convert('Europe/Paris').dt.tz_localize(None)
        df_pivot = df.pivot_table(index='Datetime', columns='Type', values='Value', aggfunc='sum').fillna(0)

        # Mapping Anglais -> Français
        mapping_logique = {
            'Nucléaire': ['NUCLEAR'], 'Gaz': ['FOSSIL_GAS'], 'Charbon': ['FOSSIL_HARD_COAL'],
            'Fioul': ['FOSSIL_OIL'], 'Hydraulique': ['HYDRO_PUMPED_STORAGE', 'HYDRO_RUN_OF_RIVER_AND_POUNDAGE', 'HYDRO_WATER_RESERVOIR'],
            'Eolien': ['WIND_ONSHORE', 'WIND_OFFSHORE'], 'Solaire': ['SOLAR'], 'Bioénergies': ['BIOMASS']
        }

        df_final = pd.DataFrame(index=df_pivot.index)
        for fr_col, eng_cols in mapping_logique.items():
            valid = [c for c in eng_cols if c in df_pivot.columns]
            df_final[fr_col] = df_pivot[valid].sum(axis=1) if valid else 0.0

        return df_final.sort_index(), None
    except Exception as e:
        return pd.DataFrame(), f"Erreur API : {str(e)}"

# --- 3. FUSION ---
def merge_data(client_id=None, client_secret=None):
    """
    Accepte ID et SECRET séparés, les encode, et lance la récupération.
    """
    messages = []
    
    # A. Historique
    df_hist, err_h = get_historical_data()
    if err_h: messages.append(err_h)
    
    # B. API (Avec encodage automatique)
    df_api = pd.DataFrame()
    if client_id and client_secret:
        try:
            # Encodage Base64(ID:Secret)
            auth_str = f"{client_id}:{client_secret}"
            b64_key = base64.b64encode(auth_str.encode()).decode()
            df_api, err_a = get_realtime_data(b64_key)
            if err_a: messages.append(err_a)
        except Exception as e:
            messages.append(f"Erreur encodage clés : {e}")
    
    # C. Fusion
    if df_hist.empty and df_api.empty:
        return pd.DataFrame(), " | ".join(messages)
    
    if df_api.empty: return df_hist, "Historique seul (API échouée ou absente)"
    if df_hist.empty: return df_api, "API seule (Historique échoué)"

    df_combined = pd.concat([df_hist, df_api])
    df_combined = df_combined[~df_combined.index.duplicated(keep='last')].sort_index()
    
    return df_combined, None