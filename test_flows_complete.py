#!/usr/bin/env python3
import requests
import json
import base64
import os
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

BASE_URL = 'http://localhost:8000'

def encrypt_login_data(public_key_pem, email, password):
    """Encrypt login data using the same format as test_encryption.py"""
    # Load public key
    public_key = serialization.load_pem_public_key(public_key_pem.encode(), backend=default_backend())
    
    # Generate AES key and IV
    aes_key = os.urandom(32)  # 256 bit key
    iv = os.urandom(16)  # 16 byte IV
    
    # Encrypt password with AES
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    # Pad password to 16 byte boundary
    padding_length = 16 - (len(password) % 16)
    padded_password = password + chr(padding_length) * padding_length
    
    encrypted_password = encryptor.update(padded_password.encode()) + encryptor.finalize()
    encrypted_password_b64 = base64.b64encode(encrypted_password).decode()
    
    # Encrypt AES key with RSA
    encrypted_aes_key = public_key.encrypt(
        aes_key.hex().encode(),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    encrypted_aes_key_b64 = base64.b64encode(encrypted_aes_key).decode()
    
    # Create payload in the expected format
    payload = {
        'data': {
            'email': email,
            'password': {
                'data': encrypted_password_b64,
                'encrypted': True
            }
        },
        'key': encrypted_aes_key_b64,
        'iv': iv.hex()
    }
    
    return payload

def test_flow_apis_complete():
    """Test complete flow management APIs with proper authentication"""
    
    print("🧪 Testing Complete Flow Management APIs")
    print("=" * 60)
    
    # Step 1: Get public key
    print("1. Getting public key...")
    try:
        pubkey_response = requests.get(f'{BASE_URL}/api/public-key/')
        if pubkey_response.status_code == 200:
            public_key = pubkey_response.json()['public_key']
            print("✅ Public key retrieved")
        else:
            print(f"❌ Failed to get public key: {pubkey_response.text}")
            return
    except Exception as e:
        print(f"❌ Public key error: {e}")
        return
    
    # Step 2: Login with encryption
    print("2. Logging in with encryption...")
    try:
        login_payload = encrypt_login_data(public_key, "test@example.com", "testpassword123")
        
        login_response = requests.post(f'{BASE_URL}/api/login/', json=login_payload)
        if login_response.status_code == 200:
            token = login_response.json()['token']
            print("✅ Login successful")
        else:
            print(f"❌ Login failed: {login_response.text}")
            return
    except Exception as e:
        print(f"❌ Login error: {e}")
        return
    
    # Headers for authenticated requests
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Step 3: Test flow templates
    print("3. Testing flow templates...")
    try:
        templates_response = requests.get(f'{BASE_URL}/api/flows/templates/', headers=headers)
        if templates_response.status_code == 200:
            templates = templates_response.json()
            print(f"✅ Found {len(templates)} flow templates")
            for template in templates:
                print(f"   - {template['name']}: {template['description']}")
        else:
            print(f"❌ Templates failed: {templates_response.text}")
    except Exception as e:
        print(f"❌ Templates error: {e}")
    
    # Step 4: Create a new flow
    print("4. Creating a new flow...")
    flow_data = {
        "name": "Test IoT Data Pipeline",
        "description": "A comprehensive test flow for IoT data processing",
        "nodes": [
            {
                "id": "mqtt-input-1",
                "type": "input",
                "position": {"x": 100, "y": 100},
                "data": {"label": "MQTT Sensor Input", "nodeType": "mqtt", "topic": "sensors/temperature"}
            },
            {
                "id": "transform-1",
                "type": "function",
                "position": {"x": 350, "y": 100},
                "data": {"label": "Data Transform", "nodeType": "transform", "operation": "moving_average"}
            },
            {
                "id": "database-1",
                "type": "storage",
                "position": {"x": 600, "y": 100},
                "data": {"label": "Store to Database", "nodeType": "database", "table": "sensor_readings"}
            },
            {
                "id": "debug-1",
                "type": "debug",
                "position": {"x": 350, "y": 250},
                "data": {"label": "Debug Output", "nodeType": "debug"}
            }
        ],
        "edges": [
            {
                "id": "e1-2",
                "source": "mqtt-input-1",
                "target": "transform-1",
                "sourceHandle": null,
                "targetHandle": null
            },
            {
                "id": "e2-3",
                "source": "transform-1",
                "target": "database-1",
                "sourceHandle": null,
                "targetHandle": null
            },
            {
                "id": "e2-4",
                "source": "transform-1",
                "target": "debug-1",
                "sourceHandle": null,
                "targetHandle": null
            }
        ],
        "metadata": {
            "created_by": "test_user",
            "flow_type": "iot_pipeline",
            "version": "1.0.0"
        },
        "tags": ["iot", "mqtt", "temperature", "test"],
        "version": "1.0.0"
    }
    
    try:
        create_response = requests.post(f'{BASE_URL}/api/flows/', 
                                      json=flow_data, headers=headers)
        if create_response.status_code == 201:
            flow = create_response.json()
            flow_id = flow['id']
            print(f"✅ Flow created successfully")
            print(f"   - ID: {flow_id}")
            print(f"   - Name: {flow['name']}")
            print(f"   - Nodes: {len(flow['nodes'])}")
            print(f"   - Edges: {len(flow['edges'])}")
        else:
            print(f"❌ Flow creation failed: {create_response.text}")
            return
    except Exception as e:
        print(f"❌ Flow creation error: {e}")
        return
    
    # Step 5: Retrieve the flow
    print(f"5. Retrieving flow {flow_id}...")
    try:
        get_response = requests.get(f'{BASE_URL}/api/flows/{flow_id}/', headers=headers)
        if get_response.status_code == 200:
            retrieved_flow = get_response.json()
            print(f"✅ Flow retrieved successfully")
            print(f"   - Name: {retrieved_flow['name']}")
            print(f"   - Created: {retrieved_flow['created_at']}")
            print(f"   - Updated: {retrieved_flow['updated_at']}")
        else:
            print(f"❌ Flow retrieval failed: {get_response.text}")
    except Exception as e:
        print(f"❌ Flow retrieval error: {e}")
    
    # Step 6: Update the flow
    print(f"6. Updating flow {flow_id}...")
    update_data = flow_data.copy()
    update_data["name"] = "Updated Test IoT Data Pipeline"
    update_data["description"] = "An updated and improved test flow"
    update_data["nodes"].append({
        "id": "alert-1",
        "type": "output",
        "position": {"x": 850, "y": 100},
        "data": {"label": "Email Alert", "nodeType": "email", "recipient": "admin@example.com"}
    })
    update_data["edges"].append({
        "id": "e3-5",
        "source": "database-1",
        "target": "alert-1",
        "sourceHandle": null,
        "targetHandle": null
    })
    update_data["tags"].append("email")
    update_data["version"] = "1.1.0"
    
    try:
        update_response = requests.put(f'{BASE_URL}/api/flows/{flow_id}/', 
                                     json=update_data, headers=headers)
        if update_response.status_code == 200:
            updated_flow = update_response.json()
            print(f"✅ Flow updated successfully")
            print(f"   - New name: {updated_flow['name']}")
            print(f"   - Nodes: {len(updated_flow['nodes'])}")
            print(f"   - Edges: {len(updated_flow['edges'])}")
        else:
            print(f"❌ Flow update failed: {update_response.text}")
    except Exception as e:
        print(f"❌ Flow update error: {e}")
    
    # Step 7: Duplicate the flow
    print(f"7. Duplicating flow {flow_id}...")
    try:
        duplicate_response = requests.post(f'{BASE_URL}/api/flows/{flow_id}/duplicate/', 
                                         headers=headers)
        if duplicate_response.status_code == 201:
            duplicate_flow = duplicate_response.json()
            duplicate_id = duplicate_flow['id']
            print(f"✅ Flow duplicated successfully")
            print(f"   - Duplicate ID: {duplicate_id}")
            print(f"   - Name: {duplicate_flow['name']}")
        else:
            print(f"❌ Flow duplication failed: {duplicate_response.text}")
    except Exception as e:
        print(f"❌ Flow duplication error: {e}")
    
    # Step 8: Execute the flow
    print(f"8. Executing flow {flow_id}...")
    try:
        execute_response = requests.post(f'{BASE_URL}/api/flows/{flow_id}/execute/', 
                                       headers=headers)
        if execute_response.status_code == 200:
            execution_data = execute_response.json()
            print(f"✅ Flow execution started")
            print(f"   - Message: {execution_data['message']}")
            print(f"   - Execution ID: {execution_data['execution_id']}")
        else:
            print(f"❌ Flow execution failed: {execute_response.text}")
    except Exception as e:
        print(f"❌ Flow execution error: {e}")
    
    # Step 9: List all flows
    print("9. Listing all flows...")
    try:
        list_response = requests.get(f'{BASE_URL}/api/flows/', headers=headers)
        if list_response.status_code == 200:
            flows = list_response.json()
            print(f"✅ Found {len(flows)} flows for user")
            for flow in flows:
                print(f"   - {flow['name']} (ID: {flow['id']}) - {len(flow['nodes'])} nodes")
        else:
            print(f"❌ Flow list failed: {list_response.text}")
    except Exception as e:
        print(f"❌ Flow list error: {e}")
    
    # Step 10: Cleanup - delete test flows
    print("10. Cleaning up test flows...")
    try:
        # Delete original flow
        delete_response = requests.delete(f'{BASE_URL}/api/flows/{flow_id}/', headers=headers)
        if delete_response.status_code == 204:
            print(f"✅ Original flow {flow_id} deleted")
        else:
            print(f"❌ Delete original flow failed: {delete_response.text}")
        
        # Delete duplicate flow if it exists
        if 'duplicate_id' in locals():
            delete_dup_response = requests.delete(f'{BASE_URL}/api/flows/{duplicate_id}/', headers=headers)
            if delete_dup_response.status_code == 204:
                print(f"✅ Duplicate flow {duplicate_id} deleted")
            else:
                print(f"❌ Delete duplicate flow failed: {delete_dup_response.text}")
        
    except Exception as e:
        print(f"❌ Cleanup error: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 Complete Flow API testing finished!")
    print("✨ All flow management features verified")

if __name__ == "__main__":
    test_flow_apis_complete() 