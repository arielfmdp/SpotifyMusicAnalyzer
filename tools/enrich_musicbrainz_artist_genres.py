#!/usr/bin/env python3

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# ----------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE = DATA_DIR / "spotify_music.db"

MUSICBRAINZ_BASE_URL = "https://musicbrainz.org/ws/2/artist"

USER_AGENT = "SpotifyMusicAnalyzer/1.0 (personal project)"

REQUEST_INTERVAL = 1.1
MAX_RETRIES = 3

# MusicBrainz returns artist data as JSON when fmt=json is specified.
INCLUDE = "genres"


# ----------------------------------------------------------------------
# DATABASE
# ----------------------------------------------------------------------

def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_tables(connection):
    """
    Creates the normalized artist-genre relationship and the raw
    MusicBrainz artist source table.

    Existing tables are not modified.
    """

    connection.execute("""
        CREATE TABLE IF NOT EXISTS mb_genres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS mb_artist_genres (
            artist_id TEXT NOT NULL,
            genre_id INTEGER NOT NULL,

            PRIMARY KEY (artist_id, genre_id),

            FOREIGN KEY (artist_id)
                REFERENCES mb_artists(mb_artist_id)
                ON DELETE CASCADE,

            FOREIGN KEY (genre_id)
                REFERENCES mb_genres(id)
                ON DELETE CASCADE
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS mb_artist_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_id TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            data_json TEXT,
            retrieved_at TEXT NOT NULL,

            UNIQUE (artist_id, source),

            FOREIGN KEY (artist_id)
                REFERENCES mb_artists(mb_artist_id)
                ON DELETE CASCADE
        )
    """)

    connection.commit()


# ----------------------------------------------------------------------
# MUSICBRAINZ API
# ----------------------------------------------------------------------

def fetch_artist_genres(mb_artist_id):
    """
    Retrieves a MusicBrainz artist including genres.

    Returns:
        (status, payload)

    status:
        "found"
        "not_found"
        "error"
    """

    url = (
        f"{MUSICBRAINZ_BASE_URL}/"
        f"{mb_artist_id}"
        f"?inc={INCLUDE}&fmt=json"
    )

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    for attempt in range(1, MAX_RETRIES + 1):

        request = Request(url, headers=headers)

        try:
            with urlopen(request, timeout=30) as response:
                data = response.read().decode("utf-8")

            payload = json.loads(data)

            return "found", payload

        except HTTPError as exc:

            # MusicBrainz can temporarily return 503 when requests
            # arrive too quickly or the service is under load.
            if exc.code in (429, 502, 503, 504):

                if attempt < MAX_RETRIES:
                    delay = 2.2 * attempt

                    print(
                        f"    HTTP {exc.code}; "
                        f"retrying in {delay:.1f}s..."
                    )

                    time.sleep(delay)
                    continue

            if exc.code == 404:
                return "not_found", None

            print(
                f"    HTTP error {exc.code}: {exc.reason}"
            )

            return "error", None

        except (URLError, TimeoutError) as exc:

            if attempt < MAX_RETRIES:
                delay = 2.2 * attempt

                print(
                    f"    Network error; "
                    f"retrying in {delay:.1f}s..."
                )

                time.sleep(delay)
                continue

            print(f"    Network error: {exc}")

            return "error", None

        except json.JSONDecodeError as exc:

            print(f"    Invalid JSON response: {exc}")

            return "error", None

    return "error", None


# ----------------------------------------------------------------------
# NORMALIZATION
# ----------------------------------------------------------------------

def normalize_genres(payload):
    """
    Extracts and normalizes MusicBrainz genre names.

    MusicBrainz genre objects normally contain:
        name
        count

    Only the genre name is required for the normalized model.
    """

    genres = payload.get("genres", [])

    result = set()

    for genre in genres:

        name = genre.get("name")

        if not name:
            continue

        name = name.strip()

        if not name:
            continue

        result.add(name)

    return sorted(result, key=str.casefold)


def get_or_create_genre(connection, name):
    """
    Returns the normalized genre ID.
    """

    connection.execute(
        """
        INSERT INTO mb_genres (name)
        VALUES (?)
        ON CONFLICT(name) DO NOTHING
        """,
        (name,),
    )

    row = connection.execute(
        """
        SELECT id
        FROM mb_genres
        WHERE name = ?
        """,
        (name,),
    ).fetchone()

    return row["id"]


def replace_artist_genres(connection, artist_id, genres):
    """
    Replaces the current normalized genre relationships for an artist.

    This makes the process idempotent and ensures that a later API
    response can correct an earlier result.
    """

    connection.execute(
        """
        DELETE FROM mb_artist_genres
        WHERE artist_id = ?
        """,
        (artist_id,),
    )

    for genre_name in genres:

        genre_id = get_or_create_genre(
            connection,
            genre_name,
        )

        connection.execute(
            """
            INSERT OR IGNORE INTO mb_artist_genres
                (artist_id, genre_id)
            VALUES (?, ?)
            """,
            (
                artist_id,
                genre_id,
            ),
        )


def store_raw_source(
    connection,
    artist_id,
    status,
    payload,
):
    """
    Stores the complete MusicBrainz artist response.

    There is one current raw response per artist/source.
    """

    retrieved_at = datetime.now(timezone.utc).isoformat()

    data_json = (
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if payload is not None
        else None
    )

    connection.execute(
        """
        INSERT INTO mb_artist_sources (
            artist_id,
            source,
            status,
            data_json,
            retrieved_at
        )
        VALUES (?, ?, ?, ?, ?)

        ON CONFLICT(artist_id, source)
        DO UPDATE SET
            status = excluded.status,
            data_json = excluded.data_json,
            retrieved_at = excluded.retrieved_at
        """,
        (
            artist_id,
            "musicbrainz",
            status,
            data_json,
            retrieved_at,
        ),
    )


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main():

    if not DATABASE.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE}"
        )

    connection = get_connection()

    try:

        create_tables(connection)

        # --------------------------------------------------------------
        # Artists already linked to MusicBrainz recordings
        # --------------------------------------------------------------

        rows = connection.execute(
            """
            SELECT DISTINCT
                ra.artist_id
            FROM mb_recording_artists ra
            INNER JOIN mb_artists a
                ON a.mb_artist_id = ra.artist_id
            ORDER BY ra.artist_id
            """
        ).fetchall()

        artist_ids = [
            row["artist_id"]
            for row in rows
        ]

        total = len(artist_ids)

        print("=" * 78)
        print("SPOTIFY MUSIC ANALYZER — MUSICBRAINZ ARTIST GENRES")
        print("=" * 78)
        print()
        print(f"Database: {DATABASE}")
        print()
        print(
            f"Distinct MusicBrainz artists to process: {total}"
        )
        print()
        print(f"Request interval: {REQUEST_INTERVAL:.1f}s")
        print()
        print("Starting MusicBrainz requests...")
        print()

        successful = 0
        with_genres = 0
        without_genres = 0
        failed = 0
        total_genres = 0

        for index, artist_id in enumerate(artist_ids, start=1):

            artist_row = connection.execute(
                """
                SELECT name
                FROM mb_artists
                WHERE mb_artist_id = ?
                """,
                (artist_id,),
            ).fetchone()

            artist_name = (
                artist_row["name"]
                if artist_row
                else "(unknown)"
            )

            print(
                f"[{index}/{total}] "
                f"{artist_name} "
                f"({artist_id})"
            )

            status, payload = fetch_artist_genres(
                artist_id
            )

            if status == "error":

                failed += 1

                store_raw_source(
                    connection,
                    artist_id,
                    "error",
                    None,
                )

                connection.commit()

                print("  Genres: ERROR")

            elif status == "not_found":

                store_raw_source(
                    connection,
                    artist_id,
                    "not_found",
                    None,
                )

                replace_artist_genres(
                    connection,
                    artist_id,
                    [],
                )

                connection.commit()

                print("  Genres: NONE")
                without_genres += 1

            else:

                successful += 1

                genres = normalize_genres(payload)

                store_raw_source(
                    connection,
                    artist_id,
                    "success",
                    payload,
                )

                replace_artist_genres(
                    connection,
                    artist_id,
                    genres,
                )

                connection.commit()

                if genres:

                    with_genres += 1
                    total_genres += len(genres)

                    print(
                        "  Genres: "
                        + ", ".join(genres)
                    )

                else:

                    without_genres += 1

                    print("  Genres: NONE")

            # Respect MusicBrainz request rate.
            if index < total:
                time.sleep(REQUEST_INTERVAL)

        # --------------------------------------------------------------
        # Final statistics
        # --------------------------------------------------------------

        distinct_genres = connection.execute(
            """
            SELECT COUNT(*)
            FROM mb_genres
            """
        ).fetchone()[0]

        artist_genre_relations = connection.execute(
            """
            SELECT COUNT(*)
            FROM mb_artist_genres
            """
        ).fetchone()[0]

        artists_with_genres = connection.execute(
            """
            SELECT COUNT(DISTINCT artist_id)
            FROM mb_artist_genres
            """
        ).fetchone()[0]

        # --------------------------------------------------------------
        # Recording-level impact
        # --------------------------------------------------------------

        linked_recordings = connection.execute(
            """
            SELECT COUNT(DISTINCT mb_recording_id)
            FROM track_musicbrainz
            """
        ).fetchone()[0]

        recordings_with_genres = connection.execute(
            """
            SELECT COUNT(DISTINCT ra.recording_id)
            FROM mb_recording_artists ra
            INNER JOIN mb_artist_genres ag
                ON ag.artist_id = ra.artist_id
            """
        ).fetchone()[0]

        # Recordings with their own MusicBrainz tags.
        recordings_with_tags = connection.execute(
            """
            SELECT COUNT(DISTINCT recording_id)
            FROM mb_recording_tags
            """
        ).fetchone()[0]

        recordings_without_any_genre_info = connection.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT DISTINCT tm.mb_recording_id
                FROM track_musicbrainz tm
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM mb_recording_tags rt
                    WHERE rt.recording_id = tm.mb_recording_id
                )
                AND NOT EXISTS (
                    SELECT 1
                    FROM mb_recording_artists ra
                    INNER JOIN mb_artist_genres ag
                        ON ag.artist_id = ra.artist_id
                    WHERE ra.recording_id = tm.mb_recording_id
                )
            )
            """
        ).fetchone()[0]

        print()
        print("=" * 78)
        print("MUSICBRAINZ ARTIST GENRE COVERAGE")
        print("=" * 78)
        print()
        print(
            f"Artists processed:                 {total}"
        )
        print(
            f"Successful API responses:          "
            f"{successful} / {total}"
        )
        print(
            f"Artists with genres:               "
            f"{artists_with_genres} / {total}"
        )
        print(
            f"Artists without genres:            "
            f"{without_genres}"
        )
        print(
            f"Failed requests:                   "
            f"{failed}"
        )
        print()
        print(
            f"Distinct normalized genres:         "
            f"{distinct_genres}"
        )
        print(
            f"Artist ↔ genre relations:           "
            f"{artist_genre_relations}"
        )

        print()
        print("-" * 78)
        print("RECORDING COVERAGE IMPACT")
        print("-" * 78)
        print()
        print(
            f"Linked MusicBrainz recordings:     "
            f"{linked_recordings}"
        )
        print(
            f"Recordings with recording tags:    "
            f"{recordings_with_tags}"
        )
        print(
            f"Recordings with artist genres:     "
            f"{recordings_with_genres}"
        )

        if linked_recordings:
            coverage = (
                recordings_with_genres
                / linked_recordings
                * 100
            )
        else:
            coverage = 0.0

        print(
            f"Artist-genre recording coverage:   "
            f"{coverage:.2f}%"
        )

        print(
            f"Recordings without any genre info: "
            f"{recordings_without_any_genre_info}"
        )

        print()
        print("=" * 78)
        print("COMPLETED")
        print("=" * 78)
        print()
        print("SQLite database was updated with:")
        print("  - mb_genres")
        print("  - mb_artist_genres")
        print("  - mb_artist_sources")
        print()
        print(
            "MusicBrainz artist responses are preserved "
            "in mb_artist_sources.data_json."
        )

    finally:

        connection.close()


if __name__ == "__main__":
    main()