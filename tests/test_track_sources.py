import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE = PROJECT_ROOT / "data" / "spotify_music.db"

connection = sqlite3.connect(DATABASE)

# Tomamos un track real de nuestra base
track = connection.execute("""
    SELECT spotify_id, isrc, track_name
    FROM tracks
    LIMIT 1
""").fetchone()

spotify_id, isrc, track_name = track


# Datos ficticios que simulan una respuesta externa
fake_data = {
    "example": True,
    "message": "Prueba de track_sources"
}


connection.execute("""
INSERT INTO track_sources (
    spotify_id,
    isrc,
    source,
    source_id,
    status,
    data_json,
    retrieved_at
)
VALUES (?, ?, ?, ?, ?, ?, ?)
""", (
    spotify_id,
    isrc,
    "test",
    "TEST-001",
    "found",
    json.dumps(fake_data),
    datetime.now(timezone.utc).isoformat()
))

connection.commit()


print("=" * 70)
print("PRUEBA track_sources")
print("=" * 70)

row = connection.execute("""
    SELECT
        spotify_id,
        isrc,
        source,
        source_id,
        status,
        data_json,
        retrieved_at
    FROM track_sources
    WHERE source = 'test'
""").fetchone()

print(row)


# Eliminamos el registro de prueba
connection.execute("""
DELETE FROM track_sources
WHERE source = 'test'
""")

connection.commit()

print("\nRegistro de prueba eliminado correctamente.")

connection.close()