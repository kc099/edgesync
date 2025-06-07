 Multi-Tenant IoT Platform Improvements

  I've successfully implemented all the requested improvements to your EdgeSync IoT platform. Here's what has been completed:

  🔧 Key Changes Made:

  1. New User App Architecture

  - ✅ Created separate user Django app for user management
  - ✅ Added UserProfile model with subscription types (free, freemium, paid)
  - ✅ Moved MQTT-related models (MosquittoUser, MosquittoACL, etc.) to user app
  - ✅ Added device history tracking with DeviceHistory model

  2. Updated MQTT Configuration

  - ✅ MQTT Broker IP: Updated to 13.203.165.247
  - ✅ Auth Database: Remains at 68.178.150.182 (as specified)
  - ✅ New Password Flow: "Set Password" → "Connect" instead of "Generate Password"

  3. Enhanced User Management

  - ✅ Subscription Types: Free (5 devices), Freemium, Paid
  - ✅ Device Limits: Enforced based on subscription level
  - ✅ Auto Profile Creation: UserProfile created automatically for new users
  - ✅ MQTT Username Generation: Improved handling for OAuth users

  4. New Password Workflow

  - ✅ Set Password: Users can set custom MQTT passwords (min 8 chars)
  - ✅ Connect Button: Only appears after password is set
  - ✅ Status Tracking: Visual feedback for password and connection status
  - ✅ Database Integration: Creates mosquitto_users entries only when needed

  🎯 How It Works Now:

  1. User Signs Up: via Google OAuth or email
  2. UserProfile Created: Automatically with default settings (free tier, 5 device limit)
  3. Set MQTT Password: User clicks "Set Password" and enters custom password
  4. Password Stored: Creates entry in mosquitto_users table with PBKDF2 hash
  5. Connect to MQTT: User can then connect to broker at 13.203.165.247:1883
  6. Device Registration: Creates proper ACLs and enforces device limits

  📊 New Models Structure:

  user/
  ├── UserProfile (subscription, limits, MQTT status)
  ├── MosquittoUser (MQTT auth table)
  ├── MosquittoACL (topic permissions)
  ├── DeviceHistory (activity tracking)
  └── UserACL (user-based topic patterns)

  sensors/
  ├── SensorData (unchanged)
  └── Device (unchanged)

  🔐 Security Improvements:

  - ✅ PBKDF2 password hashing for MQTT compatibility
  - ✅ User can only access their own devices/topics
  - ✅ Device limits prevent abuse
  - ✅ Proper topic-based ACL creation

  The system is now running successfully with all the requested improvements. Users who sign up via Google/email will need to set an MQTT password before they can connect
  devices to your mosquitto broker at 13.203.165.247.