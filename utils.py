import json
import os
import requests
from datetime import datetime
import pytz
import csv
import time
import locale

CONFIG_PATH = os.path.join("config", "parks.json")
BASE_URL = "https://api.themeparks.wiki/v1/entity"

# --- Función auxiliar: obtener horario del parque ---
def obtener_horario(entity_id, hoy):
    schedule_url = f"{BASE_URL}/{entity_id}/schedule"
    try:
        response = requests.get(schedule_url)
        response.raise_for_status()
        data = response.json()

        horarios = data.get("schedule", [])
        horario_hoy = next(
    (h for h in horarios if h["date"] == hoy and h.get("type") == "OPERATING"),
    None
)

        if horario_hoy:
            apertura = horario_hoy.get("openingTime")
            cierre = horario_hoy.get("closingTime")
            if apertura and cierre:
                return (datetime.fromisoformat(apertura), datetime.fromisoformat(cierre))
    except:
        pass
    return (None, None)


# --- Función auxiliar: recoger datos en vivo ---
def recoger_datos(parque, evento_activo, ahora):
    nombre = parque["name"]
    entity_id = parque["entity_id"]
    timezone = parque["timezone"]
    zona = pytz.timezone(timezone)

    live_url = f"{BASE_URL}/{entity_id}/live"
    nombre_archivo = f"{nombre.replace(' ', '_')}_{ahora.date().isoformat()}.csv"
    ruta_archivo = os.path.join("data", nombre_archivo)
    os.makedirs("data", exist_ok=True)
    archivo_existe = os.path.isfile(ruta_archivo)

    try:
        response_live = requests.get(live_url)
        response_live.raise_for_status()
        data_live = response_live.json()

        atracciones = data_live.get("liveData", [])
        if not atracciones:
            print(f"⚠️  No se encontraron atracciones en {nombre}")
            return 0, ruta_archivo

        with open(ruta_archivo, mode="a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            if not archivo_existe:
                writer.writerow(["timestamp", "weekday", "ride_id", "ride_name", "status", "wait_time", "evento"])

            total_atracciones = 0
            for ride in atracciones:
                if ride.get("entityType") != "ATTRACTION":
                    continue
                total_atracciones += 1
                ride_id = ride.get("id", "")
                ride_name = ride.get("name", "")
                status = ride.get("status", "")
                wait_time = ride.get("queue", {}).get("STANDBY", {}).get("waitTime", "")
                weekday = ahora.strftime("%A")
                writer.writerow([ahora.isoformat(), weekday, ride_id, ride_name, status, wait_time, evento_activo])

        print(f"  ✅ {nombre}: {total_atracciones} atracciones registradas")
        return total_atracciones, ruta_archivo

    except Exception as e:
        print(f"  ❌ Error al obtener datos de {nombre}: {e}")
        return 0, ruta_archivo


# --- Carga inicial ---
with open(CONFIG_PATH, "r", encoding="utf-8") as file:
    parques = json.load(file)

print("🚀 Iniciando colector de datos...\n")

# --- Obtenemos horas de cierre por parque ---
cierres = {}
for parque in parques:
    nombre = parque["name"]
    timezone = parque["timezone"]
    zona = pytz.timezone(timezone)
    hoy = datetime.now(zona).date().isoformat()

    apertura, cierre = obtener_horario(parque["entity_id"], hoy)
    if cierre:
        cierres[nombre] = cierre
        print(f"🕓 {nombre} cierra hoy a las {cierre.astimezone(zona).strftime('%H:%M')}")
    else:
        print(f"⚠️ No se pudo determinar hora de cierre de {nombre}")
print()

# --- Para el resumen final ---
resumen_parques = {parque["name"]: {"registros": 0, "archivo": ""} for parque in parques}

# --- Bucle principal ---
while True:
    ahora_global = datetime.utcnow().replace(tzinfo=pytz.utc)

    # Si todos los parques ya cerraron, terminamos
    todos_cerrados = True
    for nombre, cierre in cierres.items():
        if ahora_global < cierre:
            todos_cerrados = False
            break

    if todos_cerrados:
        print("\n🏁 Todos los parques han cerrado. Finalizando recolección de datos.")
        break

    # Recoger datos de todos los parques activos
    for parque in parques:
        nombre = parque["name"]
        timezone = parque["timezone"]
        zona = pytz.timezone(timezone)
        ahora_local = datetime.now(zona)

        # Saltar parques sin horario
        if nombre not in cierres:
            continue

        # Si ya cerró, lo saltamos
        if ahora_local >= cierres[nombre]:
            print(f"⏹️  {nombre} ya ha cerrado, no se recogen más datos hoy.")
            continue

        # Detectar evento activo
        evento_activo = ""
        for evento in parque.get("eventos", []):
            desde = datetime.fromisoformat(evento["desde"]).date()
            hasta = datetime.fromisoformat(evento["hasta"]).date()
            if desde <= ahora_local.date() <= hasta:
                evento_activo = evento["nombre"]
                break

        nuevos_registros, archivo = recoger_datos(parque, evento_activo, ahora_local)
        resumen_parques[nombre]["registros"] += nuevos_registros
        resumen_parques[nombre]["archivo"] = archivo

    print("⏳ Esperando 5 minutos para la próxima recolección...\n")
    time.sleep(5 * 60)

# --- Resumen final ---
print("\n📊 RESUMEN DEL DÍA")
print("=" * 40)
for nombre, info in resumen_parques.items():
    if info["registros"] > 0:
        print(f"🎢 {nombre}: {info['registros']} registros → {info['archivo']}")
    else:
        print(f"🎢 {nombre}: sin datos guardados")
print("=" * 40)
print("✅ Recolección completada con éxito.")
