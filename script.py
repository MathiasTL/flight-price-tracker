"""
Chequea precios de vuelos vía SerpAPI (Google Flights) y notifica por Telegram:
- Primer chequeo: mensaje con el precio base.
- Cada bajada respecto al chequeo anterior: alerta inmediata.
- Resumen diario (primer chequeo desde las 08:00 hora de Perú).
Soporta ventana horaria de salida para el vuelo de ida y fecha de fin de
monitoreo (active_until) por ruta, definidas en routes.json.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests

BASE_DIR = Path(__file__).resolve().parent
ROUTES_FILE = BASE_DIR / "routes.json"
HISTORY_FILE = BASE_DIR / "prices_history.json"

SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SERPAPI_URL = "https://serpapi.com/search.json"

# Hora de Perú (UTC-5, sin horario de verano)
LIMA_TZ = timezone(timedelta(hours=-5))
SUMMARY_HOUR = 8  # resumen diario a partir de esta hora (Lima)


def load_json(path, default):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Faltan credenciales de Telegram, no se pudo notificar.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, data=payload, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Error enviando mensaje a Telegram: {e}")


def parse_hhmm(value):
    """'05:00' -> minutos desde medianoche (300)."""
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def departure_minutes(flight):
    """Minutos desde medianoche de la salida del primer tramo, o None."""
    legs = flight.get("flights") or []
    if not legs:
        return None
    time_str = (legs[0].get("departure_airport") or {}).get("time", "")
    try:
        return parse_hhmm(time_str.split(" ")[1])
    except (IndexError, ValueError):
        return None


def fetch_cheapest_price(route):
    params = {
        "engine": "google_flights",
        "departure_id": route["origin"],
        "arrival_id": route["destination"],
        "outbound_date": route["outbound_date"],
        "currency": route.get("currency", "USD"),
        "hl": "es",
        "api_key": SERPAPI_KEY,
    }

    if route.get("trip_type", "round_trip") == "round_trip":
        params["type"] = 1
        if route.get("return_date"):
            params["return_date"] = route["return_date"]
    else:
        params["type"] = 2

    window_from = route.get("outbound_departure_from")
    window_to = route.get("outbound_departure_to")
    if window_from and window_to:
        # SerpAPI filtra por hora de salida del vuelo de ida (horas enteras)
        params["outbound_times"] = (
            f"{parse_hhmm(window_from) // 60},{parse_hhmm(window_to) // 60}"
        )

    resp = requests.get(SERPAPI_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise RuntimeError(data["error"])

    search_url = (data.get("search_metadata") or {}).get("google_flights_url")

    min_minutes = parse_hhmm(window_from) if window_from else None
    max_minutes = parse_hhmm(window_to) if window_to else None

    candidates = []
    for key in ("best_flights", "other_flights"):
        for flight in data.get(key, []):
            price = flight.get("price")
            if not isinstance(price, (int, float)):
                continue
            if min_minutes is not None:
                dep = departure_minutes(flight)
                # El filtro de SerpAPI es por horas enteras; aquí se valida
                # la ventana exacta y se descarta lo que no se pueda verificar
                if dep is None or dep < min_minutes or dep > max_minutes:
                    continue
            candidates.append(price)

    if not candidates:
        return None, search_url

    return min(candidates), search_url


def format_route_label(route):
    label = f"{route['origin']} -> {route['destination']}"
    dates = route["outbound_date"]
    if route.get("return_date"):
        dates += f" / {route['return_date']}"
    return f"{label} ({dates})"


def check_expired(route, entry, now_lima):
    """True si la ruta ya venció; notifica una sola vez."""
    active_until = route.get("active_until")
    if not active_until or now_lima.date().isoformat() <= active_until:
        return False
    if not entry.get("expired_notified"):
        send_telegram_message(
            f"🏁 Monitoreo finalizado para {format_route_label(route)} "
            f"(venció el {active_until}). Edita 'active_until' en routes.json "
            f"si quieres extenderlo."
        )
        entry["expired_notified"] = True
    return True


def process_route(route, history):
    route_id = route["id"]
    label = format_route_label(route)
    entry = history.setdefault(route_id, {})
    now_lima = datetime.now(LIMA_TZ)

    if check_expired(route, entry, now_lima):
        print(f"[{route_id}] Ruta vencida (active_until), se omite.")
        return

    try:
        current_price, search_url = fetch_cheapest_price(route)
    except Exception as e:
        print(f"[{route_id}] Error consultando precio: {e}")
        return

    link_line = (
        f'\n🔗 <a href="{search_url}">Ver vuelos en Google Flights</a>'
        if search_url
        else ""
    )

    if current_price is None:
        print(f"[{route_id}] No se encontraron vuelos dentro de la ventana horaria.")
        return

    currency = route.get("currency", "USD")
    previous_price = entry.get("price")
    first_price = entry.get("first_price")
    min_price = entry.get("min_price")

    print(f"[{route_id}] Precio actual: {current_price} {currency} (anterior: {previous_price})")

    today_lima = now_lima.date().isoformat()
    new_min = min_price is None or current_price < min_price
    min_price = current_price if new_min else min_price

    if first_price is None:
        # Primer chequeo: registrar base y confirmar que el sistema funciona
        first_price = current_price
        send_telegram_message(
            f"✅ <b>Monitoreo iniciado</b>\n"
            f"{label}\n"
            f"Precio base: <b>{current_price} {currency}</b>\n"
            f"Te avisaré con cada bajada y con un resumen diario."
            f"{link_line}"
        )
        entry["last_summary_date"] = today_lima
    elif previous_price is not None and current_price < previous_price:
        diff = previous_price - current_price
        send_telegram_message(
            f"✈️ <b>Bajada de precio</b>\n"
            f"{label}\n"
            f"Precio actual: <b>{current_price} {currency}</b> "
            f"(bajó {diff:.2f} {currency}, antes {previous_price} {currency})\n"
            f"Mínimo visto: {min_price} {currency} | Base: {first_price} {currency}"
            f"{link_line}"
        )
    else:
        threshold = route.get("price_alert_threshold")
        if threshold is not None and current_price <= threshold:
            send_telegram_message(
                f"✈️ <b>Precio bajo tu umbral</b>\n"
                f"{label}\n"
                f"Precio actual: <b>{current_price} {currency}</b> "
                f"(umbral: {threshold} {currency})"
                f"{link_line}"
            )

    if (
        entry.get("last_summary_date") != today_lima
        and now_lima.hour >= SUMMARY_HOUR
    ):
        send_telegram_message(
            f"📊 <b>Resumen diario</b>\n"
            f"{label}\n"
            f"Precio actual: <b>{current_price} {currency}</b>\n"
            f"Mínimo visto: {min_price} {currency} | Base: {first_price} {currency}"
            f"{link_line}"
        )
        entry["last_summary_date"] = today_lima

    entry.update(
        {
            "price": current_price,
            "currency": currency,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "first_price": first_price,
            "min_price": min_price,
        }
    )


def main():
    if not SERPAPI_KEY:
        print("Falta la variable de entorno SERPAPI_KEY.")
        sys.exit(1)

    config = load_json(ROUTES_FILE, {"routes": []})
    history = load_json(HISTORY_FILE, {})

    routes = config.get("routes", [])
    if not routes:
        print("routes.json no tiene rutas configuradas.")
        return

    for route in routes:
        process_route(route, history)

    save_json(HISTORY_FILE, history)


if __name__ == "__main__":
    main()
