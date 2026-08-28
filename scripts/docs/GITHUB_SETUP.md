# Subir ChannelWatch Cron a GitHub

## Nombre recomendado del repositorio

Usa exactamente:

```text
channelwatch-cron
```

La web `tv-latino-web` usa ese nombre para encontrar automáticamente los JSON publicados.

## Qué hace GitHub automáticamente

El workflow `.github/workflows/check-and-publish.yml`:

1. Se ejecuta una vez por semana: domingo a las 08:00 UTC (04:00 Bolivia).
2. Ejecuta las pruebas una sola vez.
3. Lanza 20 trabajos, uno por país.
4. Como máximo revisa 5 países al mismo tiempo.
5. Cada país conserva su propio historial SQLite mediante GitHub Actions Cache.
6. Cada país conserva el JSON anterior como protección si una fuente cae o la cantidad de canales baja de forma anormal.
7. El trabajo final reúne todos los `<pais>.json`, genera `countries.json` y publica `public/` en GitHub Pages.

No pregunta país, CORS ni ninguna opción durante la ejecución automática.

## Origen web automático

El cron comprueba CORS usando automáticamente:

```text
https://TU-USUARIO.github.io
```

Ese es el Origin real del navegador tanto para `channelwatch-cron` como para `tv-latino-web` cuando ambos están en GitHub Pages bajo la misma cuenta.

## Primera publicación

Después de subir el repo:

1. En GitHub abre **Settings > Pages**.
2. En **Build and deployment > Source**, selecciona **GitHub Actions**.
3. Abre **Actions > Weekly channel check and JSON publish**.
4. Pulsa **Run workflow** una sola vez para generar los primeros JSON inmediatamente.

Después no necesitas hacer nada: el cron corre semanalmente solo.

## URLs resultantes

Si tu usuario es `ejemplo`, los datos quedan en:

```text
https://ejemplo.github.io/channelwatch-cron/data/countries.json
https://ejemplo.github.io/channelwatch-cron/data/bo.json
https://ejemplo.github.io/channelwatch-cron/data/ar.json
```

## Agregar más fuentes en el futuro

Edita `config/countries.toml`:

```toml
[countries.BO]
name = "Bolivia"
custom_urls = [
  "https://tu-fuente.example/bolivia.m3u"
]
```

El cron combinará esas fuentes con las dos fuentes base ya configuradas.
