document.addEventListener('DOMContentLoaded', function() {
    // Calendar view functionality
    // This file is loaded on pages that display a calendar

    // Initialize calendar if the element exists
    const calendarEl = document.getElementById('calendar');
    if (calendarEl) {
        initializeCalendar(calendarEl);
    }

    // Initialize date range picker if it exists
    const dateRangeElement = document.getElementById('dateRangePicker');
    if (dateRangeElement) {
        initializeDateRange(dateRangeElement);
    }
});

/**
 * Initialize the FullCalendar instance
 * @param {HTMLElement} element - The container element for the calendar
 */
function initializeCalendar(element) {
    const calendar = new FullCalendar.Calendar(element, {
        initialView: 'timeGridWeek',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay'
        },
        allDaySlot: false,
        slotDuration: '00:30:00',
        slotLabelInterval: '01:00',
        slotMinTime: '09:00:00',
        slotMaxTime: '17:00:00',
        weekends: false,
        height: 'auto',
        eventTimeFormat: {
            hour: '2-digit',
            minute: '2-digit',
            meridiem: 'short'
        },
        slotLabelFormat: {
            hour: '2-digit',
            minute: '2-digit',
            hour12: true
        },
        themeSystem: 'bootstrap5',
        // Additional event handlers can be added here
        eventClick: function(info) {
            handleEventClick(info);
        },
        dateClick: function(info) {
            handleDateClick(info);
        }
    });

    calendar.render();
    
    // Store calendar instance as a global variable for other scripts to access
    window.calendarInstance = calendar;
    
    return calendar;
}

/**
 * Handle event click interactions
 * @param {Object} info - The event information from FullCalendar
 */
function handleEventClick(info) {
    // Default implementation, can be overridden by page-specific scripts
    console.log('Event clicked:', info.event.title);
    
    // If this is a bookable event, we may want to show booking form
    if (typeof showBookingForm === 'function' && info.event.extendedProps.bookable) {
        showBookingForm(info.event);
    }
}

/**
 * Handle date click interactions
 * @param {Object} info - The date information from FullCalendar
 */
function handleDateClick(info) {
    // Default implementation, can be overridden by page-specific scripts
    console.log('Date clicked:', info.dateStr);
}

/**
 * Initialize date range picker
 * @param {HTMLElement} element - The container element for the date range picker
 */
function initializeDateRange(element) {
    // Implementation would depend on the date range picker library
    console.log('Date range picker initialized');
}

/**
 * Refresh events on the calendar from the server
 * @param {Object} options - Options for the refresh, including date range
 */
function refreshEvents(options = {}) {
    if (!window.calendarInstance) return;
    
    const calendar = window.calendarInstance;
    const startDate = options.startDate || calendar.view.activeStart;
    const endDate = options.endDate || calendar.view.activeEnd;
    
    // Remove existing events
    calendar.removeAllEvents();
    
    // Show loading state
    calendar.setOption('loading', true);
    
    // Fetch new events from server
    fetchEvents(startDate, endDate)
        .then(events => {
            // Add events to calendar
            events.forEach(event => calendar.addEvent(event));
            calendar.setOption('loading', false);
        })
        .catch(error => {
            console.error('Error fetching events:', error);
            calendar.setOption('loading', false);
        });
}

/**
 * Fetch events from the server
 * @param {Date} startDate - Start date for events
 * @param {Date} endDate - End date for events
 * @returns {Promise<Array>} - Promise resolving to array of events
 */
function fetchEvents(startDate, endDate) {
    // Format dates for API
    const startStr = startDate.toISOString();
    const endStr = endDate.toISOString();
    
    // Implement the actual fetch logic based on your API
    return fetch(`/api/events?start=${startStr}&end=${endStr}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch events');
            }
            return response.json();
        })
        .then(data => data.events || []);
}
