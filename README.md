# Perigo Events - Community Events Announcement System

A Python application that fetches local events, generates AI-powered announcements, and converts them to audio using various APIs.

## Features

- Fetches events from PredictHQ API across multiple categories
- Generates AI-powered event announcements using DeepSeek
- Converts text to speech using Perigo TTS API
- Finds ticket information via Ticketmaster API
- Weather alerts integration with Tomorrow.io
- Supports multiple event categories: concerts, sports, festivals, community events, etc.

## Setup

### Prerequisites

- Python 3.8+
- pip package manager

### Installation

1. Clone the repository:
```bash
git clone https://github.com/kalyanvv/perigo-events.git
cd perigo-events
```

2. Create and activate virtual environment:
```bash
python -m venv env
env\Scripts\activate  # Windows
source env/bin/activate  # macOS/Linux
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure your API keys in `config.json`:
   - PredictHQ API token
   - DeepSeek API key
   - Ticketmaster API key
   - Tomorrow.io API key

## Usage

Run the main application:
```bash
python main.py
```

The application will:
1. Fetch events for your configured location
2. Generate announcements for top events
3. Create audio files for each announcement
4. Save all data to the `output/` directory

## Configuration

Edit `config.json` to customize:
- Location settings (city, state, coordinates)
- Time frame for events
- API credentials
- Story generation parameters
- Audio settings

## Project Structure

```
perigo-events/
├── main.py                 # Main application entry point
├── event_fetcher.py        # Event fetching logic
├── story_generator.py      # AI story generation
├── ticket_finder.py        # Ticket information finder
├── location_utils.py       # Location utilities
├── weather.py             # Weather integration
├── tomorrow_alerts.py     # Weather alerts
├── requirements.txt       # Python dependencies
├── config.json           # Configuration file
└── output/               # Generated announcements and audio
```

## API Requirements

You'll need API keys for:
- [PredictHQ](https://www.predicthq.com/) - Event data
- [DeepSeek](https://www.deepseek.com/) - AI text generation
- [Ticketmaster](https://developer.ticketmaster.com/) - Ticket information
- [Tomorrow.io](https://www.tomorrow.io/) - Weather alerts

## License

This project is licensed under the MIT License.