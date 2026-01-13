import pandas as pd
import requests
import zipfile
import io
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DATA_URL = "https://eco2mix.rte-france.com/download/eco2mix/eCO2mix_RTE_En-cours-TR.zip"
DATALAKE_PATH = "rte_datalake.parquet"

def inspect_and_fix():
    print("1. TÉLÉCHARGEMENT & INSPECTION BRUTE")
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(DATA_URL, headers=headers, timeout=30, verify=False)
    
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        target = [f for f in z.namelist() if 'xls' in f.lower()][0]
        with z.open(target) as f:
            # Affiche les 5 premières lignes brutes pour voir le séparateur et les headers
            print("\n--- [START] RAW FILE CONTENT (First 5 lines) ---")
            for _ in range(5):
                print(f.readline().decode('cp1252').strip())
            print("--- [END] RAW FILE CONTENT ---\n")
            
            # Rembobinage pour lecture Pandas
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

    print(f"Structure chargée : {df.shape}")
    print(f"Colonnes actuelles : {list(df.columns[:5])} ...")

    # 2. DIAGNOSTIC DU DÉCALAGE
    # On regarde ce qu'il y a dans la colonne 'Nature' (index 1)
    sample_val = df['Nature'].dropna().iloc[0] if not df['Nature'].dropna().empty else ""
    print(f"\nValeur témoin dans 'Nature' : '{sample_val}'")

    is_shifted = False
    if re.match(r'^\d{4}-\d{2}-\d{2}$', str(sample_val)):
        print("⚠️ DÉCALAGE CONFIRMÉ : La colonne 'Nature' contient des dates.")
        is_shifted = True

    # 3. APPLICATION DU CORRECTIF (SANS DOUBLONS)
    if is_shifted:
        print("🛠️ Correction : Réalignement global des colonnes...")
        
        # Liste actuelle des colonnes (ex: ['Périmètre', 'Nature', 'Date', 'Heures', 'Consommation'...])
        cols = df.columns.tolist()
        
        # LOGIQUE : 
        # Le fichier a N colonnes de données, mais N+1 headers (la colonne 'Nature' est vide/absente dans les données)
        # On construit la bonne liste : 
        # 1. On garde 'Périmètre' (index 0)
        # 2. On saute 'Nature' (index 1) qui n'a pas de données correspondantes
        # 3. On prend tout le reste ('Date', 'Heures', 'Conso'...)
        # 4. On ajoute une colonne 'TRASH' à la fin pour combler le trou laissé par le décalage de pandas
        
        new_columns = [cols[0]] + cols[2:] + ['_TRASH_COLUMN']
        
        # Vérification de sécurité taille
        if len(new_columns) == len(df.columns):
            df.columns = new_columns
            print("✅ Headers réassignés avec succès.")
        else:
            print(f"❌ Erreur dimension : Headers calculés ({len(new_columns)}) != Dataframe ({len(df.columns)})")
            return

        # On supprime la colonne poubelle
        df = df.drop(columns=['_TRASH_COLUMN'])

    # 4. FINALISATION
    print("\n--- APERÇU APRÈS CORRECTION ---")
    print(df[['Date', 'Heures', 'Consommation']].head())

    # Traitement Datetime classique
    df = df.dropna(subset=['Date', 'Heures'])
    df['Datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Heures'], format='%Y-%m-%d %H:%M', errors='coerce')
    df = df.dropna(subset=['Datetime']).set_index('Datetime').sort_index()

    # Sauvegarde
    # On filtre les colonnes pour éviter tout autre résidu
    clean_cols = [c for c in df.columns if c not in ['_TRASH_COLUMN']]
    df = df[clean_cols]
    
    df.to_parquet(DATALAKE_PATH)
    print(f"\n✅ Sauvegarde réussie : {DATALAKE_PATH} ({len(df)} lignes)")

if __name__ == "__main__":
    inspect_and_fix()