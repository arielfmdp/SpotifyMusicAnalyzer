# Spotify Music Analyzer

## 1. Propósito

Spotify Music Analyzer es una aplicación personal, local y de uso privado destinada a analizar, organizar, clasificar y explorar una biblioteca musical de Spotify de gran volumen.

El sistema utilizará la **Spotify Web API** como fuente de verdad para la información proveniente de Spotify y mantendrá una base de datos local destinada a facilitar consultas, análisis estadístico, clasificación, generación de agrupamientos y construcción dinámica de playlists.

El objetivo no es simplemente visualizar estadísticas de Spotify, sino construir un **sistema personal de análisis musical**, configurable y extensible, capaz de responder preguntas sobre la biblioteca y ejecutar acciones sobre ella.

---

## 2. Visión

La aplicación deberá evolucionar hacia una herramienta integral que permita:

* importar y mantener sincronizada la biblioteca musical del usuario;
* analizar tracks, artistas, álbumes, playlists y demás entidades relevantes;
* realizar búsquedas y consultas avanzadas;
* aplicar criterios de clasificación configurables;
* generar puntuaciones y rankings cuando resulte útil;
* descubrir agrupamientos y relaciones mediante técnicas estadísticas y de machine learning;
* construir playlists automáticamente a partir de criterios definidos por el usuario;
* reconstruir o analizar playlists existentes;
* explorar visualmente la biblioteca mediante un dashboard;
* generar estadísticas y visualizaciones;
* permitir al usuario experimentar con distintos modelos de clasificación y organización musical.

La aplicación deberá ser progresivamente más inteligente sin perder transparencia: el usuario debe poder comprender por qué un track fue incluido en determinada clasificación o playlist.

---

## 3. Objetivos

### 3.1 Objetivos principales

1. Obtener información de Spotify mediante sus mecanismos oficiales.
2. Mantener una representación local de la biblioteca relevante para análisis.
3. Mantener la información local sincronizada con Spotify.
4. Permitir búsquedas y filtros avanzados.
5. Clasificar tracks mediante reglas configurables.
6. Analizar características musicales y metadatos.
7. Producir estadísticas y visualizaciones.
8. Construir playlists a partir de criterios definidos por el usuario.
9. Experimentar con scoring, clustering y machine learning.
10. Proporcionar una interfaz web local completa mediante un dashboard.
11. Mantener una arquitectura suficientemente modular para incorporar nuevas capacidades posteriormente.

### 3.2 Objetivos secundarios

* Automatizar tareas repetitivas de organización musical.
* Facilitar el descubrimiento de patrones dentro de una biblioteca extensa.
* Permitir experimentación con diferentes criterios de clasificación.
* Conservar información histórica útil para análisis temporal cuando sea técnicamente viable.
* Evitar depender de servicios externos para el almacenamiento analítico.

---

## 4. Alcance inicial

El sistema se desarrollará inicialmente para uso personal y ejecución local.

El alcance inicial contempla:

* integración con Spotify Web API;
* autenticación mediante OAuth;
* importación de tracks;
* importación y análisis de playlists;
* almacenamiento local;
* sincronización;
* búsquedas;
* filtros;
* estadísticas;
* clasificación configurable;
* generación de playlists;
* dashboard web;
* visualizaciones;
* experimentación con scoring;
* clustering;
* machine learning cuando aporte valor real.

El sistema no se diseñará inicialmente como un servicio multiusuario ni como una aplicación pública alojada en Internet.

---

## 5. Principios del proyecto

### 5.1 Spotify como fuente de verdad

Spotify constituye la autoridad respecto de los datos y relaciones que provienen de Spotify.

La base local no reemplaza Spotify.

La aplicación podrá enriquecer localmente los datos para fines analíticos, pero deberá distinguir claramente entre:

* datos provenientes de Spotify;
* datos calculados por la aplicación;
* datos definidos por el usuario;
* resultados de modelos o algoritmos.

### 5.2 Simplicidad antes que complejidad

No se incorporará una tecnología, servicio o abstracción únicamente porque sea técnicamente interesante.

La complejidad deberá estar justificada por una necesidad real.

### 5.3 Desarrollo incremental

El proyecto se desarrollará por etapas funcionales.

Cada etapa deberá dejar el sistema en un estado razonablemente utilizable y verificable.

### 5.4 Transparencia de los algoritmos

Cuando el sistema clasifique o puntúe tracks, se procurará que los criterios utilizados puedan ser inspeccionados y modificados.

### 5.5 Configurabilidad

Los criterios musicales no deberán quedar rígidamente codificados.

El usuario deberá poder definir y modificar criterios de análisis y clasificación sin necesidad de modificar el núcleo de la aplicación siempre que sea razonablemente posible.

### 5.6 Experimentación controlada

El proyecto debe permitir probar diferentes estrategias de clasificación, scoring, clustering y machine learning sin comprometer los datos originales provenientes de Spotify.

### 5.7 Privacidad

La aplicación está destinada al uso personal.

Las credenciales, tokens, datos sensibles y configuración privada nunca deberán formar parte del repositorio Git.

---

## 6. Unidad musical fundamental

La unidad musical fundamental será inicialmente el **Spotify Track**.

La identidad de un track estará determinada por su identificador de Spotify.

No se intentará inicialmente resolver semánticamente si distintos tracks representan una misma obra musical.

Por ejemplo, versiones remasterizadas, grabaciones en vivo, versiones alternativas y ediciones diferentes podrán considerarse tracks independientes cuando Spotify los identifique de esa manera.

La noción de "obra musical" podrá incorporarse posteriormente si un caso de uso concreto justifica su necesidad.

---

## 7. Modelo conceptual

El sistema podrá trabajar inicialmente con entidades como:

* Track
* Artist
* Album
* Playlist
* Playlist Item
* User
* Metadata musical enriquecida
* Metadata
* Classification
* Classification Rule
* Score
* Cluster
* Analysis
* Synchronization State

La estructura definitiva será determinada después de estudiar en detalle la información actualmente disponible mediante la Spotify Web API.

No se considera definitiva esta lista.

---

## 8. Datos y persistencia

La aplicación utilizará inicialmente una base de datos local basada en **SQLite**.

SQLite se considera apropiado para la primera versión debido a:

* uso individual;
* ejecución local;
* ausencia de necesidad de un servidor de base de datos;
* facilidad de distribución;
* buen rendimiento para el volumen esperado;
* integración sencilla con Python.

El acceso a la base se realizará inicialmente mediante **SQLAlchemy**.

La arquitectura deberá evitar depender de características exclusivamente específicas de SQLite cuando ello dificulte una futura migración a otro motor.

La base local deberá distinguir entre datos importados desde Spotify y datos generados localmente.

---

## Estado actual del desarrollo

### Etapa actual

**Enriquecimiento musical mediante fuentes externas de metadata.**

La importación y estructuración inicial de la biblioteca de Spotify está completada. La etapa de enriquecimiento comenzó con MusicBrainz y se amplió posteriormente con Last.fm.

El objetivo de esta etapa es complementar los datos de Spotify mediante metadata musical disponible en fuentes externas gratuitas, manteniendo estrictamente la procedencia de cada fuente.

No se incorporará análisis acústico de archivos de audio en esta fase. El enriquecimiento se limita a metadata obtenida mediante APIs y otras fuentes externas.


### Estado de la base de datos

La base local `data/spotify_music.db` contiene actualmente:

- **5.493 tracks**
- **3.090 álbumes**
- **1.754 artistas**
- **6.550 relaciones track-artista**
- **5.493 tracks con ISRC**

La base SQLite se considera un artefacto local generado durante el proceso de importación y enriquecimiento, por lo que no forma parte del repositorio Git. Puede reconstruirse a partir del código y de las fuentes de datos.

### Componentes desarrollados

Actualmente se encuentran desarrollados, entre otros, los siguientes componentes:

- `app.py`
- `database.py`
- `database_stats.py`
- `import_spotify.py`
- `query_database.py`
- `create_enrichment_table.py`
- `analyze_musicbrainz_entities.py`

También se conservan herramientas de inspección, scripts experimentales y pruebas utilizadas durante la investigación y el desarrollo en `tools/` y `tests/`.

La documentación auxiliar se conserva en `docs/`.

### MusicBrainz v1 — adquisición y normalización

La etapa **MusicBrainz v1 — adquisición + normalización** fue completada, validada e incorporada al repositorio.

El ISRC se utiliza como identificador principal para relacionar los tracks de Spotify con registros de MusicBrainz.

La información original obtenida de MusicBrainz permanece conservada en `track_sources.data_json`.

Se implementó y validó `normalize_musicbrainz.py`, que genera las siguientes estructuras normalizadas:

* `mb_recordings`
* `mb_artists`
* `mb_recording_artists`
* `mb_artist_aliases`
* `mb_tags`
* `mb_recording_tags`
* `track_musicbrainz`

La normalización fue validada sobre una muestra de 51 tracks. Se comprobó además que las relaciones múltiples se conservan correctamente, ya que un track de Spotify puede estar relacionado con varios recordings de MusicBrainz.

Los releases de MusicBrainz no se normalizan en esta etapa y permanecen en el JSON original.

La etapa fue cerrada formalmente mediante commit y push al repositorio.


### Last.fm — fuente secundaria

Last.fm fue evaluado como fuente secundaria de metadata mediante su API, utilizando una API key almacenada localmente y excluida del repositorio.

Las respuestas obtenidas mediante `track.getInfo` se conservan en `track_sources.data_json`, manteniendo la procedencia de los datos.

Las pruebas realizadas sobre una muestra de 73 tracks mostraron una cobertura elevada para artista, listeners y playcount, y una cobertura parcial para álbum, duración y MBID.

Last.fm queda incorporado como fuente secundaria de enriquecimiento, sin sustituir los datos provenientes de Spotify ni de MusicBrainz.

#### Tags de tracks

Se evaluó `track.getTopTags`.

Las pruebas mediante MBID presentaron una cobertura insuficiente. Posteriormente se probó la modalidad documentada mediante `artist + track` sobre una muestra de 50 tracks.

El resultado fue:

* 2 tracks con tags;
* 48 tracks sin tags;
* cobertura observada: **4 %**.

Por lo tanto, Last.fm no se considera una fuente sistemática de tags de tracks. No obstante, los tags obtenidos se podrán conservar y utilizar cuando estén disponibles.

#### Tags de artistas

Se evaluó `artist.getTopTags` sobre una muestra de 50 artistas únicos.

La prueba mostró:

* 15 artistas con tags;
* 35 artistas sin tags;
* cobertura observada: **30 %**.

La cobertura se considera suficiente para utilizar Last.fm como fuente secundaria y opcional de tags de artistas.

La prueba mostró además que los resultados con tags correspondieron a las consultas realizadas mediante el parámetro `artist`, mientras que las consultas mediante MBID no devolvieron tags en la muestra analizada.

Por decisión del proyecto, para tags de artistas se utilizará `artist.getTopTags` mediante nombre de artista y, para tags de tracks, `track.getTopTags` mediante `artist + track`.

La ausencia de tags en Last.fm no se considera un error y no impedirá el enriquecimiento mediante otras fuentes.

Los datos de Last.fm permanecerán identificados por su fuente y no se mezclarán silenciosamente con datos provenientes de otras fuentes.


### Próximo objetivo

Continuar el enriquecimiento musical identificando únicamente los atributos de metadata que todavía resulten necesarios para las funcionalidades previstas de búsqueda, filtrado, organización, catalogación, clasificación y análisis.

Las nuevas fuentes deberán justificarse por una necesidad concreta de metadata y evaluarse por cobertura, calidad, disponibilidad, límites de uso, coste y facilidad de automatización.

Se priorizarán fuentes gratuitas y accesibles mediante API.

La arquitectura de enriquecimiento mantendrá separada la procedencia de cada fuente y utilizará el JSON raw únicamente cuando conserve información potencialmente útil que no haya sido normalizada.

No se incorporará una capa de análisis acústico de audio en esta fase.

---

## 9. Sincronización con Spotify

La sincronización será una característica fundamental del sistema.

El modelo conceptual será:

```text
Spotify
   ↓
sincronización
   ↓
Base local
   ↓
análisis / clasificación / estadísticas
   ↓
acciones sobre Spotify
```

Spotify será la fuente de verdad para los datos remotos.

La aplicación deberá poder detectar, en la medida permitida por la API:

* nuevos tracks;
* tracks eliminados o modificados;
* cambios en playlists;
* modificaciones relevantes de metadata;
* cambios en la biblioteca del usuario.

La estrategia exacta de sincronización será definida después de estudiar los endpoints, límites y comportamiento actual de la API.

---

## 10. Clasificación configurable

El sistema deberá permitir definir reglas de clasificación sobre tracks.

Las reglas podrán combinar diferentes atributos, por ejemplo:

* artista;
* álbum;
* género cuando esté disponible;
* duración;
* popularidad;
* características musicales disponibles;
* pertenencia a playlists;
* atributos calculados;
* criterios estadísticos;
* resultados de otros análisis.

La clasificación podrá producir:

* categorías;
* etiquetas;
* conjuntos de tracks;
* playlists derivadas.

Las reglas deberán ser configurables y potencialmente combinables.

---

## 11. Scoring

Se estudiará la posibilidad de asignar una puntuación numérica a cada track mediante la combinación ponderada de diferentes criterios.

Un scoring podría permitir representar conceptos como:

* afinidad con determinado estilo;
* adecuación a una playlist;
* energía;
* accesibilidad;
* similitud con una selección de referencia;
* prioridad para determinadas colecciones.

El modelo concreto de scoring no está definido todavía y será diseñado posteriormente mediante ejemplos reales.

---

## 12. Clustering y machine learning

El proyecto podrá incorporar técnicas de aprendizaje automático y análisis estadístico cuando proporcionen una ventaja real.

Entre las posibilidades se encuentran:

* clustering de tracks;
* reducción dimensional;
* detección de grupos musicales;
* búsqueda de similitud;
* detección de anomalías;
* clasificación supervisada;
* recomendación basada en características de la biblioteca.

El uso de machine learning será experimental y orientado al análisis personal.

No se incorporará ML simplemente por razones de sofisticación tecnológica.

---

## 13. Playlists

La aplicación deberá poder trabajar con playlists de Spotify y, cuando la API lo permita:

* obtener sus tracks;
* analizar su contenido;
* reconstruir localmente su estructura;
* compararlas;
* generar playlists nuevas;
* actualizar playlists existentes;
* crear playlists derivadas de clasificaciones;
* crear playlists a partir de criterios dinámicos.

Una playlist generada por la aplicación deberá poder conservar una relación trazable con los criterios que originaron su creación.

---

## 14. Dashboard

El dashboard será una aplicación web local completa, no solamente un panel de estadísticas.

Inicialmente se utilizará:

* Python;
* Flask;
* Jinja2;
* Bootstrap;
* JavaScript.

El dashboard deberá evolucionar hacia una interfaz funcional que permita:

* explorar la biblioteca;
* buscar;
* filtrar;
* clasificar;
* analizar;
* visualizar estadísticas;
* administrar reglas;
* ejecutar análisis;
* crear playlists;
* revisar playlists existentes;
* consultar resultados de clustering y ML;
* configurar la sincronización.

La arquitectura deberá mantener separadas la lógica de negocio, persistencia y presentación para facilitar una futura evolución de la interfaz.

No se considera necesario introducir React o Vue en la primera versión.

La aplicación deberá diseñarse de modo que una futura migración de la capa de presentación no obligue a reescribir el núcleo de negocio.

---

## 15. Estadísticas y visualización

Las estadísticas serán una parte importante de la aplicación.

Podrán incluir:

* distribución por artistas;
* distribución por álbumes;
* distribución por características musicales;
* evolución temporal;
* composición de playlists;
* rankings;
* comparaciones;
* correlaciones;
* agrupamientos;
* análisis de clasificación;
* métricas derivadas.

Las visualizaciones se incorporarán progresivamente según los casos de uso que demuestren utilidad.

---

## 16. Seguridad y credenciales

Las credenciales utilizadas para acceder a Spotify no deberán almacenarse en el repositorio.

La aplicación deberá utilizar mecanismos locales de configuración y variables de entorno o archivos excluidos de Git.

Nunca deberán aparecer en:

* código fuente;
* README;
* documentación pública;
* commits;
* issues;
* logs.

La estrategia concreta de autenticación y almacenamiento de tokens será definida durante la implementación de la integración con Spotify.

---

## 17. Arquitectura conceptual

La arquitectura prevista inicialmente será aproximadamente:

```text
┌───────────────────────────────────────┐
│              Dashboard                │
│       Flask / Jinja / Bootstrap       │
│             JavaScript                │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│          Application / Services       │
│                                       │
│ Synchronization                       │
│ Classification                         │
│ Scoring                               │
│ Analysis                              │
│ Playlist Management                   │
│ Statistics                            │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│             Data Layer                │
│            SQLAlchemy                 │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│                SQLite                 │
└───────────────────────────────────────┘

                    ▲
                    │
                    │
┌───────────────────┴───────────────────┐
│          Spotify Web API              │
│       Fuente de verdad externa        │
└───────────────────────────────────────┘
```

Esta arquitectura es conceptual y podrá modificarse durante el desarrollo.

---

## 18. Evolución futura

El proyecto deberá mantener abiertas posibilidades como:

* modelos de recomendación;
* machine learning avanzado;
* análisis temporal;
* descubrimiento automático de patrones;
* generación inteligente de playlists;
* sistemas de scoring personalizados;
* comparación entre bibliotecas o períodos;
* nuevas fuentes de datos;
* interfaz frontend independiente;
* migración a otro motor de base de datos;
* ejecución programada de análisis y sincronizaciones.

Estas posibilidades no forman parte necesariamente de la primera versión.

---

## 19. Fuera del alcance inicial

No forman parte de la primera versión:

* aplicación multiusuario;
* servicio público;
* infraestructura cloud;
* aplicación móvil;
* frontend React/Vue;
* sistema de recomendación comercial;
* publicación o distribución del sistema;
* resolución automática de identidad entre distintas grabaciones que representen una misma obra.

Podrán reconsiderarse posteriormente si aparecen necesidades concretas.

---

## 20. Criterio general de éxito

Spotify Music Analyzer será considerado exitoso cuando permita al usuario transformar una biblioteca extensa y difícil de manejar en un sistema musical:

* consultable;
* analizable;
* clasificable;
* estadísticamente explorable;
* configurable;
* automatizable;
* sincronizado con Spotify;
* capaz de generar y administrar playlists;
* y extensible hacia técnicas avanzadas de análisis y machine learning.

El objetivo final no es simplemente "tener una base de datos de Spotify", sino disponer de una **herramienta personal de inteligencia y organización musical**.


## Estado actual

Checkpoint: 2026-08-24

- Integración básica con Spotify implementada.
- Base SQLite creada en data/spotify_music.db.
- Modelo inicial de datos implementado.
- Importación inicial de biblioteca completada.
- 5.493 tracks importados.
- 3.090 álbumes.
- 1.754 artistas.
- 6.550 relaciones track-artista.
- Todos los tracks importados disponen de ISRC.
- Próxima etapa: enriquecimiento musical externo de los tracks.
- Spotify audio_features/audio_analysis no se consideran dependencias disponibles.
- MusicBrainz forma parte del pipeline de enriquecimiento.
- Soundcharts queda como fuente complementaria para casos no resueltos.


### Enriquecimiento musical — estado

La etapa MusicBrainz v1 — adquisición + normalización quedó completada y validada.

Se mantiene el JSON original de MusicBrainz en track_sources.data_json y se
dispone de las tablas normalizadas correspondientes a recordings, artists,
aliases, tags y relaciones con tracks.

Se evaluó Last.fm como fuente secundaria de metadata mediante su API.

Las pruebas realizadas sobre una muestra local de tracks demostraron una
cobertura elevada para artista, listeners y playcount, y una cobertura
razonable para álbum, duración y MBID. Last.fm queda incorporado como fuente
secundaria, manteniendo siempre la procedencia de sus datos.

Los tags de track de Last.fm fueron evaluados mediante track.getTopTags sobre
50 tracks. La cobertura observada fue insuficiente (2/50), por lo que no se
utilizará Last.fm como fuente sistemática de tags de tracks.

Los tags de artista fueron evaluados mediante artist.getTopTags sobre 50
artistas únicos. Se obtuvieron tags en 15/50 casos (30 %). Esta cobertura se
considera suficiente para utilizar Last.fm como fuente secundaria opcional de
tags de artista, sin considerar su ausencia como error.

Las estadísticas listeners y playcount se consideran datos de Last.fm y
deberán conservar su procedencia y fecha de adquisición.

No se incorporará análisis acústico de archivos de audio en esta fase del
proyecto. El enriquecimiento se concentrará exclusivamente en metadata
proveniente de fuentes externas.

La búsqueda de nuevas fuentes se realizará únicamente cuando exista una
necesidad concreta de metadata que las fuentes actuales no cubran
adecuadamente.


## Estado del pipeline
Spotify
  ↓
Importación local              ← COMPLETADO
  ↓
Enriquecimiento MusicBrainz    ← COMPLETADO
  ↓
Fuentes musicales adicionales  ← PENDIENTE
  ↓
Análisis / clasificación       ← PENDIENTE

