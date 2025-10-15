// Global variables
let userLocation = {
    latitude: null,
    longitude: null,
    country: '',
    city: ''
};

// Get geolocation on page load
document.addEventListener('DOMContentLoaded', function() {
    // Load initial count
    updateCount();
    
    // Request geolocation
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            handleGeolocationSuccess,
            handleGeolocationError,
            { timeout: 10000, enableHighAccuracy: false }
        );
    } else {
        console.log('Geolocation is not supported by this browser.');
        fallbackIPLookup();
    }
    
    // Setup form submission
    const form = document.getElementById('waitlistForm');
    form.addEventListener('submit', handleFormSubmit);
});

// Handle successful geolocation
function handleGeolocationSuccess(position) {
    userLocation.latitude = position.coords.latitude;
    userLocation.longitude = position.coords.longitude;
    
    // Reverse geocode to get country and city
    reverseGeocode(userLocation.latitude, userLocation.longitude);
}

// Handle geolocation error
function handleGeolocationError(error) {
    console.log('Geolocation error:', error.message);
    
    // Fallback to IP-based lookup
    fallbackIPLookup();
}

// Reverse geocode coordinates to get country and city
function reverseGeocode(lat, lon) {
    // Using Nominatim (OpenStreetMap) for reverse geocoding - free and no API key required
    fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=10`)
        .then(response => response.json())
        .then(data => {
            if (data.address) {
                userLocation.country = data.address.country || '';
                userLocation.city = data.address.city || data.address.town || data.address.village || '';
            }
        })
        .catch(error => {
            console.log('Reverse geocoding failed:', error);
        });
}

// Fallback IP-based location lookup
function fallbackIPLookup() {
    // Using ipapi.co - free tier allows 1000 requests per day
    fetch('https://ipapi.co/json/')
        .then(response => response.json())
        .then(data => {
            userLocation.latitude = data.latitude || null;
            userLocation.longitude = data.longitude || null;
            userLocation.country = data.country_name || '';
            userLocation.city = data.city || '';
        })
        .catch(error => {
            console.log('IP lookup failed:', error);
            // Continue without location data
        });
}

// Update registration count
function updateCount() {
    fetch('/api/count')
        .then(response => response.json())
        .then(data => {
            const countElement = document.getElementById('registrationCount');
            countElement.textContent = data.count || 0;
        })
        .catch(error => {
            console.log('Error fetching count:', error);
        });
}

// Handle form submission
function handleFormSubmit(event) {
    event.preventDefault();
    
    const emailInput = document.getElementById('emailInput');
    const submitBtn = document.getElementById('submitBtn');
    const messageContainer = document.getElementById('messageContainer');
    const email = emailInput.value.trim();
    
    // Validate email
    if (!email || !isValidEmail(email)) {
        showMessage('Please enter a valid email address', 'error');
        return;
    }
    
    // Disable form during submission
    submitBtn.disabled = true;
    submitBtn.textContent = 'Joining...';
    
    // Prepare data
    const registrationData = {
        email: email,
        latitude: userLocation.latitude,
        longitude: userLocation.longitude,
        country: userLocation.country,
        city: userLocation.city
    };
    
    // Submit to backend
    fetch('/api/register', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(registrationData)
    })
    .then(response => response.json().then(data => ({ status: response.status, body: data })))
    .then(result => {
        if (result.status === 200 && result.body.success) {
            showMessage(result.body.message, 'success');
            emailInput.value = '';
            
            // Update count with animation
            const countElement = document.getElementById('registrationCount');
            countElement.classList.add('updated');
            countElement.textContent = result.body.count;
            setTimeout(() => {
                countElement.classList.remove('updated');
            }, 500);
            
        } else {
            showMessage(result.body.message || 'An error occurred', 'error');
        }
    })
    .catch(error => {
        console.error('Submission error:', error);
        showMessage('Network error. Please try again.', 'error');
    })
    .finally(() => {
        // Re-enable form
        submitBtn.disabled = false;
        submitBtn.textContent = 'Join Waitlist';
    });
}

// Show message to user
function showMessage(message, type) {
    const messageContainer = document.getElementById('messageContainer');
    const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
    
    messageContainer.innerHTML = `
        <div class="alert ${alertClass}" role="alert">
            ${message}
        </div>
    `;
    
    // Auto-hide success messages after 5 seconds
    if (type === 'success') {
        setTimeout(() => {
            messageContainer.innerHTML = '';
        }, 5000);
    }
}

// Email validation
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

