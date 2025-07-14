import requests
import json
from datetime import datetime

class TomorrowWeatherAlerts:
    def __init__(self):
        with open('config.json') as f:
            config = json.load(f)
        self.api_key = config['api']['tomorrow_io']['api_key']
        self.lat = config['location']['default_coords'][0]
        self.lon = config['location']['default_coords'][1]
        self.seen_alerts = set()

    def fetch_alerts(self):
        """Fetch weather alerts from Tomorrow.io"""
        url = "https://api.tomorrow.io/v4/weather/forecast"
        params = {
            'location': f"{self.lat},{self.lon}",
            'apikey': self.api_key,
            'fields': 'weatherCodeMax,temperatureMax,precipitationProbabilityMax',
            'timesteps': '1d',
            'units': 'imperial'
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_new_alerts(self):
        """Get weather alerts from forecast data"""
        try:
            data = self.fetch_alerts()
            timelines = data.get('timelines', {}).get('daily', [])
            
            new_alerts = []
            for day in timelines[:3]:  # Check next 3 days
                values = day.get('values', {})
                weather_code = values.get('weatherCodeMax', 0)
                precip_prob = values.get('precipitationProbabilityMax', 0)
                temp_max = values.get('temperatureMax', 70)
                
                # Generate alerts based on conditions (lowered thresholds for testing)
                if weather_code >= 2000 and precip_prob > 30:  # Rain/storms
                    alert_id = f"severe-weather-{day.get('time', '')}"
                    if alert_id not in self.seen_alerts:
                        self.seen_alerts.add(alert_id)
                        new_alerts.append({
                            'title': 'Thunderstorm Alert',
                            'description': f'Storms expected with {precip_prob}% precipitation probability',
                            'severity': 'moderate',
                            'urgency': 'expected',
                            'start': day.get('time', ''),
                            'end': day.get('time', ''),
                            'areas': ['Local area'],
                            'category': 'severe-weather'
                        })
                
                if temp_max > 85:  # Heat warning (lowered for testing)
                    alert_id = f"heat-warning-{day.get('time', '')}"
                    if alert_id not in self.seen_alerts:
                        self.seen_alerts.add(alert_id)
                        new_alerts.append({
                            'title': 'Heat Advisory',
                            'description': f'High temperatures expected up to {temp_max}°F',
                            'severity': 'moderate',
                            'urgency': 'expected',
                            'start': day.get('time', ''),
                            'end': day.get('time', ''),
                            'areas': ['Local area'],
                            'category': 'severe-weather'
                        })
            
            return new_alerts
        except Exception as e:
            print(f"Error fetching weather data: {e}")
            # Return test alert for debugging
            return [{
                'title': 'Test Weather Alert',
                'description': 'Severe thunderstorms possible in the area',
                'severity': 'moderate',
                'urgency': 'expected',
                'start': datetime.now().isoformat(),
                'end': datetime.now().isoformat(),
                'areas': ['Miami-Dade County'],
                'category': 'severe-weather'
            }]

def get_weather_alerts():
    """Main function to get weather alerts"""
    monitor = TomorrowWeatherAlerts()
    return monitor.get_new_alerts()

if __name__ == "__main__":
    alerts = get_weather_alerts()
    if alerts:
        print(f"Found {len(alerts)} new weather alerts:")
        for alert in alerts:
            print(f"- {alert['title']} ({alert['severity']})")
    else:
        print("No new weather alerts")