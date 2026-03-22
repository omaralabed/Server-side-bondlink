// Login page JavaScript

const loginForm     = document.getElementById('loginForm');
const errorMessage  = document.getElementById('errorMessage');
const usernameInput = document.getElementById('username');
const passwordInput = document.getElementById('password');
const submitButton  = loginForm.querySelector('button[type="submit"]');
const btnText       = submitButton.querySelector('.btn-text');
const btnLoader     = submitButton.querySelector('.btn-loader');

// Helper: reset the submit button back to its idle state
function resetButton() {
    submitButton.disabled   = false;
    btnText.style.display   = 'block';
    btnLoader.style.display = 'none';
}

// Helper: show an error message in the form
function showError(message) {
    errorMessage.textContent    = message;
    errorMessage.style.display  = 'block';
}

loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const username = usernameInput.value.trim();
    const password = passwordInput.value;       // don't trim passwords

    if (!username || !password) {
        showError('Please enter username and password');
        return;
    }

    // Show loading state and hide any previous error
    submitButton.disabled       = true;
    btnText.style.display       = 'none';
    btnLoader.style.display     = 'flex';
    errorMessage.style.display  = 'none';

    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
        }

        const data = await response.json();

        // Store token and user info
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('username',     data.username);
        localStorage.setItem('role',         data.role);

        // Redirect — keep button disabled so user can't double-submit during navigation
        window.location.href = '/dashboard';

    } catch (error) {
        showError(error.message || 'Login failed. Please try again.');
        // Bug fix: re-enable the button so the user can try again
        resetButton();
    }
});

// If already logged in, verify the token is still valid then redirect
const existingToken = localStorage.getItem('access_token');
if (existingToken) {
    fetch('/api/status', {
        headers: { 'Authorization': `Bearer ${existingToken}` }
    })
    .then(response => {
        if (response.ok) {
            window.location.href = '/dashboard';
        } else {
            // Token is invalid/expired — clear ALL stored credentials
            // Bug fix: was only removing access_token, leaving username and role behind
            localStorage.removeItem('access_token');
            localStorage.removeItem('username');
            localStorage.removeItem('role');
        }
    })
    .catch(() => {
        // Network error — clear ALL stored credentials so login form is clean
        localStorage.removeItem('access_token');
        localStorage.removeItem('username');
        localStorage.removeItem('role');
    });
}
