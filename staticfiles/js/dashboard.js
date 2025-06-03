class SensorDashboard {
    constructor() {
        this.socket = null;
        this.sensorData = new Map();
        this.logEntries = [];
        this.chart = null;
        this.maxLogEntries = 100;
        this.maxChartPoints = 50;
        
        this.initWebSocket();
        this.initChart();
        this.loadHistoricalData();
        this.setupFilters();
    }

    initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/sensors/`;
        
        this.socket = new WebSocket(wsUrl);
        
        this.socket.onopen = () => {
            console.log('WebSocket connected');
            this.updateConnectionStatus(true);
        };
        
        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'sensor_data') {
                this.handleSensorData(data);
            }
        };
        
        this.socket.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateConnectionStatus(false);
            // Attempt to reconnect after 3 seconds
            setTimeout(() => this.initWebSocket(), 3000);
        };
        
        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateConnectionStatus(false);
        };
    }

    updateConnectionStatus(connected) {
        const statusDot = document.getElementById('connectionStatus');
        const statusText = document.getElementById('connectionText');
        
        if (connected) {
            statusDot.classList.add('connected');
            statusText.textContent = 'Connected';
        } else {
            statusDot.classList.remove('connected');
            statusText.textContent = 'Disconnected';
        }
    }

    handleSensorData(data) {
        const key = `${data.device_id}_${data.sensor_type}`;
        this.sensorData.set(key, data);
        
        this.updateSensorCard(data);
        this.addLogEntry(data);
        this.updateChart();
        this.updateFilters();
    }

    updateSensorCard(data) {
        const key = `${data.device_id}_${data.sensor_type}`;
        let card = document.getElementById(`card_${key}`);
        
        if (!card) {
            card = this.createSensorCard(data);
            document.getElementById('sensorCards').appendChild(card);
        }
        
        const valueElement = card.querySelector('.card-value');
        const timestampElement = card.querySelector('.card-timestamp');
        
        valueElement.textContent = data.value.toFixed(2);
        timestampElement.textContent = `Last updated: ${new Date(data.timestamp).toLocaleString()}`;
        
        // Add animation effect
        card.style.transform = 'scale(1.02)';
        setTimeout(() => {
            card.style.transform = 'scale(1)';
        }, 200);
    }

    createSensorCard(data) {
        const key = `${data.device_id}_${data.sensor_type}`;
        const card = document.createElement('div');
        card.className = 'card';
        card.id = `card_${key}`;
        
        const icon = this.getSensorIcon(data.sensor_type);
        
        card.innerHTML = `
            <div class="card-header">
                <h3 class="card-title">${icon} ${data.sensor_type}</h3>
                <small>${data.device_id}</small>
            </div>
            <div class="card-value">${data.value.toFixed(2)}</div>
            <div class="card-unit">${data.unit}</div>
            <div class="card-timestamp">Last updated: ${new Date(data.timestamp).toLocaleString()}</div>
        `;
        
        return card;
    }

    getSensorIcon(sensorType) {
        const icons = {
            'temperature': '🌡️',
            'humidity': '💧',
            'pressure': '📊',
            'light': '💡',
            'motion': '🏃',
            'gas': '💨',
            'sound': '🔊'
        };
        return icons[sensorType.toLowerCase()] || '📡';
    }

    addLogEntry(data) {
        this.logEntries.unshift(data);
        if (this.logEntries.length > this.maxLogEntries) {
            this.logEntries.pop();
        }
        
        this.updateLogDisplay();
    }

    updateLogDisplay() {
        const logContainer = document.getElementById('dataLog');
        const logCount = document.getElementById('logCount');
        
        logContainer.innerHTML = '';
        
        this.logEntries.forEach((entry, index) => {
            const logEntry = document.createElement('div');
            logEntry.className = 'log-entry';
            if (index === 0) logEntry.classList.add('new');
            
            logEntry.innerHTML = `
                <div>
                    <span class="log-device">${entry.device_id}</span>
                    <span class="log-sensor">${entry.sensor_type}</span>
                </div>
                <div class="log-value">${entry.value.toFixed(2)} ${entry.unit}</div>
                <div class="log-time">${new Date(entry.timestamp).toLocaleString()}</div>
            `;
            
            logContainer.appendChild(logEntry);
        });
        
        logCount.textContent = `${this.logEntries.length} entries`;
    }

    initChart() {
        const ctx = document.getElementById('sensorChart').getContext('2d');
        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: []
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            displayFormats: {
                                minute: 'HH:mm'
                            }
                        }
                    },
                    y: {
                        beginAtZero: false
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    title: {
                        display: true,
                        text: 'Real-time Sensor Readings'
                    }
                }
            }
        });
    }

    updateChart() {
        const datasets = new Map();
        
        this.sensorData.forEach((data, key) => {
            const datasetKey = `${data.device_id} - ${data.sensor_type}`;
            
            if (!datasets.has(datasetKey)) {
                datasets.set(datasetKey, {
                    label: datasetKey,
                    data: [],
                    borderColor: this.getRandomColor(),
                    backgroundColor: 'transparent',
                    tension: 0.4
                });
            }
            
            const dataset = datasets.get(datasetKey);
            dataset.data.push({
                x: new Date(data.timestamp),
                y: data.value
            });
            
            // Keep only the last N points
            if (dataset.data.length > this.maxChartPoints) {
                dataset.data.shift();
            }
        });
        
        this.chart.data.datasets = Array.from(datasets.values());
        this.chart.update('none');
    }

    getRandomColor() {
        const colors = [
            '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0',
            '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF'
        ];
        return colors[Math.floor(Math.random() * colors.length)];
    }

    async loadHistoricalData() {
        try {
            const response = await fetch('/api/latest/');
            const data = await response.json();
            
            data.forEach(item => {
                this.handleSensorData({
                    type: 'sensor_data',
                    device_id: item.device_id,
                    sensor_type: item.sensor_type,
                    value: item.value,
                    unit: item.unit,
                    timestamp: item.timestamp,
                    id: item.id
                });
            });
        } catch (error) {
            console.error('Error loading historical data:', error);
        }
    }

    setupFilters() {
        const deviceFilter = document.getElementById('deviceFilter');
        const sensorFilter = document.getElementById('sensorFilter');
        
        deviceFilter.addEventListener('change', () => this.applyFilters());
        sensorFilter.addEventListener('change', () => this.applyFilters());
    }

    updateFilters() {
        const deviceFilter = document.getElementById('deviceFilter');
        const sensorFilter = document.getElementById('sensorFilter');
        
        const devices = new Set();
        const sensorTypes = new Set();
        
        this.sensorData.forEach(data => {
            devices.add(data.device_id);
            sensorTypes.add(data.sensor_type);
        });
        
        // Update device filter
        const currentDeviceValue = deviceFilter.value;
        deviceFilter.innerHTML = '<option value="">All Devices</option>';
        devices.forEach(device => {
            const option = document.createElement('option');
            option.value = device;
            option.textContent = device;
            if (device === currentDeviceValue) option.selected = true;
            deviceFilter.appendChild(option);
        });
        
        // Update sensor filter
        const currentSensorValue = sensorFilter.value;
        sensorFilter.innerHTML = '<option value="">All Sensors</option>';
        sensorTypes.forEach(sensor => {
            const option = document.createElement('option');
            option.value = sensor;
            option.textContent = sensor;
            if (sensor === currentSensorValue) option.selected = true;
            sensorFilter.appendChild(option);
        });
    }

    applyFilters() {
        const deviceFilter = document.getElementById('deviceFilter').value;
        const sensorFilter = document.getElementById('sensorFilter').value;
        
        const cards = document.querySelectorAll('#sensorCards .card');
        cards.forEach(card => {
            const cardId = card.id.replace('card_', '');
            const [deviceId, sensorType] = cardId.split('_');
            
            const showDevice = !deviceFilter || deviceId === deviceFilter;
            const showSensor = !sensorFilter || sensorType === sensorFilter;
            
            card.style.display = (showDevice && showSensor) ? 'block' : 'none';
        });
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    new SensorDashboard();
}); 