import random
import time

import matplotlib
matplotlib.use('Agg')

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

client = MongoClient("mongodb+srv://whiteturtle1:dvIw4evFuDVOzea3@cluster0.1e4vx.mongodb.net/sb_users?retryWrites=true&w=majority&appName=Cluster0")
db = client["sb_users"]
albums_collection = db['albums']
artists_collection = db['artists']
users_collection = db['users']
logs_collection = db['userlogs']
tracks_collection = db['tracks']

# Cache dictionary to store the data and timestamp for each user
user_cache = {}
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

def deserialize_object_id(obj):
    """
    Recursively convert string back to ObjectId.
    """
    if isinstance(obj, dict):
        return {key: deserialize_object_id(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [deserialize_object_id(item) for item in obj]
    elif isinstance(obj, str):
        try:
            # Try to convert string to ObjectId if it's in valid format
            return ObjectId(obj)
        except Exception as e:
            # If the string is not a valid ObjectId, return it as is
            return obj
    return obj

def generate_pie_chart(dictionary):
    labels = dictionary.keys()
    sizes = dictionary.values()

    colors = ['#D32F2F', '#1976D2', '#388E3C', '#FBC02D', '#8E24AA', '#F57C00']
    fig, ax = plt.subplots()
    fig.patch.set_facecolor('#121212')
    fig.set_size_inches(10, 10)

    wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=45, 
                                      textprops={'color': "#e0e0e0", 'fontsize': 18, 'fontweight': 'bold'})

    ax.axis('equal')

    for text in texts:
        text.set_fontsize(20)
        text.set_fontweight('bold')
        text.set_color('#e0e0e0')

    for autotext in autotexts:
        autotext.set_fontsize(16)
        autotext.set_fontweight('bold')
        autotext.set_color('#e0e0e0')

    ax.legend(wedges, labels, title="Artists", loc="upper left", bbox_to_anchor=(1, 0.9), fontsize=15, facecolor="#121212", edgecolor="#e0e0e0", labelcolor='#e0e0e0')

    # Save the figure to a BytesIO object
    img_io = io.BytesIO()
    plt.savefig(img_io, format='png', bbox_inches='tight', pad_inches=0.1)
    img_io.seek(0)

    img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
    return img_base64

def generate_bar_chart(dictionary):
    labels = list(dictionary.keys())
    sizes = list(dictionary.values())

    bar_color = '#1976D2' 
    fig, ax = plt.subplots(figsize=(10, 6)) 
    ax.bar(labels, sizes, color=bar_color)

    fig.patch.set_facecolor('#121212')
    ax.set_facecolor('#121212') 

    ax.set_xlabel('Artists', fontsize=16, fontweight='bold', color='#e0e0e0')
    ax.set_ylabel('Play Count', fontsize=16, fontweight='bold', color='#e0e0e0')

    ax.tick_params(axis='x', labelcolor='#e0e0e0', labelrotation=45) 
    ax.tick_params(axis='y', labelcolor='#e0e0e0')

    for label in ax.get_xticklabels():
        label.set_fontsize(14) 
        label.set_fontweight('bold')

    ax.grid(True, color='#e0e0e0', linestyle='--', linewidth=0.5)

    # Save the figure to a BytesIO object
    img_io = io.BytesIO()
    plt.savefig(img_io, format='png', bbox_inches='tight', pad_inches=0.1)
    img_io.seek(0)

    # Return the image as a base64 encoded string
    img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
    return img_base64

def is_cache_valid(user_email):
    """Check if the cache is valid for the given user (i.e., data is less than 24 hours old)."""
    user_cache_data = user_cache.get(user_email)
    if not user_cache_data:
        return False
    return time.time() - user_cache_data["timestamp"] < CACHE_EXPIRY_TIME

def fetch_and_cache_data(user_email):
    """Fetch fresh data from the database and cache it for the given user."""
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

    # Cache the data for this user with the current timestamp
    user_cache[user_email] = {
        "data": {
            "popularAlbums": random.sample(popular_albums, min(10, len(popular_albums))),
            "singles": random.sample(singles, min(10, len(singles))),
            "recommendedForToday": random.sample(recommended_for_today, min(10, len(recommended_for_today))),
            "newReleases": random.sample(new_releases, min(10, len(new_releases))),
            "favoriteArtists": favorite_artist_info
        },
        "timestamp": time.time()
    }

    return user_cache[user_email]["data"]

@app.route('/api/popular_albums/<user_email>', methods=['GET'])
def get_popular_albums(user_email):
    try:
        # Check if the cache is still valid for the given user
        if is_cache_valid(user_email):
            return jsonify(user_cache[user_email]["data"])

        # If the cache is invalid, fetch fresh data and cache it for the user
        data = fetch_and_cache_data(user_email)
        return jsonify(data)

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": f"An error occurred while fetching data: {str(e)}"}), 500
    

def get_artist_names_by_ids(artist_ids):
    """Fetch the artist names from the artist IDs."""
    try:
        artist_ids = [ObjectId(id) if not isinstance(id, ObjectId) else id for id in artist_ids]
        
        artists_cursor = artists_collection.find({'_id': {'$in': artist_ids}})                
        artist_names = [artist['artistName'] for artist in artists_cursor if 'artistName' in artist]
                
        return artist_names
    except Exception as e:
        print(f"Error fetching artist names: {str(e)}")
        return []

def get_top_artists(artist_frequency):
    sorted_artists = sorted(artist_frequency.items(), key=lambda item: item[1], reverse=True)
    top_5_artists = dict(sorted_artists[:5])

    others_count = max([value for key, value in sorted_artists[5:]], default=0)
    if others_count > 0:
        top_5_artists['Others'] = others_count

    sorted_top_artists = dict(sorted(top_5_artists.items(), key=lambda item: item[1], reverse=True))
    return sorted_top_artists

def fetch_artists_and_playcount():
    try:
        artists = artists_collection.find({}, {'_id': 1, 'artistName': 1, 'playCount': 1})
        
        artist_dict = {}

        # Iterate through the cursor and populate the dictionary
        for artist in artists:
            artist_dict[artist['artistName']] = artist['playCount']

        # Sort the artists by play count in descending order
        sorted_artists = sorted(artist_dict.items(), key=lambda item: item[1], reverse=True)

        # Select top 5 artists
        top_5_artists = dict(sorted_artists[:5])

        # Calculate the maximum play count for the remaining artists (if any)
        remaining_artists_play_counts = [play_count for name, play_count in sorted_artists[5:]]
        if remaining_artists_play_counts:
            others_play_count = max(remaining_artists_play_counts)
        else:
            others_play_count = 0  # No remaining artists

        # Add "Others" category if there are any remaining artists
        if others_play_count > 0:
            top_5_artists["Others"] = others_play_count

        return top_5_artists
    
    except Exception as e:
        print(f"Error fetching artists: {str(e)}")
        return {}

@app.route('/api/user_logs/<user_email>', methods=['GET'])
def get_user_logs(user_email):
    try:
        user = users_collection.find_one({'email': user_email})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_id = user['_id']  # This is the ObjectId

        user_logs = logs_collection.find({'user': user_id})
        track_details = {}
        artist_frequency = {} 
        current_date = datetime.utcnow().date()

        # Group the tracks by date
        for log in user_logs:
            listened_date = log['listenedAt'].date()
            track_id = log['track']
            track = tracks_collection.find_one({'_id': track_id}) 

            if track:
                track_info = serialize_object_id(track) 

                # Fetch the artist names from the artist IDs
                artist_ids = track_info.get('artists', [])

                artist_names = get_artist_names_by_ids(artist_ids)  # Get artist names by their IDs
                
                # Update the frequency count for each artist
                for artist_name in artist_names:
                    if artist_name in artist_frequency:
                        artist_frequency[artist_name] += 1
                    else:
                        artist_frequency[artist_name] = 1

                top_artists = get_top_artists(artist_frequency)
                artists_playcount = fetch_artists_and_playcount()

                day_diff = (current_date - listened_date).days

                # Categorize the date
                if day_diff == 0:
                    day_key = 'Today'
                elif day_diff == 1:
                    day_key = 'Yesterday'
                else:
                    day_key = listened_date.strftime('%Y-%m-%d')

                if day_key not in track_details:
                    track_details[day_key] = []

                track_details[day_key].append({
                    'trackName': track_info.get('trackName'),
                    'trackImage': track_info.get('trackImage'),
                    'trackFileUrl': track_info.get('trackFileUrl'),
                    'artists': artist_names, 
                    'listenedAt': log['listenedAt'],
                })

        for day_key in track_details:
            track_details[day_key].sort(key=lambda x: x['listenedAt'], reverse=True)

        # Sort the overall categories: 'Today' and 'Yesterday' should appear first, followed by specific dates
        sorted_dates = ['Today', 'Yesterday'] + [date for date in track_details if date not in ['Today', 'Yesterday']]

        sorted_track_details = {date: track_details[date] for date in sorted_dates}

        artist_pie_chart_base64 = generate_pie_chart(top_artists)
        artist_bar_chart_base64 = generate_bar_chart(artists_playcount)

        return jsonify({
            "logs": sorted_track_details,
            # "artistFrequency": top_artists, 
            "pieChart": artist_pie_chart_base64,
            # "topArtists": artists_playcount,
            "barChart": artist_bar_chart_base64
        })

    except Exception as e:
        return jsonify({"error": f"An error occurred while fetching user logs: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
