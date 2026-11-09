from pathlib import Path
import requests
from tqdm import tqdm

RECORD_ID = "14983362"
OUT = Path("data/raw")
CHUNK = 1024 * 1024

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    response = requests.get(f"https://zenodo.org/api/records/{RECORD_ID}", timeout=60)
    response.raise_for_status()
    record = response.json()
    entries = record.get("files", [])
    if not entries:
        raise RuntimeError("Zenodo API returned no files.")
    print(record.get("metadata", {}).get("title", RECORD_ID))
    for item in entries:
        target = OUT / item["key"]
        if target.exists() and target.stat().st_size == item.get("size"):
            print(f"Already downloaded: {target.name}")
            continue
        url = item.get("links", {}).get("self")
        if not url:
            print(f"No download link: {item['key']}")
            continue
        with requests.get(url, stream=True, timeout=(30, 180)) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", item.get("size", 0)))
            with target.open("wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc=target.name) as bar:
                for chunk in r.iter_content(chunk_size=CHUNK):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))
    print(f"Files saved to {OUT.resolve()}")

if __name__ == "__main__":
    main()
