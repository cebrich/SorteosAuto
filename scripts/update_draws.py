import os
import datetime
import requests

# Configuración de anclaje
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
            
    os.makedirs("data", exist_ok=True)
    
    # Cabecera para simular un navegador web y evitar el error 403
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for draw in targets:
        print(f"Descargando sorteo: {draw['key']} ({draw['date']})...")
        try:
            res = requests.get(draw['url'], headers=headers, timeout=15)
            if res.status_code == 200 and len(res.text) > 100:
                filepath = os.path.join("data", f"{draw['key']}.csv")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(res.text)
                print(f"-> Guardado con éxito en {filepath}")
            else:
                print(f"-> Aviso: El sorteo aún no está disponible o devolvió estado {res.status_code}")
        except Exception as e:
            print(f"-> Error al descargar {draw['key']}: {e}")

if __name__ == "__main__":
    main()
