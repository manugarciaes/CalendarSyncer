import logging
import requests
import json
from datetime import datetime, timedelta
import pytz
from collections import Counter, defaultdict
from apscheduler.schedulers.background import BackgroundScheduler
from icalendar import Calendar as ICalendar
from models import Calendar, Booking, SharedLink
from app import db

# Create a background scheduler for refreshing ICS feeds
scheduler = BackgroundScheduler(daemon=True)

def get_calendar_events(calendar, start_date, end_date):
    """Fetch events from a calendar using its ICS feed"""
    # First check if we have cached events
    if calendar.cached_events:
        try:
            cached_data = json.loads(calendar.cached_events)
            return cached_data
        except Exception as e:
            logging.error(f"Error parsing cached events for calendar {calendar.id}: {e}")
    
    # If no cache or error parsing it, fetch from ICS
    return refresh_calendar_events(calendar)

def refresh_calendar_events(calendar):
    """Refresh events from an ICS feed and update the cache"""
    try:
        # Make the request to the ICS URL
        response = requests.get(calendar.ics_url)
        
        if response.status_code == 200:
            # Parse the ICS data
            cal = ICalendar.from_ical(response.content)
            
            # Extract events
            events = []
            for component in cal.walk():
                if component.name == "VEVENT":
                    # Extract start and end times
                    start_dt = component.get('dtstart').dt
                    end_dt = component.get('dtend').dt
                    
                    # Check if they are date objects (all-day events) or datetime objects
                    is_all_day = isinstance(start_dt, datetime.date) and not isinstance(start_dt, datetime)
                    
                    # Convert date objects to datetime for consistency
                    if is_all_day:
                        if not isinstance(start_dt, datetime):
                            start_dt = datetime.combine(start_dt, datetime.min.time(), tzinfo=pytz.UTC)
                        if not isinstance(end_dt, datetime):
                            end_dt = datetime.combine(end_dt, datetime.min.time(), tzinfo=pytz.UTC)
                    
                    event = {
                        'id': str(component.get('uid', '')),
                        'subject': str(component.get('summary', 'No Title')),
                        'start': start_dt,
                        'end': end_dt,
                        'is_all_day': is_all_day,
                        'status': str(component.get('status', 'CONFIRMED')),
                        'description': str(component.get('description', '')),
                        'location': str(component.get('location', '')),
                        'organizer': str(component.get('organizer', '')),
                        'recurrence': component.get('rrule', None)
                    }
                    
                    # Add busy/free status (ICS doesn't have this explicitly, assume all events are busy)
                    event['show_as'] = 'busy'
                    
                    events.append(event)
            
            # Update the cache
            calendar.cached_events = json.dumps(events, default=str)
            calendar.last_synced = datetime.now()
            db.session.commit()
            
            return events
        else:
            logging.error(f"Error fetching ICS feed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logging.error(f"Exception fetching ICS feed: {e}")
        return None

def create_calendar_event(calendar, event_data):
    """
    Create a booking event
    
    Note: Since we're using ICS feeds which are typically read-only,
    this function doesn't actually create an event in the original calendar.
    Instead, it returns a simulated success response with a generated event ID.
    
    In a real-world scenario, you would implement methods to add events to the 
    source calendar through their respective APIs (Google, Outlook, etc.)
    or use email notifications to notify the calendar owner about the booking.
    """
    try:
        # Generate a unique ID for the event
        event_id = f"booking_{datetime.now().strftime('%Y%m%d%H%M%S')}_{calendar.id}"
        
        # Simulate a successful response
        response = {
            'id': event_id,
            'subject': event_data['subject'],
            'start': event_data['start'],
            'end': event_data['end'],
            'attendees': event_data['attendees'],
            'status': 'confirmed'
        }
        
        logging.info(f"Created booking event for calendar {calendar.id}: {event_id}")
        
        # In a real implementation, you would send this data to the calendar provider
        # or send email notifications to the calendar owner
        
        return response
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
            description=description,
            status="confirmed"
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
        
        # No need to store event IDs in the booking as we've removed that field
        db.session.commit()
        
        return booking, None
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating booking: {e}")
        return None, str(e)

def get_booking_analytics(user_id, start_date=None, end_date=None):
    """
    Get analytics data for bookings associated with a user
    
    Parameters:
    - user_id: The ID of the user to get analytics for
    - start_date: Optional start date for the analytics period
    - end_date: Optional end date for the analytics period
    
    Returns a dictionary containing various analytics metrics
    """
    try:
        # Set default date range if not specified (last 30 days)
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
            
        # Query all shared links for the user
        shared_links = SharedLink.query.filter_by(user_id=user_id, active=True).all()
        shared_link_ids = [link.id for link in shared_links]
        
        if not shared_link_ids:
            return {
                "total_bookings": 0,
                "bookings_by_link": {},
                "bookings_by_day": {},
                "bookings_by_hour": {},
                "bookings_by_weekday": {},
                "top_customers": [],
                "average_duration": 0,
                "start_date": start_date,
                "end_date": end_date
            }
        
        # Query all bookings for these shared links within the date range
        bookings = Booking.query.filter(
            Booking.shared_link_id.in_(shared_link_ids),
            Booking.start_time >= start_date,
            Booking.start_time <= end_date
        ).all()
        
        # Initialize analytics metrics
        total_bookings = len(bookings)
        bookings_by_link = defaultdict(int)
        bookings_by_day = defaultdict(int)
        bookings_by_hour = defaultdict(int)
        bookings_by_weekday = defaultdict(int)
        customers = Counter()
        total_duration = timedelta(0)
        
        link_name_map = {link.id: link.name for link in shared_links}
        
        # Process each booking to collect metrics
        for booking in bookings:
            # Count by shared link
            link_name = link_name_map.get(booking.shared_link_id, f"Link {booking.shared_link_id}")
            bookings_by_link[link_name] += 1
            
            # Count by day
            day_key = booking.start_time.strftime('%Y-%m-%d')
            bookings_by_day[day_key] += 1
            
            # Count by hour
            hour = booking.start_time.hour
            bookings_by_hour[hour] += 1
            
            # Count by weekday
            weekday = booking.start_time.strftime('%A')
            bookings_by_weekday[weekday] += 1
            
            # Count by customer
            customers[booking.customer_email] += 1
            
            # Add to total duration
            duration = booking.end_time - booking.start_time
            total_duration += duration
        
        # Calculate averages and prepare final metrics
        average_duration = total_duration.total_seconds() / total_bookings if total_bookings > 0 else 0
        average_duration_minutes = average_duration / 60
        
        # Get top 5 customers
        top_customers = [
            {"email": email, "count": count}
            for email, count in customers.most_common(5)
        ]
        
        # Sort the day-based metrics chronologically 
        sorted_days = sorted(bookings_by_day.items())
        bookings_by_day = {day: count for day, count in sorted_days}
        
        # Sort hour-based metrics
        sorted_hours = sorted(bookings_by_hour.items())
        bookings_by_hour = {f"{hour}:00": count for hour, count in sorted_hours}
        
        # Order weekdays correctly
        weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        sorted_weekdays = {day: bookings_by_weekday.get(day, 0) for day in weekday_order}
        
        return {
            "total_bookings": total_bookings,
            "bookings_by_link": dict(bookings_by_link),
            "bookings_by_day": bookings_by_day,
            "bookings_by_hour": bookings_by_hour,
            "bookings_by_weekday": sorted_weekdays,
            "top_customers": top_customers,
            "average_duration": round(average_duration_minutes, 1),
            "start_date": start_date,
            "end_date": end_date
        }
    
    except Exception as e:
        logging.error(f"Error generating booking analytics: {e}")
        return None

def get_calendar_analytics(user_id, calendar_id=None, start_date=None, end_date=None):
    """
    Get analytics data for calendar usage
    
    Parameters:
    - user_id: The ID of the user to get analytics for
    - calendar_id: Optional specific calendar ID to analyze
    - start_date: Optional start date for the analytics period
    - end_date: Optional end date for the analytics period
    
    Returns a dictionary containing various calendar analytics metrics
    """
    try:
        # Set default date range if not specified (last 30 days)
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Query calendars
        calendars_query = Calendar.query.filter_by(user_id=user_id, active=True)
        if calendar_id:
            calendars_query = calendars_query.filter_by(id=calendar_id)
        
        calendars = calendars_query.all()
        
        if not calendars:
            return {
                "busy_vs_free": {"busy": 0, "free": 100},
                "events_by_calendar": {},
                "busiest_days": {},
                "busiest_hours": {},
                "free_slot_distribution": {},
                "start_date": start_date,
                "end_date": end_date
            }
        
        calendar_names = {calendar.id: calendar.name for calendar in calendars}
        
        # Initialize analytics metrics
        events_by_calendar = defaultdict(int)
        events_by_day = defaultdict(int)
        events_by_hour = defaultdict(int)
        total_busy_minutes = 0
        total_possible_minutes = 0
        free_slots_count = 0
        
        # For each calendar, get events
        for calendar in calendars:
            events = get_calendar_events(calendar, start_date, end_date)
            if not events:
                continue
                
            events_by_calendar[calendar_names[calendar.id]] = len(events)
            
            # Process each event
            for event in events:
                if event['showAs'] in ['busy', 'tentative', 'oof', 'workingElsewhere']:
                    # Calculate event start and end
                    event_start = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                    event_end = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                    
                    # Count by day
                    day_key = event_start.strftime('%Y-%m-%d')
                    events_by_day[day_key] += 1
                    
                    # Count by hour
                    hour = event_start.hour
                    events_by_hour[hour] += 1
                    
                    # Calculate duration in minutes
                    duration = (event_end - event_start).total_seconds() / 60
                    total_busy_minutes += duration
        
        # Calculate free time distribution
        # Get free slots for all calendars
        free_slots = get_free_slots(calendars, start_date, end_date)
        
        # Count slots by day of week
        free_slots_by_weekday = defaultdict(int)
        for slot in free_slots:
            weekday = slot['start'].strftime('%A')
            free_slots_by_weekday[weekday] += 1
            free_slots_count += 1
        
        # Calculate total possible working minutes (9am-5pm, weekdays only)
        working_days = 0
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() < 5:  # Weekday (0-4 is Monday-Friday)
                working_days += 1
            current_date += timedelta(days=1)
        
        # 8 working hours per day
        total_possible_minutes = working_days * 8 * 60
        
        # Calculate busy vs free ratio
        busy_percentage = (total_busy_minutes / total_possible_minutes * 100) if total_possible_minutes > 0 else 0
        busy_percentage = min(100, busy_percentage)  # Cap at 100%
        free_percentage = 100 - busy_percentage
        
        # Sort the day-based metrics chronologically 
        sorted_days = sorted(events_by_day.items())
        events_by_day = {day: count for day, count in sorted_days}
        
        # Sort hour-based metrics
        sorted_hours = sorted(events_by_hour.items())
        events_by_hour = {f"{hour}:00": count for hour, count in sorted_hours}
        
        # Order weekdays correctly for free slots
        weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        sorted_free_slots = {day: free_slots_by_weekday.get(day, 0) for day in weekday_order}
        
        return {
            "busy_vs_free": {
                "busy": round(busy_percentage, 1),
                "free": round(free_percentage, 1)
            },
            "events_by_calendar": dict(events_by_calendar),
            "busiest_days": events_by_day,
            "busiest_hours": events_by_hour,
            "free_slot_distribution": sorted_free_slots,
            "free_slots_count": free_slots_count,
            "start_date": start_date,
            "end_date": end_date
        }
        
    except Exception as e:
        logging.error(f"Error generating calendar analytics: {e}")
        return None

def setup_calendar_refresh_jobs():
    """Set up background jobs to refresh calendar events at regular intervals"""
    try:
        # Get all active calendars
        calendars = Calendar.query.filter_by(active=True).all()
        
        # Schedule jobs for each calendar based on refresh_interval
        for calendar in calendars:
            # Schedule the job with the calendar's refresh interval (in minutes)
            job_id = f"refresh_calendar_{calendar.id}"
            
            # Remove any existing job with this ID
            scheduler.remove_job(job_id, ignore_if_not_exists=True)
            
            # Schedule a new job
            scheduler.add_job(
                refresh_calendar_events,
                'interval',
                minutes=calendar.refresh_interval,
                id=job_id,
                replace_existing=True,
                args=[calendar]
            )
            
            logging.info(f"Scheduled refresh job for calendar {calendar.id} ('{calendar.name}') every {calendar.refresh_interval} minutes")
    
    except Exception as e:
        logging.error(f"Error setting up calendar refresh jobs: {e}")

def start_scheduler():
    """Start the background scheduler for calendar refreshing"""
    if not scheduler.running:
        scheduler.start()
        setup_calendar_refresh_jobs()
        logging.info("Calendar refresh scheduler started")

def update_calendar_refresh_interval(calendar_id, refresh_interval):
    """Update the refresh interval for a calendar and reschedule the job"""
    try:
        calendar = Calendar.query.get(calendar_id)
        if not calendar:
            return False, "Calendar not found"
        
        # Update the refresh interval
        calendar.refresh_interval = refresh_interval
        db.session.commit()
        
        # Reschedule the job
        if scheduler.running:
            # Remove existing job
            job_id = f"refresh_calendar_{calendar.id}"
            scheduler.remove_job(job_id, ignore_if_not_exists=True)
            
            # Add new job with updated interval
            scheduler.add_job(
                refresh_calendar_events,
                'interval',
                minutes=refresh_interval,
                id=job_id,
                replace_existing=True,
                args=[calendar]
            )
        
        return True, None
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating calendar refresh interval: {e}")
        return False, str(e)
