import requests
import json
from datetime import datetime
from colorama import init, Fore, Back, Style

# Inicializar colorama para colores en consola
init(autoreset=True)

# Tu API Key de Last.fm
API_KEY = "187fbefc80ea2462263cadba46e9e25e"

def print_section(title, color=Fore.CYAN):
    """Imprime un título de sección con colores"""
    print(f"\n{color}{'='*60}")
    print(f"{color}► {title.upper()}")
    print(f"{color}{'='*60}")

def print_field(label, value, color=Fore.WHITE, indent=0):
    """Imprime un campo con formato bonito"""
    if value and value != "N/A":
        indent_str = "  " * indent
        print(f"{indent_str}{Fore.YELLOW}{label}: {color}{value}")

def get_safe_value(obj, key, default="N/A"):
    """Obtiene un valor de forma segura, manejando strings y diccionarios"""
    if isinstance(obj, dict):
        value = obj.get(key, default)
        return value if value is not None else default
    return default

def get_artist_name(artist_data):
    """Extrae el nombre del artista de forma segura, manejando strings y diccionarios"""
    if isinstance(artist_data, dict):
        return artist_data.get('name', 'N/A')
    elif isinstance(artist_data, str):
        return artist_data
    return 'N/A'

def print_nested(data, indent=0):
    """Función recursiva para imprimir estructuras anidadas"""
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                print(f"{'  ' * indent}{Fore.MAGENTA}{key}:")
                print_nested(value, indent + 1)
            else:
                if value and value != "":
                    print(f"{'  ' * indent}{Fore.YELLOW}{key}: {Fore.WHITE}{value}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, dict):
                print(f"{'  ' * indent}{Fore.CYAN}Elemento {i+1}:")
                print_nested(item, indent + 1)
            else:
                print(f"{'  ' * indent}{Fore.WHITE}• {item}")

def get_all_track_info(artist, track):
    """Obtiene TODA la información disponible de un track"""
    params = {
        'method': 'track.getInfo',
        'api_key': API_KEY,
        'artist': artist,
        'track': track,
        'format': 'json'
    }
    
    try:
        response = requests.get('https://ws.audioscrobbler.com/2.0/', params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'error' in data:
            print(f"{Fore.RED}❌ Error de Last.fm: {data['message']}")
            return None
        
        return data
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}❌ Error en la petición: {e}")
        return None

def display_track_info(data):
    """Muestra TODA la información del track de forma estructurada y con colores"""
    if not data or 'track' not in data:
        print(f"{Fore.RED}❌ No se encontró información para este track")
        return
    
    track = data['track']
    
    # === SECCIÓN 1: INFORMACIÓN BÁSICA ===
    print_section("INFORMACIÓN BÁSICA", Fore.CYAN)
    print_field("Nombre", track.get('name'), Fore.WHITE)
    
    # Manejar artista de forma segura
    artist_name = get_artist_name(track.get('artist'))
    print_field("Artista", artist_name, Fore.WHITE)
    
    # Manejar álbum de forma segura
    album_data = track.get('album', {})
    if isinstance(album_data, dict):
        print_field("Álbum", album_data.get('title'), Fore.WHITE)
    
    print_field("URL", track.get('url'), Fore.BLUE)
    print_field("ID", track.get('id'), Fore.WHITE)
    
    # === SECCIÓN 2: ESTADÍSTICAS ===
    print_section("ESTADÍSTICAS DE POPULARIDAD", Fore.GREEN)
    print_field("Oyentes totales", f"{int(track.get('listeners', 0)):,}".replace(',', '.'), Fore.WHITE)
    print_field("Reproducciones totales", f"{int(track.get('playcount', 0)):,}".replace(',', '.'), Fore.WHITE)
    
    # === SECCIÓN 3: DURACIÓN ===
    if track.get('duration'):
        duration_sec = int(track.get('duration', 0))
        if duration_sec > 0:
            minutes = duration_sec // 60
            seconds = duration_sec % 60
            print_section("DURACIÓN", Fore.MAGENTA)
            print_field("Duración", f"{minutes}:{seconds:02d} (min:seg)", Fore.WHITE)
    
    # === SECCIÓN 4: ETIQUETAS (GÉNEROS) ===
    print_section("ETIQUETAS / GÉNEROS", Fore.YELLOW)
    tags = track.get('toptags', {}).get('tag', [])
    if tags:
        # Asegurar que tags es una lista
        if not isinstance(tags, list):
            tags = [tags]
        
        for i, tag in enumerate(tags[:10], 1):  # Mostrar top 10
            if isinstance(tag, dict):
                name = tag.get('name', 'N/A')
                count = tag.get('count', 0)
                print(f"  {Fore.CYAN}{i}.{Fore.WHITE} {name} {Fore.GREEN}({count} usos)")
            else:
                print(f"  {Fore.CYAN}{i}.{Fore.WHITE} {tag}")
    else:
        print(f"  {Fore.WHITE}No hay etiquetas disponibles")
    
    # === SECCIÓN 5: IMÁGENES ===
    print_section("IMÁGENES", Fore.BLUE)
    if isinstance(album_data, dict):
        images = album_data.get('image', [])
        if images:
            for img in images:
                size = img.get('size', 'desconocido')
                url = img.get('#text', 'N/A')
                if url != 'N/A':
                    print(f"  {Fore.CYAN}{size}:{Fore.WHITE} {url}")
    
    # === SECCIÓN 6: INFORMACIÓN DEL ÁLBUM ===
    print_section("INFORMACIÓN DEL ÁLBUM", Fore.MAGENTA)
    if isinstance(album_data, dict) and album_data:
        print_field("Título", album_data.get('title'), Fore.WHITE)
        
        # Manejar artista del álbum de forma segura
        album_artist = album_data.get('artist')
        if album_artist:
            album_artist_name = get_artist_name(album_artist)
            print_field("Artista", album_artist_name, Fore.WHITE)
        
        print_field("URL", album_data.get('url'), Fore.BLUE)
        if album_data.get('releasedate'):
            print_field("Fecha de lanzamiento", album_data.get('releasedate'), Fore.WHITE)
    else:
        print(f"  {Fore.WHITE}No hay información de álbum disponible")
    
    # === SECCIÓN 7: BIOGRAFÍA DEL ARTISTA (si está disponible) ===
    print_section("INFORMACIÓN DEL ARTISTA", Fore.CYAN)
    artist = track.get('artist', {})
    if artist:
        artist_name = get_artist_name(artist)
        print_field("Nombre", artist_name, Fore.WHITE)
        
        # Si artist es diccionario, obtener más datos
        if isinstance(artist, dict):
            print_field("URL", artist.get('url'), Fore.BLUE)
            if artist.get('mbid'):
                print_field("MBID", artist.get('mbid'), Fore.WHITE)
    
    # === SECCIÓN 8: DATOS CRUDOS (JSON) ===
    print_section("DATOS CRUDOS (JSON)", Fore.RED)
    print(f"{Fore.WHITE}Estructura completa de la respuesta:")
    print_nested(track, 1)
    
    # === SECCIÓN 9: RESUMEN DE CAMPOS DISPONIBLES ===
    print_section("CAMPOS DISPONIBLES EN LA RESPUESTA", Fore.YELLOW)
    all_keys = []
    def extract_keys(obj, prefix=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                full_key = f"{prefix}.{key}" if prefix else key
                all_keys.append(full_key)
                if isinstance(value, dict):
                    extract_keys(value, full_key)
                elif isinstance(value, list) and value and isinstance(value[0], dict):
                    extract_keys(value[0], f"{full_key}[0]")
    
    extract_keys(track)
    print(f"{Fore.WHITE}Total de campos: {len(all_keys)}")
    for key in sorted(all_keys)[:20]:  # Mostrar primeros 20 para no saturar
        print(f"  {Fore.CYAN}•{Fore.WHITE} {key}")
    if len(all_keys) > 20:
        print(f"  {Fore.YELLOW}... y {len(all_keys) - 20} campos más")

def search_tracks(query, limit=5):
    """Busca tracks que coincidan con una consulta"""
    params = {
        'method': 'track.search',
        'api_key': API_KEY,
        'track': query,
        'limit': limit,
        'format': 'json'
    }
    
    try:
        response = requests.get('https://ws.audioscrobbler.com/2.0/', params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'error' in data:
            print(f"{Fore.RED}❌ Error de Last.fm: {data['message']}")
            return None
        
        return data
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}❌ Error en la petición: {e}")
        return None

def display_search_results(data):
    """Muestra resultados de búsqueda"""
    if not data or 'results' not in data:
        print(f"{Fore.RED}❌ No se encontraron resultados")
        return
    
    results = data['results'].get('trackmatches', {}).get('track', [])
    if not results:
        print(f"{Fore.YELLOW}⚠️ No se encontraron canciones")
        return
    
    print_section("RESULTADOS DE BÚSQUEDA", Fore.GREEN)
    for i, track in enumerate(results, 1):
        print(f"{Fore.CYAN}{i}.{Fore.WHITE} {track.get('name')} - {track.get('artist')}")
        print(f"   {Fore.BLUE}URL: {track.get('url')}")
        print(f"   {Fore.YELLOW}Oyentes: {track.get('listeners', 'N/A')}")
        print()

def test_track_info(artist, track):
    """Función de prueba para verificar un track específico"""
    print(f"\n{Fore.CYAN}🔍 Probando: {artist} - {track}")
    print(f"{Fore.CYAN}{'='*60}")
    
    data = get_all_track_info(artist, track)
    if data:
        display_track_info(data)
    else:
        print(f"{Fore.RED}❌ No se pudo obtener información")

# ============ EJEMPLOS DE USO ============

def main():
    print(f"{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}🎵 LAST.FM TRACK INFO - EXPLORADOR COMPLETO")
    print(f"{Fore.CYAN}{'='*60}")
    
    # Ejemplo 1: Queen - Bohemian Rhapsody (generalmente tiene estructura completa)
    print(f"\n{Fore.GREEN}📌 EJEMPLO 1: Información de 'Bohemian Rhapsody' de Queen")
    test_track_info("Queen", "Bohemian Rhapsody")
    
    # Ejemplo 2: Un caso que podría tener el problema del artista como string
    print(f"\n\n{Fore.GREEN}📌 EJEMPLO 2: Información de un track con formato variable")
    test_track_info("Queen", "We Will Rock You")
    
    # Ejemplo 3: Buscar tracks
    print(f"\n\n{Fore.GREEN}📌 EJEMPLO 3: Buscar canciones de 'The Beatles'")
    search_data = search_tracks("The Beatles", limit=3)
    display_search_results(search_data)

if __name__ == "__main__":
    main()