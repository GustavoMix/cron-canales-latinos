# Agregar fuentes y países

## Agregar una fuente M3U propia a un país existente

`config/countries.toml` permite una lista ilimitada de fuentes por país:

```toml
[countries.BO]
name = "Bolivia"
custom_urls = [
  "https://ejemplo.com/lista-a.m3u",
  "https://ejemplo.com/lista-b.m3u",
  "https://ejemplo.com/lista-c.m3u"
]
```

Cada URL adicional recibe internamente un ID `custom_1`, `custom_2`, etc. Como la fuente está declarada dentro de Bolivia, los canales se consideran bolivianos aunque la lista no incluya `tvg-country`.

Solo agrega fuentes públicas o autorizadas. No pongas URLs que contengan usuario/contraseña ni credenciales privadas.

## Agregar un país nuevo

Ejemplo para Estados Unidos:

```toml
[countries.US]
name = "Estados Unidos"
custom_urls = []
```

Eso basta para que ChannelWatch construya automáticamente:

```text
https://iptv-org.github.io/iptv/countries/us.m3u
```

y además filtre `US` desde Free-TV.

## Cambiar las fuentes base

Están declaradas en `config/settings.toml`:

```toml
[[builtin_sources]]
id = "iptv_org"
url_template = "https://iptv-org.github.io/iptv/countries/{country_lower}.m3u"
mode = "fixed"
priority = 10

[[builtin_sources]]
id = "free_tv"
url = "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"
mode = "attribute"
priority = 20
```

`mode = "fixed"` significa que la lista pertenece al país solicitado. `mode = "attribute"` exige que cada entrada M3U tenga un `tvg-country` coincidente.

## URLs temporales

Por defecto se descartan URLs que parecen depender de tokens temporales. Si una fuente pública usa parámetros firmados estables y sabes que quieres aceptarlos, puedes desactivar el filtro globalmente:

```toml
[checker]
block_temporary_urls = false
```

Hazlo solo si entiendes que esas URLs pueden caducar y volver inestable el feed.
