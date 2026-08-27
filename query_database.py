import sqlite3
from pathlib import Path


DATABASE = Path(__file__).resolve().parent / "data" / "spotify_music.db"

connection = sqlite3.connect(DATABASE)
connection.row_factory = sqlite3.Row

sql = """
SELECT
    t.track_name,
    GROUP_CONCAT(a.name, ', ') AS artists
FROM tracks t
JOIN track_artists ta
    ON ta.spotify_id = t.spotify_id
JOIN artists a
    ON a.spotify_id = ta.artist_id
GROUP BY t.spotify_id
ORDER BY t.track_name;
"""

rows = connection.execute(sql).fetchall()

print("=" * 80)
print("TRACKS + ARTISTAS")
print("=" * 80)

for row in rows:
    print(
        f"{row['track_name']:<50} | {row['artists']}"
    )

connection.close()