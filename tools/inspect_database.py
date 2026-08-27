import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE = PROJECT_ROOT / "data" / "spotify_music.db"

connection = sqlite3.connect(DATABASE)
connection.row_factory = sqlite3.Row


print("=" * 80)
print("SQLITE — INSPECCIÓN DE LA BASE")
print("=" * 80)

# Cantidad de tracks
row = connection.execute(
    "SELECT COUNT(*) AS total FROM tracks"
).fetchone()

print(f"\nTracks en la base: {row['total']}")


# Estructura de la tabla
print("\n" + "-" * 80)
print("ESTRUCTURA DE tracks")
print("-" * 80)

columns = connection.execute(
    "PRAGMA table_info(tracks)"
).fetchall()

for column in columns:
    print(
        f"{column['name']:20} "
        f"{column['type']:10} "
        f"PK={column['pk']}"
    )


# Primeros 10 tracks
print("\n" + "-" * 80)
print("PRIMEROS 10 TRACKS")
print("-" * 80)

tracks = connection.execute(
    """
    SELECT
        spotify_id,
        artist_name,
        track_name,
        album_name,
        isrc,
        release_date,
        duration_ms,
        added_at
    FROM tracks
    ORDER BY added_at
    LIMIT 10
    """
).fetchall()


for track in tracks:
    print(
        f"{track['artist_name']} - "
        f"{track['track_name']}"
    )

    print(
        f"  Álbum    : {track['album_name']}"
    )

    print(
        f"  ISRC     : {track['isrc']}"
    )

    print(
        f"  Spotify  : {track['spotify_id']}"
    )

    print()


connection.close()