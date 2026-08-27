import sqlite3
from pathlib import Path


DATABASE = Path(__file__).resolve().parent / "data" / "spotify_music.db"


connection = sqlite3.connect(DATABASE)

connection.execute("""
CREATE TABLE IF NOT EXISTS track_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    spotify_id TEXT NOT NULL,
    isrc TEXT,

    source TEXT NOT NULL,
    source_id TEXT,

    status TEXT NOT NULL,

    data_json TEXT,

    retrieved_at TEXT NOT NULL,

    UNIQUE (spotify_id, source),

    FOREIGN KEY (spotify_id)
        REFERENCES tracks (spotify_id)
);
""")

connection.commit()
connection.close()

print("Tabla track_sources creada correctamente.")