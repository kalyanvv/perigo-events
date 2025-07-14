import geocoder
from geopy.geocoders import Nominatim
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_coordinates():
    try:
        with open('config.json') as f:
            config = json.load(f)
        
        if config['location'].get('force_default', False):
            logger.info("📍 Using default coordinates from config")
            return config['location']['default_coords']
        
        logger.info("📍 Detecting location via IP address")
        g = geocoder.ip('me')
        if g.latlng:
            return g.latlng
        
        logger.warning("📍 IP detection failed, using default coordinates")
        return config['location']['default_coords']
    except Exception as e:
        logger.error(f"📍 Location detection failed: {e}")
        return [34.0522, -118.2437]

def get_full_address(lat, lon):
    try:
        with open('config.json') as f:
            config = json.load(f)
            
        if config['location'].get('force_default', False):
            return f"{config['location']['default_city']}, {config['location']['default_state']}"
        
        logger.info("📍 Reverse geocoding detected coordinates")
        geolocator = Nominatim(user_agent="community_events_locator")
        location = geolocator.reverse((lat, lon), timeout=10, language='en')
        if location and location.address:
            return location.address
        
        logger.warning("📍 Reverse geocoding failed, using coordinates")
        return f"{lat}, {lon}"
    except Exception as e:
        logger.error(f"📍 Address lookup failed: {e}")
        return "Unknown Location"

def extract_city_and_state(full_address):
    try:
        with open('config.json') as f:
            config = json.load(f)
        
        if config['location'].get('force_default', False):
            return config['location']['default_city'], config['location']['default_state']
        
        logger.info(f"📍 Parsing city/state from address: {full_address}")
        parts = [p.strip() for p in full_address.split(",")]
        city = "Unknown City"
        state = "Unknown State"
        
        # Handle format: "Road, City, County, State, ZIP, Country"
        if len(parts) >= 4:
            # Try to find state (Georgia, Texas, etc.)
            for i, part in enumerate(parts):
                if part.lower() in ['georgia', 'texas', 'california', 'florida', 'north carolina', 'south carolina', 'new york', 'illinois']:
                    state_map = {
                        'georgia': 'GA', 'texas': 'TX', 'california': 'CA', 
                        'florida': 'FL', 'north carolina': 'NC', 'south carolina': 'SC',
                        'new york': 'NY', 'illinois': 'IL'
                    }
                    state = state_map[part.lower()]
                    # City is typically 2 positions before state
                    if i >= 2:
                        city = parts[i-2]
                    break
        
        # Fallback to original logic
        if city == "Unknown City" and len(parts) >= 3:
            city = parts[-3]
            state_part = parts[-2]
            if len(state_part) > 2:
                state_parts = state_part.split()
                if state_parts:
                    state = state_parts[0][:2].upper()
            else:
                state = state_part
        
        logger.info(f"📍 Parsed location: {city}, {state}")
        return city, state
        
    except Exception as e:
        logger.error(f"📍 Address parsing failed: {e}")
        return "Unknown City", "Unknown State"