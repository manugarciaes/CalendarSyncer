document.addEventListener('DOMContentLoaded', function() {
    // Booking form functionality
    // This file is loaded on pages that have booking forms

    // Initialize booking form if it exists
    const bookingForm = document.getElementById('bookingForm');
    if (bookingForm) {
        initializeBookingForm(bookingForm);
    }

    // Initialize slot selection if on customer view page
    const slotSelectionElements = document.querySelectorAll('.slot-selection');
    if (slotSelectionElements.length) {
        initializeSlotSelection();
    }
});

/**
 * Initialize the booking form with validation and submission handling
 * @param {HTMLElement} form - The booking form element
 */
function initializeBookingForm(form) {
    // Add validation
    form.addEventListener('submit', function(event) {
        if (!validateBookingForm(form)) {
            event.preventDefault();
            return false;
        }
        
        // Show loading state
        const submitButton = form.querySelector('button[type="submit"]');
        const originalText = submitButton.innerHTML;
        submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
        submitButton.disabled = true;
        
        // Let the form submit normally
        return true;
    });
    
    // Initialize any date/time pickers if needed
    const dateTimeInputs = form.querySelectorAll('.datetime-picker');
    if (dateTimeInputs.length) {
        dateTimeInputs.forEach(input => {
            // Implementation would depend on your date/time picker library
            console.log('Date/time picker initialized');
        });
    }
}

/**
 * Validate the booking form before submission
 * @param {HTMLElement} form - The booking form element
 * @returns {boolean} - Whether the form is valid
 */
function validateBookingForm(form) {
    let isValid = true;
    
    // Check required fields
    const requiredFields = form.querySelectorAll('[required]');
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            isValid = false;
            field.classList.add('is-invalid');
            
            // Create or update error message
            let errorMessage = field.nextElementSibling;
            if (!errorMessage || !errorMessage.classList.contains('invalid-feedback')) {
                errorMessage = document.createElement('div');
                errorMessage.className = 'invalid-feedback';
                field.parentNode.insertBefore(errorMessage, field.nextElementSibling);
            }
            errorMessage.textContent = 'This field is required';
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    // Email validation
    const emailField = form.querySelector('input[type="email"]');
    if (emailField && emailField.value.trim() && !validateEmail(emailField.value)) {
        isValid = false;
        emailField.classList.add('is-invalid');
        
        // Create or update error message
        let errorMessage = emailField.nextElementSibling;
        if (!errorMessage || !errorMessage.classList.contains('invalid-feedback')) {
            errorMessage = document.createElement('div');
            errorMessage.className = 'invalid-feedback';
            emailField.parentNode.insertBefore(errorMessage, emailField.nextElementSibling);
        }
        errorMessage.textContent = 'Please enter a valid email address';
    }
    
    return isValid;
}

/**
 * Validate an email address
 * @param {string} email - The email to validate
 * @returns {boolean} - Whether the email is valid
 */
function validateEmail(email) {
    const re = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
    return re.test(String(email).toLowerCase());
}

/**
 * Initialize the slot selection functionality on the customer view page
 */
function initializeSlotSelection() {
    // If using calendar for slot selection, this might be handled in calendar.js
    // This function would handle any additional slot selection UI
    
    const slotButtons = document.querySelectorAll('.slot-button');
    slotButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Clear previous selection
            slotButtons.forEach(btn => btn.classList.remove('selected', 'btn-primary'));
            btn.classList.add('btn-outline-primary');
            
            // Mark this slot as selected
            this.classList.add('selected', 'btn-primary');
            this.classList.remove('btn-outline-primary');
            
            // Update hidden form fields
            const startTime = this.getAttribute('data-start');
            const endTime = this.getAttribute('data-end');
            const slotLabel = this.getAttribute('data-label');
            
            document.getElementById('startTimeInput').value = startTime;
            document.getElementById('endTimeInput').value = endTime;
            
            // Update visible slot selection display
            const selectedSlotDisplay = document.getElementById('selectedSlot');
            if (selectedSlotDisplay) {
                selectedSlotDisplay.value = slotLabel;
            }
            
            // Show the booking form
            showBookingForm();
        });
    });
}

/**
 * Show the booking form after a slot is selected
 * @param {Object} event - Optional event data if called from calendar
 */
function showBookingForm(event) {
    const bookingForm = document.getElementById('bookingForm');
    const selectTimeMessage = document.getElementById('selectTimeMessage');
    
    if (bookingForm && selectTimeMessage) {
        // Hide message, show form
        selectTimeMessage.style.display = 'none';
        bookingForm.style.display = 'block';
        
        // If called with event data, update the form
        if (event) {
            // Update form fields based on event data
            document.getElementById('startTimeInput').value = event.start.toISOString();
            document.getElementById('endTimeInput').value = event.end.toISOString();
            
            // Format for display
            const options = { 
                weekday: 'long', 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            };
            const formattedStart = event.start.toLocaleString('en-US', options);
            const formattedEnd = event.end.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
            
            document.getElementById('selectedSlot').value = `${formattedStart} - ${formattedEnd}`;
        }
    }
}
