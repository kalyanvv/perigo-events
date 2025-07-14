import logging
from pathlib import Path
from location_utils import get_coordinates, get_full_address, extract_city_and_state
from event_fetcher import fetch_all_events
from story_generator import generate_story, PROMPT_GENERATORS, generate_combined_alerts_prompt, generate_fallback_story
# from story_validator import validate_and_clean_story
from ticket_finder import TicketFinder
from tomorrow_alerts import get_weather_alerts
import requests
import json
import os
from datetime import datetime
import textwrap

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def clean_text_for_audio(text):
    import re
    
    # Remove quotes at start/end
    text = text.strip('"\'')
    
    # Remove markdown formatting
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # **bold**
    text = re.sub(r'\*(.*?)\*', r'\1', text)      # *italic*
    
    # Remove any remaining asterisks or special formatting
    text = re.sub(r'[*_`#]', '', text)
    
    # Remove promotional phrases
    promotional_phrases = [
        r'don\'t miss', r'check out', r'see you there', r'join us',
        r'come and', r'be sure to', r'make sure to', r'check our calendar',
        r'for more information', r'visit our website', r'call us',
        r'sourced from.*', r'predicthq\.com', r'amazing', r'great',
        r'wonderful', r'exciting', r'fantastic', r'incredible'
    ]
    
    for phrase in promotional_phrases:
        text = re.sub(phrase, '', text, flags=re.IGNORECASE)
    
    # Remove guidelines, instructions, or meta text
    text = re.sub(r'Guidelines:.*', '', text, flags=re.DOTALL)
    text = re.sub(r'Instructions:.*', '', text, flags=re.DOTALL)
    text = re.sub(r'Note:.*', '', text, flags=re.DOTALL)
    text = re.sub(r'Rules:.*', '', text, flags=re.DOTALL)
    
    # Clean up extra whitespace and punctuation
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*[.,;]\s*[.,;]+', '.', text)  # Fix multiple punctuation
    
    return text

def generate_audio(text, output_path):
    try:
        # Clean text before audio generation
        clean_text = clean_text_for_audio(text)
        
        # Ensure directory exists
        output_dir = os.path.dirname(output_path)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # API call to convert text to audio
        api_url = "https://www.perigo.app/api/tts_interns"
        payload = {
            "text": clean_text,
            "language_code": "en-US",
            "user_id": "3f6ce79c-10da-469c-9a0f-c02a47ca341f"
        }
        
        response = requests.post(api_url, json=payload, timeout=30)
        response.raise_for_status()
        
        # Parse JSON response to get audio URL
        response_data = response.json()
        if response_data.get('success') and 'audio_url' in response_data:
            audio_url = response_data['audio_url']
            
            # Download the actual audio file
            audio_response = requests.get(audio_url, timeout=30)
            audio_response.raise_for_status()
            
            # Save the audio file
            with open(output_path, 'wb') as f:
                f.write(audio_response.content)
            
            return output_path
        else:
            logger.error(f"API response missing audio_url: {response_data}")
            return None
            
    except Exception as e:
        logger.error(f"Audio generation failed: {e}")
        return None

def format_story_output(story, category, event_title):
    width = 70
    border = "=" * width
    header = f"📢 {category.upper()} ANNOUNCEMENT: {event_title}".center(width)
    
    wrapped_lines = []
    for paragraph in story.split('\n\n'):
        wrapped = textwrap.wrap(paragraph, width=width-4)
        wrapped_lines.extend(wrapped)
        wrapped_lines.append("")
    
    formatted = [border, header, border, ""]
    for line in wrapped_lines:
        if line:
            formatted.append(f"  {line}")
        else:
            formatted.append("")
    formatted.append(border)
    
    return "\n".join(formatted)

def save_story_to_file(story, output_path):
    try:
        # Ensure directory exists
        output_dir = os.path.dirname(output_path)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(story)
        logger.info(f"📝 Story saved to {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Failed to save story: {e}")
        return None

def validate_time_config():
    try:
        with open('config.json') as f:
            config = json.load(f)
        
        time_config = config.get('time_frame', {})
        if not time_config.get('enabled', False):
            return True
            
        start_date = time_config.get('start_date')
        end_date = time_config.get('end_date')
        
        if not start_date or not end_date:
            logger.error("❌ Time frame enabled but missing start/end dates")
            return False
            
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            
            if start > end:
                logger.error("❌ Start date cannot be after end date")
                return False
                
            return True
        except ValueError:
            logger.error("❌ Invalid date format. Use YYYY-MM-DD")
            return False
            
    except Exception as e:
        logger.error(f"❌ Time config validation failed: {e}")
        return False

def main():
    try:
        logger.info("🚀 Starting Community Events Announcement System")
        
        if not validate_time_config():
            logger.warning("⚠️ Proceeding with default time range")
        
        lat, lon = get_coordinates()
        address = get_full_address(lat, lon)
        city, state = extract_city_and_state(address)
        logger.info(f"📍 Location: {city}, {state}")
        
        logger.info("🔍 Fetching local events by category...")
        events_by_category, alerts = fetch_all_events(city, state, lat, lon)
        
        # Add weather alerts from Tomorrow.io
        weather_alerts = get_weather_alerts()
        if weather_alerts:
            alerts.extend(weather_alerts)
            logger.info(f"🌦️ Added {len(weather_alerts)} weather alerts from Tomorrow.io")
        
        # Save ALL fetched events (not just top 2) to a single JSON file
        all_events = []
        
        # Read raw events from saved files
        categories = ['community', 'concerts', 'sports', 'festivals', 'academic', 'performing-arts', 'conferences', 'expos', 'school-holidays']
        for category in categories:
            try:
                raw_file = f"events_data/{category}/raw_events.json"
                if os.path.exists(raw_file):
                    with open(raw_file, 'r', encoding='utf-8') as f:
                        raw_events = json.load(f)
                        all_events.extend(raw_events)
            except Exception as e:
                logger.warning(f"Could not read raw events for {category}: {e}")
        
        # Save to JSON file
        with open('all_events.json', 'w', encoding='utf-8') as f:
            json.dump(all_events, f, indent=2, ensure_ascii=False)
        logger.info(f"📄 Saved {len(all_events)} events to all_events.json")
        
        # Initialize ticket finder for selected events only
        ticket_finder = TicketFinder()
        ticketed_events = []
        
        # Create base directories
        base_dir = "output"
        Path(base_dir).mkdir(exist_ok=True)
        
        event_count = 0
        
        # Process only the top selected events for story generation
        for category, events in events_by_category.items():
            if not events:
                continue
            
            # Ensure we only process max 2 events per category
            events = events[:2]
            category_event_count = 0
            for event in events:
                event_count += 1
                category_event_count += 1
                event_title = event.get('title', f'Event #{event_count}')
                logger.info(f"✍️ Generating story for {category} event #{category_event_count}: {event_title}")
                
                # Get category-specific prompt generator
                prompt_generator = PROMPT_GENERATORS.get(category)
                if prompt_generator:
                    prompt = prompt_generator(event, city, state)
                else:
                    logger.warning(f"No prompt generator for {category}, using default")
                    # Create a fallback prompt generator
                    prompt = f"""Create a 15-second announcement for this event in {city}, {state}:
Event: {event.get('title', 'Community Event')}
When: {event.get('time_str', 'Soon')}
Where: {event.get('geo', {}).get('address', {}).get('formatted_address', 'local venue')}
Description: {event.get('description', 'Local gathering')[:100]}

Guidelines:
1. Keep under 15 seconds
2. Be engaging and friendly
3. Output ONLY the script"""
                
                # Check if event needs tickets
                ticket_result = ticket_finder.find_tickets(event)
                if ticket_result['needs_ticket']:
                    ticketed_events.append(ticket_result)
                    
                    # Save ticket info in event folder
                    ticket_file = os.path.join(event_dir, "ticket_info.json")
                    with open(ticket_file, 'w', encoding='utf-8') as f:
                        json.dump(ticket_result, f, indent=2, ensure_ascii=False)
                
                # Generate story
                raw_story = generate_story(prompt)
                if not raw_story:
                    logger.warning(f"Using fallback for event #{event_count}")
                    raw_story = generate_fallback_story(event, city, state)
                
                # Use the raw story directly with better prompting
                story = raw_story.strip('"\'')
                
                # Add ticket information if available (factual only)
                if ticket_result['needs_ticket'] and ticket_result.get('ticket_info'):
                    ticket_info = ticket_result['ticket_info']
                    if ticket_info.get('price_range') and ticket_info.get('price_range') != 'Price varies':
                        story += f" Tickets are {ticket_info.get('price_range')}."
                    elif ticket_result['needs_ticket']:
                        story += " Tickets are required."
                
                # Create output paths
                event_dir = os.path.join(base_dir, category, f"event_{category_event_count}")
                story_path = os.path.join(event_dir, "story.txt")
                audio_path = os.path.join(event_dir, "announcement.mp3")
                
                # Save story
                save_story_to_file(story, story_path)
                
                # Output formatted story
                print(f"\n{format_story_output(story, category, event_title)}")
                
                # Generate audio
                logger.info(f"🔊 Converting event #{event_count} to audio...")
                audio_file = generate_audio(story, audio_path)
                if audio_file:
                    logger.info(f"✅ Audio saved to: {audio_file}")
        
        # Process alerts as a single combined announcement
        if alerts:
            logger.info(f"⚠️ Generating combined alert announcement for {len(alerts)} alerts")
            
            # Generate combined alert story
            alert_prompt = generate_combined_alerts_prompt(alerts, city, state)
            alert_story = generate_story(alert_prompt)
            
            if not alert_story:
                alert_titles = [alert.get('title', 'Alert') for alert in alerts[:3]]
                alert_story = f"Weather alerts are in effect for {city}. {', '.join(alert_titles)}. Take necessary precautions."
            
            # Clean alert story
            alert_story = alert_story.strip('"\'')
            
            # Create output paths
            alert_dir = os.path.join(base_dir, "alerts")
            story_path = os.path.join(alert_dir, "combined_alerts.txt")
            audio_path = os.path.join(alert_dir, "combined_announcement.mp3")
            
            # Save alert story
            save_story_to_file(alert_story, story_path)
            
            # Output formatted alert story
            print(f"\n{format_story_output(alert_story, 'ALERTS', 'Combined Alert Announcement')}")
            
            # Generate audio
            logger.info(f"🔊 Converting combined alerts to audio...")
            audio_file = generate_audio(alert_story, audio_path)
            if audio_file:
                logger.info(f"✅ Combined alerts audio saved to: {audio_file}")
        
        # Save ticketed events from selected events only
        if ticketed_events:
            with open('ticketed_events.json', 'w', encoding='utf-8') as f:
                json.dump(ticketed_events, f, indent=2, ensure_ascii=False)
            logger.info(f"🎫 Found {len(ticketed_events)} ticketed events from selected events")
        
        logger.info(f"🏁 Process completed. Generated {event_count} event stories, {len(alerts)} alerts, and identified {len(ticketed_events)} ticketed events.")
    except Exception as e:
        logger.error(f"❌ Fatal application error: {e}")

if __name__ == "__main__":
    main()