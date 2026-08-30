#!/usr/bin/env python3

import json
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "spotify_music.db"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pct(value, total):
    if not total:
        return "0.00%"
    return f"{value / total * 100:.2f}%"


def table_exists(connection, table_name):
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def table_count(connection, table_name):
    return connection.execute(
        f"SELECT COUNT(*) FROM {table_name}"
    ).fetchone()[0]


def column_info(connection, table_name):
    return connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()


def print_section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def print_subsection(title):
    print()
    print("-" * 78)
    print(title)
    print("-" * 78)


def coverage(connection, table_name, columns):
    total = table_count(connection, table_name)

    print(f"{table_name} — {total:,} rows")

    for column in columns:
        count = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE {column} IS NOT NULL
              AND TRIM(CAST({column} AS TEXT)) <> ''
            """
        ).fetchone()[0]

        print(
            f"  {column:<28} "
            f"{count:>7,} / {total:,} "
            f"({pct(count, total)})"
        )


def valid_json_count(connection, table_name, column):
    rows = connection.execute(
        f"""
        SELECT {column}
        FROM {table_name}
        WHERE {column} IS NOT NULL
          AND TRIM({column}) <> ''
        """
    ).fetchall()

    valid = 0

    for row in rows:
        try:
            json.loads(row[0])
            valid += 1
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    return valid, len(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():

    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    connection = sqlite3.connect(DB_PATH)

    try:

        print("=" * 78)
        print("SPOTIFY MUSIC ANALYZER — METADATA MODEL AUDIT")
        print("=" * 78)
        print()
        print(f"Database: {DB_PATH}")

        # ------------------------------------------------------------------
        # Tables
        # ------------------------------------------------------------------

        print_section("DATABASE TABLES")

        tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        for (table_name,) in tables:
            count = table_count(connection, table_name)
            print(f"{table_name:<35} {count:>8,} rows")

        # ------------------------------------------------------------------
        # Schema
        # ------------------------------------------------------------------

        print_section("DATABASE SCHEMA")

        expected_tables = [
            "tracks",
            "artists",
            "albums",
            "track_artists",
            "track_sources",
            "track_musicbrainz",
            "mb_recordings",
            "mb_artists",
            "mb_recording_artists",
            "mb_artist_aliases",
            "mb_tags",
            "mb_recording_tags",
            "mb_genres",
            "mb_artist_genres",
            "mb_artist_sources",
        ]

        for table_name in expected_tables:

            if not table_exists(connection, table_name):
                print()
                print(f"{table_name}")
                print("  *** TABLE NOT FOUND ***")
                continue

            print_subsection(table_name)

            for row in column_info(connection, table_name):
                cid, name, data_type, notnull, default, pk = row

                constraints = []

                if notnull:
                    constraints.append("NOT NULL")

                if pk:
                    constraints.append("PK")

                constraint_text = ", ".join(constraints)

                print(
                    f"  {name:<28} "
                    f"{data_type:<10} "
                    f"{constraint_text}"
                )

        # ------------------------------------------------------------------
        # Core Spotify metadata
        # ------------------------------------------------------------------

        print_section("CORE SPOTIFY METADATA COVERAGE")

        if table_exists(connection, "tracks"):
            coverage(
                connection,
                "tracks",
                [
                    "spotify_id",
                    "isrc",
                    "track_name",
                    "album_id",
                    "duration_ms",
                    "disc_number",
                    "track_number",
                    "explicit",
                    "spotify_url",
                    "spotify_uri",
                    "is_playable",
                    "is_local",
                    "added_at",
                ],
            )

        if table_exists(connection, "artists"):
            coverage(
                connection,
                "artists",
                [
                    "spotify_id",
                    "name",
                    "spotify_url",
                    "spotify_uri",
                ],
            )

        if table_exists(connection, "albums"):
            coverage(
                connection,
                "albums",
                [
                    "spotify_id",
                    "name",
                    "album_type",
                    "release_date",
                    "release_date_precision",
                    "total_tracks",
                    "spotify_url",
                    "spotify_uri",
                ],
            )

        # ------------------------------------------------------------------
        # Relationships
        # ------------------------------------------------------------------

        print_section("RELATIONSHIP COVERAGE")

        total_tracks = table_count(connection, "tracks")
        total_artists = table_count(connection, "artists")
        total_albums = table_count(connection, "albums")

        tracks_with_artists = connection.execute(
            """
            SELECT COUNT(DISTINCT t.spotify_id)
            FROM tracks t
            JOIN track_artists ta
              ON ta.spotify_id = t.spotify_id
            """
        ).fetchone()[0]

        tracks_with_albums = connection.execute(
            """
            SELECT COUNT(*)
            FROM tracks
            WHERE album_id IS NOT NULL
            """
        ).fetchone()[0]

        track_artist_relations = table_count(
            connection,
            "track_artists",
        )

        print(
            f"Tracks with artist relation: "
            f"{tracks_with_artists:,} / {total_tracks:,} "
            f"({pct(tracks_with_artists, total_tracks)})"
        )

        print(
            f"Track ↔ artist relations: "
            f"{track_artist_relations:,}"
        )

        print(
            f"Tracks with album relation: "
            f"{tracks_with_albums:,} / {total_tracks:,} "
            f"({pct(tracks_with_albums, total_tracks)})"
        )

        # ------------------------------------------------------------------
        # External sources
        # ------------------------------------------------------------------

        print_section("EXTERNAL SOURCE COVERAGE")

        if table_exists(connection, "track_sources"):

            source_rows = connection.execute(
                """
                SELECT
                    source,
                    COUNT(*) AS rows_count,
                    COUNT(DISTINCT spotify_id) AS tracks_count
                FROM track_sources
                GROUP BY source
                ORDER BY source
                """
            ).fetchall()

            for source, rows_count, tracks_count in source_rows:

                print()
                print(source)
                print(f"  Source rows:       {rows_count:,}")
                print(
                    f"  Distinct tracks:   "
                    f"{tracks_count:,} / {total_tracks:,} "
                    f"({pct(tracks_count, total_tracks)})"
                )

                raw_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM track_sources
                    WHERE source = ?
                      AND data_json IS NOT NULL
                      AND TRIM(data_json) <> ''
                    """,
                    (source,),
                ).fetchone()[0]

                print(
                    f"  Raw JSON present:  "
                    f"{raw_count:,} / {rows_count:,} "
                    f"({pct(raw_count, rows_count)})"
                )

                statuses = connection.execute(
                    """
                    SELECT status, COUNT(*)
                    FROM track_sources
                    WHERE source = ?
                    GROUP BY status
                    ORDER BY status
                    """,
                    (source,),
                ).fetchall()

                print("  Status:")

                for status, count in statuses:
                    print(f"    {status:<16} {count:,}")

        # ------------------------------------------------------------------
        # MusicBrainz normalized metadata
        # ------------------------------------------------------------------

        print_section("MUSICBRAINZ NORMALIZED METADATA")

        mb_tables = [
            "mb_recordings",
            "mb_artists",
            "mb_recording_artists",
            "mb_artist_aliases",
            "mb_tags",
            "mb_recording_tags",
            "track_musicbrainz",
        ]

        for table_name in mb_tables:

            if not table_exists(connection, table_name):
                continue

            count = table_count(connection, table_name)
            print(f"{table_name:<35} {count:>8,} rows")

        if table_exists(connection, "track_musicbrainz"):

            linked_recordings = connection.execute(
                """
                SELECT COUNT(DISTINCT mb_recording_id)
                FROM track_musicbrainz
                WHERE mb_recording_id IS NOT NULL
                """
            ).fetchone()[0]

            linked_tracks = connection.execute(
                """
                SELECT COUNT(DISTINCT spotify_id)
                FROM track_musicbrainz
                """
            ).fetchone()[0]

            print()
            print(
                f"Tracks linked to MusicBrainz: "
                f"{linked_tracks:,} / {total_tracks:,} "
                f"({pct(linked_tracks, total_tracks)})"
            )

            print(
                f"Distinct MB recordings linked: "
                f"{linked_recordings:,}"
            )

        if table_exists(connection, "mb_recordings"):

            coverage(
                connection,
                "mb_recordings",
                [
                    "mb_id",
                    "title",
                    "length_ms",
                    "first_release_date",
                    "disambiguation",
                    "score",
                ],
            )

        if table_exists(connection, "mb_artists"):

            coverage(
                connection,
                "mb_artists",
                [
                    "mb_artist_id",
                    "name",
                    "sort_name",
                    "disambiguation",
                ],
            )

        if (
            table_exists(connection, "mb_recordings")
            and table_exists(connection, "mb_recording_tags")
        ):

            total_recordings = table_count(
                connection,
                "mb_recordings",
            )

            recordings_with_tags = connection.execute(
                """
                SELECT COUNT(DISTINCT recording_id)
                FROM mb_recording_tags
                """
            ).fetchone()[0]

            print()
            print(
                f"Recordings with MusicBrainz tags: "
                f"{recordings_with_tags:,} / {total_recordings:,} "
                f"({pct(recordings_with_tags, total_recordings)})"
            )

        # ------------------------------------------------------------------
        # Last.fm
        # ------------------------------------------------------------------

        print_section("LAST.FM RAW METADATA")

        if table_exists(connection, "track_sources"):

            lastfm_rows = connection.execute(
                """
                SELECT data_json
                FROM track_sources
                WHERE source = 'lastfm'
                  AND data_json IS NOT NULL
                """
            ).fetchall()

            print(
                f"Last.fm source rows: "
                f"{len(lastfm_rows):,}"
            )

            valid = 0

            for (data_json,) in lastfm_rows:
                try:
                    json.loads(data_json)
                    valid += 1
                except (TypeError, ValueError, json.JSONDecodeError):
                    pass

            print(
                f"Valid JSON responses: "
                f"{valid:,} / {len(lastfm_rows):,} "
                f"({pct(valid, len(lastfm_rows))})"
            )

            # Last.fm coverage is evaluated from the raw JSON because
            # these attributes intentionally remain source-specific.
            fields = [
                "artist",
                "album",
                "duration",
                "listeners",
                "playcount",
                "track_mbid",
                "artist_mbid",
            ]

            field_counts = {field: 0 for field in fields}

            for (data_json,) in lastfm_rows:

                try:
                    data = json.loads(data_json)
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue

                track = data.get("track", data)

                for field in fields:
                    value = track.get(field)

                    if value not in (None, "", [], {}):
                        field_counts[field] += 1

            for field in fields:

                count = field_counts[field]

                print(
                    f"  {field:<20} "
                    f"{count:>4,} / {len(lastfm_rows):,} "
                    f"({pct(count, len(lastfm_rows))})"
                )

        # ------------------------------------------------------------------
        # Genre model
        # ------------------------------------------------------------------

        print_section("GENRE MODEL")

        genre_tables_present = all(
            table_exists(connection, table)
            for table in (
                "mb_genres",
                "mb_artist_genres",
                "mb_artist_sources",
            )
        )

        if not genre_tables_present:

            print("MusicBrainz artist genre tables are not present.")
            print("Genre model has not yet been incorporated.")

        else:

            genre_count = table_count(
                connection,
                "mb_genres",
            )

            artist_genre_relations = table_count(
                connection,
                "mb_artist_genres",
            )

            artist_source_rows = table_count(
                connection,
                "mb_artist_sources",
            )

            artists_with_genres = connection.execute(
                """
                SELECT COUNT(DISTINCT artist_id)
                FROM mb_artist_genres
                """
            ).fetchone()[0]

            print(
                f"MusicBrainz genres:               "
                f"{genre_count:,}"
            )

            print(
                f"Artist ↔ genre relations:          "
                f"{artist_genre_relations:,}"
            )

            print(
                f"Artists with genres:               "
                f"{artists_with_genres:,}"
            )

            print(
                f"Artist source rows:                "
                f"{artist_source_rows:,}"
            )

            valid_json, json_rows = valid_json_count(
                connection,
                "mb_artist_sources",
                "data_json",
            )

            print(
                f"Valid artist source JSON:          "
                f"{valid_json:,} / {json_rows:,} "
                f"({pct(valid_json, json_rows)})"
            )

            # --------------------------------------------------------------
            # Integrity checks
            # --------------------------------------------------------------

            print()
            print("Genre integrity checks:")

            orphan_artist_genres = connection.execute(
                """
                SELECT COUNT(*)
                FROM mb_artist_genres ag
                LEFT JOIN mb_artists a
                  ON a.mb_artist_id = ag.artist_id
                WHERE a.mb_artist_id IS NULL
                """
            ).fetchone()[0]

            orphan_genres = connection.execute(
                """
                SELECT COUNT(*)
                FROM mb_artist_genres ag
                LEFT JOIN mb_genres g
                  ON g.id = ag.genre_id
                WHERE g.id IS NULL
                """
            ).fetchone()[0]

            duplicate_artist_genres = connection.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT artist_id, genre_id, COUNT(*) AS c
                    FROM mb_artist_genres
                    GROUP BY artist_id, genre_id
                    HAVING c > 1
                )
                """
            ).fetchone()[0]

            print(
                f"  Artist relations with missing artist: "
                f"{orphan_artist_genres}"
            )

            print(
                f"  Artist relations with missing genre:  "
                f"{orphan_genres}"
            )

            print(
                f"  Duplicate artist ↔ genre groups:      "
                f"{duplicate_artist_genres}"
            )

            # --------------------------------------------------------------
            # Artist source integrity
            # --------------------------------------------------------------

            print()
            print("Artist source checks:")

            source_without_artist = connection.execute(
                """
                SELECT COUNT(*)
                FROM mb_artist_sources s
                LEFT JOIN mb_artists a
                  ON a.mb_artist_id = s.artist_id
                WHERE a.mb_artist_id IS NULL
                """
            ).fetchone()[0]

            print(
                f"  Sources with missing artist:           "
                f"{source_without_artist}"
            )

        # ------------------------------------------------------------------
        # Effective genre coverage
        # ------------------------------------------------------------------

        print_section("EFFECTIVE MUSICBRAINZ GENRE COVERAGE")

        if (
            table_exists(connection, "track_musicbrainz")
            and table_exists(connection, "mb_recording_tags")
            and table_exists(connection, "mb_recording_artists")
            and table_exists(connection, "mb_artist_genres")
        ):

            linked_recordings = connection.execute(
                """
                SELECT DISTINCT mb_recording_id
                FROM track_musicbrainz
                WHERE mb_recording_id IS NOT NULL
                """
            ).fetchall()

            linked_recording_ids = [
                row[0]
                for row in linked_recordings
            ]

            linked_count = len(linked_recording_ids)

            direct_count = connection.execute(
                """
                SELECT COUNT(DISTINCT tmb.mb_recording_id)
                FROM track_musicbrainz tmb
                JOIN mb_recording_tags mrt
                  ON mrt.recording_id = tmb.mb_recording_id
                """
            ).fetchone()[0]

            artist_genre_count = connection.execute(
                """
                SELECT COUNT(DISTINCT tmb.mb_recording_id)
                FROM track_musicbrainz tmb
                JOIN mb_recording_artists mra
                  ON mra.recording_id = tmb.mb_recording_id
                JOIN mb_artist_genres mag
                  ON mag.artist_id = mra.artist_id
                """
            ).fetchone()[0]

            both_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT DISTINCT tmb.mb_recording_id
                    FROM track_musicbrainz tmb
                    JOIN mb_recording_tags mrt
                      ON mrt.recording_id = tmb.mb_recording_id
                ) direct
                JOIN (
                    SELECT DISTINCT tmb.mb_recording_id
                    FROM track_musicbrainz tmb
                    JOIN mb_recording_artists mra
                      ON mra.recording_id = tmb.mb_recording_id
                    JOIN mb_artist_genres mag
                      ON mag.artist_id = mra.artist_id
                ) artist
                  ON artist.mb_recording_id = direct.mb_recording_id
                """
            ).fetchone()[0]

            covered_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT DISTINCT tmb.mb_recording_id
                    FROM track_musicbrainz tmb
                    JOIN mb_recording_tags mrt
                      ON mrt.recording_id = tmb.mb_recording_id

                    UNION

                    SELECT DISTINCT tmb.mb_recording_id
                    FROM track_musicbrainz tmb
                    JOIN mb_recording_artists mra
                      ON mra.recording_id = tmb.mb_recording_id
                    JOIN mb_artist_genres mag
                      ON mag.artist_id = mra.artist_id
                )
                """
            ).fetchone()[0]

            no_genre_count = linked_count - covered_count

            print(
                f"Linked MusicBrainz recordings:      "
                f"{linked_count:,}"
            )

            print(
                f"With recording-level genre tags:    "
                f"{direct_count:,} / {linked_count:,} "
                f"({pct(direct_count, linked_count)})"
            )

            print(
                f"With artist-level genres:           "
                f"{artist_genre_count:,} / {linked_count:,} "
                f"({pct(artist_genre_count, linked_count)})"
            )

            print(
                f"With both:                          "
                f"{both_count:,} / {linked_count:,} "
                f"({pct(both_count, linked_count)})"
            )

            print(
                f"Covered by at least one source:     "
                f"{covered_count:,} / {linked_count:,} "
                f"({pct(covered_count, linked_count)})"
            )

            print(
                f"Without any genre information:      "
                f"{no_genre_count:,} / {linked_count:,} "
                f"({pct(no_genre_count, linked_count)})"
            )

        else:

            print(
                "Effective genre coverage cannot be evaluated "
                "because the required tables are missing."
            )

        # ------------------------------------------------------------------
        # Musically useful attributes
        # ------------------------------------------------------------------

        print_section("MUSICALLY USEFUL ATTRIBUTES")

        print(
            "Current status for the attributes considered relevant to"
        )
        print(
            "searching, filtering, classification and later analysis:"
        )
        print()

        print("Genre")
        print("  MusicBrainz recording tags:     AVAILABLE")
        print("  MusicBrainz artist genres:      AVAILABLE")
        print("  Effective MB-linked coverage:   EVALUATED ABOVE")

        print()
        print("Tags")
        print("  MusicBrainz recording tags:     AVAILABLE")
        print("  Last.fm track tags:             PARTIAL / RAW")

        print()
        print("BPM / tempo")
        print("  NOT NORMALIZED")

        print()
        print("Musical key")
        print("  NOT NORMALIZED")

        print()
        print("Mode")
        print("  NOT NORMALIZED")

        print()
        print("Energy")
        print("  NOT AVAILABLE")

        print()
        print("Danceability")
        print("  NOT AVAILABLE")

        print()
        print("Valence / mood")
        print("  NOT AVAILABLE")

        print()
        print("Acousticness")
        print("  NOT AVAILABLE")

        print()
        print("Instrumentalness")
        print("  NOT AVAILABLE")

        print()
        print("Liveness")
        print("  NOT AVAILABLE")

        print()
        print("Speechiness")
        print("  NOT AVAILABLE")

        # ------------------------------------------------------------------
        # Data quality
        # ------------------------------------------------------------------

        print_section("DATA QUALITY CHECKS")

        checks = [
            (
                "Missing track name",
                """
                SELECT COUNT(*)
                FROM tracks
                WHERE track_name IS NULL
                   OR TRIM(track_name) = ''
                """,
                total_tracks,
            ),
            (
                "Missing ISRC",
                """
                SELECT COUNT(*)
                FROM tracks
                WHERE isrc IS NULL
                   OR TRIM(isrc) = ''
                """,
                total_tracks,
            ),
            (
                "Missing duration",
                """
                SELECT COUNT(*)
                FROM tracks
                WHERE duration_ms IS NULL
                """,
                total_tracks,
            ),
            (
                "Missing album",
                """
                SELECT COUNT(*)
                FROM tracks
                WHERE album_id IS NULL
                """,
                total_tracks,
            ),
            (
                "Artists without name",
                """
                SELECT COUNT(*)
                FROM artists
                WHERE name IS NULL
                   OR TRIM(name) = ''
                """,
                total_artists,
            ),
            (
                "Albums without name",
                """
                SELECT COUNT(*)
                FROM albums
                WHERE name IS NULL
                   OR TRIM(name) = ''
                """,
                total_albums,
            ),
        ]

        for label, query, total in checks:

            count = connection.execute(query).fetchone()[0]

            print(
                f"{label:<30} "
                f"{count:,} / {total:,} "
                f"({pct(count, total)})"
            )

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------

        print_section("AUDIT SUMMARY")

        print(
            "The metadata model now includes MusicBrainz artist genres."
        )
        print(
            "Genre coverage is deliberately separated into:"
        )
        print(
            "  1. recording-level MusicBrainz tags;"
        )
        print(
            "  2. artist-level MusicBrainz genres."
        )
        print()
        print(
            "Artist genres are not treated as recording genres."
        )
        print(
            "They provide an additional classification signal for"
        )
        print(
            "searching, filtering and catalog organization."
        )
        print()
        print(
            "No database changes were performed by this audit."
        )

        print()
        print(f"Tracks:   {total_tracks:,}")
        print(f"Albums:   {total_albums:,}")
        print(f"Artists:  {total_artists:,}")

        print()
        print("=" * 78)
        print("AUDIT COMPLETED")
        print("=" * 78)

    finally:
        connection.close()


if __name__ == "__main__":
    main()