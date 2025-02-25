import random
import time

from flask import Flask, jsonify, request
from flask_cors import CORS 
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)
CORS(app)

# MongoDB connection
client = MongoClient("mongodb+srv://whiteturtle1:dvIw4evFuDVOzea3@cluster0.1e4vx.mongodb.net/sb_users?retryWrites=true&w=majority&appName=Cluster0")
db = client["sb_users"]
albums_collection = db['albums']
artists_collection = db['artists']
users_collection = db['users']
logs_collection = db['userlogs']

# Cache dictionary to store the data and timestamp
cache = {
    "data": None,
    "timestamp": None
}

CACHE_EXPIRY_TIME = 24 * 60 * 60  # 24 hours in seconds

def get_artist_names(artist_ids):
    artists = artists_collection.find({'_id': {'$in': artist_ids}})
    artist_names = {str(artist['_id']): artist['artistName'] for artist in artists}
    return artist_names

def serialize_object_id(obj):
    """
    Recursively convert ObjectId to string.
    """
    if isinstance(obj, dict):
        return {key: serialize_object_id(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_object_id(item) for item in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    return obj

def generate_pie_chart():
    labels = ['Pop', 'Rock', 'Jazz', 'Classical', 'Hip-hop']
    sizes = [30, 20, 10, 25, 15] 
    colors = ['#ff9999','#66b3ff','#99ff99','#ffcc99','#c2c2f0']

    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')

    img_io = io.BytesIO()
    plt.savefig(img_io, format='png')
    img_io.seek(0)

    img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
    return img_base64

def is_cache_valid():
    """Check if the cache is valid (i.e., data is less than 24 hours old)."""
    if cache["timestamp"] is None:
        return False
    return time.time() - cache["timestamp"] < CACHE_EXPIRY_TIME

def fetch_and_cache_data(user_email):
    """Fetch fresh data from the database and cache it."""
    release_year = 2000
    start_date = datetime(release_year, 1, 1)

    album_query = {'releaseDate': {'$gte': start_date}} 
    albums_cursor = albums_collection.find(album_query)
    albums_list = list(albums_cursor)

    user = users_collection.find_one({'email': user_email})
    if not user:
        return jsonify({"error": "User not found"}), 404

    favorite_artist_ids = user.get('favoriteArtists', [])

    favorite_artists = artists_collection.find({'_id': {'$in': favorite_artist_ids}})
    favorite_artist_info = [
        {
            "id": str(artist['_id']),
            "name": artist['artistName'],
            "image": artist.get('artistImage', "default_image_url"),
        }
        for artist in favorite_artists
    ]

    popular_albums = []
    singles = []
    recommended_for_today = []
    new_releases = []

    added_to_new_releases = set()

    for album in albums_list:
        artist_ids = album.get('artists', [])
        artist_names = get_artist_names(artist_ids)

        album_info = album 
        album_info = serialize_object_id(album_info)

        if album['releaseDate'].year >= 2024:
            # Add album to new releases if not already added
            if str(album['_id']) not in added_to_new_releases:
                new_releases.append(album_info)
                added_to_new_releases.add(str(album['_id']))
            continue

        is_popular = False
        for artist_id in artist_ids:
            if artist_id in favorite_artist_ids:
                if len(album.get('tracks', [])) == 1:
                    if str(album['_id']) not in added_to_new_releases:
                        singles.append(album_info)
                else:
                    if str(album['_id']) not in added_to_new_releases:
                        popular_albums.append(album_info)
                is_popular = True
                break

        # Check if the album is not popular and should be recommended
        if not is_popular:
            is_recommended = True
            for artist_id in artist_ids:
                if artist_id in favorite_artist_ids:
                    is_recommended = False
                    break
            if is_recommended and album['releaseDate'].year < 2024:
                if str(album['_id']) not in added_to_new_releases:
                    recommended_for_today.append(album_info)

    # Generate pie chart
    pie_chart_base64 = generate_pie_chart()

    # Cache the data with the current timestamp
    cache["data"] = {
        "popularAlbums": random.sample(popular_albums, min(10, len(popular_albums))),
        "singles": random.sample(singles, min(10, len(singles))),
        "recommendedForToday": random.sample(recommended_for_today, min(10, len(recommended_for_today))),
        "newReleases": random.sample(new_releases, min(10, len(new_releases))),
        "pieChart": pie_chart_base64,
        "favoriteArtists": favorite_artist_info
    }
    cache["timestamp"] = time.time()

    return cache["data"]

@app.route('/api/popular_albums/<user_email>', methods=['GET'])
def get_popular_albums(user_email):
    try:
        # Check if the cache is still valid
        if is_cache_valid():
            return jsonify(cache["data"])

        # If the cache is invalid, fetch fresh data and cache it
        data = fetch_and_cache_data(user_email)
        return jsonify(data)

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": f"An error occurred while fetching data: {str(e)}"}), 500

if __name__ == '__main__':
    app.run()
