# Google OAuth Setup Guide

## Prerequisites
1. A Google Cloud Console account
2. A Firebase project (you already have this)

## Step 1: Configure Google OAuth in Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (quizora-c2123)
3. Navigate to "APIs & Services" > "Credentials"
4. Click "Create Credentials" > "OAuth 2.0 Client IDs"
5. Choose "Web application" as the application type
6. Add the following authorized redirect URIs:
   - `http://localhost:5000/google/callback` (for development)
   - `https://yourdomain.com/google/callback` (for production)
7. Click "Create"
8. Copy the Client ID and Client Secret

## Step 2: Update the Configuration

In `app.py`, replace the placeholder values with your actual credentials:

```python
# Google OAuth Configuration
GOOGLE_CLIENT_ID = "your-actual-client-id.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "your-actual-client-secret"
GOOGLE_REDIRECT_URI = "http://localhost:5000/google/callback"  # Update for production
```

## Step 3: Enable Google+ API (if needed)

1. In Google Cloud Console, go to "APIs & Services" > "Library"
2. Search for "Google+ API" or "Google Identity API"
3. Enable it if not already enabled

## Step 3.5: Configure OAuth Consent Screen

To change the project name from "project-10741631728" to "Quizora":

1. In Google Cloud Console, go to "APIs & Services" > "OAuth consent screen"
2. Choose "External" user type (unless you have a Google Workspace organization)
3. Fill in the required information:
   - **App name**: Quizora
   - **User support email**: Your email address
   - **App logo**: Upload a logo for your app (optional)
   - **Application home page**: Your app's URL
   - **Application privacy policy link**: Your privacy policy URL (optional)
   - **Application terms of service link**: Your terms of service URL (optional)
4. Add authorized domains:
   - Add `localhost` for development
   - Add your production domain when ready
5. Add scopes:
   - `openid`
   - `email`
   - `profile`
6. Add test users (optional for development)
7. Click "Save and Continue"
8. Review and publish (or keep in testing mode)

## Step 4: Test the Integration

1. Run your Flask application
2. Go to the login page
3. Click "Sign in with Google"
4. You should be redirected to Google's OAuth page
5. Only @somaiya.edu emails will be accepted

## Security Notes

- Keep your Client Secret secure and never commit it to version control
- Consider using environment variables for sensitive configuration
- In production, use HTTPS for all OAuth redirects
- The domain restriction (@somaiya.edu) is enforced both on the frontend and backend

## Troubleshooting

- If you get "redirect_uri_mismatch" error, double-check the redirect URI in Google Cloud Console
- If authentication fails, check the browser console and Flask logs for errors
- Make sure the Google+ API is enabled in your project 