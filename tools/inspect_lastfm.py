"""
Inspect Last.fm raw responses already stored in track_sources.

This script performs NO network requests and does NOT modify the database.
It summarizes the Last.fm JSON currently stored in the local SQLite database.

Usage:
    python inspect_lastfm.py
    python inspect_lastfm.py --limit 20
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE = BASE_DIR / "data" / "spotify_music.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect stored Last.fm raw JSON without network access."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Inspect at most N Last.fm records.",
    )
    return parser.parse_args()


def is_nonempty(value) -> bool:
    return value not in (None, "", [], {})


def main() -> None:
    args = parse_args()

    if not DATABASE.exists():
        raise FileNotFoundError(f"No existe la base de datos: {DATABASE}")

    connection = get_connection()

    try:
        query = """
            SELECT
                id,
                spotify_id,
                source_id,
                status,
                data_json
            FROM track_sources
            WHERE source = 'lastfm'
              AND status = 'success'
            ORDER BY id
        """

        rows = connection.execute(query).fetchall()

        if args.limit is not None:
            rows = rows[: args.limit]

        if not rows:
            print("No hay respuestas Last.fm almacenadas.")
            return

        total = len(rows)

        counters = Counter()
        artists_missing = 0
        albums_missing = 0
        tags_missing = 0
        wiki_missing = 0
        duration_missing = 0
        listeners_missing = 0
        playcount_missing = 0
        mbid_missing = 0

        durations = []
        listener_values = []
        playcount_values = []

        top_tag_counter = Counter()
        artist_mbid_count = 0
        album_mbid_count = 0
        track_mbid_count = 0

        parse_errors = []
        examples = []

        for row in rows:
            try:
                payload = json.loads(row["data_json"])
            except (TypeError, json.JSONDecodeError) as exc:
                parse_errors.append((row["id"], str(exc)))
                continue

            # Last.fm track.getInfo normally wraps the result in "track".
            track = payload.get("track", payload)
            if not isinstance(track, dict):
                counters["invalid_track_object"] += 1
                continue

            counters["valid_json"] += 1

            artist = track.get("artist")
            album = track.get("album")
            tags = track.get("toptags", {}).get("tag", [])
            wiki = track.get("wiki")

            if is_nonempty(artist):
                counters["artist_present"] += 1
                if isinstance(artist, dict) and is_nonempty(artist.get("mbid")):
                    artist_mbid_count += 1
            else:
                artists_missing += 1

            if is_nonempty(album):
                counters["album_present"] += 1
                if isinstance(album, dict) and is_nonempty(album.get("mbid")):
                    album_mbid_count += 1
            else:
                albums_missing += 1

            if is_nonempty(tags):
                counters["tags_present"] += 1
                if isinstance(tags, list):
                    for tag in tags:
                        if isinstance(tag, dict) and is_nonempty(tag.get("name")):
                            top_tag_counter[tag["name"]] += 1
            else:
                tags_missing += 1

            if is_nonempty(wiki):
                counters["wiki_present"] += 1
            else:
                wiki_missing += 1

            duration = track.get("duration")
            if is_nonempty(duration):
                try:
                    duration_ms = int(duration)
                    if duration_ms > 0:
                        duration_values = duration_ms
                        durations.append(duration_values)
                        counters["duration_present"] += 1
                    else:
                        duration_missing += 1
                except (TypeError, ValueError):
                    counters["duration_invalid"] += 1
            else:
                duration_missing += 1

            listeners = track.get("listeners")
            if is_nonempty(listeners):
                try:
                    listener_values.append(int(listeners))
                    counters["listeners_present"] += 1
                except (TypeError, ValueError):
                    counters["listeners_invalid"] += 1
            else:
                listeners_missing += 1

            playcount = track.get("playcount")
            if is_nonempty(playcount):
                try:
                    playcount_values.append(int(playcount))
                    counters["playcount_present"] += 1
                except (TypeError, ValueError):
                    counters["playcount_invalid"] += 1
            else:
                playcount_missing += 1

            track_mbid = track.get("mbid")
            if is_nonempty(track_mbid):
                track_mbid_count += 1
            else:
                mbid_missing += 1

            # Keep a few examples useful for manual inspection.
            if len(examples) < 5:
                examples.append(
                    {
                        "spotify_id": row["spotify_id"],
                        "lastfm_source_id": row["source_id"],
                        "name": track.get("name"),
                        "artist": (
                            artist.get("name")
                            if isinstance(artist, dict)
                            else artist
                        ),
                        "mbid": track_mbid,
                        "album": (
                            album.get("title")
                            if isinstance(album, dict)
                            else album
                        ),
                        "tags": [
                            tag.get("name")
                            for tag in tags
                            if isinstance(tag, dict) and tag.get("name")
                        ][:10],
                    }
                )

        print("=" * 72)
        print("LAST.FM — INSPECCIÓN DE RESPUESTAS RAW")
        print("=" * 72)
        print(f"Registros inspeccionados : {total}")
        print(f"JSON válidos             : {counters['valid_json']}")
        print(f"Errores de parseo        : {len(parse_errors)}")
        print()

        print("COBERTURA DE CAMPOS")
        print("-" * 72)

        def show_presence(label: str, present: int) -> None:
            percentage = present * 100 / total
            print(f"{label:<24} {present:>5}/{total:<5} ({percentage:6.2f}%)")

        show_presence("Artist", counters["artist_present"])
        show_presence("Album", counters["album_present"])
        show_presence("Tags", counters["tags_present"])
        show_presence("Wiki", counters["wiki_present"])
        show_presence("Duration", counters["duration_present"])
        show_presence("Listeners", counters["listeners_present"])
        show_presence("Playcount", counters["playcount_present"])
        show_presence("Track MBID", track_mbid_count)
        show_presence("Artist MBID", artist_mbid_count)
        show_presence("Album MBID", album_mbid_count)

        print()
        print("VALORES NUMÉRICOS")
        print("-" * 72)

        if durations:
            print(
                f"Duration (ms)           min={min(durations):,} "
                f"max={max(durations):,} "
                f"avg={sum(durations) / len(durations):,.0f}"
            )
        else:
            print("Duration                 sin valores válidos")

        if listener_values:
            print(
                f"Listeners                min={min(listener_values):,} "
                f"max={max(listener_values):,} "
                f"avg={sum(listener_values) / len(listener_values):,.0f}"
            )
        else:
            print("Listeners                sin valores válidos")

        if playcount_values:
            print(
                f"Playcount                min={min(playcount_values):,} "
                f"max={max(playcount_values):,} "
                f"avg={sum(playcount_values) / len(playcount_values):,.0f}"
            )
        else:
            print("Playcount                sin valores válidos")

        print()
        print("TOP TAGS")
        print("-" * 72)

        if top_tag_counter:
            for name, count in top_tag_counter.most_common(20):
                print(f"{name:<45} {count:>5}")
        else:
            print("No se encontraron tags.")

        print()
        print("EJEMPLOS")
        print("-" * 72)

        for example in examples:
            print(json.dumps(example, ensure_ascii=False, indent=2))
            print()

        if parse_errors:
            print("ERRORES DE PARSEO")
            print("-" * 72)
            for record_id, error in parse_errors:
                print(f"id={record_id}: {error}")

    finally:
        connection.close()


if __name__ == "__main__":
    main()