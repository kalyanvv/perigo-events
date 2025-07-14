
import subprocess
import logging
import json
from threading import Timer
import time
from datetime import datetime
import random
import requests
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALL_CATEGORIES = [
    "community", "concerts", "conferences", "expos", "festivals",
    "performing-arts", "sports", "academic", "school-holidays"
]

ALERT_CATEGORIES = ["severe-weather", "disasters", "airport-delays"]

def get_season():
    month = datetime.now().month
    if 3 <= month <= 5: return "spring"
    elif 6 <= month <= 8: return "summer"
    elif 9 <= month <= 11: return "fall"
    else: return "winter"

def get_time_of_day():
    hour = datetime.now().hour
    if 5 <= hour < 12: return "morning"
    elif 12 <= hour < 17: return "afternoon"
    elif 17 <= hour < 21: return "evening"
    else: return "night"

def get_weather_context():
    conditions = ["sunny", "partly cloudy", "clear", "breezy"]
    temps = ["warm", "pleasant", "mild", "cool"]
    return {
        "condition": random.choice(conditions),
        "temperature": random.choice(temps)
    }

def get_event_emoji(category):
    emojis = {
        "concerts": "🎵", "festivals": "🎪", "community": "👨‍👩‍👧‍👦",
        "performing-arts": "🎭", "sports": "⚽", "conferences": "📊",
        "expos": "🏢", "academic": "🎓", "school-holidays": "🎒",
        "severe-weather": "⚠️", "disasters": "🚨", "airport-delays": "✈️"
    }
    return emojis.get(category, "🎉")

# Category-specific prompt generators (single event focus)
def generate_community_prompt(event, city, state):
    title = event.get('title', 'Community Event')
    time_str = event.get('time_str', 'Soon')
    location = event.get('geo', {}).get('address', {}).get('formatted_address', 'local venue')
    
    # Clean location to avoid incomplete addresses
    if location and ',' in location:
        location = location.split(',')[0].strip()
    
    prompt = f"""You are a professional news anchor reading a factual announcement. Write EXACTLY one complete sentence.

Event: {title}
When: {time_str}
Where: {location}

STRICT REQUIREMENTS:
- Write ONE complete sentence only
- Start with the event name
- Include when and where
- Use format: "[Event name] will take place [when] at [location]."
- NO promotional language
- NO incomplete sentences
- NO website mentions
- NO source references
- End with a period

Example: "Community Garden Workshop will take place Saturday at 2 PM at City Park."

Write the announcement:"""
    return prompt

def generate_concerts_prompt(event, city, state):
    title = event.get('title', 'Live Music Event')
    artist = event.get('entities', [{}])[0].get('name', 'Local artist') if event.get('entities') else 'Local artist'
    time_str = event.get('time_str', 'This week')
    venue = event.get('geo', {}).get('address', {}).get('formatted_address', 'local venue')
    
    if venue and ',' in venue:
        venue = venue.split(',')[0].strip()
    
    prompt = f"""You are a professional news anchor. Write EXACTLY one complete sentence about this concert.

Concert: {title}
Artist: {artist}
When: {time_str}
Where: {venue}

STRICT REQUIREMENTS:
- Write ONE complete sentence only
- Include artist, event, when, and where
- Use format: "[Artist] will perform [event] [when] at [venue]."
- NO promotional words
- NO incomplete sentences
- End with a period

Example: "The Jazz Quartet will perform live music Friday at 8 PM at Downtown Theater."

Write the announcement:"""
    return prompt

def generate_sports_prompt(event, city, state):
    title = event.get('title', 'Sports Event')
    time_str = event.get('time_str', 'Soon')
    venue = event.get('geo', {}).get('address', {}).get('formatted_address', 'local venue')
    
    prompt = f"""Create a factual sports announcement.

Event: {title}
Date/Time: {time_str}
Venue: {venue}

Rules:
- State facts only
- No promotional language (exciting, thrilling, epic, don't miss)
- Format: [Event] will take place [when] at [venue]
- Maximum 15 seconds when spoken
- Output only the announcement text
"""
    return prompt

def generate_festivals_prompt(event, city, state):
    title = event.get('title', 'Festival')
    time_str = event.get('time_str', 'Weekend')
    location = event.get('geo', {}).get('address', {}).get('formatted_address', 'local area')
    
    prompt = f"""Create a factual festival announcement.

Festival: {title}
Date/Time: {time_str}
Location: {location}

Rules:
- State facts only
- No promotional language (vibrant, amazing, fantastic, don't miss)
- Format: [Festival name] will take place [when] at [location]
- Maximum 15 seconds when spoken
- Output only the announcement text
"""
    return prompt

def generate_academic_prompt(event, city, state):
    title = event.get('title', 'Academic Event')
    time_str = event.get('time_str', 'Upcoming')
    location = event.get('geo', {}).get('address', {}).get('formatted_address', 'local venue')
    
    prompt = f"""Create a factual academic announcement.

Event: {title}
Date/Time: {time_str}
Location: {location}

Rules:
- State facts only
- No promotional language (inspiring, enlightening, valuable, don't miss)
- Format: [Event name] will take place [when] at [location]
- Maximum 15 seconds when spoken
- Output only the announcement text
"""
    return prompt

def generate_performing_arts_prompt(event, city, state):
    title = event.get('title', 'Performance')
    time_str = event.get('time_str', 'This week')
    venue = event.get('geo', {}).get('address', {}).get('formatted_address', 'local venue')
    
    prompt = f"""Create a factual performance announcement.

Performance: {title}
Date/Time: {time_str}
Venue: {venue}

Rules:
- State facts only
- No promotional language (elegant, beautiful, stunning, don't miss)
- Format: [Performance name] will take place [when] at [venue]
- Maximum 15 seconds when spoken
- Output only the announcement text
"""
    return prompt

def generate_conferences_prompt(event, city, state):
    prompt = f"""Create a neutral, factual 15-second conference announcement for {city}, {state}.

**Event Details:**
{get_event_emoji("conferences")} {event.get('title', 'Professional Event')}
- When: {event.get('time_str', 'Upcoming')}
- Where: {event.get('geo', {}).get('address', {}).get('formatted_address', 'convention center')}
- Industry: {event.get('phq_labels', [{}])[0].get('label', 'Professional field')}
- Speakers: {event.get('entities', [{}])[0].get('name', 'Industry leaders')}

**Guidelines:**
1. State facts only - no promotional language
2. No subjective words like "excellent", "valuable", "outstanding"
3. No calls to action
4. Format: Conference name, industry, date, time, location
5. Keep under 15 seconds
6. Output ONLY the script
"""
    return prompt

def generate_expos_prompt(event, city, state):
    prompt = f"""Create a neutral, factual 15-second expo announcement for {city}, {state}.

**Event Details:**
{get_event_emoji("expos")} {event.get('title', 'Exhibition')}
- When: {event.get('time_str', 'Weekend')}
- Where: {event.get('geo', {}).get('address', {}).get('formatted_address', 'expo center')}
- Features: {event.get('description', 'Innovative displays').split('.')[0]}
- Exhibitors: {event.get('phq_labels', [{}])[0].get('label', 'Industry leaders')}

**Guidelines:**
1. State facts only - no promotional language
2. No subjective words like "exciting", "innovative", "cutting-edge"
3. No calls to action
4. Format: Expo name, focus area, date, time, location
5. Keep under 15 seconds
6. Output ONLY the script
"""
    return prompt

def generate_school_holidays_prompt(event, city, state):
    season = get_season()
    prompt = f"""Create a neutral, factual 15-second announcement for {city}, {state}.

**Event Details:**
{get_event_emoji("school-holidays")} {event.get('title', 'Family Event')}
- When: {event.get('time_str', 'During break')}
- Where: {event.get('geo', {}).get('address', {}).get('formatted_address', 'community center')}
- Age Group: {event.get('phq_labels', [{}])[0].get('label', 'All ages')}
- Activities: {event.get('description', 'Fun for kids')[:100]}

**Guidelines:**
1. State facts only - no promotional language
2. No subjective words like "fun", "exciting", "wonderful"
3. No calls to action
4. Format: Event name, age group, date, time, location, activities
5. Keep under 15 seconds
6. Output ONLY the script
"""
    return prompt

def generate_alerts_prompt(event, city, state):
    prompt = f"""Create an urgent 15-second alert announcement for {city}, {state}.

**Alert Details:**
{get_event_emoji(event.get("category", "severe-weather"))} {event.get('title', 'Important Alert')}
- When: {event.get('time_str', 'Imminent')}
- Severity: {event.get('phq_labels', [{}])[0].get('label', 'High')}
- Action: {event.get('description', 'Take precautions').split('.')[0]}

**Guidelines:**
1. Focus on this single alert
2. Use urgent but calm tone
3. Provide clear safety instructions
4. Keep under 15 seconds
5. Output ONLY the script
"""
    return prompt

# Category to function mapping
PROMPT_GENERATORS = {
    "community": generate_community_prompt,
    "concerts": generate_concerts_prompt,
    "sports": generate_sports_prompt,
    "festivals": generate_festivals_prompt,
    "academic": generate_academic_prompt,
    "performing-arts": generate_performing_arts_prompt,
    "conferences": generate_conferences_prompt,
    "expos": generate_expos_prompt,
    "school-holidays": generate_school_holidays_prompt
}

def run_ollama(prompt):
    try:
        with open('config.json') as f:
            config = json.load(f)
        
        if not prompt:
            return ""
            
        logger.info("Generating story with Ollama...")
        start_time = time.time()
        
        process = subprocess.Popen(
            ["ollama", "run", config['ollama']['model']],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            bufsize=1
        )

        timer = Timer(config['ollama']['timeout'], process.terminate)
        timer.start()

        process.stdin.write(prompt)
        process.stdin.close()

        output_lines = []
        while True:
            line = process.stdout.readline()
            if not line:
                if process.poll() is not None:
                    break
                time.sleep(0.1)
                continue
            output_lines.append(line)
            
            elapsed = time.time() - start_time
            if elapsed > 15 and int(elapsed) % 15 == 0:
                logger.info(f"Generating... ({int(elapsed)}s elapsed)")

        timer.cancel()
        
        full_output = ''.join(output_lines)
        if full_output.startswith(">>>"):
            full_output = full_output.split('\n', 1)[-1]
        
        logger.info(f"Story generated in {time.time()-start_time:.1f}s")
        return full_output.strip()
    except Exception as e:
        logger.error(f"Story generation with Ollama failed: {e}")
        return ""

def run_deepseek(prompt):
    try:
        with open('config.json') as f:
            config = json.load(f)
        
        if not prompt:
            return ""
            
        logger.info("Generating story with DeepSeek...")
        start_time = time.time()
        
        api_key = config['api']['deepseek']['api_key']
        model = config['api']['deepseek']['model']
        url = f"{config['api']['deepseek']['base_url']}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a professional news anchor reading factual announcements. Write complete sentences only. Never use promotional language, incomplete phrases, or website references. Always end sentences with proper punctuation."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }
        
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=config['story_generation'].get('timeout', 30)
        )
        response.raise_for_status()
        
        story = response.json()['choices'][0]['message']['content']
        elapsed = time.time() - start_time
        logger.info(f"Story generated in {elapsed:.1f}s")
        return story.strip()
        
    except Exception as e:
        logger.error(f"DeepSeek API failed: {e}")
        return ""

def get_generation_provider():
    try:
        with open('config.json') as f:
            config = json.load(f)
        return config['story_generation'].get('provider', 'deepseek')
    except:
        return 'deepseek'

def post_process_story(story):
    """Clean and validate generated story"""
    import re
    
    if not story:
        return ""
    
    # Remove quotes and extra whitespace
    story = story.strip('"\'')
    
    # Remove promotional phrases that might slip through
    forbidden_phrases = [
        r'don\'t miss', r'check out', r'see you there', r'join us',
        r'come and enjoy', r'be sure to', r'make sure to', r'visit us',
        r'for more info', r'call us', r'check our', r'amazing', r'great',
        r'wonderful', r'exciting', r'fantastic', r'incredible', r'awesome',
        r'sourced from', r'predicthq', r'calendar', r'website'
    ]
    
    for phrase in forbidden_phrases:
        story = re.sub(phrase, '', story, flags=re.IGNORECASE)
    
    # Clean up punctuation and spacing
    story = re.sub(r'\s+', ' ', story)
    story = re.sub(r'\s*[.,;]\s*[.,;]+', '.', story)
    story = story.strip()
    
    # Ensure it ends with proper punctuation
    if story and not story.endswith(('.', '!', '?')):
        story += '.'
    
    return story

def generate_story(prompt):
    provider = get_generation_provider()
    if provider == 'ollama':
        raw_story = run_ollama(prompt)
    else:
        raw_story = run_deepseek(prompt)
    
    return post_process_story(raw_story)

def generate_fallback_story(event, city, state):
    title = event.get('title', 'Local event')
    location = event.get('geo', {}).get('address', {}).get('formatted_address', 'a local venue')
    time_str = event.get('time_str', 'soon')
    
    # Clean location
    if location and ',' in location:
        location = location.split(',')[0].strip()
    
    return f"{title} will take place {time_str} at {location}."

def generate_combined_alerts_prompt(alerts, city, state):
    alert_titles = [alert.get('title', 'Alert') for alert in alerts[:3]]
    
    prompt = f"""Create a factual emergency alert for {city}, {state}.

Alerts: {', '.join(alert_titles)}

Rules:
- State facts only
- Use calm, urgent tone
- No promotional language
- Include safety instructions
- Format: [Alert type] is in effect for [location]. [Safety instruction].
- Maximum 15 seconds when spoken
- Output only the alert text
"""
    return prompt