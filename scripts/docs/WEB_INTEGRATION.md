# Consumir ChannelWatch desde Next.js y Kotlin

## Next.js

La Home puede descargar únicamente el índice:

```ts
export async function getCountries() {
  const response = await fetch(
    "https://TU-USUARIO.github.io/TU-REPO/data/countries.json",
    { cache: "no-store" }
  );

  if (!response.ok) throw new Error("No se pudo cargar countries.json");
  return response.json();
}
```

Cuando el usuario pulse Bolivia:

```ts
export async function getCountryChannels(code: string) {
  const normalized = code.toLowerCase();
  const response = await fetch(
    `https://TU-USUARIO.github.io/TU-REPO/data/${normalized}.json`,
    { cache: "no-store" }
  );

  if (!response.ok) throw new Error(`No se pudo cargar ${normalized}.json`);
  return response.json();
}
```

Para una web, prioriza canales con:

```text
status == "stable"
web_playable == true
```

Todos los canales publicados ya son estables, pero `web_playable` requiere que hayas configurado `CHANNELWATCH_WEB_ORIGIN` para que el cron pueda comprobar CORS contra tu dominio.

## Kotlin / Android

Android/Media3 normalmente no está sujeto a CORS del navegador. Puede usar canales publicados con:

```text
status == "stable"
android_playable == true
```

Ejemplo de modelo Kotlin simplificado:

```kotlin
data class Channel(
    val id: String,
    val name: String,
    val logo: String?,
    val stream: String,
    val status: String,
    val android_playable: Boolean,
    val web_playable: Boolean?
)
```

La app puede intentar `stream` primero y, si falla durante reproducción, probar los elementos de `alternates`.

## Caché

Como los feeds se regeneran periódicamente, evita empaquetarlos dentro del APK. Descárgalos desde la URL pública y guarda una copia local para que la app pueda abrir con el último feed conocido si no hay Internet.
