# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "bs4>=0.0.2",
#     "requests>=2.34.2",
# ]
# ///
import json
import re
import requests
from bs4 import BeautifulSoup

OUTPUT_PATH = r"assets\bedwars_map_types.json"

def get_maps_via_api():
    print("Fetching Bed Wars Maps page via MediaWiki API to bypass Cloudflare...")
    
    # The MediaWiki API endpoint for Fandom
    url = "https://hypixel.fandom.com/api.php"
    params = {
        "action": "parse",
        "page": "Bed_Wars/Maps",
        "format": "json"
    }
    headers = {
        "User-Agent": "ProxhyMapScraper/1.0"
    }
    
    res = requests.get(url, params=params, headers=headers, timeout=30)
    res.raise_for_status()
    
    data = res.json()
    # Extract the raw HTML payload from the API response
    html = data["parse"]["text"]["*"]
    soup = BeautifulSoup(html, "html.parser")
    
    out = {}
    
    # Iterate over all headlines (which correspond to the map categories)
    for headline in soup.find_all(class_="mw-headline"):
        title = headline.get_text(strip=True)
        
        # Determine the bucket from the header
        current_bucket = None
        if "Solo/Doubles" in title:
            current_bucket = "solo"
        elif "3v3v3v3/4v4v4v4" in title or "3's/4's" in title:
            current_bucket = "threes"
        elif "4v4 Maps" in title:
            current_bucket = "4v4"
        elif "Seasonal Maps" in title:
            current_bucket = "seasonal"
        else:
            continue
            
        # The table associated with this category is typically the next table element
        table = headline.find_next("table")
        if not table:
            continue
            
        # Find column indices based on headers
        headers_text = [th.get_text(strip=True).lower() for th in table.find_all(["th", "td"])[:10]]
        
        name_idx = 1  # Default assumption (Image is 0, Name is 1)
        mode_idx = -1
        
        for i, h in enumerate(headers_text):
            if "name" in h:
                name_idx = i
            elif "mode" in h:
                mode_idx = i
                
        # Parse the rows
        for tr in table.find_all("tr")[1:]:  # Skip header row
            tds = tr.find_all("td")
            if len(tds) > name_idx:
                # Clean up the map name (remove wiki citations like [1])
                name_cell = tds[name_idx]
                a_tag = name_cell.find("a")
                
                if a_tag:
                    raw_name = a_tag.get_text(strip=True)
                else:
                    raw_name = name_cell.get_text(strip=True)
                    
                name = re.sub(r'\[\d+\]', '', raw_name).lower().strip()
                
                if not name:
                    continue
                    
                if current_bucket == "seasonal":
                    # Seasonal maps have their type in the specific Mode column
                    if mode_idx != -1 and len(tds) > mode_idx:
                        mode_text = tds[mode_idx].get_text(strip=True).lower()
                        if "solo/doubles" in mode_text:
                            out[name] = {"type": "solo"}
                        elif "3's/4's" in mode_text or "3s/4s" in mode_text:
                            out[name] = {"type": "threes"}
                        else:
                            out[name] = {"type": "unknown"}
                    else:
                        out[name] = {"type": "unknown"}
                else:
                    out[name] = {"type": current_bucket}
                    
    return out


def main():
    try:
        maps = get_maps_via_api()
    except Exception as e:
        print(f"Fatal error reaching the API: {e}")
        return
        
    if not maps:
        print("Failed to parse any maps. The wiki structure might have changed.")
        return
        
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(maps, f, ensure_ascii=False, indent=4, sort_keys=True)
        
    print(f"Successfully wrote {len(maps)} maps to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()