import csv
import time
import requests


CSV_FILE = "test_music_sources.csv"

MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2/isrc"

HEADERS = {
    "User-Agent": "SpotifyMusicAnalyzer/0.1 (arielfmdp@gmail.com)"
}


def main():

    # Leer los tracks que la búsqueda anterior no encontró
    unmatched = []

    with open(CSV_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            if row.get("musicbrainz_status") == "not_found":
                unmatched.append(row)

    print("=" * 80)
    print("MUSICBRAINZ — LOOKUP DIRECTO POR ISRC")
    print("=" * 80)

    print(f"\nISRC no encontrados anteriormente: {len(unmatched)}\n")

    found = 0
    not_found = 0
    errors = 0

    for i, row in enumerate(unmatched, start=1):

        isrc = row["isrc"]
        artist = row["artist"]
        title = row["track"]

        print("-" * 80)
        print(f"{i:02d}. {artist} - {title}")
        print(f"    ISRC: {isrc}")

        try:

            url = f"{MUSICBRAINZ_URL}/{isrc}"

            response = requests.get(
                url,
                params={
                    "fmt": "json"
                },
                headers=HEADERS,
                timeout=30
            )

            if response.status_code == 404:
                print("    Resultado: NO ENCONTRADO")
                not_found += 1

            else:
                response.raise_for_status()

                data = response.json()
                recordings = data.get("recording-list", [])

                if recordings:

                    found += 1

                    print(f"    Resultado: ENCONTRADO")
                    print(f"    Grabaciones: {len(recordings)}")

                    for recording in recordings:
                        print(
                            f"    MBID   : {recording.get('id')}"
                        )
                        print(
                            f"    Título : {recording.get('title')}"
                        )

                else:
                    not_found += 1
                    print("    Resultado: NO ENCONTRADO")

        except Exception as e:

            errors += 1
            print(f"    ERROR: {type(e).__name__}: {e}")

        # MusicBrainz exige como máximo aproximadamente
        # una solicitud por segundo.
        time.sleep(1.1)

    print()
    print("=" * 80)
    print("RESULTADO")
    print("=" * 80)

    print(f"""
ISRC analizados              : {len(unmatched)}

Encontrados por lookup       : {found}
No encontrados               : {not_found}
Errores                      : {errors}

Cobertura del lookup         : {
    (found / len(unmatched) * 100) if unmatched else 0
:.1f}%
""")


if __name__ == "__main__":
    main()