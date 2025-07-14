import requests
import time
from datetime import datetime

class WeatherAlertMonitor:
    def __init__(self, api_key, latitude, longitude, webhook_callback):
        self.api_key = api_key
        self.lat = latitude
        self.lon = longitude
        self.webhook_callback = webhook_callback
        self.last_checked = None
        self.seen_alerts = set()

    def fetch_weather_data(self):
        """Fetch current weather data from OpenWeatherMap API"""
        url = f"https://api.openweathermap.org/data/3.0/onecall"
        params = {
            'lat': self.lat,
            'lon': self.lon,
            'exclude': 'minutely,hourly,daily',
            'appid': self.api_key
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def check_for_new_alerts(self):
        """Check for new alerts and trigger webhook if found"""
        try:
            data = self.fetch_weather_data()
            self.last_checked = datetime.utcnow()
            
            if 'alerts' not in data:
                print(f"No alerts at {self.last_checked.strftime('%Y-%m-%d %H:%M:%S')}")
                return
                
            current_alerts = []
            for alert in data['alerts']:
                # Create unique alert identifier
                alert_id = f"{alert['event']}-{alert['start']}-{alert['end']}"
                
                if alert_id not in self.seen_alerts:
                    self.seen_alerts.add(alert_id)
                    current_alerts.append(alert)
                    print(f"New alert detected: {alert['event']}")
            
            if current_alerts:
                self.trigger_webhook(current_alerts)
                
        except Exception as e:
            print(f"Error checking alerts: {str(e)}")

    def trigger_webhook(self, alerts):
        """Trigger the webhook callback with alert data"""
        alert_data = []
        for alert in alerts:
            alert_data.append({
                'event': alert['event'],
                'description': alert['description'],
                'start': datetime.utcfromtimestamp(alert['start']).isoformat(),
                'end': datetime.utcfromtimestamp(alert['end']).isoformat(),
                'severity': alert.get('severity', 'unknown'),
                'sender': alert.get('sender_name', 'N/A')
            })
        
        payload = {
            'location': {'lat': self.lat, 'lon': self.lon},
            'alerts': alert_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Call the webhook function
        self.webhook_callback(payload)

# Example webhook implementation (replace with your actual notification method)
def example_webhook(payload):
    """Example webhook handler that prints alerts"""
    print("\n⚠️ WEATHER ALERT TRIGGERED ⚠️")
    print(f"Location: {payload['location']['lat']}, {payload['location']['lon']}")
    for alert in payload['alerts']:
        print(f"\nALERT: {alert['event']}")
        print(f"From: {alert['start']} to {alert['end']}")
        print(f"Severity: {alert['severity'].upper()}")
        print(f"Issued by: {alert['sender']}")
        print(f"Details: {alert['description'][:150]}...")
    print("\n" + "="*50 + "\n")

# Configuration
API_KEY = "f47d7fc7595bdb01727094a77c126e9e"
LATITUDE = 37.7749
LONGITUDE = -122.4194
CHECK_INTERVAL = 1800

if __name__ == "__main__":
    monitor = WeatherAlertMonitor(
        api_key=API_KEY,
        latitude=LATITUDE,
        longitude=LONGITUDE,
        webhook_callback=example_webhook
    )

    print(f"Weather Alert Monitor Started for {LATITUDE}, {LONGITUDE}")
    print(f"Checking every {CHECK_INTERVAL//60} minutes...\n")

    try:
        while True:
            monitor.check_for_new_alerts()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\nMonitoring stopped")