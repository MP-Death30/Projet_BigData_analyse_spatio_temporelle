#!/usr/bin/env python3
"""
Script de test pour charger les données depuis le fichier Excel
et créer/mettre à jour le datalake RTE
"""
import pandas as pd
import numpy as np
import os

EXCEL_FILE = "Electricité_consommation__production__CO2_et_échanges.xlsx"
DATALAKE_PATH = "rte_datalake.parquet"

def load_from_excel():
    """Charge les données depuis le fichier Excel"""
    print(f"📥 Chargement depuis {EXCEL_FILE}...")
    
    if not os.path.exists(EXCEL_FILE):
        print(f"❌ Fichier {EXCEL_FILE} introuvable!")
        return pd.DataFrame(), "Fichier Excel introuvable"
    
    try:
        # Charger le fichier Excel
        df = pd.read_excel(EXCEL_FILE)
        
        print(f"✅ Fichier chargé: {len(df)} lignes, {len(df.columns)} colonnes")
        print(f"📋 Colonnes: {df.columns.tolist()}")
        
        # Créer la colonne Datetime
        df['Datetime'] = pd.to_datetime(
            df['Date'].astype(str) + ' ' + df['Heures'].astype(str), 
            dayfirst=True, 
            errors='coerce'
        )
        
        # Supprimer les lignes avec datetime invalide
        df = df.dropna(subset=['Datetime'])
        df = df.set_index('Datetime')
        
        # Colonnes d'énergie à extraire
        energy_cols = [
            'Nucléaire', 'Gaz', 'Charbon', 'Fioul', 
            'Hydraulique', 'Eolien', 'Solaire', 'Bioénergies', 
            'Pompage', 'Consommation'
        ]
        
        # Créer le DataFrame final
        final_df = pd.DataFrame(index=df.index)
        
        for col in energy_cols:
            if col in df.columns:
                # Convertir en numérique
                final_df[col] = pd.to_numeric(
                    df[col].replace(['ND', 'Nd', 'nd', '-', ''], np.nan), 
                    errors='coerce'
                )
            else:
                print(f"⚠️  Colonne manquante: {col}")
        
        # Remplir les NaN par 0
        final_df = final_df.fillna(0)
        
        # Supprimer les doublons
        final_df = final_df[~final_df.index.duplicated(keep='last')]
        
        # Trier par index
        final_df = final_df.sort_index()
        
        print(f"✅ Données traitées: {len(final_df)} lignes")
        print(f"📅 Période: {final_df.index.min()} à {final_df.index.max()}")
        print(f"📊 Colonnes finales: {final_df.columns.tolist()}")
        
        return final_df, None
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return pd.DataFrame(), str(e)

def save_to_datalake(df):
    """Sauvegarde les données dans le datalake"""
    if df.empty:
        print("❌ Pas de données à sauvegarder")
        return False
    
    try:
        # Sauvegarder en Parquet
        df.to_parquet(DATALAKE_PATH)
        
        print(f"✅ Datalake sauvegardé: {DATALAKE_PATH}")
        print(f"📊 {len(df)} lignes, {len(df.columns)} colonnes")
        
        # Afficher des statistiques
        print("\n" + "="*60)
        print("📈 STATISTIQUES")
        print("="*60)
        
        for col in df.columns:
            if col != 'Datetime':
                avg = df[col].mean()
                max_val = df[col].max()
                print(f"{col:15s} | Moy: {avg:>10,.0f} MW | Max: {max_val:>10,.0f} MW")
        
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("🔌 CHARGEMENT DES DONNÉES RTE")
    print("="*60 + "\n")
    
    # Charger depuis Excel
    df, error = load_from_excel()
    
    if df.empty:
        print(f"\n❌ Échec: {error}")
        return
    
    # Sauvegarder dans le datalake
    print("\n" + "="*60)
    print("💾 SAUVEGARDE DANS LE DATALAKE")
    print("="*60 + "\n")
    
    success = save_to_datalake(df)
    
    if success:
        print("\n🎉 Opération réussie!")
        print(f"👉 Le fichier {DATALAKE_PATH} est prêt à être utilisé par l'application Streamlit")
    else:
        print("\n❌ Échec de la sauvegarde")

if __name__ == "__main__":
    main()
