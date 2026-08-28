# ChannelWatch Cron — GitHub Edition

Checker rápido en Python para listas IPTV públicas/autorizadas. Filtra, deduplica y valida HLS; conserva únicamente señales estables y publica un JSON por país para la web/app.

## GitHub automático

Este repo está listo para llamarse **`channelwatch-cron`** en GitHub.

- Cron: **1 vez por semana**, domingo 08:00 UTC (04:00 Bolivia).
- 20 países.
- Máximo 5 países en paralelo.
- Cada país corre en un job independiente para evitar una ejecución gigantesca secuencial.
- Dos fuentes base por país + `custom_urls` para tus fuentes futuras.
- GitHub Pages publica `public/data/*.json`.
- Conserva el JSON anterior si una comprobación falla de forma anormal.
- No hay preguntas interactivas en GitHub Actions.

Consulta [docs/GITHUB_SETUP.md](docs/GITHUB_SETUP.md) para los pasos de publicación.

## Salida

```text
public/data/
├── countries.json
├── bo.json
├── ar.json
├── br.json
└── ...
```

## Probar localmente en Windows

Haz doble clic en:

```text
PROBAR_LOCAL.bat
```

Para una prueba rápida elige `BO`. Para CORS local usa:

```text
http://localhost:3000
```

## Configuración de fuentes

`config/countries.toml` contiene los 20 países y deja `custom_urls = []` preparado para agregar listas propias.

`config/settings.toml` contiene las dos fuentes base y los límites rápidos del checker.

## Comandos

```bash
pip install -e ".[dev]"
python -m channelwatch validate-config
python -m channelwatch run --country BO
python -m channelwatch publish-index
pytest -q
```

## Uso responsable

El proyecto está diseñado para comprobar streams públicos o para los que tengas autorización. No retransmite contenido ni implementa mecanismos para saltarse autenticación, DRM o controles de acceso.
