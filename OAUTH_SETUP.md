# Google OAuth Setup for EdgeSync

This guide will help you set up Google OAuth authentication for your EdgeSync Django application using Django Allauth.

## 🔧 Prerequisites

You should already have:
- ✅ Google Client ID and Secret from Google Cloud Console
- ✅ Redirect URI configured in Google Console: `http://127.0.0.1:8000/accounts/google/login/callback/`

## 📝 Step 1: Environment Configuration

1. Copy the example environment file:
```bash
cp env.example .env
```

2. Add your Google OAuth credentials to `.env`:
```env
DJANGO_SETTINGS_MODULE=edgesync.settings
DEBUG=True
SECRET_KEY=your-secret-key-here
REDIS_URL=redis://localhost:6379

# Google OAuth Credentials
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
```

## 🚀 Step 2: Database Setup

Run migrations to create the necessary database tables:
```bash
python manage.py makemigrations
python manage.py migrate
```

## 🔑 Step 3: OAuth Application Setup

Run the setup script to configure Google OAuth in Django:
```bash
python setup_oauth.py
```

This script will:
- Create the Site object for your domain
- Create the SocialApp for Google OAuth
- Configure the redirect URI
- Validate your environment variables

## 🎨 Step 4: Test the Setup

1. Start the development server:
```bash
python manage.py runserver
```

2. Visit the landing page:
```
http://127.0.0.1:8000/
```

3. Click "Login" or "Sign Up" to test authentication

## 📋 Available Authentication URLs

| URL | Description |
|-----|-------------|
| `/` | Landing page with login/signup links |
| `/accounts/login/` | Login page with Google OAuth |
| `/accounts/signup/` | Signup page with Google OAuth |
| `/accounts/logout/` | Logout confirmation |
| `/accounts/password/reset/` | Password reset |
| `/dashboard/` | Protected dashboard (requires login) |

## 🎯 Features Implemented

### ✅ Complete Authentication System
- **Email-based login/signup** with password validation
- **Google OAuth integration** with account merging
- **Password reset** functionality
- **Remember me** option
- **Responsive design** matching your landing page

### ✅ User Experience
- **Tab-based interface** for login/signup
- **Form validation** with error messages
- **Password visibility toggle**
- **Professional styling** with EdgeSync branding
- **Mobile-responsive** design

### ✅ Security Features
- **Account merging** - Google accounts automatically link to existing email accounts
- **CSRF protection** on all forms
- **Session management** with remember me option
- **Secure redirect** handling after login

### ✅ UI/UX Features
- **Consistent styling** with landing page theme
- **Animated interactions** and hover effects
- **Error state handling** with visual feedback
- **Loading states** and transitions
- **Accessibility** considerations

## 🔍 Template Structure

```
templates/
├── base.html                    # Base template with navigation
├── landing.html                 # Landing page
├── auth.html                    # Main authentication template
├── account/
│   ├── login.html              # Login page (extends auth.html)
│   ├── signup.html             # Signup page (extends auth.html)
│   ├── logout.html             # Logout confirmation
│   └── password_reset.html     # Password reset form
└── socialaccount/
    └── login_cancelled.html    # OAuth cancellation page
```

## 🎨 Styling

The authentication pages use:
- **EdgeSync color scheme** (`--primary-color: #2563eb`)
- **Inter font family** for consistency
- **CSS variables** from your landing page
- **Responsive design** with mobile breakpoints
- **Smooth animations** and transitions

## 🔧 Customization

### Changing OAuth Providers
To add more OAuth providers (Facebook, GitHub, etc.), update `settings.py`:

```python
INSTALLED_APPS = [
    # ... existing apps ...
    'allauth.socialaccount.providers.facebook',
    'allauth.socialaccount.providers.github',
]

SOCIALACCOUNT_PROVIDERS = {
    'google': { ... },
    'facebook': {
        'APP': {
            'client_id': os.getenv('FACEBOOK_CLIENT_ID'),
            'secret': os.getenv('FACEBOOK_CLIENT_SECRET'),
        }
    }
}
```

### Customizing Redirects
Update these settings in `settings.py`:

```python
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'
ACCOUNT_EMAIL_VERIFICATION = 'none'  # or 'mandatory'
```

### Custom Error Messages
Override allauth templates in `templates/account/` to customize error messages and form layouts.

## 🐛 Troubleshooting

### Common Issues

1. **"Social application not found"**
   - Run `python setup_oauth.py` again
   - Check your `.env` file has correct credentials

2. **OAuth callback error**
   - Verify redirect URI in Google Console: `http://127.0.0.1:8000/accounts/google/login/callback/`
   - Ensure you're using `http://127.0.0.1:8000` not `localhost`

3. **CSS not loading**
   - Run `python manage.py collectstatic`
   - Check `STATICFILES_DIRS` in settings.py

4. **Template not found**
   - Verify `templates/` directory is in `TEMPLATES['DIRS']`
   - Check template inheritance is correct

### Debug Mode
For debugging, check these settings in `settings.py`:
```python
DEBUG = True
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'http'
```

## 🎉 Success!

You now have a complete OAuth authentication system with:
- Professional login/signup pages
- Google OAuth integration
- Account merging capabilities
- Responsive, branded design
- Secure authentication flow

Users can now sign up with email or Google, and the system will automatically merge accounts with the same email address. 