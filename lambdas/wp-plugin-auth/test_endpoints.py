#!/usr/bin/env python3
"""
Test script for Form-Bridge WordPress Plugin Authentication API
"""

import json
import time
import requests
import hashlib
import hmac
from datetime import datetime
import argparse

class PluginAuthTester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Form-Bridge-Plugin-Tester/1.0'
        })
    
    def test_registration(self, domain: str = "example-site.com") -> dict:
        """Test site registration endpoint"""
        print(f"\n🧪 Testing Registration for {domain}")
        print("=" * 50)
        
        payload = {
            "domain": domain,
            "wp_version": "6.4.2",
            "plugin_version": "1.0.0",
            "admin_email": "admin@example-site.com"
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/register",
                json=payload,
                timeout=10
            )
            
            print(f"Status Code: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            
            result = response.json()
            print(f"Response Body: {json.dumps(result, indent=2)}")
            
            if response.status_code == 200 and result.get('success'):
                print("✅ Registration successful!")
                return result['data']
            else:
                print("❌ Registration failed!")
                return {}
                
        except Exception as e:
            print(f"❌ Registration error: {str(e)}")
            return {}
    
    def test_key_exchange(self, temp_key: str, domain: str) -> dict:
        """Test key exchange endpoint"""
        print(f"\n🔑 Testing Key Exchange")
        print("=" * 50)
        
        # Simulate creating verification file
        verification_content = f"""temp_key={temp_key}
domain={domain}
timestamp={int(time.time())}
"""
        
        print(f"Simulated verification file content:")
        print(verification_content)
        
        payload = {
            "temp_key": temp_key,
            "verification_method": "file",
            "challenge_response": verification_content.strip()
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/exchange",
                json=payload,
                timeout=15
            )
            
            print(f"Status Code: {response.status_code}")
            
            result = response.json()
            print(f"Response Body: {json.dumps(result, indent=2)}")
            
            if response.status_code == 200 and result.get('success'):
                print("✅ Key exchange successful!")
                return result['data']
            else:
                print("❌ Key exchange failed!")
                return {}
                
        except Exception as e:
            print(f"❌ Key exchange error: {str(e)}")
            return {}
    
    def test_authentication(self, api_key: str) -> bool:
        """Test API key authentication"""
        print(f"\n🔐 Testing Authentication")
        print("=" * 50)
        
        # Test with Bearer token format
        headers = {
            'Authorization': f'Bearer {api_key}'
        }
        
        try:
            # This would normally be a protected endpoint
            # For testing, we'll call a hypothetical protected endpoint
            response = self.session.get(
                f"{self.base_url}/protected-test",
                headers=headers,
                timeout=10
            )
            
            print(f"Status Code: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                print("✅ Authentication successful!")
                return True
            else:
                print(f"❌ Authentication failed with status {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Authentication error: {str(e)}")
            return False
    
    def test_update_check(self, current_version: str = "1.0.0", site_id: str = None) -> dict:
        """Test update check endpoint"""
        print(f"\n🔄 Testing Update Check")
        print("=" * 50)
        
        params = {
            'current_version': current_version,
            'wp_version': '6.4.2',
            'php_version': '8.1'
        }
        
        if site_id:
            params['site_id'] = site_id
        
        try:
            response = self.session.get(
                f"{self.base_url}/updates/check",
                params=params,
                timeout=10
            )
            
            print(f"Status Code: {response.status_code}")
            
            result = response.json()
            print(f"Response Body: {json.dumps(result, indent=2)}")
            
            if response.status_code == 200 and result.get('success'):
                print("✅ Update check successful!")
                return result['data']
            else:
                print("❌ Update check failed!")
                return {}
                
        except Exception as e:
            print(f"❌ Update check error: {str(e)}")
            return {}
    
    def test_site_validation(self, domain: str, registration_id: str = None) -> dict:
        """Test site validation endpoint"""
        print(f"\n✅ Testing Site Validation for {domain}")
        print("=" * 50)
        
        payload = {
            "domain": domain,
            "registration_id": registration_id or "test_reg_123",
            "validation_level": "standard"
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/validate",
                json=payload,
                timeout=30  # Longer timeout for validation
            )
            
            print(f"Status Code: {response.status_code}")
            
            result = response.json()
            print(f"Response Body: {json.dumps(result, indent=2)}")
            
            if response.status_code == 200 and result.get('success'):
                print("✅ Site validation completed!")
                return result['data']
            else:
                print("❌ Site validation failed!")
                return {}
                
        except Exception as e:
            print(f"❌ Site validation error: {str(e)}")
            return {}
    
    def test_rate_limiting(self, endpoint: str = "/register", max_requests: int = 5):
        """Test rate limiting by making multiple requests"""
        print(f"\n⏱️ Testing Rate Limiting on {endpoint}")
        print("=" * 50)
        
        success_count = 0
        rate_limited_count = 0
        
        payload = {
            "domain": f"test-rate-limit-{int(time.time())}.com",
            "wp_version": "6.4.2",
            "plugin_version": "1.0.0"
        }
        
        for i in range(max_requests + 2):  # Go over the limit
            try:
                response = self.session.post(
                    f"{self.base_url}{endpoint}",
                    json=payload,
                    timeout=5
                )
                
                print(f"Request {i+1}: Status {response.status_code}")
                
                if response.status_code == 200:
                    success_count += 1
                elif response.status_code == 429:
                    rate_limited_count += 1
                    print(f"  Rate limited after {i+1} requests")
                    break
                
                time.sleep(0.1)  # Small delay between requests
                
            except Exception as e:
                print(f"  Request {i+1} error: {str(e)}")
        
        print(f"\n📊 Rate Limiting Results:")
        print(f"  Successful requests: {success_count}")
        print(f"  Rate limited requests: {rate_limited_count}")
        
        if rate_limited_count > 0:
            print("✅ Rate limiting is working!")
        else:
            print("❌ Rate limiting may not be configured correctly")
    
    def run_full_test_suite(self, test_domain: str = "test-plugin-auth.com"):
        """Run complete test suite"""
        print("🚀 Form-Bridge Plugin Authentication Test Suite")
        print("=" * 60)
        
        # Test 1: Registration
        registration_data = self.test_registration(test_domain)
        
        if not registration_data:
            print("❌ Cannot continue without successful registration")
            return
        
        temp_key = registration_data.get('temp_key')
        registration_id = registration_data.get('registration_id')
        
        # Test 2: Site Validation
        validation_data = self.test_site_validation(test_domain, registration_id)
        
        # Test 3: Key Exchange (will fail without real site verification)
        if temp_key:
            credentials_data = self.test_key_exchange(temp_key, test_domain)
            
            api_key = credentials_data.get('api_key')
            site_id = credentials_data.get('site_id')
            
            # Test 4: Authentication (if we got credentials)
            if api_key:
                self.test_authentication(api_key)
        
        # Test 5: Update Check
        self.test_update_check()
        
        # Test 6: Rate Limiting
        self.test_rate_limiting()
        
        print("\n🎉 Test suite completed!")
    
    def test_cors_headers(self):
        """Test CORS configuration"""
        print(f"\n🌐 Testing CORS Headers")
        print("=" * 50)
        
        try:
            # Test OPTIONS request
            response = self.session.options(
                f"{self.base_url}/register",
                headers={'Origin': 'https://example-wordpress-site.com'}
            )
            
            print(f"OPTIONS Status Code: {response.status_code}")
            print("CORS Headers:")
            cors_headers = {k: v for k, v in response.headers.items() 
                           if k.lower().startswith('access-control')}
            
            for header, value in cors_headers.items():
                print(f"  {header}: {value}")
            
            if cors_headers:
                print("✅ CORS headers present!")
            else:
                print("❌ CORS headers missing!")
                
        except Exception as e:
            print(f"❌ CORS test error: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Test Form-Bridge Plugin Authentication API')
    parser.add_argument('api_url', help='API Gateway URL (e.g., https://api.example.com/dev)')
    parser.add_argument('--domain', default='test-plugin-auth.com', 
                       help='Test domain name')
    parser.add_argument('--endpoint', choices=['register', 'exchange', 'validate', 'updates', 'cors', 'rate-limit', 'all'],
                       default='all', help='Specific endpoint to test')
    
    args = parser.parse_args()
    
    tester = PluginAuthTester(args.api_url)
    
    if args.endpoint == 'all':
        tester.run_full_test_suite(args.domain)
    elif args.endpoint == 'register':
        tester.test_registration(args.domain)
    elif args.endpoint == 'validate':
        tester.test_site_validation(args.domain)
    elif args.endpoint == 'updates':
        tester.test_update_check()
    elif args.endpoint == 'cors':
        tester.test_cors_headers()
    elif args.endpoint == 'rate-limit':
        tester.test_rate_limiting()
    else:
        print(f"Test for {args.endpoint} not implemented yet")

if __name__ == "__main__":
    main()