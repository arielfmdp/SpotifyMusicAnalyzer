"""
Spotify Music Analyzer
Last.fm metadata acquisition.

Acquires Last.fm track metadata for the local Spotify catalog and stores the
complete API response in track_sources.data_json.

Identification strategy:
- primary artist + track name, using Spotify's existing track metadata;
- Last.fm's returned MusicBrainz ID is preserved in the source row when present.

The script intentionally does NOT normalize Last.fm data. Normalization is a
separate stage, following the same source/provenance model used for
MusicBrainz.

API key:
    LASTFM_API_KEY is read from the local .env file.
    The script does not require python-dotenv.

Rate limiting:
    Requests are spaced by at least one second. Last.fm documents rate-limit
    error 29; a small retry/backoff is also used for temporary service errors.

Safe to execute repeatedly: successful source rows are skipped unless
--refresh is supplied.

USOS:
python fetch_lastfm_v2.py
→ máximo 51 tracks.

python fetch_lastfm_v2.py --limit 10
→ máximo 10.

python fetch_lastfm_v2.py --all
→ catálogo completo.
"""

import argparse
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "data" / "spotify_music.db"
LASTFM_ENDPOINT = "https://ws.audioscrobbler.com/2.0/"
MIN_REQUEST_INTERVAL = 1.0
MAX_RETRIES = 3


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def load_dotenv():
    """Load simple KEY=VALUE entries from the project .env file."""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        if key:
            os.environ.setdefault(key, value)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def build_parser():
    parser = argparse.ArgumentParser(
        description="Acquire Last.fm track metadata into track_sources."
    )
    parser.add_argument(
        "--limit", type=int, default=51,
        help="Process at most N tracks (default: 51).",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Process the complete catalog instead of the 51-track sample.",
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Re-query tracks that already have a successful Last.fm source row.",
    )
    parser.add_argument(
        "--delay", type=float, default=MIN_REQUEST_INTERVAL,
        help="Minimum delay between Last.fm requests in seconds (default: 1.0).",
    )
    return parser


def load_tracks(connection, refresh=False, limit=None):
    query = """
        SELECT t.spotify_id, t.isrc, t.track_name, a.name AS artist_name
        FROM tracks AS t
        JOIN track_artists AS ta
            ON ta.spotify_id = t.spotify_id
           AND ta.artist_order = 0
        JOIN artists AS a ON a.spotify_id = ta.artist_id
    """
    params = []
    if not refresh:
        query += """
        LEFT JOIN track_sources AS ts
            ON ts.spotify_id = t.spotify_id AND ts.source = 'lastfm'
        WHERE ts.id IS NULL OR ts.status != 'success'
        """
    query += " ORDER BY t.spotify_id"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    return connection.execute(query, params).fetchall()


def request_lastfm(api_key, artist, track, timeout=30):
    params = {
        "method": "track.getInfo",
        "api_key": api_key,
        "artist": artist,
        "track": track,
        "autocorrect": 1,
        "format": "json",
    }
    url = f"{LASTFM_ENDPOINT}?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "User-Agent": "SpotifyMusicAnalyzer/1.0",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Last.fm returned a non-object JSON response")
    if "error" in data:
        raise RuntimeError(
            f"Last.fm API error {data.get('error')}: {data.get('message', '')}"
        )
    return data


def extract_source_id(data):
    track = data.get("track")
    if not isinstance(track, dict):
        return None
    if track.get("mbid"):
        return track["mbid"]
    if track.get("id"):
        return str(track["id"])
    return None


def save_source(connection, row, status, data=None, source_id=None):
    connection.execute(
        """
        INSERT INTO track_sources (
            spotify_id, isrc, source, source_id, status, data_json, retrieved_at
        )
        VALUES (?, ?, 'lastfm', ?, ?, ?, ?)
        ON CONFLICT(spotify_id, source) DO UPDATE SET
            isrc = excluded.isrc,
            source_id = excluded.source_id,
            status = excluded.status,
            data_json = excluded.data_json,
            retrieved_at = excluded.retrieved_at
        """,
        (
            row["spotify_id"], row["isrc"], source_id, status,
            json.dumps(data, ensure_ascii=False) if data is not None else None,
            utc_now(),
        ),
    )


def acquire_track(api_key, row, delay, last_request_time):
    if last_request_time is not None:
        elapsed = time.monotonic() - last_request_time
        if elapsed < delay:
            time.sleep(delay - elapsed)

    retry_delay = 2.0
    for attempt in range(1, MAX_RETRIES + 1):
        request_started = time.monotonic()
        try:
            data = request_lastfm(api_key, row["artist_name"], row["track_name"])
            return data, request_started, None
        except HTTPError as exc:
            request_started = time.monotonic()
            if exc.code not in (429, 500, 502, 503, 504) or attempt >= MAX_RETRIES:
                return None, request_started, f"HTTP {exc.code}: {exc.reason}"
        except (URLError, TimeoutError, json.JSONDecodeError, RuntimeError, ValueError) as exc:
            request_started = time.monotonic()
            if attempt >= MAX_RETRIES:
                return None, request_started, str(exc)
        time.sleep(retry_delay)
        retry_delay *= 2

    return None, time.monotonic(), "unknown acquisition error"


def print_summary(counters):
    print()
    print("=" * 80)
    print("SPOTIFY MUSIC ANALYZER — LAST.FM ADQUISICIÓN")
    print("=" * 80)
    print(f"Tracks seleccionados                     : {counters['selected']}")
    print(f"Consultas realizadas                     : {counters['requested']}")
    print(f"Respuestas exitosas                      : {counters['success']}")
    print(f"Tracks con error                         : {counters['errors']}")
    print()
    print("La respuesta completa de Last.fm fue almacenada en track_sources.data_json.")
    print("No se realizó normalización en esta etapa.")
    print("=" * 80)


def main():
    args = build_parser().parse_args()
    if not DATABASE.exists():
        raise FileNotFoundError(f"No existe la base de datos: {DATABASE}")

    load_dotenv()
    api_key = os.environ.get("LASTFM_API_KEY")
    if not api_key:
        raise RuntimeError("Falta LASTFM_API_KEY en el entorno.")
    if args.delay < 1.0:
        raise ValueError("El delay mínimo permitido por este script es 1.0 segundo.")

    connection = get_connection()
    counters = {"selected": 0, "requested": 0, "success": 0, "errors": 0}
    try:
        limit = None if args.all else args.limit
        rows = load_tracks(connection, refresh=args.refresh, limit=limit)
        counters["selected"] = len(rows)
        last_request_time = None
        for index, row in enumerate(rows, start=1):
            print(f"[{index}/{len(rows)}] {row['artist_name']} — {row['track_name']}")
            counters["requested"] += 1
            data, last_request_time, error = acquire_track(
                api_key, row, args.delay, last_request_time
            )
            if data is not None:
                save_source(
                    connection, row, "success", data, extract_source_id(data)
                )
                counters["success"] += 1
                print("  OK")
            else:
                save_source(connection, row, "error", {"error": error}, None)
                counters["errors"] += 1
                print(f"  ERROR: {error}")
            connection.commit()
    finally:
        connection.close()
    print_summary(counters)


if __name__ == "__main__":
    main()
