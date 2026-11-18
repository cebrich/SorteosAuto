import os
import json
import time
import datetime
import requests
from concurrent.futures import ThreadPoolExecutor

ANCHOR_DATE = datetime.date(2026, 11, 12)
ANCHOR_NUM = 91
REF_COUNTER = 13284

EXTRAS = [
    {"date": "2026-12-06", "name": "Sorteo Extraordinario Día de la Constitución"},
    {"date": "2026-12-22", "name": "Sorteo Extraordinario de Navidad"},
    {"date": "2027-01-06", "name": "Sorteo Extraordinario de “El Niño”"}
]
SKIP = ["2026-12-05", "2026-12-19", "2027-01-02"]
FIXED_NUMS = {"2026-12-22": 102, "2027-01-06": 1}

LEGACY_KEYS = {
    "2026-12-22": "navidad",
    "2027-01-06": "nino"
}

# Cuántos sorteos futuros se descargan (Navidad y El Niño se añaden siempre si existen).
MAX_SORTEOS = 10
# ScraperAPI gratuito admite hasta 5 peticiones simultáneas.
WORKERS = 4


def generate_draws():
    list_draws = []
    start_dt = ANCHOR_DATE
    num = ANCHOR_NUM
    prev_year = str(start_dt.year)
    first = True

    for i in range(431):
        curr_date = start_dt + datetime.timedelta(days=i)
        iso = curr_date.isoformat()
        dow = curr_date.weekday()

        extra = next((e for e in EXTRAS if e["date"] == iso), None)
        regular = (dow == 3 or dow == 5) and (iso not in SKIP)

        if not extra and not regular:
            continue

        if not first:
            y = str(curr_date.year)
            num = 1 if y != prev_year else num + 1
            prev_year = y
        first = False

        if iso in FIXED_NUMS:
            num = FIXED_NUMS[iso]

        if iso in LEGACY_KEYS:
            key = LEGACY_KEYS[iso]
        elif dow == 3:
            key = "jueves"
        elif dow == 5:
            key = "sabado"
        else:
            key = f"s-{iso.replace('-', '')}"

        if extra:
            name = extra["name"]
        elif dow == 3:
            name = "Sorteo del Jueves"
        else:
            name = "Sorteo del Sábado"

        days_diff = (curr_date - ANCHOR_DATE).days
        counter = REF_COUNTER + days_diff
        nnn = str(num).zfill(3)
        url = (
            f"https://www.loteriasyapuestas.es/new-geo-web/GeoTerminalServlet/"
            f"Sorteo{curr_date.year}{nnn}.csv?drawId={counter}09{nnn}&locale=es&cdc={counter}"
        )

        list_draws.append({
            "key": key,
            "date": iso,
            "num": num,
            "name": name,
            "url": url
        })
    return list_draws


def download_csv(url, api_key, retries=2):
    """Descarga un CSV con un reintento rápido. Devuelve el texto o None."""
    for attempt in range(1, retries + 1):
        try:
            if api_key:
                proxy_url = (
                    f"http://api.scraperapi.com?api_key={api_key}"
                    f"&country_code=es&url={requests.utils.quote(url)}"
                )
                res = requests.get(proxy_url, timeout=45)
            else:
                res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)

            if res.status_code == 200 and len(res.text) > 100:
                return res.text
            print(f"   Intento {attempt}/{retries}: estado {res.status_code}")
        except Exception as e:
            print(f"   Intento {attempt}/{retries}: error {e}")
        if attempt < retries:
            time.sleep(1)
    return None


def write_file(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def main():
    today = datetime.date.today().isoformat()
    all_draws = generate_draws()
    upcoming = [d for d in all_draws if d["date"] >= today]

    targets = upcoming[:MAX_SORTEOS]
    for key_target in ["navidad", "nino"]:
        found = next((d for d in upcoming if d["key"] == key_target), None)
        if found and found not in targets:
            targets.append(found)

    # Archivos "antiguos" (jueves.csv, sabado.csv, navidad.csv, nino.csv) para no romper la web actual.
    legacy_dates = {d["date"] for d in upcoming[:2]}
    legacy_dates |= {d["date"] for d in targets if d["key"] in ("navidad", "nino")}

    api_key = os.environ.get("SCRAPER_API_KEY")
    print(f"Descargando {len(targets)} sorteos...")

    def fetch(draw):
        return draw, download_csv(draw["url"], api_key)

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        results = list(ex.map(fetch, targets))

    os.makedirs("data", exist_ok=True)
    downloaded_count = 0
    for draw, text in results:
        if text:
            write_file(os.path.join("data", f"{draw['date']}.csv"), text)
            if draw["date"] in legacy_dates:
                write_file(os.path.join("data", f"{draw['key']}.csv"), text)
            print(f"-> OK: {draw['date']} {draw['name']}")
            downloaded_count += 1
        else:
            print(f"-> Aviso: no se pudo descargar {draw['date']} {draw['name']}; se conserva el archivo anterior si existía")

    if downloaded_count > 0:
        # Borra solo los CSV con fecha ya pasada (YYYY-MM-DD.csv); nunca toca los demás.
        for filename in os.listdir("data"):
            if len(filename) == 14 and filename.endswith(".csv") and filename[:10] < today:
                os.remove(os.path.join("data", filename))

        # Índice con los sorteos disponibles, para que la web llene el desplegable.
        # Se listan todos los sorteos objetivo; "disponible" indica si ya hay CSV.
        manifest = []
        for d in sorted(targets, key=lambda x: x["date"]):
            archivo = f"data/{d['date']}.csv"
            disponible = os.path.exists(archivo)
            # Navidad y El Niño: si no hay archivo con fecha, se usa el antiguo (navidad.csv / nino.csv).
            if not disponible and d["key"] in ("navidad", "nino"):
                legacy = f"data/{d['key']}.csv"
                if os.path.exists(legacy):
                    archivo = legacy
                    disponible = True
            manifest.append({
                "fecha": d["date"],
                "numero": d["num"],
                "nombre": d["name"],
                "archivo": archivo,
                "disponible": disponible,
            })
        write_file(os.path.join("data", "sorteos.json"), json.dumps(manifest, ensure_ascii=False, indent=2))
        print("Carpeta 'data' actualizada correctamente.")
    else:
        print("Aviso: No se pudo descargar ningún archivo nuevo. Se mantienen los datos anteriores por seguridad.")


if __name__ == "__main__":
    main()
