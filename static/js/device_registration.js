// Device Registration JavaScript
class DeviceManager {
    constructor() {
        this.devices = [];
        this.currentDevice = null;
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadDevices();
        this.loadMqttInfo();
        this.updateTenantId();
        this.updateTopicPreview();
    }

    bindEvents() {
        // Form submission
        document.getElementById('deviceRegistrationForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.registerDevice();
        });

        // Form reset
        document.getElementById('deviceRegistrationForm').addEventListener('reset', () => {
            setTimeout(() => this.updateTopicPreview(), 100);
        });

        // Update topic preview on input change
        ['deviceId', 'deviceType'].forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('input', () => this.updateTopicPreview());
            }
        });

        // Filters
        document.getElementById('statusFilter').addEventListener('change', () => this.filterDevices());
        document.getElementById('typeFilter').addEventListener('change', () => this.filterDevices());

        // Modal close
        document.querySelector('.close').addEventListener('click', () => this.closeModal());
        document.getElementById('deviceModal').addEventListener('click', (e) => {
            if (e.target.id === 'deviceModal') {
                this.closeModal();
            }
        });
    }

    updateTenantId() {
        // This will be set when MQTT info is loaded
        document.getElementById('tenantId').value = 'Loading...';
    }

    updateTopicPreview() {
        const deviceId = document.getElementById('deviceId').value || '[device_id]';
        const tenantId = document.getElementById('tenantId').value || '[tenant]';
        const topicPattern = `iot/${tenantId}/${deviceId}/data`;
        document.getElementById('topicPreview').textContent = topicPattern;
    }

    async registerDevice() {
        const formData = new FormData(document.getElementById('deviceRegistrationForm'));
        const deviceData = {
            deviceId: formData.get('deviceId'),
            deviceName: formData.get('deviceName'),
            deviceType: formData.get('deviceType'),
            tenantId: formData.get('tenantId'),
            permissions: formData.getAll('permissions')
        };

        // Validate required fields
        if (!deviceData.deviceId || !deviceData.deviceName || !deviceData.deviceType) {
            this.showAlert('Please fill in all required fields', 'error');
            return;
        }

        // Check for duplicate device ID
        if (this.devices.some(device => device.deviceId === deviceData.deviceId)) {
            this.showAlert('Device ID already exists', 'error');
            return;
        }

        try {
            this.showLoading(true);
            
            const response = await fetch('/api/devices/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify(deviceData)
            });

            const result = await response.json();

            if (response.ok) {
                this.showAlert('Device registered successfully!', 'success');
                document.getElementById('deviceRegistrationForm').reset();
                this.updateTopicPreview();
                this.loadDevices(); // Reload device list
            } else {
                throw new Error(result.message || 'Registration failed');
            }
        } catch (error) {
            console.error('Registration error:', error);
            this.showAlert(error.message || 'Failed to register device', 'error');
        } finally {
            this.showLoading(false);
        }
    }

    async loadDevices() {
        try {
            const response = await fetch('/api/devices/');
            if (response.ok) {
                this.devices = await response.json();
                this.renderDevices();
            } else {
                throw new Error('Failed to load devices');
            }
        } catch (error) {
            console.error('Load devices error:', error);
            this.showAlert('Failed to load devices', 'error');
        }
    }

    async loadMqttInfo() {
        try {
            const response = await fetch('/api/mqtt/info/');
            if (response.ok) {
                const mqttInfo = await response.json();
                
                // Update username display
                const usernameElement = document.getElementById('mqttUsername');
                if (mqttInfo.username) {
                    usernameElement.textContent = mqttInfo.username;
                    
                    // Generate tenant ID based on username
                    const tenantId = `tenant_${mqttInfo.username}`;
                    document.getElementById('tenantId').value = tenantId;
                    this.updateTopicPreview();
                } else {
                    usernameElement.textContent = 'Not Set';
                    document.getElementById('tenantId').value = 'tenant_user';
                }
                
                // Update credentials UI based on status
                this.updateCredentialsUI(mqttInfo);
                
                // Update connection status
                const connectionStatus = document.getElementById('connectionStatus');
                if (mqttInfo.connected) {
                    connectionStatus.textContent = '✅ Connected';
                    connectionStatus.style.color = '#16a34a';
                } else {
                    connectionStatus.textContent = '❌ Not Connected';
                    connectionStatus.style.color = '#dc2626';
                }
                
            } else {
                const result = await response.json();
                console.error('Failed to load MQTT info:', result.error);
                this.showAlert('Failed to load MQTT information', 'error');
                document.getElementById('mqttUsername').textContent = 'Error';
                document.getElementById('tenantId').value = 'tenant_user';
            }
        } catch (error) {
            console.error('MQTT info error:', error);
            this.showAlert('Failed to load MQTT information', 'error');
            document.getElementById('mqttUsername').textContent = 'Error';
            document.getElementById('tenantId').value = 'tenant_user';
        }
    }

    renderDevices() {
        const deviceGrid = document.getElementById('deviceGrid');
        
        if (this.devices.length === 0) {
            deviceGrid.innerHTML = `
                <div class="no-devices">
                    <p>🔌 No devices registered yet</p>
                    <p>Use the form above to register your first IoT device</p>
                </div>
            `;
            return;
        }

        deviceGrid.innerHTML = this.devices.map(device => `
            <div class="device-card" onclick="deviceManager.showDeviceDetails('${device.deviceId}')">
                <div class="device-card-header">
                    <h4 class="device-name">${device.deviceName}</h4>
                    <span class="device-status ${device.isActive ? 'active' : 'inactive'}">
                        ${device.isActive ? '🟢 Active' : '🔴 Inactive'}
                    </span>
                </div>
                <div class="device-info">
                    <div><strong>ID:</strong> ${device.deviceId}</div>
                    <div><strong>Type:</strong> ${this.formatDeviceType(device.deviceType)}</div>
                    <div><strong>Tenant:</strong> ${device.tenantId}</div>
                    <div><strong>Topic:</strong> <code>iot/${device.tenantId}/${device.deviceId}/data</code></div>
                    <div><strong>Created:</strong> ${this.formatDate(device.createdAt)}</div>
                </div>
            </div>
        `).join('');
    }

    filterDevices() {
        const statusFilter = document.getElementById('statusFilter').value;
        const typeFilter = document.getElementById('typeFilter').value;
        
        let filteredDevices = this.devices;
        
        if (statusFilter) {
            filteredDevices = filteredDevices.filter(device => 
                statusFilter === 'active' ? device.isActive : !device.isActive
            );
        }
        
        if (typeFilter) {
            filteredDevices = filteredDevices.filter(device => 
                device.deviceType === typeFilter
            );
        }
        
        this.renderFilteredDevices(filteredDevices);
    }

    renderFilteredDevices(devices) {
        const deviceGrid = document.getElementById('deviceGrid');
        
        if (devices.length === 0) {
            deviceGrid.innerHTML = `
                <div class="no-devices">
                    <p>🔍 No devices match your filters</p>
                    <p>Try adjusting your filter criteria</p>
                </div>
            `;
            return;
        }

        deviceGrid.innerHTML = devices.map(device => `
            <div class="device-card" onclick="deviceManager.showDeviceDetails('${device.deviceId}')">
                <div class="device-card-header">
                    <h4 class="device-name">${device.deviceName}</h4>
                    <span class="device-status ${device.isActive ? 'active' : 'inactive'}">
                        ${device.isActive ? '🟢 Active' : '🔴 Inactive'}
                    </span>
                </div>
                <div class="device-info">
                    <div><strong>ID:</strong> ${device.deviceId}</div>
                    <div><strong>Type:</strong> ${this.formatDeviceType(device.deviceType)}</div>
                    <div><strong>Tenant:</strong> ${device.tenantId}</div>
                    <div><strong>Topic:</strong> <code>iot/${device.tenantId}/${device.deviceId}/data</code></div>
                    <div><strong>Created:</strong> ${this.formatDate(device.createdAt)}</div>
                </div>
            </div>
        `).join('');
    }

    showDeviceDetails(deviceId) {
        const device = this.devices.find(d => d.deviceId === deviceId);
        if (!device) return;

        this.currentDevice = device;
        
        document.getElementById('modalTitle').textContent = `📱 ${device.deviceName}`;
        document.getElementById('deviceDetails').innerHTML = `
            <div class="device-detail-grid">
                <div class="detail-item">
                    <strong>Device ID:</strong>
                    <span>${device.deviceId}</span>
                </div>
                <div class="detail-item">
                    <strong>Device Name:</strong>
                    <span>${device.deviceName}</span>
                </div>
                <div class="detail-item">
                    <strong>Device Type:</strong>
                    <span>${this.formatDeviceType(device.deviceType)}</span>
                </div>
                <div class="detail-item">
                    <strong>Tenant ID:</strong>
                    <span>${device.tenantId}</span>
                </div>
                <div class="detail-item">
                    <strong>Status:</strong>
                    <span class="device-status ${device.isActive ? 'active' : 'inactive'}">
                        ${device.isActive ? '🟢 Active' : '🔴 Inactive'}
                    </span>
                </div>
                <div class="detail-item">
                    <strong>MQTT Topics:</strong>
                    <div class="topic-list">
                        <div><code>iot/${device.tenantId}/${device.deviceId}/data</code> - Data Publishing</div>
                        <div><code>iot/${device.tenantId}/${device.deviceId}/commands</code> - Commands</div>
                        <div><code>iot/${device.tenantId}/${device.deviceId}/status</code> - Device Status</div>
                    </div>
                </div>
                <div class="detail-item">
                    <strong>Permissions:</strong>
                    <div class="permission-list">
                        ${device.permissions ? device.permissions.map(p => 
                            `<span class="permission-badge">${p}</span>`
                        ).join('') : 'Read, Write, Subscribe'}
                    </div>
                </div>
                <div class="detail-item">
                    <strong>Created:</strong>
                    <span>${this.formatDate(device.createdAt)}</span>
                </div>
            </div>
        `;
        
        document.getElementById('deviceModal').style.display = 'block';
    }

    closeModal() {
        document.getElementById('deviceModal').style.display = 'none';
        this.currentDevice = null;
    }

    async editDevice() {
        if (!this.currentDevice) return;
        
        // This would typically open an edit form
        const newName = prompt('Enter new device name:', this.currentDevice.deviceName);
        if (!newName || newName === this.currentDevice.deviceName) return;

        try {
            const response = await fetch(`/api/devices/${this.currentDevice.deviceId}/`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ deviceName: newName })
            });

            if (response.ok) {
                this.showAlert('Device updated successfully!', 'success');
                this.loadDevices();
                this.closeModal();
            } else {
                throw new Error('Failed to update device');
            }
        } catch (error) {
            console.error('Update error:', error);
            this.showAlert('Failed to update device', 'error');
        }
    }

    async deleteDevice() {
        if (!this.currentDevice) return;
        
        if (!confirm(`Are you sure you want to delete "${this.currentDevice.deviceName}"? This action cannot be undone.`)) {
            return;
        }

        try {
            const response = await fetch(`/api/devices/${this.currentDevice.deviceId}/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });

            if (response.ok) {
                this.showAlert('Device deleted successfully!', 'success');
                this.loadDevices();
                this.closeModal();
            } else {
                throw new Error('Failed to delete device');
            }
        } catch (error) {
            console.error('Delete error:', error);
            this.showAlert('Failed to delete device', 'error');
        }
    }

    updateCredentialsUI(mqttInfo) {
        const setCredentialsBtn = document.getElementById('setCredentialsBtn');
        const saveCredentialsBtn = document.getElementById('saveCredentialsBtn');
        const connectBtn = document.getElementById('connectBtn');
        const usernameInput = document.getElementById('mqttUsernameInput');
        const passwordInput = document.getElementById('mqttPasswordInput');
        const credentialsStatus = document.getElementById('credentialsStatus');
        
        if (mqttInfo.passwordSet && mqttInfo.username) {
            setCredentialsBtn.style.display = 'none';
            usernameInput.style.display = 'none';
            passwordInput.style.display = 'none';
            saveCredentialsBtn.style.display = 'none';
            connectBtn.style.display = 'inline-block';
            credentialsStatus.textContent = '✅ Credentials Set';
            credentialsStatus.style.color = '#16a34a';
        } else {
            setCredentialsBtn.style.display = 'inline-block';
            connectBtn.style.display = 'none';
            credentialsStatus.textContent = '❌ Credentials Not Set';
            credentialsStatus.style.color = '#dc2626';
        }
    }

    async setMqttCredentials() {
        const usernameInput = document.getElementById('mqttUsernameInput');
        const passwordInput = document.getElementById('mqttPasswordInput');
        const username = usernameInput.value.trim();
        const password = passwordInput.value.trim();
        
        if (!username || username.length < 3) {
            this.showAlert('Username must be at least 3 characters long', 'error');
            return;
        }
        
        if (!/^[a-zA-Z0-9_]+$/.test(username)) {
            this.showAlert('Username can only contain letters, numbers, and underscores', 'error');
            return;
        }
        
        if (!password || password.length < 8) {
            this.showAlert('Password must be at least 8 characters long', 'error');
            return;
        }
        
        try {
            const response = await fetch('/api/mqtt/set-password/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ 
                    username: username,
                    password: password
                })
            });

            const result = await response.json();

            if (response.ok) {
                this.showAlert('MQTT credentials set successfully!', 'success');
                usernameInput.value = '';
                passwordInput.value = '';
                // Reload MQTT info to update UI
                this.loadMqttInfo();
            } else {
                throw new Error(result.error || 'Failed to set credentials');
            }
        } catch (error) {
            console.error('Credentials setting error:', error);
            this.showAlert('Failed to set credentials: ' + error.message, 'error');
        }
    }

    async connectToMqtt() {
        // For now, this is a placeholder for actual MQTT connection logic
        // In a real implementation, you would establish an MQTT connection here
        try {
            this.showAlert('Attempting to connect to MQTT broker...', 'info');
            
            // Simulate connection attempt
            setTimeout(() => {
                // Update connection status
                const connectionStatus = document.getElementById('connectionStatus');
                connectionStatus.textContent = '✅ Connected';
                connectionStatus.style.color = '#16a34a';
                this.showAlert('Successfully connected to MQTT broker!', 'success');
            }, 2000);
            
        } catch (error) {
            console.error('MQTT connection error:', error);
            this.showAlert('Failed to connect to MQTT broker', 'error');
        }
    }

    formatDeviceType(type) {
        return type.split('_').map(word => 
            word.charAt(0).toUpperCase() + word.slice(1)
        ).join(' ');
    }

    formatDate(dateString) {
        if (!dateString) return 'N/A';
        return new Date(dateString).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    showAlert(message, type = 'info') {
        // Remove existing alerts
        const existingAlert = document.querySelector('.alert');
        if (existingAlert) {
            existingAlert.remove();
        }

        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.innerHTML = `
            <div class="alert-content">
                <span class="alert-icon">
                    ${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}
                </span>
                <span class="alert-message">${message}</span>
                <button class="alert-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
        `;

        document.body.appendChild(alert);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alert.parentElement) {
                alert.remove();
            }
        }, 5000);
    }

    showLoading(show) {
        const submitBtn = document.querySelector('button[type="submit"]');
        if (show) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '⏳ Registering...';
        } else {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '🔌 Register Device';
        }
    }

    getCSRFToken() {
        const tokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
        return tokenInput ? tokenInput.value : '';
    }
}

// Global functions
function editDevice() {
    deviceManager.editDevice();
}

function deleteDevice() {
    deviceManager.deleteDevice();
}

function closeModal() {
    deviceManager.closeModal();
}

function showCredentialsInput() {
    const usernameInput = document.getElementById('mqttUsernameInput');
    const passwordInput = document.getElementById('mqttPasswordInput');
    const setCredentialsBtn = document.getElementById('setCredentialsBtn');
    const saveCredentialsBtn = document.getElementById('saveCredentialsBtn');
    
    usernameInput.style.display = 'inline-block';
    passwordInput.style.display = 'inline-block';
    setCredentialsBtn.style.display = 'none';
    saveCredentialsBtn.style.display = 'inline-block';
    usernameInput.focus();
}

function setMqttCredentials() {
    deviceManager.setMqttCredentials();
}

function connectToMqtt() {
    deviceManager.connectToMqtt();
}

// Initialize device manager when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.deviceManager = new DeviceManager();
});

// Add some additional CSS for alerts
const alertStyles = `
<style>
.alert {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 1001;
    min-width: 300px;
    max-width: 500px;
    border-radius: 10px;
    box-shadow: 0 10px 20px rgba(0, 0, 0, 0.2);
    animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

.alert-success {
    background: #dcfce7;
    border: 2px solid #16a34a;
    color: #166534;
}

.alert-error {
    background: #fef2f2;
    border: 2px solid #dc2626;
    color: #991b1b;
}

.alert-info {
    background: #dbeafe;
    border: 2px solid #2563eb;
    color: #1e40af;
}

.alert-content {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem;
}

.alert-icon {
    font-size: 1.2rem;
}

.alert-message {
    flex: 1;
    font-weight: 500;
}

.alert-close {
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    opacity: 0.7;
    transition: opacity 0.3s ease;
}

.alert-close:hover {
    opacity: 1;
}

.no-devices {
    grid-column: 1 / -1;
    text-align: center;
    padding: 3rem;
    color: #666;
}

.no-devices p:first-child {
    font-size: 1.2rem;
    margin-bottom: 0.5rem;
}

.device-detail-grid {
    display: grid;
    gap: 1rem;
}

.detail-item {
    display: grid;
    grid-template-columns: 150px 1fr;
    gap: 1rem;
    padding: 1rem;
    background: #f8fafc;
    border-radius: 8px;
    align-items: start;
}

.detail-item strong {
    color: #334155;
}

.topic-list div, .permission-list {
    font-family: 'Courier New', monospace;
    font-size: 0.9rem;
    margin-bottom: 0.5rem;
}

.permission-badge {
    display: inline-block;
    background: #667eea;
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-size: 0.8rem;
    margin-right: 0.5rem;
}
</style>
`;

document.head.insertAdjacentHTML('beforeend', alertStyles);