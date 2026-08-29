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


def call_lastfm(api_key, method, artist=None, mbid=None):
    params = {
        "method": method,
        "api_key": api_key,
        "format": "json",
    }

    if mbid:
        params["mbid"] = mbid
    elif artist:
        params["artist"] = artist

    query = urlencode(params)
    url = f"{API_URL}?{query}"

    redacted_url = url.replace(api_key, "***REDACTED***")
    print(f"  Request URL: {redacted_url}")

    request = Request(
        url,
        headers={
            "User-Agent": "SpotifyMusicAnalyzer/1.0",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            text = response.read().decode("utf-8")

            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text

    except HTTPError as exc:
        body = None

        try:
            body = exc.read().decode("utf-8")
        except Exception:
            pass

        message = f"HTTP Error {exc.code}: {exc.reason}"

        if body:
            message = f"{message} - {body}"

        raise RuntimeError(message)

    except URLError as exc:
        raise RuntimeError(f"URL error: {exc}")


def extract_artist_name_from_lastfm_json(data_json):
    """
    Obtiene el nombre del artista almacenado previamente por track.getInfo.
    No realiza ninguna consulta a Last.fm.
    """
    if not data_json:
        return None

    try:
        data = json.loads(data_json)

        if not isinstance(data, dict):
            return None

        track = data.get("track")

        if not isinstance(track, dict):
            return None

        artist = track.get("artist")

        if isinstance(artist, dict):
            return artist.get("name")

    except (json.JSONDecodeError, TypeError):
        pass

    return None


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
            SELECT DISTINCT
                a.spotify_id AS artist_id,
                a.name AS spotify_artist_name,
                ts.source_id AS lastfm_mbid,
                ts.data_json
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
            ORDER BY a.name COLLATE NOCASE
            LIMIT ?
            """,
            (TEST_LIMIT,),
        ).fetchall()

        print("=" * 72)
        print("LAST.FM — PRUEBA artist.getTopTags")
        print("=" * 72)
        print(f"Artistas únicos a probar: {len(rows)}")
        print()

        total = len(rows)
        with_tags = 0
        without_tags = 0
        errors = 0
        mbid_requests = 0
        name_requests = 0

        for index, row in enumerate(rows, start=1):

            spotify_artist_name = row["spotify_artist_name"]
            lastfm_mbid = row["lastfm_mbid"]

            lastfm_artist_name = extract_artist_name_from_lastfm_json(
                row["data_json"]
            )

            print(
                f"[{index}/{total}] "
                f"{spotify_artist_name} "
                f"(artist_id={row['artist_id']})"
            )

            print(f"  Spotify : {spotify_artist_name}")

            if lastfm_artist_name:
                print(f"  Last.fm : {lastfm_artist_name}")
            else:
                print("  Last.fm : (nombre no disponible en data_json)")

            print(f"  MBID    : {lastfm_mbid or 'None'}")

            try:
                # Preferimos el MBID del artista cuando está disponible.
                # Si no existe, utilizamos el nombre del artista.
                if lastfm_mbid:
                    mbid_requests += 1

                    data = call_lastfm(
                        api_key,
                        method="artist.getTopTags",
                        mbid=lastfm_mbid,
                    )
                else:
                    name_requests += 1

                    data = call_lastfm(
                        api_key,
                        method="artist.getTopTags",
                        artist=lastfm_artist_name or spotify_artist_name,
                    )

                tags = []

                if isinstance(data, dict):
                    toptags = data.get("toptags", {})

                    if isinstance(toptags, dict):
                        tags = toptags.get("tag", [])

                        if not isinstance(tags, list):
                            tags = [tags] if tags else []

                if tags:
                    with_tags += 1

                    print("  Tags    :")

                    for tag in tags[:15]:
                        if isinstance(tag, dict):
                            tag_name = tag.get("name", "Unknown")
                            tag_count = tag.get("count", 0)

                            print(
                                f"    - {tag_name} "
                                f"(count={tag_count})"
                            )
                else:
                    without_tags += 1
                    print("  Tags    : (sin tags)")

            except RuntimeError as exc:
                errors += 1
                print(f"  ERROR   : {exc}")

            except Exception as exc:
                errors += 1
                print(f"  ERROR   : {exc}")

            print()

            if index < total:
                time.sleep(DELAY_SECONDS)

        print("=" * 72)
        print("RESUMEN")
        print("=" * 72)
        print(f"Artistas probados       : {total}")
        print(f"Con tags                : {with_tags}")
        print(f"Sin tags                : {without_tags}")
        print(f"Errores                 : {errors}")
        print(f"Consultas mediante MBID: {mbid_requests}")
        print(f"Consultas mediante name : {name_requests}")

        if total:
            print(
                f"Cobertura de tags      : "
                f"{with_tags * 100 / total:.2f}%"
            )

    finally:
        connection.close()


if __name__ == "__main__":
    main()

