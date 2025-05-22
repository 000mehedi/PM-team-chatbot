import requests
from bs4 import BeautifulSoup
import time

def search_manual_link(manufacturer, model, serial_number=""):
    if not manufacturer or not model:
        return None

    query = f"{manufacturer} {model} {serial_number} user manual site:manualslib.com"
    url = f"https://duckduckgo.com/html/?q={query}"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        links = soup.find_all("a", href=True)

        for link in links:
            href = link["href"]
            if "manualslib.com/manual/" in href:
                return href
    except Exception as e:
        print(f"Error searching manual: {e}")
        return None

    return None
