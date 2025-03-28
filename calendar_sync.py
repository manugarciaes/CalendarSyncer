import logging
import requests
from datetime import datetime, timedelta
import pytz
from auth import refresh_calendar_token
from models import Calendar, Booking, SharedLink
from app import db

def get_calendar_events(calendar, start_date, end_date):
    """Fetch events from an Outlook calendar using Microsoft Graph API"""
    # Refresh the token if needed
    access_token = refresh_calendar_token(calendar)
    if not access_token:
        logging.error(f"Failed to get access token for calendar {calendar.id}")
        return None
    
    # Format dates for Microsoft Graph API
    start_date_str = start_date.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_date_str = end_date.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Prepare the request
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    # Request parameters
    params = {
        'startDateTime': start_date_str,
        'endDateTime': end_date_str,
        '$select': 'subject,start,end,isAllDay,showAs,id'
    }
    
    # Make the request to Microsoft Graph API
    try:
        response = requests.get(
            f'https://graph.microsoft.com/v1.0/me/calendars/{calendar.outlook_id}/calendarView',
            headers=headers,
            params=params
        )
        
        if response.status_code == 200:
            return response.json().get('value', [])
        else:
            logging.error(f"Error fetching calendar events: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logging.error(f"Exception fetching calendar events: {e}")
        return None

def create_calendar_event(calendar, event_data):
    """Create an event in an Outlook calendar using Microsoft Graph API"""
    # Refresh the token if needed
    access_token = refresh_calendar_token(calendar)
    if not access_token:
        logging.error(f"Failed to get access token for calendar {calendar.id}")
        return None
    
    # Prepare the request
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    # Make the request to Microsoft Graph API
    try:
        response = requests.post(
            f'https://graph.microsoft.com/v1.0/me/calendars/{calendar.outlook_id}/events',
            headers=headers,
            json=event_data
        )
        
        if response.status_code in [200, 201]:
            return response.json()
        else:
            logging.error(f"Error creating calendar event: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logging.error(f"Exception creating calendar event: {e}")
        return None

def get_free_slots(calendars, start_date, end_date, slot_duration=30):
    """Find free time slots across multiple calendars"""
    all_events = []
    
    # Get events from each calendar
    for calendar in calendars:
        events = get_calendar_events(calendar, start_date, end_date)
        if events:
            # Only include busy events
            busy_events = [
                {
                    'start': datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00')),
                    'end': datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00')),
                    'is_all_day': event['isAllDay'],
                    'show_as': event['showAs']
                }
                for event in events
                if event['showAs'] in ['busy', 'tentative', 'oof', 'workingElsewhere']
            ]
            all_events.extend(busy_events)
    
    # If no events, all time is free
    if not all_events:
        return generate_time_slots(start_date, end_date, slot_duration)
    
    # Sort events by start time
    all_events.sort(key=lambda x: x['start'])
    
    # Generate all possible time slots
    all_slots = generate_time_slots(start_date, end_date, slot_duration)
    
    # Mark slots as unavailable if they overlap with any event
    free_slots = []
    for slot in all_slots:
        slot_start = slot['start']
        slot_end = slot['end']
        
        # Check if the slot overlaps with any busy event
        is_free = True
        for event in all_events:
            # Check for overlap
            if (slot_start < event['end'] and slot_end > event['start']):
                is_free = False
                break
        
        # If the slot is free, add it to the list
        if is_free:
            free_slots.append(slot)
    
    return free_slots

def generate_time_slots(start_date, end_date, slot_duration=30):
    """Generate time slots between start_date and end_date with the given duration in minutes"""
    current_time = start_date
    slots = []
    
    # Assuming working hours are 9 AM to 5 PM
    working_start_hour = 9
    working_end_hour = 17
    
    while current_time < end_date:
        day_start = datetime(
            current_time.year, current_time.month, current_time.day,
            working_start_hour, 0, 0, tzinfo=current_time.tzinfo
        )
        day_end = datetime(
            current_time.year, current_time.month, current_time.day,
            working_end_hour, 0, 0, tzinfo=current_time.tzinfo
        )
        
        # Skip if current_time is past working hours for the day
        if current_time.time() >= day_end.time():
            # Move to the next day
            current_time = datetime(
                current_time.year, current_time.month, current_time.day,
                0, 0, 0, tzinfo=current_time.tzinfo
            ) + timedelta(days=1)
            continue
        
        # Start from working hours if current_time is before working hours
        if current_time.time() < day_start.time():
            current_time = day_start
        
        slot_start = current_time
        slot_end = slot_start + timedelta(minutes=slot_duration)
        
        # Skip if slot ends after working hours
        if slot_end.time() > day_end.time():
            # Move to the next day
            current_time = datetime(
                current_time.year, current_time.month, current_time.day,
                0, 0, 0, tzinfo=current_time.tzinfo
            ) + timedelta(days=1)
            continue
        
        # Skip weekends (assuming 0 = Monday, 6 = Sunday)
        weekday = slot_start.weekday()
        if weekday < 5:  # Only include Monday to Friday
            slots.append({
                'start': slot_start,
                'end': slot_end,
                'duration': slot_duration,
                'formatted_start': slot_start.strftime('%Y-%m-%dT%H:%M:%S'),
                'formatted_end': slot_end.strftime('%Y-%m-%dT%H:%M:%S'),
                'display': slot_start.strftime('%A, %B %d, %Y %I:%M %p') + ' - ' + slot_end.strftime('%I:%M %p')
            })
        
        # Move to the next slot
        current_time = slot_end
    
    return slots

def create_booking(shared_link_id, customer_name, customer_email, start_time, end_time, subject, description):
    """Create a booking and add it to all relevant calendars"""
    try:
        # Get the shared link
        shared_link = SharedLink.query.get(shared_link_id)
        if not shared_link:
            return None, "Shared link not found"
        
        # Create booking record
        booking = Booking(
            shared_link_id=shared_link_id,
            customer_name=customer_name,
            customer_email=customer_email,
            start_time=start_time,
            end_time=end_time,
            subject=subject,
            description=description
        )
        db.session.add(booking)
        db.session.flush()  # Get the booking ID without committing
        
        # Get calendar IDs from the shared link
        calendar_ids = shared_link.get_calendar_ids()
        calendars = Calendar.query.filter(Calendar.id.in_(calendar_ids)).all()
        
        # Create events in each calendar
        event_ids = []
        for calendar in calendars:
            # Prepare event data
            event_data = {
                'subject': subject,
                'body': {
                    'contentType': 'text',
                    'content': f"Booking made by {customer_name} ({customer_email})\n\n{description}"
                },
                'start': {
                    'dateTime': start_time.strftime('%Y-%m-%dT%H:%M:%S'),
                    'timeZone': 'UTC'
                },
                'end': {
                    'dateTime': end_time.strftime('%Y-%m-%dT%H:%M:%S'),
                    'timeZone': 'UTC'
                },
                'attendees': [
                    {
                        'emailAddress': {
                            'address': customer_email,
                            'name': customer_name
                        },
                        'type': 'required'
                    }
                ]
            }
            
            # Create the event
            result = create_calendar_event(calendar, event_data)
            if result and 'id' in result:
                event_ids.append(result['id'])
            else:
                # If any event creation fails, roll back and return error
                db.session.rollback()
                return None, "Failed to create events in all calendars"
        
        # Store the event IDs in the booking
        booking.outlook_event_ids = ','.join(event_ids)
        db.session.commit()
        
        return booking, None
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating booking: {e}")
        return None, str(e)
