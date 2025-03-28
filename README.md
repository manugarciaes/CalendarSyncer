# Calendar Sync Application

A sophisticated calendar synchronization application that enables seamless integration of multiple calendar sources, allowing users to manage and share their availability with ease.

## Features

- Sync multiple Outlook calendars
- Create shared booking links
- Automated booking across all calendars
- Calendar analytics dashboard
- Customer booking interface

## Tech Stack

- Python/Flask backend
- SQLAlchemy ORM
- PostgreSQL database (Docker) / SQLite (local development)
- Microsoft Graph API integration
- Bootstrap UI

## Running with Docker

The easiest way to run the application locally is using Docker Compose:

```bash
# Start the application and database
docker-compose up

# Access the application at http://localhost:5000
```

This will start:
- A PostgreSQL database
- The Flask web application

## Manual Setup

If you prefer to run without Docker:

1. Set up a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -e .
   ```

3. Set environment variables:
   ```bash
   export SESSION_SECRET=your_secure_secret_here
   # Optional: export DATABASE_URL=postgresql://username:password@localhost:5432/dbname
   ```

4. Run the application:
   ```bash
   python main.py
   ```

## Configuration

The application requires configuration for Microsoft Graph API integration. Create a file named `config.py` with the following contents:

```python
# Microsoft Graph API Configuration
MS_GRAPH_CLIENT_ID = "your_client_id"
MS_GRAPH_CLIENT_SECRET = "your_client_secret"
MS_GRAPH_AUTHORITY = "https://login.microsoftonline.com/common"
MS_GRAPH_REDIRECT_PATH = "/auth/callback"
MS_GRAPH_SCOPES = [
    "User.Read",
    "Calendars.Read",
    "Calendars.ReadWrite"
]
```

You will need to register an application in the Azure Portal to obtain the client ID and secret.

## License

This project is licensed under the MIT License - see the LICENSE file for details.