import os
import datetime
import shutil
import requests

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
    "2026-11-12": "jueves",
    "2026-11-14": "sabado",
    "2026-12-22": "navidad",
    "2027-01-06": "nino"
}

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
            
        key = LEGACY_KEYS.get(iso, f"s-{iso.replace('-', '')}")
        
        days_diff = (curr_date - ANCHOR_DATE).days
        counter = REF_COUNTER + days_diff
        nnn = str(num).zfill(3)
        url = f"https://www.loteriasyapuestas.es/new-geo-web/GeoTerminalServlet/Sorteo{curr_date.year}{nnn}.csv?drawId={counter}09{nnn}&locale=es&cdc={counter}"
        
        list_draws.append({
            "key": key,
            "date": iso,
            "num": num,
            "url": url
        })
    return list_draws

def main():
    today = datetime.date.today().isoformat()
    all_draws = generate_draws()
    
    upcoming = [d for d in all_draws if d["date"] >= today]
    targets = upcoming[:2]
    
    for key_target in ["navidad", "nino"]:
        found = next((d for d in all_draws if d["key"] == key_target), None)
        if found and found not in targets:
            targets.append(found)
            
    # Carpeta temporal para las nuevas descargas
    temp_dir = "temp_data"
    os.makedirs(temp_dir, exist_ok=True)
    
    api_key = os.environ.get("SCRAPER_API_KEY")
    downloaded_count = 0
    
    for draw in targets:
        print(f"Descargando sorteo: {draw['key']} ({draw['date']})...")
        try:
            if api_key:
                proxy_url = f"http://api.scraperapi.com?api_key={api_key}&country_code=es&url={requests.utils.quote(draw['url'])}"
                res = requests.get(proxy_url, timeout=30)
            else:
                res = requests.get(draw['url'], headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                
            if res.status_code == 200 and len(res.text) > 100:
                filepath = os.path.join(temp_dir, f"{draw['key']}.csv")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(res.text)
                print(f"-> Descargado con éxito en temporal: {draw['key']}.csv")
                downloaded_count += 1
            else:
                print(f"-> Aviso: El servidor devolvió estado {res.status_code}")
        except Exception as e:
            print(f"-> Error al descargar {draw['key']}: {e}")

    # SEGURIDAD: Solo si hemos descargado con éxito algún archivo nuevo, actualizamos la carpeta definitiva
    if downloaded_count > 0:
        os.makedirs("data", exist_ok=True)
        # Borrar archivos antiguos de la carpeta data
        for filename in os.listdir("data"):
            if filename.endswith(".csv"):
                os.remove(os.path.join("data", filename))
                
        # Mover los nuevos archivos desde la carpeta temporal a data/
        for filename in os.listdir(temp_dir):
            shutil.move(os.path.join(temp_dir, filename), os.path.join("data", filename))
        print("Carpeta 'data' actualizada correctamente con los nuevos archivos.")
    else:
        print("Aviso: No se pudo descargar ningún archivo nuevo. Se mantienen los datos anteriores por seguridad.")
        
    # Limpiar carpeta temporal
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    main()

