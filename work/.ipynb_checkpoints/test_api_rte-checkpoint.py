import requests
import base64
import json

# --- CONFIGURATION A REMPLIR ---
CLIENT_ID = "869d4b99-5a54-4369-aef6-6a7ca2950116"       # Remplacez par votre ID
CLIENT_SECRET = "541f23c1-b7cd-4666-9ea1-68c8cb35e349" # Remplacez par votre Secret
# -------------------------------

TOKEN_URL = "https://digital.iservices.rte-france.com/token/oauth/"
DATA_URL = "https://digital.iservices.rte-france.com/open_api/actual_generation/v1/actual_generations_per_production_type"

def test_api():
    print("--- TEST API RTE ---")
    
    # 1. Encodage Base64
    if "VOTRE" in CLIENT_ID:
        # Cas où l'utilisateur n'a pas mis ses clés, on demande une saisie manuelle
        print("Clés non configurées dans le script.")
        id_secret_b64 = input("Entrez votre clé Base64 (Format 'Basic XXXXX') ou juste la chaîne Base64 : ").replace("Basic ", "")
    else:
        auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
        id_secret_b64 = base64.b64encode(auth_str.encode()).decode()
        print(f"Clés encodées : {id_secret_b64[:10]}...")

    # 2. Authentification (Récupération du Token)
    print("\n1. Demande de Token...")
    headers_auth = {
        "Authorization": f"Basic {id_secret_b64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        res_auth = requests.post(TOKEN_URL, headers=headers_auth, timeout=10)
        
        if res_auth.status_code != 200:
            print(f"❌ Echec Auth : {res_auth.status_code}")
            print(res_auth.text)
            return

        token = res_auth.json().get("access_token")
        print(f"✅ Token récupéré : {token[:15]}...")
        
        # 3. Appel Données
        print("\n2. Appel API Production (Actual Generation)...")
        headers_data = {"Authorization": f"Bearer {token}"}
        
        res_data = requests.get(DATA_URL, headers=headers_data, timeout=10)
        
        if res_data.status_code == 200:
            data = res_data.json()
            print("✅ Données reçues !")
            # Affichage d'un extrait
            prods = data.get('actual_generations_per_production_type', [])
            print(f"   Nombre de types de production : {len(prods)}")
            if prods:
                print(f"   Exemple ({prods[0]['production_type']}) : {prods[0]['values'][0]['value']} MW")
        else:
            print(f"❌ Echec Data : {res_data.status_code}")
            print(res_data.text)
            
    except Exception as e:
        print(f"❌ Erreur technique : {e}")

if __name__ == "__main__":
    test_api()