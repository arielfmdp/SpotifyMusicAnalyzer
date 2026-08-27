import sqlite3
from pathlib import Path


DATABASE = Path(__file__).resolve().parent / "data" / "spotify_music.db"

connection = sqlite3.connect(DATABASE)


queries = {
    "tracks": "SELECT COUNT(*) FROM tracks",
    "albums": "SELECT COUNT(*) FROM albums",
    "artists": "SELECT COUNT(*) FROM artists",
    "track_artists": "SELECT COUNT(*) FROM track_artists",

    "tracks con ISRC": """
        SELECT COUNT(*)
        FROM tracks
        WHERE isrc IS NOT NULL
          AND isrc != ''
    """,

    "tracks sin ISRC": """
        SELECT COUNT(*)
        FROM tracks
        WHERE isrc IS NULL
           OR isrc = ''
    """,

    "tracks con URL Spotify": """
        SELECT COUNT(*)
        FROM tracks
        WHERE spotify_url IS NOT NULL
          AND spotify_url != ''
    """,

    "tracks reproducibles": """
        SELECT COUNT(*)
        FROM tracks
        WHERE is_playable = 1
    """,

    "tracks locales": """
        SELECT COUNT(*)
        FROM tracks
        WHERE is_local = 1
    """,
}


print("=" * 70)
print("SPOTIFY MUSIC ANALYZER — ESTADÍSTICAS")
print("=" * 70)

for description, sql in queries.items():
    result = connection.execute(sql).fetchone()[0]

    print(f"{description:<30}: {result:,}")



rows = connection.execute("""
    SELECT
        isrc,
        COUNT(*) AS cantidad
    FROM tracks
    WHERE isrc IS NOT NULL
      AND isrc != ''
    GROUP BY isrc
    HAVING COUNT(*) > 1
    ORDER BY cantidad DESC
    LIMIT 20
""").fetchall()

print("\n" + "-" * 70)
print("ISRC REPETIDOS")
print("-" * 70)

for isrc, cantidad in rows:
    print(f"{isrc:<20} {cantidad}")


connection.close()