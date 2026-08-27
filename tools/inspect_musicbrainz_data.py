import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE = PROJECT_ROOT / "data" / "spotify_music.db"

SOURCE = "musicbrainz"


def walk_json(value, path="", results=None):
    """
    Recorre recursivamente un JSON y registra todas las rutas,
    tipos y ejemplos encontrados.
    """

    if results is None:
        results = defaultdict(lambda: {
            "count": 0,
            "types": Counter(),
            "examples": []
        })

    # ------------------------------------------------------------------
    # Diccionario
    # ------------------------------------------------------------------

    if isinstance(value, dict):

        for key, child in value.items():

            current_path = f"{path}.{key}" if path else key

            results[current_path]["count"] += 1
            results[current_path]["types"][type(child).__name__] += 1

            # Guardamos algunos ejemplos de valores simples
            if not isinstance(child, (dict, list)):
                if len(results[current_path]["examples"]) < 3:
                    results[current_path]["examples"].append(child)

            walk_json(child, current_path, results)

    # ------------------------------------------------------------------
    # Lista
    # ------------------------------------------------------------------

    elif isinstance(value, list):

        # Registramos que esta ruta es una lista
        results[path]["types"]["list"] += 1

        # Recorremos cada elemento.
        #
        # No agregamos índices [0], [1], etc. al path porque
        # nos interesa descubrir la estructura lógica del JSON,
        # no cada posición concreta de una lista.

        for child in value:
            walk_json(child, path, results)

    return results


def format_example(value):
    """
    Convierte ejemplos complejos en texto legible.
    """

    if isinstance(value, (dict, list)):
        text = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":")
        )
    else:
        text = repr(value)

    if len(text) > 150:
        text = text[:147] + "..."

    return text


def main():

    print("=" * 100)
    print("SPOTIFY MUSIC ANALYZER — INSPECCIÓN PROFUNDA DE MUSICBRAINZ")
    print("=" * 100)

    connection = sqlite3.connect(DATABASE)

    rows = connection.execute("""
        SELECT
            spotify_id,
            isrc,
            source_id,
            data_json
        FROM track_sources
        WHERE source = ?
          AND status = 'found'
          AND data_json IS NOT NULL
    """, (SOURCE,)).fetchall()

    connection.close()

    print()
    print(f"Registros MusicBrainz encontrados: {len(rows)}")
    print()

    if not rows:
        print("No hay registros MusicBrainz para analizar.")
        return

    global_results = defaultdict(lambda: {
        "records": set(),
        "types": Counter(),
        "examples": []
    })

    # ================================================================
    # Analizar cada JSON
    # ================================================================

    for record_number, row in enumerate(rows, start=1):

        spotify_id, isrc, source_id, data_json = row

        try:
            data = json.loads(data_json)

        except json.JSONDecodeError as error:
            print()
            print(f"ERROR JSON en registro {record_number}:")
            print(f"  Spotify ID: {spotify_id}")
            print(f"  ISRC      : {isrc}")
            print(f"  Error     : {error}")
            continue

        local_results = walk_json(data)

        for path, info in local_results.items():

            global_results[path]["records"].add(record_number)

            for data_type, count in info["types"].items():
                global_results[path]["types"][data_type] += count

            for example in info["examples"]:
                if len(global_results[path]["examples"]) < 5:
                    global_results[path]["examples"].append(example)

    # ================================================================
    # Mostrar resultados
    # ================================================================

    print("-" * 100)
    print("ESTRUCTURA ENCONTRADA")
    print("-" * 100)

    sorted_paths = sorted(
        global_results.items(),
        key=lambda item: item[0].lower()
    )

    for path, info in sorted_paths:

        record_count = len(info["records"])
        percentage = record_count / len(rows) * 100

        types = ", ".join(
            f"{name} ({count})"
            for name, count in info["types"].items()
        )

        print()
        print(path)
        print(
            f"  Registros : {record_count}/{len(rows)} "
            f"({percentage:.1f}%)"
        )
        print(f"  Tipos     : {types}")

        if info["examples"]:

            print("  Ejemplos  :")

            for example in info["examples"]:

                print(
                    f"    {format_example(example)}"
                )

    # ================================================================
    # Resumen
    # ================================================================

    print()
    print("=" * 100)
    print("RESUMEN")
    print("=" * 100)

    print(f"Registros analizados : {len(rows)}")
    print(f"Rutas descubiertas   : {len(global_results)}")

    # ================================================================
    # Guardar informe
    # ================================================================

    output_file = Path(__file__).resolve().parent / "musicbrainz_structure.txt"

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            "SPOTIFY MUSIC ANALYZER — INSPECCIÓN PROFUNDA DE MUSICBRAINZ\n"
        )
        file.write("=" * 100 + "\n\n")

        file.write(
            f"Registros analizados: {len(rows)}\n"
        )
        file.write(
            f"Rutas descubiertas: {len(global_results)}\n\n"
        )

        for path, info in sorted_paths:

            record_count = len(info["records"])
            percentage = record_count / len(rows) * 100

            types = ", ".join(
                f"{name} ({count})"
                for name, count in info["types"].items()
            )

            file.write("\n")
            file.write(path + "\n")
            file.write(
                f"  Registros : {record_count}/{len(rows)} "
                f"({percentage:.1f}%)\n"
            )
            file.write(
                f"  Tipos     : {types}\n"
            )

            if info["examples"]:

                file.write("  Ejemplos  :\n")

                for example in info["examples"]:

                    file.write(
                        f"    {format_example(example)}\n"
                    )

    print()
    print(f"Informe guardado en:")
    print(f"  {output_file}")
    print()


if __name__ == "__main__":
    main()