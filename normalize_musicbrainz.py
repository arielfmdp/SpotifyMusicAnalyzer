"""
Spotify Music Analyzer
MusicBrainz JSON normalization.

Reads MusicBrainz responses stored in track_sources.data_json and
normalizes the entities currently needed by the application.

This script intentionally does NOT:
- modify or delete track_sources.data_json;
- normalize MusicBrainz releases/release-tracks;
- choose a single "best" recording when multiple recordings are present;
- invent a match score.

It is safe to execute repeatedly: writes use SQLite UPSERT semantics.
"""

import json
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "data" / "spotify_music.db"


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_tables(connection):
    """Create normalized MusicBrainz tables if they do not exist."""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS mb_recordings (
            mb_id TEXT PRIMARY KEY,
            title TEXT,
            length_ms INTEGER,
            first_release_date TEXT,
            disambiguation TEXT,
            score INTEGER
        );

        CREATE TABLE IF NOT EXISTS mb_artists (
            mb_artist_id TEXT PRIMARY KEY,
            name TEXT,
            sort_name TEXT,
            disambiguation TEXT
        );

        CREATE TABLE IF NOT EXISTS mb_recording_artists (
            recording_id TEXT NOT NULL,
            artist_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            joinphrase TEXT,
            credited_name TEXT,
            PRIMARY KEY (recording_id, artist_id, position),
            FOREIGN KEY (recording_id)
                REFERENCES mb_recordings(mb_id)
                ON DELETE CASCADE,
            FOREIGN KEY (artist_id)
                REFERENCES mb_artists(mb_artist_id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS mb_artist_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_id TEXT NOT NULL,
            name TEXT NOT NULL,
            sort_name TEXT,
            locale TEXT,
            type TEXT,
            primary_alias INTEGER,
            begin_date TEXT,
            end_date TEXT,
            UNIQUE (artist_id, name, locale, type),
            FOREIGN KEY (artist_id)
                REFERENCES mb_artists(mb_artist_id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS mb_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS mb_recording_tags (
            recording_id TEXT NOT NULL,
            tag_id INTEGER NOT NULL,
            count INTEGER,
            PRIMARY KEY (recording_id, tag_id),
            FOREIGN KEY (recording_id)
                REFERENCES mb_recordings(mb_id)
                ON DELETE CASCADE,
            FOREIGN KEY (tag_id)
                REFERENCES mb_tags(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS track_musicbrainz (
            spotify_id TEXT NOT NULL,
            mb_recording_id TEXT NOT NULL,
            isrc TEXT,
            match_method TEXT NOT NULL,
            match_score INTEGER,
            PRIMARY KEY (spotify_id, mb_recording_id),
            FOREIGN KEY (spotify_id)
                REFERENCES tracks(spotify_id)
                ON DELETE CASCADE,
            FOREIGN KEY (mb_recording_id)
                REFERENCES mb_recordings(mb_id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_mb_recording_artists_artist
            ON mb_recording_artists(artist_id);

        CREATE INDEX IF NOT EXISTS idx_mb_artist_aliases_artist
            ON mb_artist_aliases(artist_id);

        CREATE INDEX IF NOT EXISTS idx_mb_recording_tags_tag
            ON mb_recording_tags(tag_id);

        CREATE INDEX IF NOT EXISTS idx_track_musicbrainz_recording
            ON track_musicbrainz(mb_recording_id);
        """
    )


def bool_to_int(value):
    if value is None:
        return None
    return int(bool(value))


def upsert_recording(connection, recording):
    connection.execute(
        """
        INSERT INTO mb_recordings (
            mb_id, title, length_ms, first_release_date,
            disambiguation, score
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(mb_id) DO UPDATE SET
            title = excluded.title,
            length_ms = excluded.length_ms,
            first_release_date = excluded.first_release_date,
            disambiguation = excluded.disambiguation,
            score = excluded.score
        """,
        (
            recording["id"],
            recording.get("title"),
            recording.get("length"),
            recording.get("first-release-date"),
            recording.get("disambiguation"),
            recording.get("score"),
        ),
    )


def upsert_artist(connection, artist):
    connection.execute(
        """
        INSERT INTO mb_artists (
            mb_artist_id, name, sort_name, disambiguation
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(mb_artist_id) DO UPDATE SET
            name = excluded.name,
            sort_name = excluded.sort_name,
            disambiguation = excluded.disambiguation
        """,
        (
            artist["id"],
            artist.get("name"),
            artist.get("sort-name"),
            artist.get("disambiguation"),
        ),
    )


def upsert_alias(connection, artist_id, alias):
    connection.execute(
        """
        INSERT INTO mb_artist_aliases (
            artist_id, name, sort_name, locale, type,
            primary_alias, begin_date, end_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(artist_id, name, locale, type) DO UPDATE SET
            sort_name = excluded.sort_name,
            primary_alias = excluded.primary_alias,
            begin_date = excluded.begin_date,
            end_date = excluded.end_date
        """,
        (
            artist_id,
            alias.get("name"),
            alias.get("sort-name"),
            alias.get("locale"),
            alias.get("type"),
            bool_to_int(alias.get("primary")),
            alias.get("begin-date"),
            alias.get("end-date"),
        ),
    )


def get_or_create_tag(connection, name):
    connection.execute(
        """
        INSERT INTO mb_tags (name)
        VALUES (?)
        ON CONFLICT(name) DO NOTHING
        """,
        (name,),
    )

    row = connection.execute(
        "SELECT id FROM mb_tags WHERE name = ?",
        (name,),
    ).fetchone()

    return row["id"]


def normalize_recording(
    connection,
    spotify_id,
    spotify_isrc,
    recording,
    counters,
):
    recording_id = recording.get("id")
    if not recording_id:
        return

    upsert_recording(connection, recording)
    counters["recordings_processed"] += 1

    for position, credit in enumerate(
        recording.get("artist-credit") or []
    ):
        if not isinstance(credit, dict):
            continue

        artist = credit.get("artist")
        if not isinstance(artist, dict):
            continue

        artist_id = artist.get("id")
        if not artist_id:
            continue

        upsert_artist(connection, artist)
        counters["artists_seen"] += 1

        connection.execute(
            """
            INSERT INTO mb_recording_artists (
                recording_id, artist_id, position,
                joinphrase, credited_name
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(recording_id, artist_id, position)
            DO UPDATE SET
                joinphrase = excluded.joinphrase,
                credited_name = excluded.credited_name
            """,
            (
                recording_id,
                artist_id,
                position,
                credit.get("joinphrase"),
                credit.get("name"),
            ),
        )
        counters["recording_artist_relations"] += 1

        for alias in artist.get("aliases") or []:
            if not isinstance(alias, dict):
                continue
            if not alias.get("name"):
                continue

            upsert_alias(connection, artist_id, alias)
            counters["aliases_seen"] += 1

    for tag in recording.get("tags") or []:
        if not isinstance(tag, dict):
            continue

        tag_name = tag.get("name")
        if not tag_name:
            continue

        tag_id = get_or_create_tag(connection, tag_name)

        connection.execute(
            """
            INSERT INTO mb_recording_tags (
                recording_id, tag_id, count
            )
            VALUES (?, ?, ?)
            ON CONFLICT(recording_id, tag_id)
            DO UPDATE SET count = excluded.count
            """,
            (
                recording_id,
                tag_id,
                tag.get("count"),
            ),
        )
        counters["recording_tag_relations"] += 1

    # The existing MusicBrainz acquisition was based on ISRC.
    # If several recordings are returned, retain all of them.
    # The MusicBrainz recording "score" is not treated as a
    # Spotify->MusicBrainz match score, so match_score remains NULL.
    connection.execute(
        """
        INSERT INTO track_musicbrainz (
            spotify_id, mb_recording_id, isrc,
            match_method, match_score
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(spotify_id, mb_recording_id)
        DO UPDATE SET
            isrc = excluded.isrc,
            match_method = excluded.match_method,
            match_score = excluded.match_score
        """,
        (
            spotify_id,
            recording_id,
            spotify_isrc,
            "isrc",
            None,
        ),
    )
    counters["track_recording_relations"] += 1


def normalize_musicbrainz(connection):
    rows = connection.execute(
        """
        SELECT spotify_id, isrc, data_json
        FROM track_sources
        WHERE source = 'musicbrainz'
          AND data_json IS NOT NULL
        ORDER BY id
        """
    ).fetchall()

    counters = {
        "source_rows": len(rows),
        "json_processed": 0,
        "json_errors": 0,
        "recordings_processed": 0,
        "artists_seen": 0,
        "aliases_seen": 0,
        "recording_artist_relations": 0,
        "recording_tag_relations": 0,
        "track_recording_relations": 0,
    }

    for row in rows:
        try:
            data = json.loads(row["data_json"])
        except (json.JSONDecodeError, TypeError):
            counters["json_errors"] += 1
            continue

        if not isinstance(data, dict):
            counters["json_errors"] += 1
            continue

        counters["json_processed"] += 1

        recordings = data.get("recordings") or []
        if not isinstance(recordings, list):
            continue

        for recording in recordings:
            if not isinstance(recording, dict):
                continue

            normalize_recording(
                connection,
                row["spotify_id"],
                row["isrc"],
                recording,
                counters,
            )

    return counters


def print_summary(counters):
    print()
    print("=" * 80)
    print("SPOTIFY MUSIC ANALYZER — NORMALIZACIÓN MUSICBRAINZ")
    print("=" * 80)

    print()
    print(f"Registros MusicBrainz en track_sources : {counters['source_rows']}")
    print(f"JSON procesados correctamente           : {counters['json_processed']}")
    print(f"JSON con errores                        : {counters['json_errors']}")

    print()
    print("-" * 80)
    print("ENTIDADES / RELACIONES PROCESADAS")
    print("-" * 80)

    print(f"Recordings procesados                   : {counters['recordings_processed']}")
    print(f"Artists encontrados                     : {counters['artists_seen']}")
    print(f"Aliases encontrados                     : {counters['aliases_seen']}")
    print(
        "Relaciones recording ↔ artist           : "
        f"{counters['recording_artist_relations']}"
    )
    print(
        "Relaciones recording ↔ tag              : "
        f"{counters['recording_tag_relations']}"
    )
    print(
        "Relaciones Spotify ↔ recording          : "
        f"{counters['track_recording_relations']}"
    )

    print()
    print("-" * 80)
    print("VERIFICACIÓN")
    print("-" * 80)
    print()
    print("track_sources.data_json NO fue modificado.")
    print("Los releases MusicBrainz NO fueron normalizados.")
    print("No se seleccionó arbitrariamente un único recording por track.")
    print("match_score se dejó NULL; no se infirió un score de matching.")

    print()
    print("=" * 80)


def main():
    if not DATABASE.exists():
        raise FileNotFoundError(
            f"No existe la base de datos: {DATABASE}"
        )

    print(f"Base de datos: {DATABASE}")
    print()
    print("Creando/verificando tablas MusicBrainz...")

    connection = get_connection()

    try:
        create_tables(connection)
        print("Tablas verificadas correctamente.")
        print()
        print("Procesando track_sources (source = 'musicbrainz')...")

        connection.execute("BEGIN")

        try:
            counters = normalize_musicbrainz(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    finally:
        connection.close()

    print_summary(counters)


if __name__ == "__main__":
    main()