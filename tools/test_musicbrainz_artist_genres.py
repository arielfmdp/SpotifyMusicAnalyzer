#!/usr/bin/env python3

"""
Spotify Music Analyzer
MusicBrainz artist genre coverage test.

Purpose
-------
Tests whether MusicBrainz artist genres can complement the genres
already obtained from MusicBrainz recordings.

The script:
- reads existing Spotify -> MusicBrainz recording relations;
- follows recording -> artist relations already stored locally;
- queries MusicBrainz artist entities using ?inc=genres;
- stores complete API responses in a local JSON file;
- reports artist-genre coverage;
- calculates how much recording coverage could potentially be
  complemented by artist genres.

IMPORTANT
---------
This script DOES NOT modify the SQLite database.

Artist genres are reported separately from recording genres.
The script does NOT assign artist genres to tracks or recordings.
"""

import json
import sqlite3
import time
from collections import defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE = BASE_DIR / "data" / "spotify_music.db"

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "musicbrainz_artist_genres_test.json"
)

MUSICBRAINZ_BASE_URL = (
    "https://musicbrainz.org/ws/2/artist"
)

USER_AGENT = (
    "SpotifyMusicAnalyzer/1.0 "
    "(personal music metadata research)"
)

REQUEST_DELAY_SECONDS = 1.1

MAX_RETRIES = 3


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    """
    Open SQLite in read-only/query-only mode.
    """

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA query_only = ON"
    )

    return connection


def get_recording_artists(connection):
    """
    Return the MusicBrainz artist relationships for all
    MusicBrainz recordings currently linked to Spotify tracks.

    Returns:
        {
            recording_id: [
                {
                    "artist_id": ...,
                    "position": ...,
                    "joinphrase": ...,
                    "credited_name": ...
                },
                ...
            ]
        }
    """

    rows = connection.execute(
        """
        SELECT
            recording_id,
            artist_id,
            position,
            joinphrase,
            credited_name
        FROM mb_recording_artists
        ORDER BY
            recording_id,
            position
        """
    ).fetchall()

    result = defaultdict(list)

    for row in rows:

        result[row["recording_id"]].append(
            {
                "artist_id": row["artist_id"],
                "position": row["position"],
                "joinphrase": row["joinphrase"],
                "credited_name": row["credited_name"],
            }
        )

    return dict(result)


def get_linked_recordings(connection):
    """
    Return the distinct MusicBrainz recordings currently linked
    to Spotify tracks.
    """

    rows = connection.execute(
        """
        SELECT DISTINCT
            spotify_id,
            mb_recording_id
        FROM track_musicbrainz
        ORDER BY
            mb_recording_id,
            spotify_id
        """
    ).fetchall()

    result = defaultdict(list)

    for row in rows:

        result[row["mb_recording_id"]].append(
            row["spotify_id"]
        )

    return dict(result)


def get_existing_recording_genres(connection):
    """
    Return genres already normalized in mb_recording_tags.

    This is used only for comparison with the artist genre
    coverage. No database modifications are performed.
    """

    rows = connection.execute(
        """
        SELECT DISTINCT
            mrt.recording_id,
            mt.name
        FROM mb_recording_tags AS mrt
        JOIN mb_tags AS mt
          ON mt.id = mrt.tag_id
        ORDER BY
            mrt.recording_id,
            mt.name
        """
    ).fetchall()

    result = defaultdict(list)

    for row in rows:

        result[row["recording_id"]].append(
            row["name"]
        )

    return dict(result)


# ============================================================
# MUSICBRAINZ API
# ============================================================

def build_url(artist_id):
    """
    Build MusicBrainz artist lookup URL.
    """

    return (
        f"{MUSICBRAINZ_BASE_URL}/"
        f"{artist_id}"
        f"?inc=genres"
        f"&fmt=json"
    )


def request_artist_genres(artist_id):
    """
    Request one MusicBrainz artist with genre information.
    """

    url = build_url(artist_id)

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

            if error.code in (
                429,
                500,
                502,
                503,
                504,
            ):

                if attempt < MAX_RETRIES:

                    wait_seconds = (
                        REQUEST_DELAY_SECONDS
                        * attempt
                        * 2
                    )

                    print(
                        f"    HTTP {error.code}; "
                        f"retrying in "
                        f"{wait_seconds:.1f}s..."
                    )

                    time.sleep(
                        wait_seconds
                    )

                    continue

            return {
                "status": "http_error",
                "http_status": error.code,
                "error": str(error),
            }

        except URLError as error:

            if attempt < MAX_RETRIES:

                wait_seconds = (
                    REQUEST_DELAY_SECONDS
                    * attempt
                    * 2
                )

                print(
                    f"    Network error; "
                    f"retrying in "
                    f"{wait_seconds:.1f}s..."
                )

                time.sleep(
                    wait_seconds
                )

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
    Extract MusicBrainz genre objects.
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
# MAIN
# ============================================================

def main():

    print("=" * 78)
    print(
        "SPOTIFY MUSIC ANALYZER — "
        "MUSICBRAINZ ARTIST GENRE TEST"
    )
    print("=" * 78)

    print()
    print(
        f"Database: {DATABASE}"
    )

    print(
        f"Output:   {OUTPUT_FILE}"
    )

    if not DATABASE.exists():

        print()
        print(
            "ERROR: SQLite database does not exist."
        )

        return 1

    # --------------------------------------------------------
    # Read local relationships
    # --------------------------------------------------------

    connection = get_connection()

    try:

        linked_recordings = (
            get_linked_recordings(
                connection
            )
        )

        recording_artists = (
            get_recording_artists(
                connection
            )
        )

        existing_recording_genres = (
            get_existing_recording_genres(
                connection
            )
        )

    finally:

        connection.close()

    print()
    print(
        "Existing MusicBrainz relationships:"
    )

    print(
        f"  Linked recordings: "
        f"{len(linked_recordings):,}"
    )

    print(
        f"  Recordings with artist relations: "
        f"{sum(1 for r in linked_recordings if r in recording_artists):,}"
    )

    # --------------------------------------------------------
    # Determine distinct artists
    # --------------------------------------------------------

    distinct_artists = {}

    for recording_id in linked_recordings:

        for relation in recording_artists.get(
            recording_id,
            [],
        ):

            artist_id = relation[
                "artist_id"
            ]

            if artist_id not in distinct_artists:

                distinct_artists[artist_id] = {
                    "artist_id": artist_id,
                    "recordings": [],
                }

            if recording_id not in (
                distinct_artists[artist_id][
                    "recordings"
                ]
            ):

                distinct_artists[artist_id][
                    "recordings"
                ].append(
                    recording_id
                )

    artists = list(
        distinct_artists.values()
    )

    print(
        f"  Distinct artists to test: "
        f"{len(artists):,}"
    )

    # --------------------------------------------------------
    # Query MusicBrainz
    # --------------------------------------------------------

    print()
    print(
        f"Request interval: "
        f"{REQUEST_DELAY_SECONDS:.1f}s"
    )

    print()
    print(
        "Starting MusicBrainz artist requests..."
    )

    artist_results = []

    for index, artist in enumerate(
        artists,
        start=1,
    ):

        artist_id = artist[
            "artist_id"
        ]

        print()
        print(
            f"[{index}/{len(artists)}] "
            f"{artist_id}"
        )

        response = request_artist_genres(
            artist_id
        )

        result = {
            "artist_id": artist_id,
            "recordings": artist[
                "recordings"
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

            artist_name = data.get(
                "name",
                "",
            )

            result["artist_name"] = (
                artist_name
            )

            if genres:

                print(
                    f"  Artist: "
                    f"{artist_name}"
                )

                print(
                    "  Genres: "
                    + ", ".join(
                        genre["name"]
                        for genre in genres
                    )
                )

            else:

                print(
                    f"  Artist: "
                    f"{artist_name}"
                )

                print(
                    "  Genres: NONE"
                )

        else:

            result["error"] = response.get(
                "error"
            )

            print(
                f"  ERROR: "
                f"{result['status']}"
            )

            if result.get("error"):

                print(
                    f"  {result['error']}"
                )

        artist_results.append(
            result
        )

        if index < len(artists):

            time.sleep(
                REQUEST_DELAY_SECONDS
            )

    # --------------------------------------------------------
    # Index artist results
    # --------------------------------------------------------

    artist_by_id = {
        result["artist_id"]: result
        for result in artist_results
    }

    # --------------------------------------------------------
    # Artist coverage
    # --------------------------------------------------------

    total_artists = len(
        artist_results
    )

    successful_artists = sum(
        1
        for result in artist_results
        if result["status"] == "success"
    )

    artists_with_genres = sum(
        1
        for result in artist_results
        if (
            result["status"] == "success"
            and result["genres"]
        )
    )

    # --------------------------------------------------------
    # Recording coverage using artist genres
    # --------------------------------------------------------

    recordings_with_artist_genres = set()

    recording_artist_genres = defaultdict(
        list
    )

    for recording_id in linked_recordings:

        for relation in recording_artists.get(
            recording_id,
            [],
        ):

            artist_id = relation[
                "artist_id"
            ]

            result = artist_by_id.get(
                artist_id
            )

            if not result:
                continue

            if result["status"] != "success":
                continue

            for genre in result["genres"]:

                name = genre["name"]

                if name not in (
                    recording_artist_genres[
                        recording_id
                    ]
                ):

                    recording_artist_genres[
                        recording_id
                    ].append(
                        name
                    )

            if result["genres"]:

                recordings_with_artist_genres.add(
                    recording_id
                )

    # --------------------------------------------------------
    # Recording genre coverage from previous test
    #
    # NOTE:
    # mb_recording_tags may include ordinary tags, not only
    # genres, depending on what the original MusicBrainz
    # acquisition stored.
    #
    # Therefore this section is intentionally labelled as
    # "existing normalized recording metadata", rather than
    # claiming it is equivalent to the new ?inc=genres data.
    # --------------------------------------------------------

    recordings_with_existing_metadata = {
        recording_id
        for recording_id in linked_recordings
        if existing_recording_genres.get(
            recording_id
        )
    }

    # --------------------------------------------------------
    # Combined coverage
    # --------------------------------------------------------

    combined_recording_coverage = (
        recordings_with_existing_metadata
        | recordings_with_artist_genres
    )

    # --------------------------------------------------------
    # Distinct artist genres
    # --------------------------------------------------------

    genre_occurrences = defaultdict(
        int
    )

    for result in artist_results:

        for genre in result["genres"]:

            genre_occurrences[
                genre["name"]
            ] += 1

    # --------------------------------------------------------
    # Report
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print(
        "ARTIST GENRE COVERAGE"
    )
    print("=" * 78)

    print()
    print(
        f"Distinct artists tested:            "
        f"{total_artists:,}"
    )

    print(
        f"Successful API responses:           "
        f"{successful_artists:,} / "
        f"{total_artists:,} "
        f"({successful_artists * 100 / total_artists:.2f}%)"
        if total_artists
        else
        "Successful API responses:           0 / 0"
    )

    print(
        f"Artists with genres:                 "
        f"{artists_with_genres:,} / "
        f"{successful_artists:,} "
        f"({artists_with_genres * 100 / successful_artists:.2f}%)"
        if successful_artists
        else
        "Artists with genres:                 0 / 0"
    )

    print()
    print(
        f"Distinct artist genre names:        "
        f"{len(genre_occurrences):,}"
    )

    if genre_occurrences:

        print()
        print("-" * 78)
        print(
            "ARTIST GENRES FOUND"
        )
        print("-" * 78)

        for name, occurrences in sorted(
            genre_occurrences.items(),
            key=lambda item: (
                -item[1],
                item[0].lower(),
            ),
        ):

            print(
                f"  {name:<45} "
                f"{occurrences:>4}"
            )

    # --------------------------------------------------------
    # Recording impact
    # --------------------------------------------------------

    total_recordings = len(
        linked_recordings
    )

    existing_count = len(
        recordings_with_existing_metadata
    )

    artist_count = len(
        recordings_with_artist_genres
    )

    combined_count = len(
        combined_recording_coverage
    )

    newly_covered = (
        combined_recording_coverage
        - recordings_with_existing_metadata
    )

    print()
    print("=" * 78)
    print(
        "RECORDING COVERAGE IMPACT"
    )
    print("=" * 78)

    print()
    print(
        f"Linked recordings:                  "
        f"{total_recordings:,}"
    )

    print(
        f"Existing recording metadata:        "
        f"{existing_count:,} / "
        f"{total_recordings:,} "
        f"({existing_count * 100 / total_recordings:.2f}%)"
        if total_recordings
        else
        "Existing recording metadata:        0 / 0"
    )

    print(
        f"Recordings with artist genres:       "
        f"{artist_count:,} / "
        f"{total_recordings:,} "
        f"({artist_count * 100 / total_recordings:.2f}%)"
        if total_recordings
        else
        "Recordings with artist genres:       0 / 0"
    )

    print(
        f"Combined potential coverage:         "
        f"{combined_count:,} / "
        f"{total_recordings:,} "
        f"({combined_count * 100 / total_recordings:.2f}%)"
        if total_recordings
        else
        "Combined potential coverage:         0 / 0"
    )

    print(
        f"New recordings potentially covered:  "
        f"{len(newly_covered):,}"
    )

    # --------------------------------------------------------
    # Detailed recording report
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print(
        "RECORDING → ARTIST GENRE DETAILS"
    )
    print("=" * 78)

    for recording_id in sorted(
        linked_recordings
    ):

        spotify_ids = linked_recordings[
            recording_id
        ]

        own_metadata = (
            existing_recording_genres.get(
                recording_id,
                [],
            )
        )

        artist_genres = (
            recording_artist_genres.get(
                recording_id,
                [],
            )
        )

        print()
        print(
            f"MB Recording: {recording_id}"
        )

        print(
            "Spotify tracks: "
            + ", ".join(
                spotify_ids
            )
        )

        print(
            "Existing normalized recording "
            "metadata: "
            + (
                ", ".join(own_metadata)
                if own_metadata
                else "NONE"
            )
        )

        print(
            "Artist genres: "
            + (
                ", ".join(
                    sorted(
                        artist_genres,
                        key=str.lower,
                    )
                )
                if artist_genres
                else "NONE"
            )
        )

    # --------------------------------------------------------
    # Save complete raw test result
    # --------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "test": (
            "musicbrainz_artist_genres"
        ),
        "database": str(DATABASE),
        "endpoint": (
            MUSICBRAINZ_BASE_URL
        ),
        "include": "genres",
        "request_delay_seconds":
            REQUEST_DELAY_SECONDS,
        "artists_tested": len(
            artist_results
        ),
        "results": artist_results,
        "recording_analysis": {
            "linked_recordings":
                total_recordings,
            "recordings_with_existing_metadata":
                existing_count,
            "recordings_with_artist_genres":
                artist_count,
            "combined_potential_coverage":
                combined_count,
            "newly_covered_recordings":
                len(newly_covered),
            "recording_artist_genres": {
                recording_id: sorted(
                    genres,
                    key=str.lower,
                )
                for recording_id, genres
                in recording_artist_genres.items()
            },
        },
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

    print()
    print("=" * 78)
    print(
        "TEST COMPLETED"
    )
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

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "Artist genres have NOT been assigned to "
        "recordings or Spotify tracks."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
