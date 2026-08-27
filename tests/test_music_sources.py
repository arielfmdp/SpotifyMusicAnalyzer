import csv
import os
import time
import requests

from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyPKCE


# =========================================================
# CONFIGURACIÓN
# =========================================================

load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

SCOPE = (
    "user-read-private "
    "user-library-read "
    "playlist-read-private "
    "playlist-read-collaborative"
)

TEST_TRACKS = 50

MB_URL = "https://musicbrainz.org/ws/2/recording"

MB_HEADERS = {
    "User-Agent": "SpotifyMusicAnalyzer/0.1 (arielfmdp@gmail.com)"
}

AB_URL = "https://acousticbrainz.org/api/v1/high-level"

MB_REQUEST_INTERVAL = 1.1


# =========================================================
# SPOTIFY
# =========================================================

sp_oauth = SpotifyPKCE(
    client_id=CLIENT_ID,
    redirect_uri=REDIRECT_URI,
    scope=SCOPE,
    open_browser=False,
    cache_path=".spotify_cache",
)

token = sp_oauth.get_cached_token()

if not token:
    raise RuntimeError(
        "No hay una sesión Spotify válida."
    )

sp = spotipy.Spotify(auth=token["access_token"])


# =========================================================
# MUSICBRAINZ
# =========================================================

last_mb_request = 0


def find_musicbrainz_recording(isrc):

    global last_mb_request

    if not isrc:
        return None, "no_isrc"

    # Garantizar <= 1 request/segundo
    elapsed = time.monotonic() - last_mb_request

    if elapsed < MB_REQUEST_INTERVAL:
        time.sleep(MB_REQUEST_INTERVAL - elapsed)

    params = {
        "query": f"isrc:{isrc}",
        "fmt": "json",
        "limit": 5,
    }

    for attempt in range(3):

        try:

            response = requests.get(
                MB_URL,
                params=params,
                headers=MB_HEADERS,
                timeout=20,
            )

            last_mb_request = time.monotonic()

            if response.status_code == 503:

                wait = 3 * (attempt + 1)

                print(
                    f"    MusicBrainz 503. "
                    f"Reintentando en {wait}s..."
                )

                time.sleep(wait)
                continue

            response.raise_for_status()

            data = response.json()
            recordings = data.get("recordings", [])

            if not recordings:
                return None, "not_found"

            return recordings[0], "found"

        except requests.RequestException as e:

            last_mb_request = time.monotonic()

            if attempt == 2:
                return None, f"error:{type(e).__name__}"

            time.sleep(3 * (attempt + 1))

    return None, "error"


# =========================================================
# ACOUSTICBRAINZ
# =========================================================

def get_acousticbrainz_bulk(mbids):

    if not mbids:
        return {}

    params = {
        "recording_ids": ";".join(mbids),
        "map_classes": "true",
    }

    response = requests.get(
        AB_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# OBTENER TRACKS DE SPOTIFY
# =========================================================

items = []

offset = 0
page_size = 50

while len(items) < TEST_TRACKS:

    remaining = TEST_TRACKS - len(items)

    limit = min(page_size, remaining)

    page = sp.current_user_saved_tracks(
        limit=limit,
        offset=offset,
    )

    items.extend(page["items"])

    if not page["next"]:
        break

    offset += limit


print()
print("=" * 80)
print("SPOTIFY → MUSICBRAINZ → ACOUSTICBRAINZ")
print("=" * 80)

print(f"\nBiblioteca total: {page['total']}")
print(f"Analizando: {len(items)} tracks\n")

# =========================================================
# FASE 1 — SPOTIFY → MUSICBRAINZ
# =========================================================

results = []
mbids = []

stats = {
    "tracks": len(items),
    "isrc": 0,
    "no_isrc": 0,
    "mb_found": 0,
    "mb_not_found": 0,
    "mb_error": 0,
}


for position, item in enumerate(items, start=1):

    track = item["track"]

    name = track["name"]
    artist = ", ".join(
        artist["name"]
        for artist in track["artists"]
    )

    spotify_id = track["id"]

    isrc = (
        track.get("external_ids", {})
        .get("isrc")
    )

    print(
        f"[{position:03d}/{len(items)}] "
        f"{artist} - {name}"
    )

    result = {
        "spotify_id": spotify_id,
        "artist": artist,
        "track": name,
        "isrc": isrc or "",
        "musicbrainz_id": "",
        "musicbrainz_status": "",
        "acousticbrainz": "",
        "danceability": "",
        "genre": "",
    }

    if isrc:
        stats["isrc"] += 1

        recording, status = find_musicbrainz_recording(isrc)

        result["musicbrainz_status"] = status

        if recording:

            mbid = recording["id"]

            result["musicbrainz_id"] = mbid

            mbids.append(mbid)

            stats["mb_found"] += 1

        elif status == "not_found":

            stats["mb_not_found"] += 1

        else:

            stats["mb_error"] += 1

    else:

        stats["no_isrc"] += 1
        result["musicbrainz_status"] = "no_isrc"

    results.append(result)


# =========================================================
# FASE 2 — MUSICBRAINZ → ACOUSTICBRAINZ
# =========================================================

print()
print("Consultando AcousticBrainz...")

# Eliminamos duplicados
unique_mbids = list(dict.fromkeys(mbids))

acoustic_data = {}

# AcousticBrainz admite hasta 25 MBIDs por petición
for start in range(0, len(unique_mbids), 25):

    batch = unique_mbids[start:start + 25]

    print(
        f"  AcousticBrainz: "
        f"{start + 1}-{start + len(batch)} "
        f"de {len(unique_mbids)}"
    )

    try:

        data = get_acousticbrainz_bulk(batch)

        acoustic_data.update(data)

    except Exception as e:

        print(
            f"  ERROR AcousticBrainz: "
            f"{type(e).__name__}: {e}"
        )


# =========================================================
# EXTRAER DATOS A LOS RESULTADOS
# =========================================================

ab_found = 0
ab_not_found = 0

for result in results:

    mbid = result["musicbrainz_id"]

    if not mbid:
        continue

    data = acoustic_data.get(mbid)

    if not data:

        ab_not_found += 1
        continue

    ab_found += 1

    result["acousticbrainz"] = "found"

    # AcousticBrainz devuelve offset 0
    document = data.get("0", {})

    highlevel = document.get("highlevel", {})

    danceability = highlevel.get("danceability")

    if danceability:

        result["danceability"] = danceability.get(
            "probability",
            ""
        )

    genre = highlevel.get("genre_rosamerica")

    if genre:

        result["genre"] = genre.get(
            "value",
            ""
        )


# =========================================================
# GUARDAR CSV
# =========================================================

output_file = "test_music_sources.csv"

fieldnames = [
    "spotify_id",
    "artist",
    "track",
    "isrc",
    "musicbrainz_id",
    "musicbrainz_status",
    "acousticbrainz",
    "danceability",
    "genre",
]

with open(
    output_file,
    "w",
    newline="",
    encoding="utf-8",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames,
    )

    writer.writeheader()
    writer.writerows(results)


# =========================================================
# RESUMEN
# =========================================================

print()
print("=" * 80)
print("RESULTADO")
print("=" * 80)

print()
print(f"Tracks analizados             : {stats['tracks']}")
print(f"Con ISRC                      : {stats['isrc']}")
print(f"Sin ISRC                      : {stats['no_isrc']}")

print()
print("MusicBrainz")
print(f"  Encontrados                 : {stats['mb_found']}")
print(f"  No encontrados              : {stats['mb_not_found']}")
print(f"  Errores                     : {stats['mb_error']}")

print()
print("AcousticBrainz")
print(f"  Con datos                   : {ab_found}")
print(f"  Sin datos                   : {ab_not_found}")

if stats["isrc"]:
    print()
    print(
        "Cobertura Spotify → MusicBrainz: "
        f"{stats['mb_found'] / stats['isrc']:.1%}"
    )

if stats["mb_found"]:
    print(
        "Cobertura MusicBrainz → AcousticBrainz: "
        f"{ab_found / stats['mb_found']:.1%}"
    )

if stats["isrc"]:
    print(
        "Cobertura Spotify → AcousticBrainz: "
        f"{ab_found / stats['isrc']:.1%}"
    )

print()
print(f"Resultados guardados en: {output_file}")
print()