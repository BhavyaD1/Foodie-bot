from flask import Flask, render_template, request, jsonify, session
import requests
import logging
import secrets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

application = Flask(__name__)
# Secret key is required to use sessions
application.secret_key = secrets.token_hex(16)

# Expanded keyword mapping for flavor profiles and categories
CUISINE_MAP = {
    "pizza": "pizza", 
    "burger": "burger", 
    "sushi": "japanese",
    "ramen": "asian;japanese", 
    "chinese": "chinese", 
    "indian": "indian", 
    "mexican": "mexican", 
    "spicy": "indian;mexican;thai;chinese", 
    "sweet": "ice_cream;bakery;dessert;cake",
    "dessert": "ice_cream;bakery;dessert",
    "coffee": "coffee_shop;cafe",
    "tea": "cafe",
    "healthy": "vegetarian;vegan;salad",
    "italian": "italian;pasta",
    "fast food": "fast_food;burger"
}

IGNORE_WORDS = {"want", "need", "find", "food", "crave", "give", "some", "this", "please", "me", "a", "the", "in"}

def extract_intent(text):
    text = text.lower()
    found_tags = []
    for keyword, tag in CUISINE_MAP.items():
        if keyword in text:
            found_tags.append(tag)
    return ";".join(found_tags) if found_tags else "restaurant"

def geocode_city(text):
    try:
        words = text.replace("?", "").replace(",", "").split()
        for word in words:
            if len(word) > 3 and word.lower() not in IGNORE_WORDS:
                url = f"https://nominatim.openstreetmap.org/search?q={word}&format=json&limit=1"
                headers = {'User-Agent': 'NeuralBites/1.0'}
                res = requests.get(url, headers=headers, timeout=10).json()
                if res:
                    return {
                        "lat": float(res[0]['lat']), 
                        "lon": float(res[0]['lon']), 
                        "name": res[0]['display_name'].split(',')[0]
                    }
    except Exception as e:
        logger.error(f"Geocoding Error: {e}")
    return None

def find_restaurants(lat, lon, cuisine_type):
    try:
        overpass_url = "http://overpass-api.de/api/interpreter"
        # Uses a regex search for the cuisine tags found
        query = f"""
        [out:json];
        (node["amenity"~"restaurant|fast_food|cafe"]["cuisine"~"{cuisine_type}"](around:5000,{lat},{lon});
         node["amenity"~"restaurant|fast_food|cafe"](around:3000,{lat},{lon}););
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
    
    # 1. Check for a NEW city in the message
    new_location = geocode_city(user_input)
    
    if new_location:
        # Update memory
        session['last_city'] = new_location
        location = new_location
        context_msg = f"Updating coordinates to {location['name']}."
    elif 'last_city' in session:
        # Use memory
        location = session['last_city']
        context_msg = f"Still searching in {location['name']}."
    else:
        # Fallback if no city mentioned yet
        location = {"lat": 21.1702, "lon": 72.8311, "name": "Surat"}
        context_msg = "City not detected. Defaulting to Surat sector."

    cuisine_tag = extract_intent(user_input)
    places = find_restaurants(location['lat'], location['lon'], cuisine_tag)
    
    response_places = []
    for p in places:
        name = p.get("tags", {}).get("name", "Unknown Spot")
        gmaps_link = f"https://www.google.com/maps/search/?api=1&query={p['lat']},{p['lon']}"
        response_places.append({
            "name": name,
            "lat": p["lat"],
            "lon": p["lon"],
            "link": gmaps_link
        })
    
    return jsonify({
        "reply": f"{context_msg} Found {len(response_places)} spots for your request.",
        "location": location,
        "places": response_places
    })

if __name__ == '__main__':
    application.run(host='0.0.0.0', port=5000)