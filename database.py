import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATABASE = DATA_DIR / "spotify_music.db"


def get_connection():
    DATA_DIR.mkdir(exist_ok=True)

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    # Activamos las foreign keys de SQLite.
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def init_database():
    connection = get_connection()

    # -----------------------------------------------------
    # ARTISTS
    # -----------------------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS artists (
            spotify_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            spotify_url TEXT,
            spotify_uri TEXT
        )
    """)

    # -----------------------------------------------------
    # ALBUMS
    # -----------------------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS albums (
            spotify_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            album_type TEXT,
            release_date TEXT,
            release_date_precision TEXT,
            total_tracks INTEGER,
            spotify_url TEXT,
            spotify_uri TEXT
        )
    """)

    # -----------------------------------------------------
    # TRACKS
    # -----------------------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            spotify_id TEXT PRIMARY KEY,
            isrc TEXT,
            track_name TEXT NOT NULL,
            album_id TEXT,
            duration_ms INTEGER,
            disc_number INTEGER,
            track_number INTEGER,
            explicit INTEGER,
            spotify_url TEXT,
            spotify_uri TEXT,
            is_playable INTEGER,
            is_local INTEGER,
            added_at TEXT,

            FOREIGN KEY (album_id)
                REFERENCES albums(spotify_id)
        )
    """)

    # -----------------------------------------------------
    # TRACK ↔ ARTISTS
    # -----------------------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS track_artists (
            spotify_id TEXT NOT NULL,
            artist_id TEXT NOT NULL,
            artist_order INTEGER NOT NULL,

            PRIMARY KEY (spotify_id, artist_id),

            FOREIGN KEY (spotify_id)
                REFERENCES tracks(spotify_id)
                ON DELETE CASCADE,

            FOREIGN KEY (artist_id)
                REFERENCES artists(spotify_id)
                ON DELETE CASCADE
        )
    """)

    connection.commit()
    connection.close()


if __name__ == "__main__":
    init_database()

    print("=" * 70)
    print("SQLITE — INICIALIZACIÓN")
    print("=" * 70)
    print(f"\nBase de datos: {DATABASE}")
    print("Base inicializada correctamente.")