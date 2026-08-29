#!/usr/bin/env python3

import json
import os
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE = BASE_DIR / "data" / "spotify_music.db"
ENV_FILE = BASE_DIR / ".env"

API_URL = "https://ws.audioscrobbler.com/2.0/"
DELAY_SECONDS = 1.0
TEST_LIMIT = 50


def load_dotenv():
    if not ENV_FILE.exists():
        raise FileNotFoundError(f"No existe .env: {ENV_FILE}")

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)

        key = key.strip()
        value = value.strip()

        if len(value) >= 2 and value[0] == value[-1]:
            if value[0] in {"'", '"'}:
                value = value[1:-1]

        os.environ.setdefault(key, value)


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def call_lastfm(api_key, mbid=None, method="track.getTopTags", artist=None, track_name=None):
    params = {
        "method": method,
        "api_key": api_key,
        "format": "json",
    }

    # Prefer mbid when provided, otherwise use artist+track if present
    if mbid:
        params["mbid"] = mbid
    else:
        if artist is not None and track_name is not None:
            params["artist"] = artist
            params["track"] = track_name

    query = urlencode(params)
    url = f"{API_URL}?{query}"

    # Redact the API key when printing the URL for debugging
    redacted_url = url.replace(api_key, "***REDACTED***")
    print(f"  Request URL: {redacted_url}")

    req = Request(url, headers={
        "User-Agent": "SpotifyMusicAnalyzer/1.0",
        "Accept": "application/json",
    })

    try:
        with urlopen(req, timeout=30) as response:
            text = response.read().decode("utf-8")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # return raw text if not JSON
                return text
    except HTTPError as exc:
        # Try to read response body to get Last.fm's error message
        body = None
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            body = None
        msg = f"HTTP Error {exc.code}: {exc.reason}"
        if body:
            msg = f"{msg} - {body}"
        raise RuntimeError(msg)
    except URLError as exc:
        raise RuntimeError(f"URL error: {exc}")


def main():
    load_dotenv()

    api_key = os.environ.get("LASTFM_API_KEY")

    if not api_key:
        raise RuntimeError(
            "No se encontró LASTFM_API_KEY en el archivo .env"
        )

    if not DATABASE.exists():
        raise FileNotFoundError(
            f"No existe la base de datos: {DATABASE}"
        )

    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                ts.spotify_id,
                ts.source_id,
                t.track_name,
                a.name AS artist_name
            FROM track_sources ts
            JOIN tracks t
                ON t.spotify_id = ts.spotify_id
            JOIN track_artists ta
                ON ta.spotify_id = t.spotify_id
            AND ta.artist_order = 0
            JOIN artists a
                ON a.spotify_id = ta.artist_id
            WHERE ts.source = 'lastfm'
            AND ts.status = 'success'
            ORDER BY ts.id
            LIMIT ?
            """,
            (TEST_LIMIT,),
        ).fetchall()

        print("=" * 72)
        print("LAST.FM — PRUEBA track.getTopTags")
        print("=" * 72)
        print(f"Tracks a probar: {len(rows)}")
        print()

        for index, row in enumerate(rows, start=1):
            print(f"[{index}/{len(rows)}] {row['track_name']} (spotify_id={row['spotify_id']})")
            print(f"  Artist : {row['artist_name']}")
            print(f"  MBID   : {row['source_id']}")

            # Try to get the Last.fm-provided track name from track_sources.data_json (if present)
            lastfm_track_name_db = None
            try:
                ts_row = connection.execute(
                    "SELECT data_json FROM track_sources WHERE spotify_id = ? AND source = 'lastfm' AND status = 'success' LIMIT 1",
                    (row['spotify_id'],),
                ).fetchone()
                if ts_row and ts_row['data_json']:
                    try:
                        ts_data = json.loads(ts_row['data_json'])
                        # Last.fm's track name is typically at track.name
                        if isinstance(ts_data, dict):
                            track_obj = ts_data.get('track')
                            if isinstance(track_obj, dict):
                                lastfm_track_name_db = track_obj.get('name')
                    except Exception:
                        lastfm_track_name_db = None
            except Exception:
                lastfm_track_name_db = None

            try:
                # If MBID is available, use it to get top tags
                # data = call_lastfm(api_key, mbid=row["source_id"], method="track.getTopTags")
                
                # If MBID is not available, use artist and track name
                data = call_lastfm(
                    api_key,
                    method="track.getTopTags",
                    artist=row["artist_name"],
                    track_name=row["track_name"],
                )

                # Try to extract track name from Last.fm response
                lastfm_track_name = None
                if isinstance(data, dict):
                    # Some endpoints (like track.getTopTags) do not include the track object,
                    # so try multiple places.
                    track_info = data.get("track") or data.get("toptags", {}).get("track")
                    if isinstance(track_info, dict):
                        lastfm_track_name = track_info.get("name")

                # If we don't have a Last.fm track name from the API response, call track.getInfo for diagnostics / name
                if not lastfm_track_name:
                    try:
                        # Prefer MBID if present in DB
                        mbid = row.get("source_id")
                        if mbid:
                            info = call_lastfm(api_key, mbid=mbid, method="track.getInfo")
                        else:
                            info = call_lastfm(
                                api_key,
                                method="track.getInfo",
                                artist=row["artist_name"],
                                track_name=row["track_name"],
                            )
                        if isinstance(info, dict):
                            t = info.get("track")
                            if isinstance(t, dict):
                                lastfm_track_name = t.get("name")
                    except Exception:
                        # ignore diagnostic failures — we still want to show Spotify name
                        lastfm_track_name = None

                # Prefer the name stored in the DB (track_sources.data_json) if present — use it for comparison
                final_lastfm_name = lastfm_track_name_db or lastfm_track_name

                # Print track names
                print(f"  Spotify: {row['track_name']}")
                if final_lastfm_name:
                    print(f"  Last.fm: {final_lastfm_name}")
                else:
                    print(f"  Last.fm: (sin nombre en track_sources) ")
                print(f"  Artist : {row['artist_name']}")

                if isinstance(data, dict) and data:
                    toptags = data.get("toptags", {})
                    if isinstance(toptags, dict):
                        tags = toptags.get("tag", [])
                        if not isinstance(tags, list):
                            tags = [tags] if tags else []

                        if tags:
                            print(f"  Tags   :")
                            for tag in tags[:10]:
                                if isinstance(tag, dict):
                                    tag_name = tag.get('name', 'Unknown')
                                    tag_count = tag.get('count', 0)
                                    print(f"    - {tag_name} (count={tag_count})")
                        else:
                            print(f"  Tags   : (sin tags)")
                else:
                    print("  Tags   : (Last.fm returned empty response)")

            except RuntimeError as exc:
                exc_text = str(exc)
                if 'HTTP Error 400' in exc_text and '{}' in exc_text:
                    print(f"  Spotify: {row['track_name']}")
                    print(f"  Artist : {row['artist_name']}")
                    print(f"  Tags   : (Last.fm HTTP 400: MBID/artist+track has no tags)")
                else:
                    print(f"  ERROR  : {exc}")

            except Exception as exc:
                print(f"  ERROR  : {exc}")

            finally:
                print()
                if index < len(rows):
                    time.sleep(DELAY_SECONDS)

    finally:
        connection.close()


if __name__ == "__main__":
    main()