# Flight price tracker (GitHub Actions + Telegram)

Monitorea el precio de una o más rutas de vuelo y te avisa por Telegram cuando
baja. Corre gratis sobre GitHub Actions, sin servidores propios.

## Cómo funciona

1. Un workflow de GitHub Actions se ejecuta cada 2 horas (`cron`).
2. `script.py` consulta el precio más barato de cada ruta configurada en
   `routes.json` usando la API de Google Flights de SerpAPI, respetando la
   ventana horaria de salida del vuelo de ida si la definiste.
3. Compara ese precio contra el último guardado en `prices_history.json`.
4. Envía un mensaje de Telegram en **cada chequeo**, suba o baje el precio:
   precio actual (con 📉/📈/➡️ según la variación), mínimo visto, precio
   base, equipaje incluido según Google Flights y link a la búsqueda.
5. Guarda el nuevo precio en `prices_history.json` y lo commitea al repo,
   para que el próximo chequeo tenga con qué comparar.
6. Cuando llega la fecha `active_until` de una ruta, avisa una vez que el
   monitoreo terminó y deja de consultarla.

## Paso 1: crear el repositorio

Sube esta carpeta tal cual (con la subcarpeta `.github/workflows/`) a un
repositorio nuevo en GitHub. Puede ser privado o público — ambos corren
gratis para este volumen de uso (unos segundos, varias veces al día).

## Paso 2: obtener una API key de SerpAPI (gratis)

1. Crea una cuenta en serpapi.com.
2. En tu dashboard, copia tu API key. El plan gratuito incluye 250
   búsquedas al mes.
3. Con un chequeo cada 2 horas (12 veces al día) y una sola ruta, usas
   ~168 búsquedas en las 2 semanas que dura el monitoreo (`active_until`),
   dentro del límite. Si agregas más rutas o extiendes el plazo, multiplica
   y ajusta la frecuencia del cron para no pasarte.

## Paso 3: crear el bot de Telegram (gratis)

1. Abre Telegram y busca a **@BotFather**.
2. Envía `/newbot` y sigue las instrucciones. Al final te da un **token**
   (algo como `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxx`).
3. Para saber tu **chat_id**: envíale cualquier mensaje a tu bot recién
   creado, y luego abre en el navegador:
   `https://api.telegram.org/bot<TU_TOKEN>/getUpdates`
   Ahí vas a ver un campo `"chat":{"id": ...}` — ese número es tu chat_id.

## Paso 4: agregar los secrets en GitHub

En tu repositorio: **Settings → Secrets and variables → Actions → New
repository secret**. Crea estos tres:

- `SERPAPI_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Paso 5: configurar tus rutas reales

Edita `routes.json`. La configuración actual monitorea Lima → Tarapoto:

```json
{
  "routes": [
    {
      "id": "lima_tarapoto",
      "origin": "LIM",
      "destination": "TPP",
      "outbound_date": "2026-09-19",
      "return_date": "2026-09-22",
      "trip_type": "round_trip",
      "currency": "PEN",
      "outbound_departure_from": "05:00",
      "outbound_departure_to": "13:00",
      "active_until": "2026-07-19"
    }
  ]
}
```

Campos:
- `id`: identificador único (para el historial), sin espacios.
- `origin` / `destination`: códigos IATA de aeropuerto (LIM, TPP, MAD, etc.).
- `outbound_date` / `return_date`: formato `YYYY-MM-DD`. `return_date` solo
  aplica si `trip_type` es `"round_trip"`.
- `trip_type`: `"round_trip"` o `"one_way"`.
- `currency`: moneda de los precios (`PEN`, `USD`, etc.).
- `outbound_departure_from` / `outbound_departure_to`: ventana horaria
  (`HH:MM`) de salida del vuelo de ida. Solo se consideran vuelos que salen
  dentro de esa ventana. Omite ambos campos si te da igual el horario.
- `active_until`: fecha (`YYYY-MM-DD`, hora de Perú) en que termina el
  monitoreo de la ruta. Al vencer, te avisa una vez y deja de consultar.
  Omítelo o déjalo en `null` para monitorear indefinidamente.

## Paso 6: probarlo

Ve a la pestaña **Actions** de tu repo → selecciona el workflow "Chequeo de
precios de vuelos" → **Run workflow**, para ejecutarlo manualmente sin
esperar al cron. Revisa los logs para confirmar que consultó bien los
precios. La primera corrida solo guarda el precio base — recién desde la
segunda en adelante puede detectar bajadas.

## Cambiar la frecuencia

Edita la línea `cron` en `.github/workflows/check-prices.yml`. Por ejemplo,
`"0 8,20 * * *"` corre dos veces al día (8am y 8pm UTC).

## Costo

$0. GitHub Actions es gratis para este volumen de ejecución, SerpAPI free
tier cubre hasta 500 búsquedas/mes, y la API de Telegram no tiene costo.
