import os
import secrets
import logging
import requests
import boto3
from flask import Flask, render_template, request, jsonify, session

# 1. Setup Logging - Crucial for debugging 502 errors
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Initialize Flask - MUST be named 'application' for Elastic Beanstalk
application = Flask(__name__)
application.secret_key = secrets.token_hex(16)  # Required for session storage

# 3. AWS Lex Configuration
# Make sure region_name matches where your Lex bot is hosted
LEX_CLIENT = boto3.client('lexv2-runtime', region_name='us-east-1')
BOT_ID = 'YOUR_BOT_ID'           # Paste your Bot ID here
BOT_ALIAS_ID = 'YOUR_ALIAS_ID'   # Paste your Bot Alias ID here

def find_restaurants(lat, lon, cuisine_type):
    """Fetch restaurant data from Overpass API (OpenStreetMap)"""
    try:
        overpass_url = "http://overpass-api.de/query"
        query = f"""
        [out:json];
        (
          node["amenity"~"restaurant|fast_food|cafe"]["cuisine"~"{cuisine_type}"](around:5000,{lat},{lon});
          node["amenity"~"restaurant|fast_food|cafe"](around:3000,{lat},{lon});
        );
        out 10;
        """
        response = requests.get(overpass_url, params={'data': query}, timeout=15)
        return response.json().get('elements', [])
    except Exception as e:
        logger.error(f"Map API Error: {e}")
        return []

def geocode_city_name(city_name):
    """Convert city name to Latitude/Longitude using Nominatim"""
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={city_name}&format=json&limit=1"
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

@application.route('/')
def home():
    return render_template('chat.html')

@application.route('/api/ask', methods=['POST'])
def ask_ai():
    data = request.get_json()
    user_input = data.get('message', '')
    
    # Session management for Lex and City memory
    if 'user_sid' not in session:
        session['user_sid'] = secrets.token_hex(8)
    
    session_id = session['user_sid']

    try:
        # Send message to Amazon Lex V2
        lex_response = LEX_CLIENT.recognize_text(
            botId=IQ8SBPJUJC,
            botAliasId=IQ8SBPJUJC,
            localeId='en_US',
            sessionId=session_id,
            text=user_input
        )

        # Process Lex Interpretation
        interpretations = lex_response.get('interpretations', [])
        if not interpretations:
            return jsonify({"reply": "Neural pathways unstable. Try again."})

        top_intent = interpretations[0].get('intent', {})
        slots = top_intent.get('slots', {})

        # Extract Slot Values
        cuisine = slots.get('Cuisine', {}).get('value', {}).get('interpretedValue', 'restaurant')
        city_name = slots.get('City', {}).get('value', {}).get('interpretedValue', None)

        # Persistence: If a new city is mentioned, update session
        if city_name:
            location = geocode_city_name(city_name)
            if location:
                session['last_city'] = location
        
        # Default to Surat if no city has ever been mentioned
        current_loc = session.get('last_city', {"lat": 21.1702, "lon": 72.8311, "name": "Surat"})

        # Get restaurant results
        places_data = find_restaurants(current_loc['lat'], current_loc['lon'], cuisine)
        
        response_places = []
        for p in places_data:
            name = p.get("tags", {}).get("name", "Unknown Spot")
            response_places.append({
                "name": name,
                "lat": p["lat"],
                "lon": p["lon"],
                "link": f"https://www.google.com/maps?q={p['lat']},{p['lon']}"
            })

        return jsonify({
            "reply": f"Scanning {cuisine.upper()} sectors in {current_loc['name']}...",
            "location": current_loc,
            "places": response_places
        })

    except Exception as e:
        logger.error(f"App Error: {e}")
        return jsonify({"reply": "Neural Link Error: Check your Bot ID and Permissions."}), 500

# Required for Elastic Beanstalk
if __name__ == '__main__':
    application.run(host='0.0.0.0', port=5000)