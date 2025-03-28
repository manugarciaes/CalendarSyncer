from app import app
from calendar_sync import start_scheduler

# Start the background scheduler for calendar refreshing
start_scheduler()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
