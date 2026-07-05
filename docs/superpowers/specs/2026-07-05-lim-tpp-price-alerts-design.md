# Monitoreo de precios LIM → TPP con alertas por Telegram

**Fecha:** 2026-07-05
**Estado:** Aprobado por el usuario

## Objetivo

Monitorear cada 3 horas, durante 2 semanas, el precio del vuelo
Lima (LIM) → Tarapoto (TPP), ida 2026-09-19 y vuelta 2026-09-22, con el
vuelo de ida saliendo entre las 05:00 y las 13:00. Notificar por Telegram
cada bajada de precio y enviar un resumen diario.

## Arquitectura (sin cambios)

GitHub Actions (cron) → `script.py` → SerpAPI Google Flights → Telegram.
El historial se persiste en `prices_history.json` y se commitea al repo.

## Configuración (`routes.json`)

Una ruta:

- `origin: LIM`, `destination: TPP`, `outbound_date: 2026-09-19`,
  `return_date: 2026-09-22`, `trip_type: round_trip`, `currency: PEN`.
- **Nuevo** `outbound_departure_from: "05:00"` / `outbound_departure_to: "13:00"`:
  ventana horaria de salida del vuelo de ida. Se traduce al parámetro
  `outbound_times` de SerpAPI y además se valida en la respuesta
  (se descartan vuelos cuya primera salida cae fuera de la ventana).
- **Nuevo** `active_until: "2026-07-19"`: pasada esa fecha (hora de Lima) el
  script omite la ruta y avisa una sola vez por Telegram que el monitoreo
  terminó, para no seguir gastando búsquedas.

## Lógica de alertas (`script.py`)

1. **Primer chequeo:** guarda el precio como base (`first_price`) y envía un
   mensaje con el precio inicial (confirma que el sistema funciona).
2. **Bajada:** si el precio actual < precio del chequeo anterior, alerta
   inmediata con precio actual, diferencia y mínimo histórico visto.
3. **Resumen diario:** en el primer chequeo a partir de las 08:00 hora de
   Perú (UTC-5, sin DST), envía precio actual, precio base y mínimo visto,
   aunque no haya cambios.
4. El umbral opcional (`price_alert_threshold`) se mantiene; queda en `null`.

Historial por ruta: `price`, `currency`, `checked_at`, `first_price`,
`min_price`, `last_summary_date`, `expired_notified`.

## Programación

Cron `0 */3 * * *` (cada 3 horas, UTC). ~8 chequeos/día ≈ 112 búsquedas en
2 semanas, dentro del límite gratuito de SerpAPI (500/mes).

## Manejo de errores

- Error de SerpAPI o sin vuelos: se registra en el log y no se altera el
  historial de esa ruta.
- Credenciales de Telegram ausentes: se registra en el log, el chequeo
  continúa.

## Fuera de alcance

Pasos manuales del usuario (documentados en README): subir el repo a
GitHub, crear API key de SerpAPI, bot de Telegram y los 3 secrets.
