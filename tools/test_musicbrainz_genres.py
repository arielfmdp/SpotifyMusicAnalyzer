#!/usr/bin/env python3

"""
Spotify Music Analyzer
MusicBrainz genre coverage test.

Purpose
-------
Tests whether MusicBrainz recordings already linked to Spotify tracks
contain useful genre information.

The script:
- reads existing Spotify -> MusicBrainz recording relations;
- queries MusicBrainz recording entities using ?inc=genres;
- stores the complete API responses in a local JSON file;
- reports genre coverage and genre names found.

IMPORTANT
---------
This script DOES NOT modify the SQLite database.

It is an exploratory test only.
No database schema or data is changed.

The generated JSON file is a local test artifact and should not be
committed to Git.
"""

import json
import sqlite3
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE = BASE_DIR / "data" / "spotify_music.db"

OUTPUT_FILE = BASE_DIR / "data" / "musicbrainz_genres_test.json"

MUSICBRAINZ_BASE_URL = "https://musicbrainz.org/ws/2/recording"

# MusicBrainz asks clients to identify themselves with a meaningful
# User-Agent.
USER_AGENT = (
    "SpotifyMusicAnalyzer/1.0 "
    "(personal music metadata research)"
)

# Conservative request interval.
# MusicBrainz generally expects clients not to exceed roughly
# one request per second.
REQUEST_DELAY_SECONDS = 1.1

# Number of retries for transient HTTP/network errors.
MAX_RETRIES = 3


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    """
    Open the SQLite database in read-only/query-only mode.
    """

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    # Defensive protection against accidental writes.
    connection.execute("PRAGMA query_only = ON")

    return connection


def get_musicbrainz_recordings(connection):
    """
    Return all distinct MusicBrainz recording IDs currently linked
    to Spotify tracks.
    """

    rows = connection.execute(
        """
        SELECT DISTINCT
            tm.spotify_id,
            tm.mb_recording_id,
            tm.isrc
        FROM track_musicbrainz AS tm
        ORDER BY
            tm.mb_recording_id,
            tm.spotify_id
        """
    ).fetchall()

    return rows


# ============================================================
# MUSICBRAINZ API
# ============================================================

def build_url(mb_recording_id):
    """
    Build the MusicBrainz recording lookup URL.
    """

    return (
        f"{MUSICBRAINZ_BASE_URL}/"
        f"{mb_recording_id}"
        f"?inc=genres"
        f"&fmt=json"
    )


def request_recording_genres(mb_recording_id):
    """
    Request one MusicBrainz recording with genre information.

    Returns:
        {
            "status": "success",
            "http_status": 200,
            "data": {...}
        }

    or an error structure.
    """

    url = build_url(mb_recording_id)

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
        method="GET",
    )

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            with urlopen(
                request,
                timeout=30,
            ) as response:

                raw = response.read()

                data = json.loads(
                    raw.decode("utf-8")
                )

                return {
                    "status": "success",
                    "http_status": response.status,
                    "data": data,
                }

        except HTTPError as error:

            # Retry transient server/rate-limit responses.
            if error.code in (429, 500, 502, 503, 504):

                if attempt < MAX_RETRIES:

                    wait_seconds = (
                        REQUEST_DELAY_SECONDS * attempt * 2
                    )

                    print(
                        f"    HTTP {error.code}; "
                        f"retrying in "
                        f"{wait_seconds:.1f}s..."
                    )

                    time.sleep(wait_seconds)
                    continue

            return {
                "status": "http_error",
                "http_status": error.code,
                "error": str(error),
            }

        except URLError as error:

            if attempt < MAX_RETRIES:

                wait_seconds = (
                    REQUEST_DELAY_SECONDS * attempt * 2
                )

                print(
                    f"    Network error; "
                    f"retrying in "
                    f"{wait_seconds:.1f}s..."
                )

                time.sleep(wait_seconds)
                continue

            return {
                "status": "network_error",
                "http_status": None,
                "error": str(error),
            }

        except json.JSONDecodeError as error:

            return {
                "status": "json_error",
                "http_status": None,
                "error": str(error),
            }

    return {
        "status": "unknown_error",
        "http_status": None,
        "error": "Unknown request failure",
    }


# ============================================================
# GENRE EXTRACTION
# ============================================================

def extract_genres(data):
    """
    Extract genre objects from a MusicBrainz recording response.

    Returns a list of dictionaries preserving the information
    returned by MusicBrainz.
    """

    if not isinstance(data, dict):
        return []

    genres = data.get("genres")

    if not isinstance(genres, list):
        return []

    result = []

    for genre in genres:

        if not isinstance(genre, dict):
            continue

        name = genre.get("name")

        if not name:
            continue

        result.append(
            {
                "id": genre.get("id"),
                "name": name,
                "count": genre.get("count"),
            }
        )

    return result


# ============================================================
# REPORTING
# ============================================================

def print_header(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def coverage_text(count, total):
    if total == 0:
        return "0 / 0 (0.00%)"

    percentage = count * 100 / total

    return (
        f"{count:,} / {total:,} "
        f"({percentage:.2f}%)"
    )


def print_summary(results):
    """
    Print a concise coverage report.
    """

    print_header(
        "MUSICBRAINZ GENRE COVERAGE — TEST RESULT"
    )

    total = len(results)

    successful = sum(
        1
        for result in results
        if result["status"] == "success"
    )

    failed = total - successful

    recordings_with_genres = sum(
        1
        for result in results
        if result["status"] == "success"
        and result["genres"]
    )

    recordings_without_genres = (
        successful - recordings_with_genres
    )

    print()
    print(
        f"Recordings tested:                 {total:,}"
    )

    print(
        f"Successful API responses:          "
        f"{coverage_text(successful, total)}"
    )

    print(
        f"Responses with genres:              "
        f"{coverage_text(recordings_with_genres, successful)}"
    )

    print(
        f"Responses without genres:           "
        f"{coverage_text(recordings_without_genres, successful)}"
    )

    print(
        f"Failed requests:                    "
        f"{failed:,}"
    )

    # --------------------------------------------------------
    # Distinct genres
    # --------------------------------------------------------

    genre_names = {}

    for result in results:

        for genre in result["genres"]:

            name = genre["name"]

            genre_names[name] = (
                genre_names.get(name, 0) + 1
            )

    print()

    print(
        f"Distinct genre names:               "
        f"{len(genre_names):,}"
    )

    if genre_names:

        print()
        print("-" * 78)
        print("GENRES FOUND")
        print("-" * 78)

        sorted_genres = sorted(
            genre_names.items(),
            key=lambda item: (
                -item[1],
                item[0].lower(),
            ),
        )

        for name, occurrences in sorted_genres:

            print(
                f"  {name:<45} "
                f"{occurrences:>4}"
            )

    # --------------------------------------------------------
    # Recording details
    # --------------------------------------------------------

    print()
    print("-" * 78)
    print("RECORDING RESULTS")
    print("-" * 78)

    for result in results:

        mb_id = result["mb_recording_id"]
        spotify_ids = result["spotify_ids"]

        print()

        print(
            f"MB Recording: {mb_id}"
        )

        print(
            f"Spotify tracks: {', '.join(spotify_ids)}"
        )

        if result["status"] != "success":

            print(
                f"Status: {result['status']}"
            )

            if result.get("error"):

                print(
                    f"Error: {result['error']}"
                )

            continue

        data = result.get("data") or {}

        print(
            f"Title: {data.get('title', '')}"
        )

        genres = result["genres"]

        if not genres:

            print(
                "Genres: NONE"
            )

        else:

            genre_text = ", ".join(
                genre["name"]
                for genre in genres
            )

            print(
                f"Genres: {genre_text}"
            )


# ============================================================
# MAIN TEST
# ============================================================

def main():

    print("=" * 78)
    print(
        "SPOTIFY MUSIC ANALYZER — "
        "MUSICBRAINZ GENRE TEST"
    )
    print("=" * 78)

    print()
    print(
        f"Database: {DATABASE}"
    )

    print(
        f"Output:   {OUTPUT_FILE}"
    )

    # --------------------------------------------------------
    # Validate database
    # --------------------------------------------------------

    if not DATABASE.exists():

        print()
        print(
            "ERROR: SQLite database does not exist."
        )

        return 1

    # --------------------------------------------------------
    # Read existing relations
    # --------------------------------------------------------

    connection = get_connection()

    try:

        rows = get_musicbrainz_recordings(
            connection
        )

    finally:

        connection.close()

    if not rows:

        print()
        print(
            "No Spotify ↔ MusicBrainz recording "
            "relations were found."
        )

        return 0

    # --------------------------------------------------------
    # Group Spotify relationships by recording
    #
    # A single MusicBrainz recording may currently be related
    # to more than one Spotify track.
    # --------------------------------------------------------

    grouped = {}

    for row in rows:

        mb_id = row["mb_recording_id"]

        if mb_id not in grouped:

            grouped[mb_id] = {
                "mb_recording_id": mb_id,
                "spotify_ids": [],
                "isrcs": [],
            }

        if row["spotify_id"] not in grouped[mb_id][
            "spotify_ids"
        ]:

            grouped[mb_id]["spotify_ids"].append(
                row["spotify_id"]
            )

        if row["isrc"]:

            if row["isrc"] not in grouped[mb_id][
                "isrcs"
            ]:

                grouped[mb_id]["isrcs"].append(
                    row["isrc"]
                )

    recordings = list(
        grouped.values()
    )

    print()
    print(
        f"Distinct MusicBrainz recordings to test: "
        f"{len(recordings):,}"
    )

    print()
    print(
        f"Request interval: "
        f"{REQUEST_DELAY_SECONDS:.1f}s"
    )

    print()
    print(
        "Starting MusicBrainz requests..."
    )

    # --------------------------------------------------------
    # Query API
    # --------------------------------------------------------

    results = []

    for index, recording in enumerate(
        recordings,
        start=1,
    ):

        mb_id = recording[
            "mb_recording_id"
        ]

        print()
        print(
            f"[{index}/{len(recordings)}] "
            f"{mb_id}"
        )

        response = request_recording_genres(
            mb_id
        )

        result = {
            "mb_recording_id": mb_id,
            "spotify_ids": recording[
                "spotify_ids"
            ],
            "isrcs": recording[
                "isrcs"
            ],
            "status": response[
                "status"
            ],
            "http_status": response.get(
                "http_status"
            ),
            "genres": [],
            "data": None,
        }

        if response["status"] == "success":

            data = response["data"]

            genres = extract_genres(
                data
            )

            result["genres"] = genres
            result["data"] = data

            if genres:

                print(
                    "  Genres: "
                    + ", ".join(
                        genre["name"]
                        for genre in genres
                    )
                )

            else:

                print(
                    "  Genres: NONE"
                )

        else:

            result["error"] = response.get(
                "error"
            )

            print(
                f"  ERROR: {result['status']}"
            )

            if result.get("error"):

                print(
                    f"  {result['error']}"
                )

        results.append(result)

        # ----------------------------------------------------
        # Respect API request interval.
        #
        # No delay is needed after the final request.
        # ----------------------------------------------------

        if index < len(recordings):

            time.sleep(
                REQUEST_DELAY_SECONDS
            )

    # --------------------------------------------------------
    # Save complete test result
    # --------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "test": "musicbrainz_recording_genres",
        "database": str(DATABASE),
        "endpoint": MUSICBRAINZ_BASE_URL,
        "include": "genres",
        "request_delay_seconds":
            REQUEST_DELAY_SECONDS,
        "recordings_tested": len(results),
        "results": results,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )

    # --------------------------------------------------------
    # Report
    # --------------------------------------------------------

    print_summary(
        results
    )

    print()
    print("=" * 78)
    print("TEST COMPLETED")
    print("=" * 78)

    print()
    print(
        "SQLite database was NOT modified."
    )

    print(
        f"Test responses saved to:"
    )

    print(
        f"  {OUTPUT_FILE}"
    )

    print()
    print(
        "The generated JSON is a local test artifact "
        "and should not be committed to Git."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
