import requests
from config import BASE_URL
from config import ADM4

def fetch_bmkg_data():
    url = f"{BASE_URL}?adm4={ADM4}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()