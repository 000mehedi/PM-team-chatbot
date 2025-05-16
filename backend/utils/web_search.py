from serpapi import GoogleSearch
import os

def search_manual(manufacturer, model, serial_number=""):
    if not manufacturer and not model:
        return []

    # Force them to strings and clean up any list wrappers
    if isinstance(model, list):
        model = " ".join(model)
    if isinstance(manufacturer, list):
        manufacturer = " ".join(manufacturer)
    if isinstance(serial_number, list):
        serial_number = " ".join(serial_number)

    model_part = model.strip()
    query = f"{manufacturer} {model_part}"
    if serial_number:
        query += f" {serial_number}"
    query += " user manual"

    print(f"Search Query: {query}")

    params = {
        "q": query,
        "api_key": os.getenv("SERPAPI_KEY"),
        "num": 20,
        "gl": "us"
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    print("Search results:")
    scored_links = []

    for result in results.get("organic_results", []):
        link = result.get("link", "").lower()
        title = result.get("title", "").lower()

        if any(word in title or word in link for word in ["manual", "guide", "pdf"]):
            score = 0
            if "manual" in title or "manual" in link:
                score += 2
            if manufacturer.lower() in title or manufacturer.lower() in link:
                score += 2
            if model_part.lower() in title or model_part.lower() in link:
                score += 2
            if serial_number and serial_number.lower() in title + link:
                score += 1

            scored_links.append((score, result.get("link", "")))

    # Sort by score (descending) and return the top result
    scored_links.sort(reverse=True)
    top_link = scored_links[0][1] if scored_links else None

    print(f"Top selected link: {top_link}")
    return [top_link] if top_link else []
