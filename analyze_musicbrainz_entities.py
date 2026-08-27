import json
import sqlite3
from collections import Counter, defaultdict


DB_PATH = "data/spotify_music.db"


def load_musicbrainz_json():

    connection = sqlite3.connect(DB_PATH)

    rows = connection.execute("""
        SELECT
            id,
            spotify_id,
            isrc,
            source_id,
            data_json
        FROM track_sources
        WHERE source = 'musicbrainz'
          AND data_json IS NOT NULL
    """).fetchall()

    connection.close()

    return rows


def collect_entities(rows):

    recordings = {}
    artists = {}
    aliases = {}
    releases = {}
    release_tracks = {}
    tags = {}
    isrcs = set()

    recording_occurrences = Counter()
    artist_occurrences = Counter()
    release_occurrences = Counter()

    track_recordings = defaultdict(set)

    json_errors = 0
    json_processed = 0

    for db_id, spotify_id, spotify_isrc, source_id, data_json in rows:

        try:
            data = json.loads(data_json)
        except (json.JSONDecodeError, TypeError):
            json_errors += 1
            continue

        json_processed += 1

        recordings_list = data.get("recordings", [])

        if not isinstance(recordings_list, list):
            continue

        for recording in recordings_list:

            if not isinstance(recording, dict):
                continue

            recording_id = recording.get("id")

            if recording_id:

                recording_occurrences[recording_id] += 1

                recordings[recording_id] = {
                    "title": recording.get("title"),
                    "length": recording.get("length"),
                    "first_release_date": recording.get(
                        "first-release-date"
                    ),
                    "score": recording.get("score"),
                    "disambiguation": recording.get(
                        "disambiguation"
                    ),
                }

                track_recordings[spotify_id].add(recording_id)

            # ---------------------------------------------------------
            # ISRC
            # ---------------------------------------------------------

            for isrc in recording.get("isrcs", []):

                if isrc:
                    isrcs.add(isrc)

            # ---------------------------------------------------------
            # ARTISTS
            # ---------------------------------------------------------

            for credit in recording.get("artist-credit", []):

                if not isinstance(credit, dict):
                    continue

                artist = credit.get("artist")

                if not isinstance(artist, dict):
                    continue

                artist_id = artist.get("id")

                if artist_id:

                    artist_occurrences[artist_id] += 1

                    artists[artist_id] = {
                        "name": artist.get("name"),
                        "sort_name": artist.get("sort-name"),
                        "disambiguation": artist.get(
                            "disambiguation"
                        ),
                    }

                # -----------------------------------------------------
                # ALIASES
                # -----------------------------------------------------

                for alias in artist.get("aliases", []):

                    if not isinstance(alias, dict):
                        continue

                    alias_name = alias.get("name")

                    if not alias_name:
                        continue

                    key = (
                        artist_id,
                        alias_name,
                        alias.get("locale"),
                        alias.get("type"),
                    )

                    aliases[key] = {
                        "artist_id": artist_id,
                        "name": alias_name,
                        "sort_name": alias.get("sort-name"),
                        "locale": alias.get("locale"),
                        "type": alias.get("type"),
                        "primary": alias.get("primary"),
                        "begin_date": alias.get("begin-date"),
                        "end_date": alias.get("end-date"),
                    }

            # ---------------------------------------------------------
            # TAGS
            # ---------------------------------------------------------

            for tag in recording.get("tags", []):

                if not isinstance(tag, dict):
                    continue

                tag_name = tag.get("name")

                if tag_name:
                    tags[tag_name] = tag.get("count")

            # ---------------------------------------------------------
            # RELEASES
            # ---------------------------------------------------------

            for release in recording.get("releases", []):

                if not isinstance(release, dict):
                    continue

                release_id = release.get("id")

                if not release_id:
                    continue

                release_occurrences[release_id] += 1

                release_group = release.get(
                    "release-group"
                )

                if not isinstance(release_group, dict):
                    release_group = {}

                releases[release_id] = {
                    "title": release.get("title"),
                    "date": release.get("date"),
                    "country": release.get("country"),
                    "status": release.get("status"),
                    "track_count": release.get("track-count"),
                    "release_group_id": release_group.get(
                        "id"
                    ),
                    "release_group_title": release_group.get(
                        "title"
                    ),
                    "primary_type": release_group.get(
                        "primary-type"
                    ),
                }

                # -----------------------------------------------------
                # MEDIA / RELEASE TRACKS
                # -----------------------------------------------------

                for medium in release.get("media", []):

                    if not isinstance(medium, dict):
                        continue

                    medium_id = medium.get("id")
                    medium_position = medium.get("position")

                    for track in medium.get("tracks", []):

                        if not isinstance(track, dict):
                            continue

                        release_track_id = track.get("id")

                        if not release_track_id:
                            continue

                        key = (
                            release_track_id,
                            release_id,
                        )

                        release_tracks[key] = {
                            "track_id": release_track_id,
                            "release_id": release_id,
                            "medium_id": medium_id,
                            "medium_position": medium_position,
                            "number": track.get("number"),
                            "title": track.get("title"),
                            "length": track.get("length"),
                        }

    return {
        "recordings": recordings,
        "artists": artists,
        "aliases": aliases,
        "releases": releases,
        "release_tracks": release_tracks,
        "tags": tags,
        "isrcs": isrcs,
        "recording_occurrences": recording_occurrences,
        "artist_occurrences": artist_occurrences,
        "release_occurrences": release_occurrences,
        "track_recordings": track_recordings,
        "json_processed": json_processed,
        "json_errors": json_errors,
    }


def print_section(title):

    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def main():

    print("=" * 80)
    print(
        "SPOTIFY MUSIC ANALYZER — "
        "INVENTARIO DE ENTIDADES MUSICBRAINZ"
    )
    print("=" * 80)

    rows = load_musicbrainz_json()

    print()
    print(
        f"Registros MusicBrainz en track_sources : {len(rows)}"
    )

    result = collect_entities(rows)

    print()
    print(
        f"JSON procesados correctamente           : "
        f"{result['json_processed']}"
    )

    print(
        f"JSON con errores                        : "
        f"{result['json_errors']}"
    )

    # ================================================================
    # ENTIDADES
    # ================================================================

    print_section("ENTIDADES ÚNICAS")

    print(
        f"Recordings únicos                       : "
        f"{len(result['recordings'])}"
    )

    print(
        f"Artists únicos                          : "
        f"{len(result['artists'])}"
    )

    print(
        f"Aliases únicos                          : "
        f"{len(result['aliases'])}"
    )

    print(
        f"Releases únicos                         : "
        f"{len(result['releases'])}"
    )

    print(
        f"Release tracks únicos                   : "
        f"{len(result['release_tracks'])}"
    )

    print(
        f"Tags únicos                             : "
        f"{len(result['tags'])}"
    )

    print(
        f"ISRC únicos                             : "
        f"{len(result['isrcs'])}"
    )

    # ================================================================
    # RELACIÓN SPOTIFY → RECORDINGS
    # ================================================================

    print_section(
        "RELACIÓN SPOTIFY → MUSICBRAINZ RECORDINGS"
    )

    spotify_with_mb = 0

    for spotify_id, recording_ids in (
        result["track_recordings"].items()
    ):

        if recording_ids:
            spotify_with_mb += 1

    print(
        f"Tracks Spotify con recordings MB        : "
        f"{spotify_with_mb}"
    )

    print(
        f"Tracks Spotify representados en JSON    : "
        f"{len(result['track_recordings'])}"
    )

    # ================================================================
    # RECORDINGS MÁS REPETIDOS
    # ================================================================

    print_section(
        "RECORDINGS MÁS REPETIDOS EN LAS RESPUESTAS"
    )

    for recording_id, occurrences in (
        result["recording_occurrences"]
        .most_common(20)
    ):

        recording = result["recordings"][recording_id]

        print(
            f"{occurrences:4}  "
            f"{recording['title']}  "
            f"[{recording_id}]"
        )

    # ================================================================
    # ARTISTAS
    # ================================================================

    print_section("ARTISTAS")

    for artist_id, artist in list(
        result["artists"].items()
    )[:30]:

        print()
        print(f"ID     : {artist_id}")
        print(f"Nombre : {artist['name']}")

        if artist["sort_name"]:
            print(
                f"Sort   : {artist['sort_name']}"
            )

        if artist["disambiguation"]:
            print(
                f"Detalle: {artist['disambiguation']}"
            )

    # ================================================================
    # TAGS
    # ================================================================

    print_section("TAGS")

    tag_counter = Counter()

    for tag_name, count in result["tags"].items():

        tag_counter[tag_name] = count or 0

    for tag_name, count in (
        tag_counter.most_common(40)
    ):

        print(
            f"{tag_name:35} {count}"
        )

    # ================================================================
    # RELEASES
    # ================================================================

    print_section("RELEASES MÁS REPETIDOS")

    for release_id, occurrences in (
        result["release_occurrences"]
        .most_common(30)
    ):

        release = result["releases"][release_id]

        print()
        print(
            f"Ocurrencias : {occurrences}"
        )
        print(
            f"ID          : {release_id}"
        )
        print(
            f"Título      : {release['title']}"
        )
        print(
            f"Fecha       : {release['date']}"
        )
        print(
            f"País        : {release['country']}"
        )
        print(
            f"Tipo        : {release['primary_type']}"
        )
        print(
            f"Tracks      : {release['track_count']}"
        )

    # ================================================================
    # RESUMEN
    # ================================================================

    print_section("RESUMEN")

    print()
    print(
        "La información encontrada representa:"
    )
    print()

    print(
        f"  {len(result['recordings']):6} "
        f"recordings MusicBrainz únicos"
    )

    print(
        f"  {len(result['artists']):6} "
        f"artistas únicos"
    )

    print(
        f"  {len(result['aliases']):6} "
        f"aliases de artistas únicos"
    )

    print(
        f"  {len(result['releases']):6} "
        f"releases únicos"
    )

    print(
        f"  {len(result['release_tracks']):6} "
        f"tracks dentro de releases únicos"
    )

    print(
        f"  {len(result['tags']):6} "
        f"tags únicos"
    )

    print(
        f"  {len(result['isrcs']):6} "
        f"ISRC únicos"
    )

    print()
    print(
        "IMPORTANTE: todavía NO se modificó la base."
    )


if __name__ == "__main__":
    main()