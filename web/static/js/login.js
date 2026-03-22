// Login page JavaScript

const loginForm = document.getElementById('loginForm');
const errorMessage = document.getElementById('errorMessage');
const usernameInput = document.getElementById('username');
const passwordInput = document.getElementById('password');
const submitButton = loginForm.querySelector('button[type="submit"]');
const btnText = submitButton.querySelector('.btn-text');
const btnLoader = submitButton.querySelector('.btn-loader');

loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = usernameInput.value.trim();
    const password = passwordInput.value;
    
    if (!username || !password) {
        showError('Please enter username and password');
        return;
    }
    
    // Show loading state
    submitButton.disabled = true;
    btnText.style.display = 'none';
    btnLoader.style.display = 'flex';
    errorMessage.style.display = 'none';
    
    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password }),
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
        }
        
        const data = await response.json();
        
        // Store token and user info
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('username', data.username);
        localStorage.setItem('role', data.role);
        
        // Redirect to dashboard
        window.location.href = '/dashboard';
        
    } catch (error) {
        showError(error.message || 'Login failed. Please try again.');
        submitButton.disabled = false;
        btnText.style.display = 'block';
        btnLoader.style.display = 'none';
    }
});

function showError(message) {
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';
}

// Check if already logged in
const token = localStorage.getItem('access_token');
if (token) {
    // Verify token is still valid
    fetch('/api/status', {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    })
    .then(response => {
        if (response.ok) {
            window.location.href = '/dashboard';
        }
    })
    .catch(() => {
        // Token invalid, stay on login page
        localStorage.removeItem('access_token');
        localStorage.removeItem('username');
        localStorage.removeItem('role');
    });
}
