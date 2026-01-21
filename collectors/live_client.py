import requests

BASE_URL = "https://api.themeparks.wiki/v1/entity"

def get_live_data(entity_id):
    live_url = f"{BASE_URL}/{entity_id}/live"

    try:
        response = requests.get(live_url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"  ❌ Error al llamar live API ({entity_id}): {e}")
        return None