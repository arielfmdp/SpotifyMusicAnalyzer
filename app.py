import os

import spotipy
from dotenv import load_dotenv
from flask import Flask, redirect, request
from spotipy.oauth2 import SpotifyPKCE
from pprint import pformat

load_dotenv()

app = Flask(__name__)

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

SCOPE = (
    "user-read-private "
    "user-library-read "
    "playlist-read-private "
    "playlist-read-collaborative"
)

sp_oauth = SpotifyPKCE(
    client_id=CLIENT_ID,
    redirect_uri=REDIRECT_URI,
    scope=SCOPE,
    open_browser=False,
    cache_path=".spotify_cache",
)


@app.route("/")
def index():
    return '<a href="/login">Conectar con Spotify</a>'


@app.route("/login")
def login():
    return redirect(sp_oauth.get_authorize_url())


@app.route("/callback")
def callback():
    code = request.args.get("code")

    if not code:
        return "Error: Spotify no devolvió el código de autorización."

    access_token = sp_oauth.get_access_token(code)

    sp = spotipy.Spotify(auth=access_token)

    user = sp.current_user()
    saved_tracks = sp.current_user_saved_tracks(limit=1)
    saved_tracks_total = saved_tracks["total"]
    first_item = saved_tracks["items"][0]
    first_track = first_item["track"]
    playlists = sp.current_user_playlists(limit=50)
    playlist_items = playlists["items"]

    playlist_list = ""

    for playlist in playlists["items"]:
        playlist_list += f"""
            <li>
                {playlist["name"]}
                — {playlist["items"]["total"]} tracks
            </li>
        """

    return f"""
        <h1>Spotify Music Analyzer</h1>

        <p>Conectado correctamente.</p>
        <p>Usuario: {user["display_name"]}</p>
        <p>Canciones guardadas: {saved_tracks_total}</p>
        <pre>primer track: {pformat(first_track)}</pre>
        <pre>primer item: {pformat(first_item)}</pre>

        <h2>Mis playlists</h2>

        <ul>
            {playlist_list}
        </ul>
    """


if __name__ == "__main__":
    app.run(debug=True)