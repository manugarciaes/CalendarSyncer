import os

# Microsoft Graph API settings
MS_GRAPH_CLIENT_ID = os.environ.get("MS_GRAPH_CLIENT_ID", "")
MS_GRAPH_CLIENT_SECRET = os.environ.get("MS_GRAPH_CLIENT_SECRET", "")
MS_GRAPH_AUTHORITY = "https://login.microsoftonline.com/common"
# Microsoft Graph API resource scopes
MS_GRAPH_SCOPES = [
    "User.Read",
    "Calendars.Read",
    "Calendars.ReadWrite"
]

# Special scopes to be added separately in auth.py
ADDITIONAL_SCOPES = ["offline_access"]

# Redirect URI for OAuth
REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:5000/auth/callback")

# Application settings
APP_NAME = "Calendar Sync"
APP_DESCRIPTION = "Synchronize multiple Outlook calendars and share free slots with customers"

# Time settings
DEFAULT_SLOT_DURATION = 30  # in minutes
