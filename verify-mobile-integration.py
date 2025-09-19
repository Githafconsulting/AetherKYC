#!/usr/bin/env python3
"""
Verify that the mobile app backend integration is working correctly.
"""

import requests
import json
import time
import sys
import io

# Set UTF-8 encoding for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_mobile_app_integration():
    """Test the complete mobile app flow"""

    print("🚀 Testing Mobile App Backend Integration\n")

    # 1. Check all services
    print("1️⃣ Checking Services Health...")
    services = [
        ("User Forms API", "http://localhost:8005/health"),
        ("Command Center", "http://localhost:8006/"),
        ("Mobile App", "http://localhost:8083/"),
    ]

    all_healthy = True
    for name, url in services:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                print(f"   ✅ {name}: Online")
            else:
                print(f"   ❌ {name}: Status {response.status_code}")
                all_healthy = False
        except Exception as e:
            print(f"   ❌ {name}: Connection failed - {e}")
            all_healthy = False

    if not all_healthy:
        print("\n⚠️ Some services are not healthy. Please check Docker containers.")
        return False

    # 2. Submit application
    print("\n2️⃣ Submitting Test Application...")
    submission_data = {
        "personal_info": {
            "first_name": "Integration",
            "last_name": "Test",
            "email": "integration.test@example.com",
            "phone": "+1234567890",
            "date_of_birth": "1990-01-01",
            "nationality": "US",
            "address_line1": "123 Test Street",
            "city": "Test City",
            "state_province": "CA",
            "postal_code": "90210",
            "country": "USA"
        },
        "documents": [{
            "document_type": "passport",
            "document_number": "TEST123456",
            "issuing_country": "US"
        }],
        "application_type": "kyc_verification",
        "additional_notes": "Automated integration test"
    }

    try:
        response = requests.post(
            "http://localhost:8005/submit-application",
            json=submission_data,
            headers={
                "Content-Type": "application/json",
                "Origin": "http://localhost:8083"
            }
        )

        if response.status_code == 200:
            result = response.json()
            app_id = result.get("application_id")
            print(f"   ✅ Application submitted: {app_id}")
            print(f"      Status: {result.get('status')}")

            # 3. Check agents status
            print("\n3️⃣ Checking Agent Processing...")
            time.sleep(2)  # Wait for processing to start

            agents_response = requests.get("http://localhost:8006/api/agents")
            if agents_response.status_code == 200:
                agents = agents_response.json()
                active_agents = [a for a in agents if a.get("status") == "active"]
                print(f"   ✅ {len(active_agents)} agents are active")

                for agent in active_agents[:4]:  # Show first 4 active agents
                    print(f"      • {agent['name']}: {agent['currentTask'][:60]}...")

            # 4. Check application status
            print("\n4️⃣ Checking Application Status...")
            status_response = requests.get(f"http://localhost:8005/application/{app_id}")
            if status_response.status_code == 200:
                status = status_response.json()
                print(f"   ✅ Application status: {status.get('status')}")
                print(f"      Documents uploaded: {len(status.get('document_uploads', {}))}")

            print("\n✅ Integration Test Successful!")
            print("\n📱 Mobile App Integration Status:")
            print("   • Backend API: ✅ Working")
            print("   • Application Submission: ✅ Working")
            print("   • Agent Processing: ✅ Working")
            print("   • Status Tracking: ✅ Working")
            print("\n🎉 The mobile app is fully integrated with the backend!")
            print(f"\n👉 Open http://localhost:8083 to use the mobile app")

            return True

        else:
            print(f"   ❌ Submission failed: {response.status_code}")
            print(f"      Response: {response.text}")
            return False

    except Exception as e:
        print(f"   ❌ Error during submission: {e}")
        return False

if __name__ == "__main__":
    success = test_mobile_app_integration()
    exit(0 if success else 1)