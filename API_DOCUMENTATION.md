# EdgeSync API Documentation

## Overview

The EdgeSync Multi-Tenant IoT Platform provides a comprehensive REST API for managing IoT devices, sensor data, flow diagrams, and user organizations. The API is built using Django REST Framework and documented using OpenAPI 3.0 specifications.

## Accessing the API Documentation

### Swagger UI
Interactive API documentation with testing capabilities:
```
http://localhost:8000/api/docs/
```

### ReDoc
Alternative documentation interface with better readability:
```
http://localhost:8000/api/redoc/
```

### OpenAPI Schema
Raw OpenAPI 3.0 schema in JSON format:
```
http://localhost:8000/api/schema/
```

## Authentication

The API uses JWT (JSON Web Token) authentication. Most endpoints require authentication.

### Getting an Access Token

1. **Get Public Key** (for encryption):
   ```
   GET /api/public-key/
   ```

2. **Login** (with encrypted credentials):
   ```
   POST /api/login/
   ```

3. **Use Token in Headers**:
   ```
   Authorization: Bearer <your_access_token>
   ```

### Token Refresh
```
POST /api/token/refresh/
```

## API Endpoints Overview

### Authentication Endpoints
- `GET /api/public-key/` - Get RSA public key for encryption
- `POST /api/login/` - User login with encrypted credentials
- `POST /api/signup/` - User registration with encrypted credentials
- `POST /api/logout/` - User logout (blacklist refresh token)
- `POST /api/token/refresh/` - Refresh access token

### User Management
- `GET /api/profile/` - Get current user profile
- `GET /api/organizations/` - List user organizations
- `POST /api/organizations/` - Create new organization
- `GET /api/organizations/{id}/` - Get organization details
- `PUT /api/organizations/{id}/` - Update organization
- `DELETE /api/organizations/{id}/` - Delete organization

### Dashboard Templates
- `GET /api/dashboard-templates/` - List dashboard templates
- `POST /api/dashboard-templates/` - Create dashboard template
- `GET /api/dashboard-templates/{uuid}/` - Get template details
- `PUT /api/dashboard-templates/{uuid}/` - Update template
- `DELETE /api/dashboard-templates/{uuid}/` - Delete template

### Device Management
- `GET /api/devices/` - List user devices
- `POST /api/devices/` - Register new device
- `GET /api/devices/{device_id}/` - Get device details
- `PATCH /api/devices/{device_id}/` - Update device
- `DELETE /api/devices/{device_id}/` - Delete device

### Sensor Data
- `GET /api/data/` - List sensor data (with filtering)
- `GET /api/summary/` - Get sensor data summary statistics
- `GET /api/latest/` - Get latest sensor readings

### MQTT Management
- `GET /api/mqtt-clusters/` - List MQTT clusters
- `POST /api/mqtt-clusters/` - Create MQTT cluster
- `GET /api/mqtt-clusters/{uuid}/` - Get cluster details
- `PUT /api/mqtt-clusters/{uuid}/` - Update cluster
- `DELETE /api/mqtt-clusters/{uuid}/` - Delete cluster
- `POST /api/mqtt-clusters/{uuid}/test/` - Test MQTT connection

### Flow Diagrams
- `GET /api/flows/` - List flow diagrams
- `POST /api/flows/` - Create flow diagram
- `GET /api/flows/{uuid}/` - Get flow details
- `PUT /api/flows/{uuid}/` - Update flow
- `DELETE /api/flows/{uuid}/` - Delete flow
- `POST /api/flows/{uuid}/execute/` - Execute flow
- `POST /api/flows/{uuid}/duplicate/` - Duplicate flow
- `GET /api/flows/templates/` - Get flow templates

## Request/Response Format

All API endpoints use JSON format for request and response bodies.

### Standard Response Format
```json
{
  "status": "success",
  "data": { ... },
  "message": "Optional message"
}
```

### Error Response Format
```json
{
  "status": "error",
  "error": "Error description",
  "details": { ... }
}
```

## Filtering and Pagination

### Sensor Data Filtering
```
GET /api/data/?device_id=sensor01&sensor_type=temperature&ordering=-timestamp
```

### Pagination
Most list endpoints support pagination:
```
GET /api/data/?page=2&page_size=50
```

## Security Considerations

### Encrypted Authentication
Login and signup endpoints require encrypted data:
```json
{
  "data": "encrypted_credentials",
  "key": "encrypted_aes_key", 
  "iv": "initialization_vector"
}
```

### JWT Token Security
- Tokens expire after 60 minutes
- Refresh tokens are valid for 7 days
- Tokens are blacklisted on logout

## Rate Limiting

API endpoints may be rate-limited to prevent abuse. Check response headers for rate limit information.

## Error Codes

| Code | Description |
|------|-------------|
| 200  | Success |
| 201  | Created |
| 400  | Bad Request |
| 401  | Unauthorized |
| 403  | Forbidden |
| 404  | Not Found |
| 429  | Too Many Requests |
| 500  | Internal Server Error |

## Examples

### Register a New Device
```bash
curl -X POST "http://localhost:8000/api/devices/" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "deviceId": "sensor001",
    "deviceName": "Temperature Sensor 1", 
    "deviceType": "temperature",
    "tenantId": "tenant123"
  }'
```

### Get Sensor Data Summary
```bash
curl -X GET "http://localhost:8000/api/summary/?device_id=sensor001" \
  -H "Authorization: Bearer <token>"
```

### Create Flow Diagram
```bash
curl -X POST "http://localhost:8000/api/flows/" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Flow",
    "description": "IoT data processing flow",
    "nodes": [...],
    "edges": [...]
  }'
```

## SDKs and Client Libraries

### JavaScript/TypeScript
```javascript
// Example using fetch API
const response = await fetch('/api/devices/', {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  }
});
const devices = await response.json();
```

### Python
```python
import requests

headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}

response = requests.get('http://localhost:8000/api/devices/', headers=headers)
devices = response.json()
```

## Development and Testing

### Running the API Server
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start development server
python manage.py runserver

# Test Swagger setup
python test_swagger.py
```

### Testing with Postman

1. Import the OpenAPI schema from `http://localhost:8000/api/schema/`
2. Set up environment variables for base URL and tokens
3. Use the authentication endpoints to get access tokens
4. Test various endpoints with proper authentication

## Support

For API support and questions:
- Check the interactive Swagger UI documentation
- Review the source code in the respective app directories
- Consult the Django REST Framework documentation

## Changelog

### Version 1.0.0
- Initial API implementation
- JWT authentication
- Device management
- Sensor data collection
- MQTT cluster management  
- Flow diagram creation and execution
- Organization and user management
- Comprehensive OpenAPI documentation 