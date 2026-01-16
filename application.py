from flask import Flask, render_template, request, jsonify
import requests
import logging

# Set up logging to help us see errors in the AWS Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

application = Flask(__name__)

# --- 1. THE BRAIN (Keyword Mapping) ---
CUISINE_MAP = {
    "pizza": "pizza", "burger": "burger", "sushi": "japanese",
    "chinese": "chinese", "indian": "indian", "mexican": "mexican",
    "spicy": "indian;mexican;thai", "romantic": "italian;french",
    "cheap": "fast_food", "coffee": "coffee_shop", "dessert": "ice_cream;bakery",
    "healthy": "vegetarian;vegan", "steak": "steakhouse", "seafood": "seafood",
    "pasta": "italian", "noodle": "asian", "taco": "mexican"
}

FALLBACK_LOC = {"lat": 40.7128, "lon": -74.0060, "name": "New York"}

def extract_intent(text):
    text = text.lower()
    for keyword, tag in CUISINE_MAP.items():
        if keyword in text:
            return tag
    return "restaurant"

def find_restaurants(lat, lon, cuisine_type):
    try:
        overpass_url = "http://overpass-api.de/api/interpreter"
        query = f"""
        [out:json];
        (
          node["amenity"~"restaurant|fast_food|cafe"]["cuisine"~"{cuisine_type}"](around:3000,{lat},{lon});
          node["amenity"~"restaurant|fast_food|cafe"](around:3000,{lat},{lon});
        );
        out 5;
        """
        # Increased timeout to 15 seconds for slow API responses
        response = requests.get(overpass_url, params={'data': query}, timeout=15)
        response.raise_for_status()
        return response.json().get('elements', [])
    except Exception as e:
        logger.error(f"Map Search Error: {e}")
        return []

def geocode_city(text):
    try:
        words = text.split()
        for word in words:
            if len(word) > 3:
                url = f"https://nominatim.openstreetmap.org/search?q={word}&format=json&limit=1"
                headers = {'User-Agent': 'NeuralBites/1.0 (AWS Deployment)'}
                res = requests.get(url, headers=headers, timeout=10).json()
                if res:
                    return {
                        "lat": float(res[0]['lat']), 
                        "lon": float(res[0]['lon']), 
                        "name": res[0]['display_name']
                    }
    except Exception as e:
        logger.error(f"Geocoding Error: {e}")
    return None

@application.route('/')
def home():
    return render_template('chat.html')

@application.route('/api/ask', methods=['POST'])
def ask_ai():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({"reply": "System Error: No message received."}), 400
            
        user_input = data.get('message', '')
        
        # 1. Detect Location
        location = geocode_city(user_input)
        if not location:
            location = FALLBACK_LOC 
            
        # 2. Detect Cuisine
        cuisine_tag = extract_intent(user_input)
        
        # 3. Find Places
        places = find_restaurants(location['lat'], location['lon'], cuisine_tag)
        
        # 4. Format Data
        response_places = []
        for p in places:
            name = p.get("tags", {}).get("name", "Unknown Spot")
            img_key = p.get("tags", {}).get("cuisine", "food")
            response_places.append({
                "name": name,
                "lat": p["lat"],
                "lon": p["lon"],
                "type": img_key
            })
        
        return jsonify({
            "reply": f"Target locked: {cuisine_tag.upper()} sector in {location['name'].split(',')[0]}.",
            "location": location,
            "places": response_places
        })
    except Exception as e:
        logger.error(f"General App Error: {e}")
        return jsonify({"reply": "Neural pathways blocked. Please try again."}), 500

if __name__ == '__main__':
    # AWS EB usually listens on port 5000 or 8080
    application.run(host='0.0.0.0', port=5000)