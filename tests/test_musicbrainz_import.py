import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE = PROJECT_ROOT / "data" / "spotify_music.db"

MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2/recording"

HEADERS = {
    "User-Agent": "SpotifyMusicAnalyzer/0.1 (personal project)"
}

TEST_TRACKS = 50

DELAY_SECONDS = 1.1
MAX_RETRIES = 3


def get_tracks():
    connection = sqlite3.connect(DATABASE)

    rows = connection.execute("""
        SELECT
            t.spotify_id,
            t.isrc,
            t.track_name,
            GROUP_CONCAT(a.name, ', ') AS artist_name
        FROM tracks t
        LEFT JOIN track_artists ta
            ON ta.spotify_id = t.spotify_id
        LEFT JOIN artists a
            ON a.spotify_id = ta.artist_id
        WHERE t.isrc IS NOT NULL
          AND t.isrc != ''
        GROUP BY t.spotify_id
        ORDER BY t.rowid
        LIMIT ?
    """, (TEST_TRACKS,)).fetchall()

    connection.close()

    return rows


def search_musicbrainz(isrc):

    params = {
        "query": f"isrc:{isrc}",
        "fmt": "json",
        "limit": 5,
    }

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            response = requests.get(
                MUSICBRAINZ_URL,
                params=params,
                headers=HEADERS,
                timeout=30,
            )

            response.raise_for_status()

            return response.json()

        except requests.RequestException as error:

            if attempt == MAX_RETRIES:
                raise

            wait = attempt * 3

            print(
                f"    Error (intento {attempt}/{MAX_RETRIES})"
                f" — reintentando en {wait}s..."
            )

            time.sleep(wait)


def save_result(
    spotify_id,
    isrc,
    source_id,
    status,
    data,
):

    connection = sqlite3.connect(DATABASE)

    connection.execute("""
        INSERT INTO track_sources (
            spotify_id,
            isrc,
            source,
            source_id,
            status,
            data_json,
            retrieved_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(spotify_id, source)
        DO UPDATE SET
            isrc = excluded.isrc,
            source_id = excluded.source_id,
            status = excluded.status,
            data_json = excluded.data_json,
            retrieved_at = excluded.retrieved_at
    """, (
        spotify_id,
        isrc,
        "musicbrainz",
        source_id,
        status,
        json.dumps(data, ensure_ascii=False),
        datetime.now(timezone.utc).isoformat(),
    ))

    connection.commit()
    connection.close()


def main():

    print("=" * 80)
    print("MUSICBRAINZ — IMPORTACIÓN DE PRUEBA")
    print("=" * 80)

    tracks = get_tracks()

    print(f"\nTracks a analizar: {len(tracks)}\n")

    found = 0
    not_found = 0
    errors = 0

    for index, track in enumerate(tracks, start=1):

        spotify_id, isrc, track_name, artist_name = track

        print("-" * 80)
        print(
            f"{index:02d}. {artist_name} - {track_name}"
        )
        print(f"    ISRC: {isrc}")

        try:

            data = search_musicbrainz(isrc)

            recordings = data.get("recordings", [])

            if not recordings:

                print("    MusicBrainz: NO ENCONTRADO")

                save_result(
                    spotify_id,
                    isrc,
                    None,
                    "not_found",
                    data,
                )

                not_found += 1

            else:

                recording = recordings[0]

                musicbrainz_id = recording.get("id")

                print(
                    f"    MusicBrainz: {musicbrainz_id}"
                )

                save_result(
                    spotify_id,
                    isrc,
                    musicbrainz_id,
                    "found",
                    data,
                )

                found += 1

        except requests.RequestException as error:

            print(f"    ERROR: {error}")

            save_result(
                spotify_id,
                isrc,
                None,
                "error",
                {
                    "error": str(error)
                },
            )

            errors += 1

        time.sleep(DELAY_SECONDS)

    print("\n")
    print("=" * 80)
    print("RESULTADO")
    print("=" * 80)

    print(f"\nTracks analizados : {len(tracks)}")
    print(f"Encontrados       : {found}")
    print(f"No encontrados    : {not_found}")
    print(f"Errores           : {errors}")


if __name__ == "__main__":
    main()