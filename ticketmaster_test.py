import requests
import json
import logging
from location_utils import get_coordinates, extract_city_and_state, get_full_address

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config():
    """Load configuration from config.json"""
    try:
        with open('config.json') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return None

def get_ticketmaster_events(api_key, lat, lon, city, state, category=None):
    """Fetch events from Ticketmaster Discovery API"""
    base_url = "https://app.ticketmaster.com/discovery/v2/events.json"
    
    params = {
        'apikey': api_key,
        'latlong': f"{lat},{lon}",
        'radius': '50',
        'unit': 'miles',
        'size': 20,
        'sort': 'date,asc'
    }
    
    if category:
        # Map categories to Ticketmaster classification IDs
        category_mapping = {
            'concerts': 'KZFzniwnSyZfZ7v7nJ',  # Music
            'sports': 'KZFzniwnSyZfZ7v7nE',   # Sports
            'performing-arts': 'KZFzniwnSyZfZ7v7na',  # Arts & Theatre
            'festivals': 'KZFzniwnSyZfZ7v7nJ',  # Music (festivals often fall under music)
            'community': 'KZFzniwnSyZfZ7v7n1',  # Miscellaneous
        }
        
        if category in category_mapping:
            params['classificationId'] = category_mapping[category]
    
    try:
        logger.info(f"Fetching {category or 'all'} events for {city}, {state}")
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        events = data.get('_embedded', {}).get('events', [])
        
        logger.info(f"Found {len(events)} events for {category or 'all'}")
        return events
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return []
    except Exception as e:
        logger.error(f"Error processing events: {e}")
        return []

def format_event_data(events):
    """Format event data for easier reading"""
    formatted_events = []
    
    for event in events:
        try:
            # Extract basic info
            event_info = {
                'name': event.get('name', 'Unknown Event'),
                'date': event.get('dates', {}).get('start', {}).get('localDate', 'TBD'),
                'time': event.get('dates', {}).get('start', {}).get('localTime', 'TBD'),
                'url': event.get('url', ''),
                'info': event.get('info', ''),
                'pleaseNote': event.get('pleaseNote', ''),
                'priceRanges': event.get('priceRanges', [])
            }
            
            # Extract venue info
            venues = event.get('_embedded', {}).get('venues', [])
            if venues:
                venue = venues[0]
                event_info['venue'] = {
                    'name': venue.get('name', 'Unknown Venue'),
                    'address': venue.get('address', {}).get('line1', ''),
                    'city': venue.get('city', {}).get('name', ''),
                    'state': venue.get('state', {}).get('stateCode', ''),
                    'postalCode': venue.get('postalCode', '')
                }
            
            # Extract classification (category)
            classifications = event.get('classifications', [])
            if classifications:
                classification = classifications[0]
                event_info['category'] = {
                    'segment': classification.get('segment', {}).get('name', ''),
                    'genre': classification.get('genre', {}).get('name', ''),
                    'subGenre': classification.get('subGenre', {}).get('name', '')
                }
            
            formatted_events.append(event_info)
            
        except Exception as e:
            logger.warning(f"Error formatting event: {e}")
            continue
    
    return formatted_events

def main():
    """Main function to test Ticketmaster API"""
    # Load configuration
    config = load_config()
    if not config:
        logger.error("Cannot proceed without configuration")
        return
    
    # Get Ticketmaster API key
    api_key = config.get('api', {}).get('ticketmaster', {}).get('api_key')
    if not api_key:
        logger.error("Ticketmaster API key not found in config")
        return
    
    # Get location data
    logger.info("Getting location data...")
    lat, lon = get_coordinates()
    full_address = get_full_address(lat, lon)
    city, state = extract_city_and_state(full_address)
    
    logger.info(f"Location: {city}, {state} ({lat}, {lon})")
    
    # Categories to test
    categories = ['concerts', 'sports', 'performing-arts', 'festivals', 'community']
    
    # Collect all events by category
    all_events_by_category = {}
    
    for category in categories:
        events = get_ticketmaster_events(api_key, lat, lon, city, state, category)
        formatted_events = format_event_data(events)
        all_events_by_category[category] = formatted_events
    
    # Also get general events (no category filter)
    general_events = get_ticketmaster_events(api_key, lat, lon, city, state)
    formatted_general = format_event_data(general_events)
    all_events_by_category['all_events'] = formatted_general
    
    # Create final JSON structure
    result = {
        'location': {
            'city': city,
            'state': state,
            'coordinates': [lat, lon],
            'full_address': full_address
        },
        'fetch_timestamp': json.dumps(None, default=str),  # Will be current time when saved
        'total_categories': len(categories),
        'events_by_category': all_events_by_category
    }
    
    # Save to JSON file
    output_file = 'ticketmaster_events_test.json'
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Events saved to {output_file}")
        
        # Print summary
        print(f"\n=== TICKETMASTER API TEST RESULTS ===")
        print(f"Location: {city}, {state}")
        print(f"Coordinates: {lat}, {lon}")
        print(f"\nEvents found by category:")
        
        total_events = 0
        for category, events in all_events_by_category.items():
            count = len(events)
            total_events += count
            print(f"  {category}: {count} events")
        
        print(f"\nTotal events: {total_events}")
        print(f"Data saved to: {output_file}")
        
    except Exception as e:
        logger.error(f"Failed to save events: {e}")

if __name__ == "__main__":
    main()