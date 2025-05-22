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


def add_manual_links_to_df(df):
    # Normalize column names
    df.columns = df.columns.str.strip().str.lower()

    required_cols = ["manufacturer", "model_number"]
    if not all(col in df.columns for col in required_cols):
        raise ValueError("Missing required columns: manufacturer, model_number")

    links = []
    for _, row in df.iterrows():
        manufacturer = str(row.get("manufacturer", ""))
        model = str(row.get("model_number", ""))
        serial = str(row.get("serial_number", ""))

        link = search_manual_link(manufacturer, model, serial)
        links.append(link or "")

        time.sleep(1.5)  # To respect DuckDuckGo rate limits

    df["manual_link"] = links
    return df