from flask import Flask, render_template, request, jsonify
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

application = Flask(__name__)

CUISINE_MAP = {
    "pizza": "pizza", "burger": "burger", "sushi": "japanese",
    "ramen": "asian;japanese", "chinese": "chinese", "indian": "indian", 
    "mexican": "mexican", "spicy": "indian;mexican;thai", "coffee": "coffee_shop"
}

# Words to ignore when searching for a city name
IGNORE_WORDS = {"want", "need", "find", "food", "crave", "give", "some", "this"}

def extract_intent(text):
    text = text.lower()
    for keyword, tag in CUISINE_MAP.items():
        if keyword in text:
            return tag
    return "restaurant"

def geocode_city(text):
    try:
        words = text.replace("?", "").split()
        for word in words:
            # Only search if the word is long and NOT in our ignore list
            if len(word) > 3 and word.lower() not in IGNORE_WORDS:
                url = f"https://nominatim.openstreetmap.org/search?q={word}&format=json&limit=1"
                headers = {'User-Agent': 'NeuralBites/1.0'}
                res = requests.get(url, headers=headers, timeout=10).json()
                if res:
                    return {"lat": float(res[0]['lat']), "lon": float(res[0]['lon']), "name": res[0]['display_name']}
    except Exception as e:
        logger.error(f"Geocoding Error: {e}")
    return None

def find_restaurants(lat, lon, cuisine_type):
    try:
        overpass_url = "http://overpass-api.de/api/interpreter"
        query = f"""
        [out:json];
        (node["amenity"~"restaurant|fast_food"](around:5000,{lat},{lon}););
        out 10;
        """
        response = requests.get(overpass_url, params={'data': query}, timeout=15)
        return response.json().get('elements', [])
    except Exception as e:
        return []

@application.route('/')
def home():
    return render_template('chat.html')

@application.route('/api/ask', methods=['POST'])
def ask_ai():
    data = request.get_json()
    user_input = data.get('message', '')
    location = geocode_city(user_input) or {"lat": 21.1702, "lon": 72.8311, "name": "Surat"}
    cuisine_tag = extract_intent(user_input)
    places = find_restaurants(location['lat'], location['lon'], cuisine_tag)
    
    response_places = []
    for p in places:
        name = p.get("tags", {}).get("name", "Unknown Spot")
        # Create Google Maps Link
        gmaps_link = f"https://www.google.com/maps/search/?api=1&query={p['lat']},{p['lon']}"
        response_places.append({
            "name": name,
            "lat": p["lat"],
            "lon": p["lon"],
            "link": gmaps_link
        })
    
    return jsonify({
        "reply": f"Found {len(response_places)} spots in {location['name'].split(',')[0]}.",
        "location": location,
        "places": response_places
    })

if __name__ == '__main__':
    application.run(host='0.0.0.0', port=5000)