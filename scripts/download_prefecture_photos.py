"""Fetch one attributed Wikimedia Commons photo for every Japanese prefecture."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "static" / "prefecture_photos"
MANIFEST = OUTPUT / "manifest.json"
USER_AGENT = "TabideaGraduationDemo/1.0 (prefecture photo assets; local student project)"

# Prefecture order follows the standard Japanese 01–47 JIS order.
PREFECTURES = [
    ("01", "北海道", "Farm Tomita Furano lavender fields"),
    ("02", "青森県", "Hirosaki Castle Aomori"),
    ("03", "岩手県", "Chusonji temple Hiraizumi Iwate"),
    ("04", "宮城県", "Matsushima Bay Miyagi Japan"),
    ("05", "秋田県", "Akita Japan"),
    ("06", "山形県", "Ginzan Onsen Yamagata Japan"),
    ("07", "福島県", "Tsuruga Castle Aizu Fukushima"),
    ("08", "茨城県", "Ibaraki Japan"),
    ("09", "栃木県", "Nikko Toshogu Shrine Tochigi Japan"),
    ("10", "群馬県", "Kusatsu Onsen Gunma Japan"),
    ("11", "埼玉県", "Chichibu Hitsujiyama Park shibazakura Saitama"),
    ("12", "千葉県", "Naritasan Shinshoji Temple Chiba Japan"),
    ("13", "東京都", "Tokyo Skytree Japan"),
    ("14", "神奈川県", "Great Buddha Kamakura Kanagawa Japan"),
    ("15", "新潟県", "Hoshitoge rice terraces Niigata Japan"),
    ("16", "富山県", "Tateyama Kurobe Alpine Route Toyama"),
    ("17", "石川県", "Kenrokuen Garden Kanazawa Ishikawa"),
    ("18", "福井県", "Tojinbo cliffs Fukui Japan"),
    ("19", "山梨県", "Arakurayama Sengen Park Mount Fuji Yamanashi"),
    ("20", "長野県", "Matsumoto Castle Nagano Japan"),
    ("21", "岐阜県", "Shirakawa-go Gifu Japan"),
    ("22", "静岡県", "Miho no Matsubara Mount Fuji Shizuoka"),
    ("23", "愛知県", "Nagoya Castle Aichi Japan"),
    ("24", "三重県", "Ise Grand Shrine Mie Japan"),
    ("25", "滋賀県", "Lake Biwa Shiga Japan"),
    ("26", "京都府", "Kyoto Japan Fushimi Inari"),
    ("27", "大阪府", "Osaka Castle Osaka Japan"),
    ("28", "兵庫県", "Himeji Castle Hyogo Japan"),
    ("29", "奈良県", "Nara Japan Todaiji"),
    ("30", "和歌山県", "Nachi Falls Wakayama Japan"),
    ("31", "鳥取県", "Tottori Sand Dunes Japan"),
    ("32", "島根県", "Izumo Taisha Shrine Shimane Japan"),
    ("33", "岡山県", "Okayama Korakuen Garden Japan"),
    ("34", "広島県", "Hiroshima Peace Memorial Dome Japan"),
    ("35", "山口県", "Yamaguchi Japan"),
    ("36", "徳島県", "Naruto whirlpools Tokushima Japan"),
    ("37", "香川県", "Ritsurin Garden Kagawa Japan"),
    ("38", "愛媛県", "Dogo Onsen Matsuyama Ehime"),
    ("39", "高知県", "Kochi Castle Japan"),
    ("40", "福岡県", "Fukuoka Tower Japan"),
    ("41", "佐賀県", "Yoshinogari Historical Park Saga"),
    ("42", "長崎県", "Glover Garden Nagasaki Japan"),
    ("43", "熊本県", "Kumamoto Castle Japan"),
    ("44", "大分県", "Beppu hot springs Oita Japan"),
    ("45", "宮崎県", "Takachiho Gorge Miyazaki Japan"),
    ("46", "鹿児島県", "Kagoshima Japan Sakurajima"),
    ("47", "沖縄県", "Kouri Beach Okinawa Japan"),
]


def plain(value):
    value = re.sub(r"<[^>]*>", " ", unescape(value or ""))
    return re.sub(r"\s+", " ", value).strip()


def download_one(prefecture):
    code, name, query = prefecture
    target = OUTPUT / f"JP-{code}.jpg"
    if target.exists() and target.stat().st_size > 10_000:
        manifest_path = MANIFEST
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            old = next((row for row in manifest if row["code"] == code), None)
            if old and old.get("prefecture") == name and not old.get("source_title", "").lower().endswith(".pdf"):
                return old

    api = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query", "generator": "search", "gsrsearch": query,
        "gsrnamespace": 6, "gsrlimit": 50, "prop": "imageinfo", "iiprop": "url|extmetadata",
        "iiurlwidth": 960, "format": "json",
    }
    response = None
    for attempt in range(5):
        response = requests.get(api, params=params, headers={"User-Agent": USER_AGENT}, timeout=45)
        if response.status_code != 429:
            break
        retry_after = response.headers.get("Retry-After", "20")
        try:
            delay = min(90, max(10, int(retry_after)))
        except ValueError:
            delay = 30
        time.sleep(delay * (attempt + 1))
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", {}).values()
    candidates = []
    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        license_name = plain(meta.get("LicenseShortName", {}).get("value", ""))
        # Avoid images whose reuse terms are not clear or are non-free.
        if not license_name or not any(token in license_name.lower() for token in ("cc", "public domain", "free art")):
            continue
        if not info.get("mime", "").startswith("image/") or page.get("title", "").lower().endswith((".pdf", ".svg")):
            continue
        title = page.get("title", "")
        title_lower = title.lower()
        score = sum(word.lower() in title_lower for word in re.findall(r"[a-z0-9]+", query) if len(word) > 3)
        if "map" in title_lower or "logo" in title_lower or "coat of arms" in title_lower:
            score -= 10
        candidates.append((score, page, info, meta, license_name))
    if not candidates:
        raise RuntimeError(f"No clearly licensed photograph found for {name} ({query})")
    candidates.sort(key=lambda candidate: (candidate[0], candidate[1].get("title", "")), reverse=True)
    _, page, info, meta, license_name = candidates[0]
    image_url = info.get("thumburl") or info.get("url")
    image_response = None
    for attempt in range(4):
        try:
            image_response = requests.get(image_url, headers={"User-Agent": USER_AGENT}, timeout=(15, 90))
            if image_response.status_code == 429:
                time.sleep(min(60, int(image_response.headers.get("Retry-After", "15"))))
                continue
            image_response.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))
    image_response.raise_for_status()
    if not image_response.headers.get("content-type", "").startswith("image/"):
        raise RuntimeError(f"Expected image data for {name}, got {image_response.headers.get('content-type')}")
    target.write_bytes(image_response.content)
    return {
        "code": code,
        "prefecture": name,
        "file": target.name,
        "place": plain(meta.get("ImageDescription", {}).get("value", ""))[:360],
        "author": plain(meta.get("Artist", {}).get("value", ""))[:180],
        "license": license_name,
        "license_url": plain(meta.get("LicenseUrl", {}).get("value", "")),
        "source_title": page.get("title", "").removeprefix("File:"),
        "source_url": "https://commons.wikimedia.org/wiki/" + quote(page.get("title", "").replace(" ", "_"), safe=":"),
        "image_url": image_url,
        "query": query,
    }


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    failures = []
    # Two simultaneous API requests are enough for a classroom demo and avoid
    # the Commons rate limiting seen with larger batches.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(download_one, row): row for row in PREFECTURES}
        for future in as_completed(futures):
            row = futures[future]
            try:
                result = future.result()
                manifest.append(result)
                print(f"OK {result['code']} {ascii(result['prefecture'])}: {ascii(result['source_title'])}", flush=True)
            except Exception as exc:
                failures.append((row, str(exc)))
                print(f"FAIL {row[0]} {ascii(row[1])}: {ascii(str(exc))}", flush=True)
            time.sleep(1.0)
    manifest.sort(key=lambda row: row["code"])
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise SystemExit(f"Downloaded {len(manifest)}/47 images. Review {MANIFEST}; {len(failures)} need curation.")
    print(f"Downloaded and attributed all 47 images in {OUTPUT}")


if __name__ == "__main__":
    main()


