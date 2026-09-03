/**
 * Auth JS - Login and Registration form handling
 */

document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');

    if (loginForm) initLoginForm(loginForm);
    if (registerForm) initRegisterForm(registerForm);

    // Password visibility toggles
    document.querySelectorAll('.toggle-password').forEach(btn => {
        btn.addEventListener('click', () => {
            const input = document.querySelector(btn.dataset.target);
            if (input) {
                input.type = input.type === 'password' ? 'text' : 'password';
                btn.querySelector('i').classList.toggle('bi-eye');
                btn.querySelector('i').classList.toggle('bi-eye-slash');
            }
        });
    });
});

function initLoginForm(form) {
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        clearErrors();

        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;
        const submitBtn = form.querySelector('[type="submit"]');

        if (!username || !password) {
            Toast.error('Please fill in all fields');
            return;
        }

        setLoading(submitBtn, true, 'Signing in...');

        const data = await API.post('/auth/login', { username, password });

        setLoading(submitBtn, false, 'Sign In');

        if (data && data._ok) {
            TokenManager.setTokens(data.access_token, data.refresh_token);
            TokenManager.setUser(data.user);
            Toast.success('Welcome back!');
            setTimeout(() => { window.location.href = '/dashboard'; }, 500);
        } else {
            const msg = data?.error || 'Login failed. Please check your credentials.';
            showError('password', msg);
            Toast.error(msg);
        }
    });
}

function initRegisterForm(form) {
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        clearErrors();

        const username = document.getElementById('username').value.trim();
        const email = document.getElementById('email').value.trim();
        const fullName = document.getElementById('full_name').value.trim();
        const phone = document.getElementById('phone').value.trim();
        const role = document.getElementById('role').value;
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirm_password').value;
        const submitBtn = form.querySelector('[type="submit"]');

        // Frontend validations
        if (!username || username.length < 3) {
            showError('username', 'Username must be at least 3 characters');
            return;
        }
        if (!email || !isValidEmail(email)) {
            showError('email', 'Enter a valid email address');
            return;
        }
        if (!password || !isValidPassword(password)) {
            showError('password', 'Password must be 8+ chars with uppercase, lowercase and number');
            return;
        }
        if (password !== confirmPassword) {
            showError('confirm_password', 'Passwords do not match');
            return;
        }

        setLoading(submitBtn, true, 'Creating account...');

        const data = await API.post('/auth/register', {
            username, email, password, role,
            full_name: fullName, phone
        });

        setLoading(submitBtn, false, 'Create Account');

        if (data && data._ok) {
            TokenManager.setTokens(data.access_token, data.refresh_token);
            TokenManager.setUser(data.user);
            Toast.success('Account created successfully!');
            setTimeout(() => { window.location.href = '/dashboard'; }, 500);
        } else {
            const msg = data?.error || 'Registration failed';
            Toast.error(msg);
            if (msg.includes('username')) showError('username', msg);
            else if (msg.includes('email')) showError('email', msg);
        }
    });

    // Password strength indicator
    const passwordInput = document.getElementById('password');
    if (passwordInput) {
        passwordInput.addEventListener('input', () => {
            updatePasswordStrength(passwordInput.value);
        });
    }
}

function updatePasswordStrength(password) {
    const indicator = document.getElementById('password-strength');
    if (!indicator) return;

    let strength = 0;
    if (password.length >= 8) strength++;
    if (/[A-Z]/.test(password)) strength++;
    if (/[a-z]/.test(password)) strength++;
    if (/\d/.test(password)) strength++;
    if (/[^A-Za-z0-9]/.test(password)) strength++;

    const labels = ['', 'Very Weak', 'Weak', 'Fair', 'Strong', 'Very Strong'];
    const colors = ['', 'danger', 'warning', 'info', 'primary', 'success'];

    indicator.innerHTML = password ? `
        <div class="progress mt-2" style="height:4px">
            <div class="progress-bar bg-${colors[strength]}" style="width:${strength * 20}%"></div>
        </div>
        <small class="text-${colors[strength]}">${labels[strength]}</small>
    ` : '';
}

function showError(fieldId, message) {
    const field = document.getElementById(fieldId);
    if (field) {
        field.classList.add('is-invalid');
        const feedback = field.parentElement.querySelector('.invalid-feedback');
        if (feedback) feedback.textContent = message;
        else {
            const div = document.createElement('div');
            div.className = 'invalid-feedback d-block';
            div.textContent = message;
            field.parentElement.appendChild(div);
        }
    }
}

function clearErrors() {
    document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
    document.querySelectorAll('.invalid-feedback').forEach(el => el.textContent = '');
}

function setLoading(btn, loading, text) {
    if (!btn) return;
    btn.disabled = loading;
    btn.innerHTML = loading
        ? `<span class="spinner-border spinner-border-sm me-2"></span>${text}`
        : text;
}

function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function isValidPassword(password) {
    return password.length >= 8 &&
        /[A-Z]/.test(password) &&
        /[a-z]/.test(password) &&
        /\d/.test(password);
}
