from flask import Flask, render_template, request, jsonify
import requests

application = Flask(__name__)

# --- 1. THE BRAIN (Keyword Mapping) ---
# Maps user words to OpenStreetMap cuisine tags
CUISINE_MAP = {
    "pizza": "pizza", "burger": "burger", "sushi": "japanese",
    "chinese": "chinese", "indian": "indian", "mexican": "mexican",
    "spicy": "indian;mexican;thai", "romantic": "italian;french",
    "cheap": "fast_food", "coffee": "coffee_shop", "dessert": "ice_cream;bakery",
    "healthy": "vegetarian;vegan", "steak": "steakhouse", "seafood": "seafood",
    "pasta": "italian", "noodle": "asian", "taco": "mexican"
}

# Default location (New York) if geolocation fails
FALLBACK_LOC = {"lat": 40.7128, "lon": -74.0060, "name": "New York"}

def extract_intent(text):
    text = text.lower()
    detected_cuisines = []
    for keyword, tag in CUISINE_MAP.items():
        if keyword in text:
            detected_cuisines.append(tag)
    # Default to generic "restaurant" if no specific food is mentioned
    return detected_cuisines[0] if detected_cuisines else "restaurant"

def find_restaurants(lat, lon, cuisine_type):
    """ Queries OpenStreetMap (Overpass API) for places nearby """
    try:
        overpass_url = "http://overpass-api.de/api/interpreter"
        # Search radius: 3000 meters (3km)
        query = f"""
        [out:json];
        (
          node["amenity"~"restaurant|fast_food|cafe"]["cuisine"~"{cuisine_type}"](around:3000,{lat},{lon});
          node["amenity"~"restaurant|fast_food|cafe"](around:3000,{lat},{lon});
        );
        out 5;
        """
        response = requests.get(overpass_url, params={'data': query}, timeout=10)
        return response.json().get('elements', [])
    except Exception as e:
        print(f"OSM Error: {e}")
        return []

def geocode_city(text):
    """ Tries to find a city name in the text using Nominatim """
    try:
        words = text.split()
        for word in words:
            if len(word) > 3: # Ignore short words like "in", "at"
                url = f"https://nominatim.openstreetmap.org/search?q={word}&format=json&limit=1"
                headers = {'User-Agent': 'NeuralBites/1.0'}
                res = requests.get(url, headers=headers).json()
                if res:
                    return {
                        "lat": float(res[0]['lat']), 
                        "lon": float(res[0]['lon']), 
                        "name": res[0]['display_name']
                    }
    except Exception as e:
        print(f"Geocoding Error: {e}")
        
    return None

@application.route('/')
def home():
    return render_template('chat.html')

@application.route('/api/ask', methods=['POST'])
def ask_ai():
    data = request.get_json()
    user_input = data.get('message', '')
    
    # 1. Detect Location
    location = geocode_city(user_input)