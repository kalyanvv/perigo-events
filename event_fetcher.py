
import requests
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALL_CATEGORIES = [
    "community", "concerts", "conferences", "expos", "festivals",
    "performing-arts", "sports", "academic", "school-holidays",
    "severe-weather", "disasters", "airport-delays"
]

ALERT_CATEGORIES = ["severe-weather", "disasters", "airport-delays"]

def get_categories_list():
    try:
        with open('config.json') as f:
            config = json.load(f)
        
        if config['api']['predicthq'].get('use_all_categories', False):
            return ALL_CATEGORIES
        
        categories = config['api']['predicthq'].get('categories')
        if categories:
            return [cat.strip() for cat in categories.split(",")]
        
        return ["community"]
    except Exception as e:
        logger.error(f"Category config error: {e}, using default")
        return ["community"]

def get_fallback_events(category):
    try:
        fallback_dir = f"fallback_events/{category}"
        os.makedirs(fallback_dir, exist_ok=True)
        fallback_file = f"{fallback_dir}/fallback.json"
        
        if not os.path.exists(fallback_file):
            default_events = [{
                "title": f"Local {category.title()} Event",
                "description": "Community gathering",
                "start_local": (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S"),
                "time_str": "Tomorrow",
                "geo": {"address": {"formatted_address": "City Center"}},
                "category": category
            }]
            with open(fallback_file, 'w') as f:
                json.dump(default_events, f)
            logger.warning(f"⚠️ Created fallback events at {fallback_file}")
        
        logger.info(f"⚠️ Using fallback events from {fallback_file}")
        with open(fallback_file, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Fallback events load failed: {e}")
        return []

def get_date_range():
    try:
        with open('config.json') as f:
            config = json.load(f)
        
        time_config = config.get('time_frame', {})
        
        if not time_config.get('enabled', False):
            start_date = datetime.utcnow().strftime("%Y-%m-%d")
            end_date = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")
            logger.info("⏰ Using default date range (next 30 days)")
            return start_date, end_date
        
        if time_config.get('force_custom', False):
            start_date = time_config['start_date']
            end_date = time_config['end_date']
            logger.info(f"⏰ Using FORCED custom dates: {start_date} to {end_date}")
            return start_date, end_date
        
        try:
            start_date = time_config['start_date']
            end_date = time_config['end_date']
            
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
            
            logger.info(f"⏰ Using custom dates: {start_date} to {end_date}")
            return start_date, end_date
        except (KeyError, ValueError):
            if time_config.get('fallback_to_default', True):
                start_date = datetime.utcnow().strftime("%Y-%m-%d")
                end_date = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")
                logger.warning("⚠️ Invalid custom dates, using default 30-day window")
                return start_date, end_date
            else:
                raise ValueError("Invalid custom date format in config")
    
    except Exception as e:
        logger.error(f"⏰ Date range error: {e}, using default")
        start_date = datetime.utcnow().strftime("%Y-%m-%d")
        end_date = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")
        return start_date, end_date

def calculate_event_score(event):
    try:
        with open('config.json') as f:
            config = json.load(f)
        weights = config['event_selection']['weights']
        category_boosts = config['event_selection']['category_boosts']
    except:
        weights = {'rank': 0.6, 'attendance': 0.3, 'urgency': 0.4}
        category_boosts = {'concerts': 1.3, 'festivals': 1.2, 'sports': 1.1}
    
    score = 0
    
    # Handle rank
    rank = event.get('rank')
    if rank is not None:
        score += rank * weights['rank']
    
    # Handle attendance
    attendance = event.get('phq_attendance')
    if attendance is not None:
        score += min(attendance * 0.0001, 30) * weights['attendance']
    
    # Handle start time
    if 'start' in event and event['start'] is not None:
        try:
            start_time = datetime.fromisoformat(event['start'].replace('Z', '+00:00'))
            hours_until = (start_time - datetime.utcnow()).total_seconds() / 3600
            
            if hours_until < 24:
                score += 40 * weights['urgency']
            elif hours_until < 72:
                score += 20 * weights['urgency']
        except Exception:
            pass
    
    # Apply category boost
    category = event.get('category', '')
    boost = category_boosts.get(category, 1.0)
    score *= boost
    
    return score

def fetch_events_by_category(category, lat, lon):
    try:
        with open('config.json') as f:
            config = json.load(f)
        
        token = config['api']['predicthq']['token']
        radius = config['location']['default_radius']
        start_date, end_date = get_date_range()
        
        params = {
            "within": f"{radius}@{lat},{lon}",
            "category": category,
            "active.gte": start_date,
            "active.lte": end_date,
            "limit": 50,
            "sort": "-" + config['story']['event_sort'],
            "expand": "phq_attendance,place,labels,entities"
        }

        resp = requests.get(
            config['api']['predicthq']['base_url'],
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=15
        )
        resp.raise_for_status()
        
        events = resp.json().get("results", [])
        logger.info(f"Fetched {len(events)} events for category: {category}")
        
        for event in events:
            event["category"] = category
            if event.get("start_local"):
                try:
                    dt = datetime.fromisoformat(event["start_local"].replace("Z", "+00:00"))
                    event["time_str"] = dt.strftime("%A, %B %d at %I:%M %p")
                except ValueError:
                    event["time_str"] = event["start_local"]
        
        return events
    except Exception as e:
        logger.error(f"API request for {category} failed: {e}")
        return []

def fetch_all_events(city, state, lat, lon):
    categories = get_categories_list()
    events_by_category = {}
    alerts = []
    
    # Create directories
    os.makedirs("events_data", exist_ok=True)
    os.makedirs("events_data/alerts", exist_ok=True)
    
    for category in categories:
        if category in ALERT_CATEGORIES:
            # Handle alerts separately
            alert_events = fetch_events_by_category(category, lat, lon)
            if alert_events:
                alerts.extend(alert_events)
        else:
            events = fetch_events_by_category(category, lat, lon)
            if not events:
                events = get_fallback_events(category)
            
            # Save raw events
            category_dir = f"events_data/{category}"
            os.makedirs(category_dir, exist_ok=True)
            with open(f"{category_dir}/raw_events.json", "w", encoding="utf-8") as f:
                json.dump(events, f, indent=4, ensure_ascii=False)
            
            # Score all events first
            scored_events = []
            for event in events:
                try:
                    event["score"] = calculate_event_score(event)
                    scored_events.append(event)
                except Exception as e:
                    logger.error(f"Scoring failed for event: {event.get('title')} - {e}")
                    # Assign default score for problematic events
                    event["score"] = 50
                    scored_events.append(event)
            
            # Sort and select top 2
            scored_events.sort(key=lambda x: x.get("score", 0), reverse=True)
            top_events = scored_events[:2]
            events_by_category[category] = top_events
            
            with open(f"{category_dir}/selected_events.json", "w", encoding="utf-8") as f:
                json.dump(top_events, f, indent=4, ensure_ascii=False)
    
    if alerts:
        with open("events_data/alerts/alerts.json", "w", encoding="utf-8") as f:
            json.dump(alerts, f, indent=4, ensure_ascii=False)
    
    return events_by_category, alerts