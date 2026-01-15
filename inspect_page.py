import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('NOTION_TOKEN_PRODUCCION')
db_id = os.getenv('NOTION_DATABASE_ID_PLANEACION')

url = f"https://api.notion.com/v1/databases/{db_id}/query"
headers = {
    "Authorization": f"Bearer {token}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

# Buscar registros donde A MOSTRAR no esté vacío
payload = {
    "filter": {
        "property": "A MOSTRAR",
        "rollup": { # Asumo que puede ser un rollup de la imagen de la Partida
            "any_every": {
                "is_not_empty": True
            }
        }
    },
    "page_size": 3
}

# Alternativa si es Files/Media
payload_files = {
    "filter": {
        "property": "A MOSTRAR",
        "files": {
            "is_not_empty": True
        }
    },
    "page_size": 3
}

def check(p):
    response = requests.post(url, headers=headers, json=p)
    if response.ok:
        data = response.json()
        if data['results']:
            for res in data['results']:
                prop = res['properties'].get('A MOSTRAR')
                print(f"Prop 'A MOSTRAR' found: {json.dumps(prop, indent=2)}")
                return True
    return False

print("Checking Files/Media filter...")
if not check(payload_files):
    print("Checking Rollup filter...")
    check(payload)
