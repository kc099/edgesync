document.addEventListener('DOMContentLoaded', function() {
    // Get URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const activeTab = urlParams.get('tab') || 'login';

    // Tab switching functionality
    const tabs = document.querySelectorAll('.auth-tab');
    const forms = document.querySelectorAll('.auth-form');

    function switchTab(tabName) {
        // Update active tab
        tabs.forEach(tab => {
            if (tab.dataset.tab === tabName) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });

        // Show active form
        forms.forEach(form => {
            if (form.id === `${tabName}-form`) {
                form.classList.add('active');
            } else {
                form.classList.remove('active');
            }
        });

        // Update URL without page reload
        const newUrl = `${window.location.pathname}?tab=${tabName}`;
        window.history.pushState({ tab: tabName }, '', newUrl);
    }

    // Initialize active tab from URL
    switchTab(activeTab);

    // Add click handlers to tabs
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            switchTab(tab.dataset.tab);
        });
    });

    // Form validation
    const loginForm = document.getElementById('login-form');
    const signupForm = document.getElementById('signup-form');

    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            const email = this.querySelector('#id_login').value;
            const password = this.querySelector('#id_password').value;

            if (!email || !password) {
                e.preventDefault();
                showError('Please fill in all fields');
            }
        });
    }

    if (signupForm) {
        signupForm.addEventListener('submit', function(e) {
            const email = this.querySelector('#id_email').value;
            const password1 = this.querySelector('#id_password1').value;
            const password2 = this.querySelector('#id_password2').value;
            const terms = this.querySelector('input[name="terms"]').checked;

            if (!email || !password1 || !password2) {
                e.preventDefault();
                showError('Please fill in all fields');
                return;
            }

            if (password1.length < 8) {
                e.preventDefault();
                showError('Password must be at least 8 characters long');
                return;
            }

            if (password1 !== password2) {
                e.preventDefault();
                showError('Passwords do not match');
                return;
            }

            if (!terms) {
                e.preventDefault();
                showError('Please agree to the Terms of Service and Privacy Policy');
                return;
            }
        });
    }

    function showError(message) {
        const activeForm = document.querySelector('.auth-form.active');
        let alertDiv = activeForm.querySelector('.alert');

        if (!alertDiv) {
            alertDiv = document.createElement('div');
            alertDiv.className = 'alert alert-error';
            activeForm.insertBefore(alertDiv, activeForm.firstChild);
        }

        alertDiv.textContent = message;
    }

    // Password visibility toggle
    const passwordInputs = document.querySelectorAll('input[type="password"]');
    passwordInputs.forEach(input => {
        const wrapper = document.createElement('div');
        wrapper.className = 'password-wrapper';
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'password-toggle';
        toggle.innerHTML = '<i class="fas fa-eye"></i>';
        wrapper.appendChild(toggle);

        toggle.addEventListener('click', () => {
            const type = input.type === 'password' ? 'text' : 'password';
            input.type = type;
            toggle.innerHTML = `<i class="fas fa-eye${type === 'password' ? '' : '-slash'}"></i>`;
        });
    });
}); 