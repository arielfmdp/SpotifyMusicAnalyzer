import os
import sqlite3
from pathlib import Path

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyPKCE


# =========================================================
# CONFIGURACIÓN
# =========================================================

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "data" / "spotify_music.db"

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

SCOPE = (
    "user-read-private "
    "user-library-read "
    "playlist-read-private "
    "playlist-read-collaborative"
)

# Para la primera prueba.
# Después lo cambiaremos a None.
TEST_TRACKS = None


# =========================================================
# AUTENTICACIÓN
# =========================================================

sp_oauth = SpotifyPKCE(
    client_id=CLIENT_ID,
    redirect_uri=REDIRECT_URI,
    scope=SCOPE,
    open_browser=True,
    cache_path=".spotify_cache",
)


# =========================================================
# BASE DE DATOS
# =========================================================

def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


# =========================================================
# IMPORTACIÓN
# =========================================================

def import_tracks(sp, maximum_tracks=None):

    connection = get_connection()

    offset = 0
    processed = 0

    try:

        while True:

            if maximum_tracks is not None:
                remaining = maximum_tracks - processed

                if remaining <= 0:
                    break

                limit = min(50, remaining)

            else:
                limit = 50

            page = sp.current_user_saved_tracks(
                limit=limit,
                offset=offset,
            )

            items = page["items"]

            if not items:
                break

            # Una transacción por página.
            connection.execute("BEGIN")

            try:

                for item in items:

                    track = item["track"]

                    if not track:
                        continue

                    spotify_id = track.get("id")

                    if not spotify_id:
                        continue

                    # -------------------------------------------------
                    # ALBUM
                    # -------------------------------------------------

                    album = track.get("album") or {}
                    album_id = album.get("id")

                    if album_id:

                        connection.execute(
                            """
                            INSERT OR IGNORE INTO albums (
                                spotify_id,
                                name,
                                album_type,
                                release_date,
                                release_date_precision,
                                total_tracks,
                                spotify_url,
                                spotify_uri
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                album_id,
                                album.get("name"),
                                album.get("album_type"),
                                album.get("release_date"),
                                album.get("release_date_precision"),
                                album.get("total_tracks"),
                                album.get("external_urls", {}).get("spotify"),
                                album.get("uri"),
                            ),
                        )

                    # -------------------------------------------------
                    # TRACK
                    # -------------------------------------------------

                    external_ids = track.get("external_ids") or {}

                    isrc = external_ids.get("isrc")

                    connection.execute(
                        """
                        INSERT OR IGNORE INTO tracks (
                            spotify_id,
                            isrc,
                            track_name,
                            album_id,
                            duration_ms,
                            disc_number,
                            track_number,
                            explicit,
                            spotify_url,
                            spotify_uri,
                            is_playable,
                            is_local,
                            added_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            spotify_id,
                            isrc,
                            track.get("name"),
                            album_id,
                            track.get("duration_ms"),
                            track.get("disc_number"),
                            track.get("track_number"),
                            int(track.get("explicit", False)),
                            track.get("external_urls", {}).get("spotify"),
                            track.get("uri"),
                            int(track.get("is_playable", False)),
                            int(track.get("is_local", False)),
                            item.get("added_at"),
                        ),
                    )

                    # -------------------------------------------------
                    # ARTISTAS
                    # -------------------------------------------------

                    artists = track.get("artists") or []

                    for artist_order, artist in enumerate(artists):

                        artist_id = artist.get("id")

                        if not artist_id:
                            continue

                        connection.execute(
                            """
                            INSERT OR IGNORE INTO artists (
                                spotify_id,
                                name,
                                spotify_url,
                                spotify_uri
                            )
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                artist_id,
                                artist.get("name"),
                                artist.get("external_urls", {}).get("spotify"),
                                artist.get("uri"),
                            ),
                        )

                        connection.execute(
                            """
                            INSERT OR IGNORE INTO track_artists (
                                spotify_id,
                                artist_id,
                                artist_order
                            )
                            VALUES (?, ?, ?)
                            """,
                            (
                                spotify_id,
                                artist_id,
                                artist_order,
                            ),
                        )

                    processed += 1

                connection.commit()

            except Exception:
                connection.rollback()
                raise

            print(
                f"Spotify → SQLite: {processed} tracks procesados"
            )

            if not page.get("next"):
                break

            offset += len(items)

    finally:
        connection.close()

    return processed


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    print("=" * 70)
    print("SPOTIFY → SQLITE")
    print("=" * 70)

    if not CLIENT_ID:
        raise RuntimeError(
            "No se encontró SPOTIFY_CLIENT_ID en .env"
        )

    print("\nAutenticando con Spotify...")

    token_info = sp_oauth.get_cached_token()

    if not token_info:
        print(
            "No existe una autorización válida. "
            "Se abrirá Spotify."
        )

        authorization_url = sp_oauth.get_authorize_url()

        import webbrowser
        webbrowser.open(authorization_url)

        code = input(
            "\nPegá aquí el código devuelto por Spotify: "
        ).strip()

        token_info = sp_oauth.get_access_token(code)

    sp = spotipy.Spotify(
        auth=(
            token_info["access_token"]
            if isinstance(token_info, dict)
            else token_info
        )
    )

    user = sp.current_user()

    print(
        f"Usuario Spotify: {user['display_name']}"
    )

    print(
        f"Base de datos: {DATABASE}"
    )

    print(
        f"\nImportando {TEST_TRACKS} tracks de prueba..."
    )

    total = import_tracks(
        sp,
        maximum_tracks=TEST_TRACKS,
    )

    print("\n" + "=" * 70)
    print("IMPORTACIÓN FINALIZADA")
    print("=" * 70)

    print(
        f"Tracks procesados: {total}"
    )