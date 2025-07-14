import json
import requests
import logging
from datetime import datetime
from difflib import SequenceMatcher
import re
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TicketFinder:
    def __init__(self):
        with open('config.json') as f:
            config = json.load(f)
        self.ticketmaster_key = config.get('api', {}).get('ticketmaster', {}).get('api_key', '')
        self.api_call_count = 0
        self.last_api_call = 0
        self.cache = {}
    
    def needs_ticket(self, event):
        """Determine if an event likely needs tickets"""
        title = event.get('title', '').lower()
        category = event.get('category', '')
        
        if 'free' in title or 'no charge' in title:
            return False
        
        if category in ['school-holidays', 'academic']:
            return False
        
        ticketed_categories = ['concerts', 'sports', 'performing-arts']
        if category in ticketed_categories:
            return True
        
        entities = event.get('entities', [])
        for entity in entities:
            if entity.get('type') == 'venue':
                venue_name = entity.get('name', '').lower()
                ticketed_venues = ['amphitheatre', 'stadium', 'arena', 'theater', 'theatre', 'auditorium', 'coliseum']
                if any(venue in venue_name for venue in ticketed_venues):
                    return True
        
        # High-rank events (major/professional events)
        if event.get('rank', 0) >= 50:
            return True
        
        # High attendance events
        if event.get('phq_attendance', 0) >= 1000:
            return True
        
        # High predicted spend (indicates ticket sales)
        if event.get('predicted_event_spend', 0) >= 50000:
            return True
        
        return False
    
    def search_ticketmaster(self, event):
        """Search Ticketmaster for event tickets"""
        if not self.ticketmaster_key:
            logger.warning("No Ticketmaster API key configured")
            return None
        
        try:
            title = event.get('title', '')
            start_date = event.get('start_local', '').split('T')[0] if event.get('start_local') else ''
            
            # Get location info
            geo = event.get('geo', {}).get('address', {})
            city = geo.get('locality', '')
            state = geo.get('region', '')
            
            # Clean up title for better matching
            clean_title = title.replace(' - ', ' ').replace('@', '').replace('vs', 'v').strip()
            
            # Extract key terms for sports events
            if 'vs' in title.lower() or ' v ' in title.lower():
                # For sports, try team names separately
                teams = re.split(r'\s+vs?\s+', title, flags=re.IGNORECASE)
                if len(teams) == 2:
                    clean_title = f"{teams[0].strip()} {teams[1].strip()}"
            
            params = {
                'apikey': self.ticketmaster_key,
                'keyword': clean_title,
                'size': 10,  # Reduced to minimize data transfer
                'sort': 'relevance,desc'
            }
            
            if city:
                params['city'] = city
            if state and len(state) >= 2:
                # Convert full state name to abbreviation if needed
                state_abbr = 'GA' if 'georgia' in state.lower() else state[:2].upper()
                params['stateCode'] = state_abbr
            
            # Try search with date first, then without if no results
            search_attempts = []
            if start_date:
                # Exact date search
                date_params = params.copy()
                date_params['startDateTime'] = f"{start_date}T00:00:00Z"
                date_params['endDateTime'] = f"{start_date}T23:59:59Z"
                search_attempts.append(date_params)
            
            # Fallback search without date constraints
            search_attempts.append(params)
            
            logger.info(f"Searching Ticketmaster for: {clean_title} in {city}, {state}")
            
            # Check cache first
            cache_key = f"{clean_title}_{city}_{state}_{start_date}"
            if cache_key in self.cache:
                logger.info("Using cached result")
                return self.cache[cache_key]
            
            # Rate limiting - max 5 calls per second
            current_time = time.time()
            if current_time - self.last_api_call < 0.2:  # 200ms between calls
                time.sleep(0.2 - (current_time - self.last_api_call))
            
            # Try only the most promising search (reduce API calls)
            best_params = search_attempts[0] if search_attempts else params
            
            try:
                self.api_call_count += 1
                self.last_api_call = time.time()
                
                logger.info(f"API call #{self.api_call_count}: {clean_title}")
                
                response = requests.get(
                    'https://app.ticketmaster.com/discovery/v2/events.json',
                    params=best_params,
                    timeout=10
                )
                
                logger.info(f"Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    events = data.get('_embedded', {}).get('events', [])
                    
                    logger.info(f"Found {len(events)} events")
                    
                    result = None
                    if events:
                        best_match = self._find_best_match(events, clean_title)
                        if best_match:
                            result = {
                                'ticket_url': best_match.get('url'),
                                'price_range': self._extract_price_range(best_match),
                                'venue': best_match.get('_embedded', {}).get('venues', [{}])[0].get('name'),
                                'date': best_match.get('dates', {}).get('start', {}).get('localDate'),
                                'source': 'Ticketmaster'
                            }
                    
                    # Cache result (even if None)
                    self.cache[cache_key] = result
                    return result
                    
                elif response.status_code == 429:
                    logger.warning("Rate limit hit - waiting 60 seconds")
                    time.sleep(60)
                    return None
                elif response.status_code == 401:
                    logger.error("Ticketmaster API authentication failed")
                    return None
                else:
                    logger.warning(f"API error: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Search failed: {e}")
                return None
            
        except Exception as e:
            logger.error(f"Ticketmaster search failed: {e}")
        
        return None
    
    def _find_best_match(self, events, target_title):
        """Find the best matching event using fuzzy string matching"""
        if not events:
            return None
        
        target_clean = self._normalize_title(target_title)
        best_match = None
        best_score = 0.0
        
        for event in events:
            event_name = event.get('name', '')
            event_clean = self._normalize_title(event_name)
            
            # Calculate similarity scores
            exact_score = SequenceMatcher(None, target_clean, event_clean).ratio()
            word_score = self._word_overlap_score(target_clean, event_clean)
            artist_score = self._artist_match_score(target_title, event_name)
            
            # Weighted final score
            final_score = (exact_score * 0.4) + (word_score * 0.4) + (artist_score * 0.2)
            
            if final_score > best_score and final_score > 0.3:  # Minimum threshold
                best_score = final_score
                best_match = event
        
        return best_match
    
    def _normalize_title(self, title):
        """Normalize title for better matching"""
        # Convert to lowercase and remove special characters
        normalized = re.sub(r'[^\w\s]', ' ', title.lower())
        # Remove common words that don't help matching
        stop_words = {'the', 'and', 'or', 'at', 'in', 'on', 'vs', 'v', 'tour', 'live', 'show'}
        words = [w for w in normalized.split() if w not in stop_words and len(w) > 2]
        return ' '.join(words)
    
    def _word_overlap_score(self, title1, title2):
        """Calculate word overlap score"""
        words1 = set(title1.split())
        words2 = set(title2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _artist_match_score(self, predicthq_title, tm_title):
        """Special scoring for artist/team names"""
        # Extract potential artist/team names (first few words)
        phq_words = predicthq_title.lower().split()[:3]
        tm_words = tm_title.lower().split()[:3]
        
        score = 0.0
        for phq_word in phq_words:
            if len(phq_word) > 3:  # Skip short words
                for tm_word in tm_words:
                    if phq_word in tm_word or tm_word in phq_word:
                        score += 0.5
                    elif SequenceMatcher(None, phq_word, tm_word).ratio() > 0.8:
                        score += 0.3
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _extract_price_range(self, tm_event):
        """Extract price range from Ticketmaster event"""
        try:
            price_ranges = tm_event.get('priceRanges', [])
            if price_ranges:
                min_price = price_ranges[0].get('min', 0)
                max_price = price_ranges[0].get('max', 0)
                currency = price_ranges[0].get('currency', 'USD')
                return f"${min_price}-${max_price} {currency}"
        except:
            pass
        return "Price varies"
    
    def find_tickets(self, event):
        """Main method to find tickets for an event"""
        if not self.needs_ticket(event):
            return {
                'needs_ticket': False,
                'reason': 'Free or community event'
            }
        
        # Search Ticketmaster only
        ticket_info = self.search_ticketmaster(event)
        
        return {
            'needs_ticket': True,
            'ticket_info': ticket_info,
            'event_details': {
                'title': event.get('title'),
                'date': event.get('start_local', '').split('T')[0],
                'venue': self._get_venue_name(event),
                'category': event.get('category'),
                'attendance': event.get('phq_attendance'),
                'rank': event.get('rank')
            }
        }
    
    def _get_venue_name(self, event):
        """Extract venue name from event"""
        entities = event.get('entities', [])
        for entity in entities:
            if entity.get('type') == 'venue':
                return entity.get('name')
        
        # Fallback to address
        geo = event.get('geo', {}).get('address', {})
        return geo.get('formatted_address', 'Location TBD')

def process_all_events():
    """Process all events and identify those needing tickets"""
    try:
        with open('all_events.json', 'r', encoding='utf-8') as f:
            all_events = json.load(f)
        
        finder = TicketFinder()
        ticketed_events = []
        
        logger.info(f"Processing {len(all_events)} events for ticket requirements...")
        
        # Process only high-priority events first to reduce API calls
        priority_events = [e for e in all_events if e.get('rank', 0) >= 50 or e.get('phq_attendance', 0) >= 5000]
        regular_events = [e for e in all_events if e not in priority_events]
        
        logger.info(f"Processing {len(priority_events)} high-priority events first")
        
        # Process high-priority events
        for i, event in enumerate(priority_events):
            if i > 0 and i % 10 == 0:  # Progress update every 10 events
                logger.info(f"Processed {i}/{len(priority_events)} priority events")
            
            result = finder.find_tickets(event)
            if result['needs_ticket']:
                ticketed_events.append(result)
        
        # Process remaining events with more restrictive criteria
        logger.info(f"Processing {len(regular_events)} regular events")
        for i, event in enumerate(regular_events[:20]):  # Limit to 20 regular events
            result = finder.find_tickets(event)
            if result['needs_ticket']:
                ticketed_events.append(result)
        
        # Save results
        with open('ticketed_events.json', 'w', encoding='utf-8') as f:
            json.dump(ticketed_events, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Found {len(ticketed_events)} events that likely need tickets")
        logger.info(f"Total API calls made: {finder.api_call_count}")
        
        # Print summary
        print(f"\n🎫 TICKET ANALYSIS SUMMARY")
        print(f"Total events analyzed: {len(all_events)}")
        print(f"Events needing tickets: {len(ticketed_events)}")
        
        # Show top ticketed events
        print(f"\n🎯 TOP TICKETED EVENTS:")
        for i, event in enumerate(ticketed_events[:5]):
            details = event['event_details']
            ticket = event.get('ticket_info', {})
            print(f"\n{i+1}. {details['title']}")
            print(f"   Category: {details['category']}")
            print(f"   Date: {details['date']}")
            print(f"   Venue: {details['venue']}")
            print(f"   Attendance: {details['attendance']}")
            if ticket:
                print(f"   Tickets: {ticket.get('price_range', 'N/A')}")
                print(f"   URL: {ticket.get('ticket_url', 'N/A')}")
        
        return ticketed_events
        
    except Exception as e:
        logger.error(f"Error processing events: {e}")
        return []

if __name__ == "__main__":
    process_all_events()
