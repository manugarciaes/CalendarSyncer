import os
import logging
from flask import session, url_for, redirect, request
import msal
from datetime import datetime, timedelta
from app import db
from models import User, Calendar
from config import MS_GRAPH_CLIENT_ID, MS_GRAPH_CLIENT_SECRET, MS_GRAPH_AUTHORITY, MS_GRAPH_SCOPES, ADDITIONAL_SCOPES, REDIRECT_URI
from werkzeug.security import generate_password_hash, check_password_hash

def get_auth_app():
    """Create and configure the MSAL application for Microsoft Graph API"""
    return msal.ConfidentialClientApplication(
        MS_GRAPH_CLIENT_ID,
        authority=MS_GRAPH_AUTHORITY,
        client_credential=MS_GRAPH_CLIENT_SECRET
    )

def get_auth_url():
    """Generate the authorization URL for Microsoft Graph API"""
    auth_app = get_auth_app()
    return auth_app.get_authorization_request_url(
        scopes=MS_GRAPH_SCOPES,
        redirect_uri=REDIRECT_URI,
        state=session.get("state", ""),
        extra_scope_to_consent=ADDITIONAL_SCOPES
    )

def get_token_from_code(code):
    """Exchange the authorization code for an access token"""
    auth_app = get_auth_app()
    try:
        # Combine regular scopes with additional scopes for token acquisition
        all_scopes = MS_GRAPH_SCOPES.copy()
        
        result = auth_app.acquire_token_by_authorization_code(
            code,
            scopes=all_scopes,
            redirect_uri=REDIRECT_URI
        )
        return result
    except Exception as e:
        logging.error(f"Error getting token from code: {e}")
        return None

def get_token_from_refresh_token(refresh_token):
    """Get a new access token using the refresh token"""
    auth_app = get_auth_app()
    try:
        # Only use regular scopes for token refresh (offline_access is for initial consent)
        result = auth_app.acquire_token_by_refresh_token(
            refresh_token,
            scopes=MS_GRAPH_SCOPES
        )
        return result
    except Exception as e:
        logging.error(f"Error refreshing token: {e}")
        return None

def store_calendar_tokens(user_id, calendar_name, outlook_id, token_data):
    """Store the access and refresh tokens for a calendar in the database"""
    try:
        # Check if the calendar already exists
        calendar = Calendar.query.filter_by(user_id=user_id, outlook_id=outlook_id).first()
        
        if calendar:
            # Update existing calendar
            calendar.name = calendar_name
            calendar.ms_graph_token = token_data.get('access_token')
            calendar.refresh_token = token_data.get('refresh_token')
            calendar.token_expiry = datetime.utcnow() + timedelta(seconds=token_data.get('expires_in', 3600))
            calendar.last_synced = datetime.utcnow()
        else:
            # Create new calendar
            calendar = Calendar(
                user_id=user_id,
                name=calendar_name,
                outlook_id=outlook_id,
                ms_graph_token=token_data.get('access_token'),
                refresh_token=token_data.get('refresh_token'),
                token_expiry=datetime.utcnow() + timedelta(seconds=token_data.get('expires_in', 3600)),
                last_synced=datetime.utcnow()
            )
            db.session.add(calendar)
        
        db.session.commit()
        return calendar
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error storing calendar tokens: {e}")
        return None

def refresh_calendar_token(calendar):
    """Refresh the access token for a calendar if it's expired or about to expire"""
    # If token is still valid for more than 5 minutes, return the current token
    if calendar.token_expiry and calendar.token_expiry > datetime.utcnow() + timedelta(minutes=5):
        return calendar.ms_graph_token
    
    # Token is expired or about to expire, refresh it
    if not calendar.refresh_token:
        logging.error(f"No refresh token available for calendar {calendar.id}")
        return None
    
    result = get_token_from_refresh_token(calendar.refresh_token)
    if result and 'access_token' in result:
        # Update the calendar with the new tokens
        calendar.ms_graph_token = result['access_token']
        if 'refresh_token' in result:
            calendar.refresh_token = result['refresh_token']
        calendar.token_expiry = datetime.utcnow() + timedelta(seconds=result.get('expires_in', 3600))
        db.session.commit()
        return calendar.ms_graph_token
    else:
        logging.error(f"Failed to refresh token for calendar {calendar.id}")
        return None

def register_user(username, email, password):
    """Register a new user"""
    try:
        # Check if user already exists
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            return None, "Username or email already exists"
        
        # Create new user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        return user, None
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error registering user: {e}")
        return None, str(e)

def login_user(username, password):
    """Authenticate a user by username and password"""
    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password_hash, password):
        return user, None
    return None, "Invalid username or password"
