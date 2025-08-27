#!/usr/bin/env python3
"""
Test client for Form-Bridge Ultra-Simple Lambda Function URL
Demonstrates how to make authenticated requests
"""

import json
import hmac
import hashlib
import time
import requests
from datetime import datetime
from typing import Dict, Any

class FormBridgeClient:
    """Simple client for testing Form-Bridge submissions"""
    
    def __init__(self, function_url: str, hmac_secret: str):
        """
        Initialize the client
        
        Args:
            function_url: The Lambda Function URL endpoint
            hmac_secret: The shared HMAC secret
        """
        self.function_url = function_url
        self.hmac_secret = hmac_secret
    
    def generate_signature(self, timestamp: str, body: Dict) -> str:
        """Generate HMAC-SHA256 signature"""
        # Create message: timestamp:json_body
        json_body = json.dumps(body, sort_keys=True, separators=(',', ':'))
        message = f"{timestamp}:{json_body}"
        
        # Generate HMAC
        signature = hmac.new(
            self.hmac_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def submit_form(self, form_data: Dict, metadata: Dict = None) -> Dict:
        """
        Submit a form to the Lambda Function URL
        
        Args:
            form_data: The form fields and values
            metadata: Optional metadata about the submission
        
        Returns:
            Response from the server
        """
        # Prepare request body
        body = {
            'form_data': form_data,
            'metadata': metadata or {'source': 'test_client'}
        }
        
        # Generate timestamp
        timestamp = str(time.time())
        
        # Generate signature
        signature = self.generate_signature(timestamp, body)
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'X-Signature': signature,
            'X-Timestamp': timestamp
        }
        
        # Make request
        try:
            response = requests.post(
                self.function_url,
                json=body,
                headers=headers,
                timeout=10
            )
            
            # Parse response
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    'error': f'Request failed with status {response.status_code}',
                    'response': response.text
                }
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
    
    def test_submission(self) -> None:
        """Run a test submission"""
        print("Form-Bridge Test Client")
        print("=" * 40)
        print(f"Endpoint: {self.function_url}")
        print()
        
        # Test data
        test_form_data = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'phone': '+1-555-0123',
            'message': 'This is a test submission from the Python client',
            'newsletter': True,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        test_metadata = {
            'source': 'python_test_client',
            'form_id': 'contact-form-1',
            'page_url': 'https://example.com/contact',
            'user_agent': 'Python Test Client v1.0'
        }
        
        print("Submitting test form...")
        print(f"Form Data: {json.dumps(test_form_data, indent=2)}")
        print()
        
        # Submit form
        result = self.submit_form(test_form_data, test_metadata)
        
        # Display result
        if 'error' in result:
            print(f"❌ Error: {result['error']}")
            if 'response' in result:
                print(f"Response: {result['response']}")
        else:
            print(f"✅ Success!")
            print(f"Submission ID: {result.get('submission_id')}")
            print(f"Timestamp: {result.get('timestamp')}")
            print(f"Message: {result.get('message')}")
        
        print()
        return result


def run_load_test(client: FormBridgeClient, num_requests: int = 10):
    """
    Run a simple load test
    
    Args:
        client: The FormBridge client
        num_requests: Number of requests to send
    """
    print(f"Running load test with {num_requests} requests...")
    print("=" * 40)
    
    successful = 0
    failed = 0
    start_time = time.time()
    
    for i in range(num_requests):
        test_data = {
            'name': f'Test User {i}',
            'email': f'user{i}@example.com',
            'message': f'Load test submission #{i}',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        result = client.submit_form(test_data)
        
        if 'error' in result:
            failed += 1
            print(f"Request {i+1}: ❌ Failed")
        else:
            successful += 1
            print(f"Request {i+1}: ✅ Success (ID: {result.get('submission_id')})")
    
    elapsed_time = time.time() - start_time
    
    print()
    print("Load Test Results:")
    print(f"Total Requests: {num_requests}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total Time: {elapsed_time:.2f} seconds")
    print(f"Avg Time: {elapsed_time/num_requests:.3f} seconds per request")
    print(f"Requests/sec: {num_requests/elapsed_time:.2f}")


def estimate_costs(monthly_requests: int):
    """
    Estimate monthly costs based on request volume
    
    Args:
        monthly_requests: Expected monthly request volume
    """
    print(f"Cost Estimate for {monthly_requests:,} requests/month")
    print("=" * 40)
    
    # Lambda costs
    lambda_requests_free = 1_000_000
    lambda_gb_seconds_free = 400_000
    lambda_request_cost = 0.0000002  # per request after free tier
    lambda_gb_second_cost = 0.0000166667  # per GB-second after free tier
    
    # Assume 512MB memory, 200ms average duration
    memory_gb = 0.5
    duration_seconds = 0.2
    gb_seconds_per_request = memory_gb * duration_seconds
    total_gb_seconds = monthly_requests * gb_seconds_per_request
    
    # Calculate Lambda costs
    billable_requests = max(0, monthly_requests - lambda_requests_free)
    billable_gb_seconds = max(0, total_gb_seconds - lambda_gb_seconds_free)
    
    lambda_request_charges = billable_requests * lambda_request_cost
    lambda_compute_charges = billable_gb_seconds * lambda_gb_second_cost
    
    # DynamoDB costs (on-demand)
    dynamodb_writes_free = 25 * 30 * 24 * 3600  # 25 WCU continuous
    dynamodb_reads_free = 25 * 30 * 24 * 3600   # 25 RCU continuous
    dynamodb_write_cost = 0.00000125  # per write after free tier
    dynamodb_read_cost = 0.00000025   # per read after free tier
    
    # Assume 1 write and 2 reads per submission
    monthly_writes = monthly_requests
    monthly_reads = monthly_requests * 2
    
    billable_writes = max(0, monthly_writes - dynamodb_writes_free)
    billable_reads = max(0, monthly_reads - dynamodb_reads_free)
    
    dynamodb_write_charges = billable_writes * dynamodb_write_cost
    dynamodb_read_charges = billable_reads * dynamodb_read_cost
    
    # CloudWatch Logs (5GB free)
    log_size_mb_per_request = 0.001  # 1KB per request
    total_log_gb = (monthly_requests * log_size_mb_per_request) / 1024
    billable_log_gb = max(0, total_log_gb - 5)
    log_charges = billable_log_gb * 0.50  # $0.50 per GB
    
    # Total costs
    total_cost = (
        lambda_request_charges +
        lambda_compute_charges +
        dynamodb_write_charges +
        dynamodb_read_charges +
        log_charges
    )
    
    print(f"Lambda Requests: ${lambda_request_charges:.4f}")
    print(f"Lambda Compute: ${lambda_compute_charges:.4f}")
    print(f"DynamoDB Writes: ${dynamodb_write_charges:.4f}")
    print(f"DynamoDB Reads: ${dynamodb_read_charges:.4f}")
    print(f"CloudWatch Logs: ${log_charges:.4f}")
    print(f"Total Monthly Cost: ${total_cost:.2f}")
    
    if total_cost == 0:
        print("✅ Fully covered by AWS Free Tier!")
    
    print()


if __name__ == '__main__':
    import sys
    import os
    
    # Get configuration from environment or arguments
    function_url = os.environ.get('FUNCTION_URL')
    hmac_secret = os.environ.get('HMAC_SECRET', 'development-secret-change-in-production')
    
    if not function_url:
        if len(sys.argv) > 1:
            function_url = sys.argv[1]
        else:
            print("Usage: python test_client.py <function_url>")
            print("   or: FUNCTION_URL=<url> python test_client.py")
            sys.exit(1)
    
    # Create client
    client = FormBridgeClient(function_url, hmac_secret)
    
    # Run tests
    print("1. Single Test Submission")
    print("-" * 40)
    client.test_submission()
    
    print("\n2. Cost Estimates")
    print("-" * 40)
    estimate_costs(100)      # Testing
    estimate_costs(1_000)    # Low usage
    estimate_costs(10_000)   # Moderate usage
    estimate_costs(100_000)  # Production
    
    # Optional: Run load test
    if len(sys.argv) > 2 and sys.argv[2] == '--load-test':
        print("\n3. Load Test")
        print("-" * 40)
        run_load_test(client, 10)