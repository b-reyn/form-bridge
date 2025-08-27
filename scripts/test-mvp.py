#!/usr/bin/env python3
"""
MVP Test Script
Quick validation of deployed Form-Bridge MVP
"""
import json
import requests
import sys
import time
from datetime import datetime

def test_form_submission(api_endpoint, tenant_id="t_sample", api_key="mvp-test-key-123"):
    """Test form submission endpoint"""
    print(f"🧪 Testing form submission to {api_endpoint}")
    
    # Prepare test payload
    payload = {
        "form_data": {
            "name": "Test User",
            "email": "test@example.com",
            "message": "This is a test submission from MVP test script",
            "timestamp": datetime.utcnow().isoformat()
        },
        "form_type": "contact",
        "source": "test_script",
        "metadata": {
            "test_run": True,
            "script_version": "1.0"
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Tenant-ID": tenant_id,
        "X-API-Key": api_key
    }
    
    try:
        # Send request
        print("📤 Sending form submission...")
        response = requests.post(
            f"{api_endpoint}/submit",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        print(f"📥 Response Status: {response.status_code}")
        print(f"📥 Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            response_data = response.json()
            print(f"✅ Success! Submission ID: {response_data.get('submission_id')}")
            return response_data.get('submission_id')
        else:
            print(f"❌ Error: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {str(e)}")
        return None

def test_unauthorized_access(api_endpoint):
    """Test that unauthorized access is blocked"""
    print(f"\n🔒 Testing unauthorized access...")
    
    payload = {"form_data": {"test": "data"}}
    
    # Test without headers
    try:
        response = requests.post(f"{api_endpoint}/submit", json=payload, timeout=5)
        if response.status_code in [401, 403]:
            print("✅ Unauthorized access properly blocked")
        else:
            print(f"⚠️  Unexpected response for unauthorized request: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {str(e)}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test-mvp.py <api-endpoint>")
        print("Example: python3 test-mvp.py https://abc123.execute-api.us-east-1.amazonaws.com/dev")
        sys.exit(1)
    
    api_endpoint = sys.argv[1].rstrip('/')
    
    print("🚀 Form-Bridge MVP Test Suite")
    print(f"🎯 Target: {api_endpoint}")
    print(f"🕐 Started: {datetime.utcnow().isoformat()}Z")
    print("=" * 50)
    
    # Test successful submission
    submission_id = test_form_submission(api_endpoint)
    
    # Test unauthorized access
    test_unauthorized_access(api_endpoint)
    
    print("\n" + "=" * 50)
    if submission_id:
        print("🎉 MVP Test Completed Successfully!")
        print(f"📝 Submission ID: {submission_id}")
        print("\n💡 Next steps:")
        print("   1. Check DynamoDB for stored submission")
        print("   2. Verify EventBridge event was published")
        print("   3. Confirm processor Lambda updated status")
    else:
        print("❌ MVP Test Failed - Check logs for details")
        sys.exit(1)

if __name__ == "__main__":
    main()