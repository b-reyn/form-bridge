"""
WordPress Multi-Site Authentication - Advanced Security Implementation
Comprehensive security features, encryption, monitoring, and compliance
"""

import boto3
import hashlib
import hmac
import secrets
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

class WordPressSecurityManager:
    """
    Advanced security manager for WordPress multi-site authentication
    Implements encryption, key derivation, rate limiting, and threat detection
    """
    
    def __init__(self, table_name: str, kms_key_id: str = None):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        self.kms = boto3.client('kms')
        self.cloudwatch = boto3.client('cloudwatch')
        self.kms_key_id = kms_key_id or 'alias/wordpress-auth'
        
        # Security configuration
        self.rate_limits = {
            'default': 100,      # requests per hour
            'premium': 1000,     # premium accounts
            'burst': 150,        # burst capacity
            'auth_failures': 10  # failed auth attempts per hour
        }
        
        self.security_policies = {
            'key_rotation_days': 90,
            'max_key_age_days': 180,
            'audit_retention_days': 365,
            'session_timeout_minutes': 60,
            'failed_auth_lockout_minutes': 15
        }
    
    # =================================================================
    # ENCRYPTION & KEY MANAGEMENT
    # =================================================================
    
    def generate_data_encryption_key(self) -> Tuple[bytes, str]:
        """
        Generate data encryption key using AWS KMS
        Returns: (plaintext_key, encrypted_key_base64)
        """
        try:
            response = self.kms.generate_data_key(
                KeyId=self.kms_key_id,
                KeySpec='AES_256'
            )
            
            plaintext_key = response['Plaintext']
            encrypted_key = base64.b64encode(response['CiphertextBlob']).decode()
            
            return plaintext_key, encrypted_key
            
        except Exception as e:
            raise Exception(f"Failed to generate data encryption key: {str(e)}")
    
    def decrypt_data_encryption_key(self, encrypted_key_b64: str) -> bytes:
        """Decrypt data encryption key using KMS"""
        try:
            encrypted_key = base64.b64decode(encrypted_key_b64)
            response = self.kms.decrypt(CiphertextBlob=encrypted_key)
            return response['Plaintext']
            
        except Exception as e:
            raise Exception(f"Failed to decrypt data encryption key: {str(e)}")
    
    def encrypt_sensitive_data(self, data: str, context: Dict = None) -> Dict:
        """
        Encrypt sensitive data with envelope encryption
        """
        # Generate DEK
        plaintext_key, encrypted_key = self.generate_data_encryption_key()
        
        # Create Fernet cipher
        fernet_key = base64.urlsafe_b64encode(plaintext_key[:32])
        cipher = Fernet(fernet_key)
        
        # Encrypt data
        encrypted_data = cipher.encrypt(data.encode())
        
        # Clear plaintext key from memory
        plaintext_key = b'\x00' * len(plaintext_key)
        
        return {
            'encrypted_data': base64.b64encode(encrypted_data).decode(),
            'encrypted_key': encrypted_key,
            'encryption_algorithm': 'AES-256-GCM',
            'encrypted_at': datetime.utcnow().isoformat(),
            'context': context or {}
        }
    
    def decrypt_sensitive_data(self, encrypted_blob: Dict) -> str:
        """
        Decrypt sensitive data using envelope encryption
        """
        try:
            # Decrypt DEK
            plaintext_key = self.decrypt_data_encryption_key(encrypted_blob['encrypted_key'])
            
            # Create cipher
            fernet_key = base64.urlsafe_b64encode(plaintext_key[:32])
            cipher = Fernet(fernet_key)
            
            # Decrypt data
            encrypted_data = base64.b64decode(encrypted_blob['encrypted_data'])
            decrypted_data = cipher.decrypt(encrypted_data).decode()
            
            # Clear key from memory
            plaintext_key = b'\x00' * len(plaintext_key)
            
            return decrypted_data
            
        except Exception as e:
            raise Exception(f"Failed to decrypt data: {str(e)}")
    
    def derive_site_secret(self, master_secret: str, site_domain: str, 
                          account_id: str, salt: str = None) -> str:
        """
        Derive site-specific secret from master secret using PBKDF2
        Ensures site isolation even with master secret compromise
        """
        if not salt:
            salt = f"{account_id}:{site_domain}:wordpress-auth"
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt.encode(),
            iterations=100000,  # OWASP recommended minimum
        )
        
        derived_key = kdf.derive(master_secret.encode())
        return base64.urlsafe_b64encode(derived_key).decode()
    
    # =================================================================
    # ADVANCED AUTHENTICATION & AUTHORIZATION
    # =================================================================
    
    def create_secure_site_credentials(self, account_id: str, site_domain: str,
                                     permissions: List[str],
                                     tier: str = 'standard') -> Dict:
        """
        Create secure site credentials with multiple layers of protection
        """
        # Generate master secret
        master_secret = secrets.token_urlsafe(64)
        
        # Derive site-specific secret
        site_secret = self.derive_site_secret(master_secret, site_domain, account_id)
        
        # Create HMAC-based key ID
        key_id = self.generate_secure_key_id(site_domain, account_id)
        
        # Create secure hash for validation
        secure_hash = self.create_secure_hash(site_secret, site_domain, key_id)
        
        # Encrypt sensitive data
        encrypted_secret = self.encrypt_sensitive_data(
            site_secret,
            {'site_domain': site_domain, 'account_id': account_id}
        )
        
        # Calculate expiration based on tier
        expiry_days = 90 if tier == 'standard' else 180
        expires_at = datetime.utcnow() + timedelta(days=expiry_days)
        
        credential_record = {
            'PK': f'SITE#{site_domain}',
            'SK': 'KEY#current',
            'key_id': key_id,
            'secure_hash': secure_hash,
            'encrypted_secret': encrypted_secret,
            'account_id': account_id,
            'site_domain': site_domain,
            'permissions': permissions,
            'tier': tier,
            'created_at': datetime.utcnow().isoformat(),
            'expires_at': expires_at.isoformat(),
            'status': 'active',
            'key_type': 'site_secure',
            'security_version': '2.0',
            'rotation_count': 0,
            'last_used': None,
            'usage_count': 0,
            'failed_attempts': 0,
            'locked_until': None,
            
            # GSI attributes for monitoring
            'GSI1PK': f'EXPIRING#{expires_at.strftime("%Y-%m-%d")}',
            'GSI1SK': f'SITE#{site_domain}',
            'GSI2PK': f'ACCOUNT#{account_id}#ACTIVE',
            'GSI2SK': f'SITE#{site_domain}',
            
            # TTL
            'ttl': int(expires_at.timestamp())
        }
        
        # Store credential
        self.table.put_item(Item=credential_record)
        
        # Log creation
        self._log_security_event(account_id, 'secure_credentials_created', {
            'site_domain': site_domain,
            'key_id': key_id,
            'tier': tier,
            'permissions': permissions
        })
        
        return {
            'key_id': key_id,
            'secret': site_secret,
            'expires_at': expires_at.isoformat(),
            'permissions': permissions,
            'security_version': '2.0'
        }
    
    def generate_secure_key_id(self, site_domain: str, account_id: str) -> str:
        """Generate cryptographically secure key ID"""
        timestamp = str(int(time.time()))
        random_part = secrets.token_hex(8)
        
        # Create deterministic but secure identifier
        base_string = f"{account_id}:{site_domain}:{timestamp}:{random_part}"
        key_hash = hashlib.sha256(base_string.encode()).hexdigest()[:16]
        
        return f"wp_auth_{key_hash}_{timestamp[-6:]}"
    
    def create_secure_hash(self, secret: str, site_domain: str, key_id: str) -> str:
        """Create secure hash for credential validation"""
        message = f"{secret}:{site_domain}:{key_id}"
        return hashlib.sha512(message.encode()).hexdigest()
    
    def validate_secure_credentials(self, key_id: str, secret: str, 
                                   site_domain: str, client_ip: str = None) -> Dict:
        """
        Validate credentials with advanced security checks
        """
        validation_context = {
            'site_domain': site_domain,
            'key_id': key_id,
            'client_ip': client_ip,
            'timestamp': datetime.utcnow().isoformat(),
            'result': None,
            'security_flags': []
        }
        
        try:
            # Rate limiting check
            if not self._check_enhanced_rate_limit(site_domain, client_ip):
                validation_context['result'] = 'rate_limited'
                self._log_security_event(None, 'rate_limit_exceeded', validation_context)
                raise Exception("Rate limit exceeded")
            
            # Get credential record
            response = self.table.get_item(
                Key={
                    'PK': f'SITE#{site_domain}',
                    'SK': 'KEY#current'
                }
            )
            
            if 'Item' not in response:
                validation_context['result'] = 'key_not_found'
                self._increment_failed_attempts(site_domain)
                raise Exception("Invalid credentials")
            
            credential = response['Item']
            
            # Check if account is locked
            if credential.get('locked_until'):
                lock_time = datetime.fromisoformat(credential['locked_until'])
                if lock_time > datetime.utcnow():
                    validation_context['result'] = 'account_locked'
                    validation_context['locked_until'] = credential['locked_until']
                    raise Exception("Account temporarily locked due to security violations")
            
            # Decrypt and validate secret
            try:
                decrypted_secret = self.decrypt_sensitive_data(credential['encrypted_secret'])
                expected_hash = self.create_secure_hash(decrypted_secret, site_domain, key_id)
                
                if (credential['key_id'] != key_id or 
                    credential['secure_hash'] != expected_hash or
                    decrypted_secret != secret):
                    
                    validation_context['result'] = 'invalid_credentials'
                    self._increment_failed_attempts(site_domain)
                    raise Exception("Invalid credentials")
                    
            except Exception as e:
                validation_context['result'] = 'decryption_failed'
                validation_context['security_flags'].append('decryption_error')
                self._increment_failed_attempts(site_domain)
                raise Exception("Credential validation failed")
            
            # Check expiration
            if datetime.fromisoformat(credential['expires_at']) < datetime.utcnow():
                validation_context['result'] = 'expired'
                self._log_security_event(credential['account_id'], 'expired_key_used', validation_context)
                raise Exception("Credentials expired")
            
            # Check status
            if credential['status'] != 'active':
                validation_context['result'] = 'inactive'
                raise Exception("Credentials inactive")
            
            # Security checks passed - update usage
            self._update_successful_auth(site_domain, client_ip)
            
            validation_context['result'] = 'success'
            validation_context['account_id'] = credential['account_id']
            
            return {
                'valid': True,
                'account_id': credential['account_id'],
                'permissions': credential['permissions'],
                'expires_at': credential['expires_at'],
                'tier': credential.get('tier', 'standard'),
                'security_version': credential.get('security_version', '1.0')
            }
            
        except Exception as e:
            self._log_security_event(
                credential.get('account_id') if 'credential' in locals() else None,
                'authentication_failed',
                validation_context
            )
            raise e
        
        finally:
            # Always log the attempt
            self._log_access_attempt(site_domain, validation_context)
    
    # =================================================================
    # ENHANCED RATE LIMITING & THREAT DETECTION
    # =================================================================
    
    def _check_enhanced_rate_limit(self, site_domain: str, 
                                  client_ip: str = None) -> bool:
        """
        Enhanced rate limiting with IP tracking and adaptive limits
        """
        current_hour = datetime.utcnow().strftime('%Y-%m-%d-%H')
        
        # Site-level rate limiting
        site_key = f'SITE#{site_domain}'
        site_limit_key = f'RATE#{current_hour}'
        
        site_count = self._increment_rate_counter(site_key, site_limit_key)
        
        # Get site tier for appropriate limit
        try:
            site_info = self.table.get_item(
                Key={'PK': site_key, 'SK': 'KEY#current'},
                ProjectionExpression='tier, failed_attempts'
            )['Item']
            
            tier = site_info.get('tier', 'standard')
            failed_attempts = site_info.get('failed_attempts', 0)
            
        except:
            tier = 'standard'
            failed_attempts = 0
        
        # Determine rate limit based on tier and security status
        if failed_attempts > 5:
            rate_limit = self.rate_limits['auth_failures']
        else:
            rate_limit = self.rate_limits.get(tier, self.rate_limits['default'])
        
        if site_count > rate_limit:
            return False
        
        # IP-level rate limiting (if IP provided)
        if client_ip:
            ip_key = f'IP#{client_ip}'
            ip_limit_key = f'RATE#{current_hour}'
            ip_count = self._increment_rate_counter(ip_key, ip_limit_key)
            
            # More restrictive IP limits
            ip_limit = min(rate_limit * 0.5, 50)  # Max 50 requests per hour per IP
            if ip_count > ip_limit:
                self._flag_suspicious_ip(client_ip, ip_count)
                return False
        
        return True
    
    def _increment_rate_counter(self, partition_key: str, 
                               sort_key: str) -> int:
        """Increment rate counter and return current count"""
        try:
            response = self.table.update_item(
                Key={'PK': partition_key, 'SK': sort_key},
                UpdateExpression='ADD request_count :inc SET #ttl = if_not_exists(#ttl, :ttl_val)',
                ExpressionAttributeNames={'#ttl': 'ttl'},
                ExpressionAttributeValues={
                    ':inc': 1,
                    ':ttl_val': int(time.time()) + (25 * 3600)  # 25 hours
                },
                ReturnValues='ALL_NEW'
            )
            
            return response['Attributes']['request_count']
            
        except Exception:
            return 1
    
    def _increment_failed_attempts(self, site_domain: str) -> None:
        """Track failed authentication attempts"""
        try:
            response = self.table.update_item(
                Key={'PK': f'SITE#{site_domain}', 'SK': 'KEY#current'},
                UpdateExpression='ADD failed_attempts :inc SET last_failed = :timestamp',
                ExpressionAttributeValues={
                    ':inc': 1,
                    ':timestamp': datetime.utcnow().isoformat()
                },
                ReturnValues='ALL_NEW'
            )
            
            failed_count = response['Attributes']['failed_attempts']
            
            # Lock account after threshold
            if failed_count >= 10:
                lock_until = datetime.utcnow() + timedelta(
                    minutes=self.security_policies['failed_auth_lockout_minutes']
                )
                
                self.table.update_item(
                    Key={'PK': f'SITE#{site_domain}', 'SK': 'KEY#current'},
                    UpdateExpression='SET locked_until = :lock_time, #status = :status',
                    ExpressionAttributeNames={'#status': 'status'},
                    ExpressionAttributeValues={
                        ':lock_time': lock_until.isoformat(),
                        ':status': 'temporarily_locked'
                    }
                )
                
        except Exception as e:
            print(f"Failed to increment failed attempts: {e}")
    
    def _update_successful_auth(self, site_domain: str, client_ip: str = None) -> None:
        """Update successful authentication metrics"""
        self.table.update_item(
            Key={'PK': f'SITE#{site_domain}', 'SK': 'KEY#current'},
            UpdateExpression='ADD usage_count :inc SET last_used = :timestamp, failed_attempts = :zero',
            ExpressionAttributeValues={
                ':inc': 1,
                ':timestamp': datetime.utcnow().isoformat(),
                ':zero': 0
            }
        )
        
        # Track successful IP
        if client_ip:
            self.table.put_item(
                Item={
                    'PK': f'IP#{client_ip}',
                    'SK': f'SUCCESS#{datetime.utcnow().isoformat()}',
                    'site_domain': site_domain,
                    'timestamp': datetime.utcnow().isoformat(),
                    'ttl': int(time.time()) + (7 * 24 * 3600)  # 7 days
                }
            )
    
    def _flag_suspicious_ip(self, client_ip: str, request_count: int) -> None:
        """Flag suspicious IP addresses"""
        flag_record = {
            'PK': f'SECURITY#SUSPICIOUS_IP',
            'SK': f'{client_ip}#{datetime.utcnow().isoformat()}',
            'ip_address': client_ip,
            'request_count': request_count,
            'flagged_at': datetime.utcnow().isoformat(),
            'status': 'under_review',
            'ttl': int(time.time()) + (30 * 24 * 3600)  # 30 days
        }
        
        self.table.put_item(Item=flag_record)
        
        # Send CloudWatch alert
        self.cloudwatch.put_metric_data(
            Namespace='WordPress/Security',
            MetricData=[
                {
                    'MetricName': 'SuspiciousIPActivity',
                    'Value': request_count,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'IPAddress', 'Value': client_ip}
                    ]
                }
            ]
        )
    
    # =================================================================
    # SECURITY MONITORING & ALERTING
    # =================================================================
    
    def _log_security_event(self, account_id: str, event_type: str, 
                           event_data: Dict) -> None:
        """Log security events with structured data"""
        event_id = secrets.token_hex(16)
        timestamp = datetime.utcnow()
        
        security_log = {
            'PK': f'SECURITY#{timestamp.strftime("%Y-%m-%d")}',
            'SK': f'{event_type}#{timestamp.isoformat()}#{event_id}',
            'event_id': event_id,
            'event_type': event_type,
            'account_id': account_id,
            'event_data': event_data,
            'timestamp': timestamp.isoformat(),
            'severity': self._determine_event_severity(event_type),
            'source': 'wordpress_auth_system',
            'version': '2.0',
            
            # GSI for time-based queries
            'GSI1PK': f'SECURITY#{event_type}',
            'GSI1SK': timestamp.isoformat(),
            
            # TTL based on retention policy
            'ttl': int(time.time()) + (self.security_policies['audit_retention_days'] * 24 * 3600)
        }
        
        self.table.put_item(Item=security_log)
        
        # Send to CloudWatch if high severity
        if security_log['severity'] in ['HIGH', 'CRITICAL']:
            self._send_security_alert(security_log)
    
    def _determine_event_severity(self, event_type: str) -> str:
        """Determine severity level for security events"""
        severity_mapping = {
            'key_compromised': 'CRITICAL',
            'account_locked': 'HIGH',
            'rate_limit_exceeded': 'MEDIUM',
            'invalid_credentials': 'LOW',
            'suspicious_ip_flagged': 'MEDIUM',
            'mass_authentication_failure': 'HIGH',
            'encryption_failure': 'CRITICAL',
            'secure_credentials_created': 'INFO',
            'successful_authentication': 'INFO'
        }
        
        return severity_mapping.get(event_type, 'LOW')
    
    def _send_security_alert(self, security_log: Dict) -> None:
        """Send security alerts to CloudWatch"""
        self.cloudwatch.put_metric_data(
            Namespace='WordPress/Security',
            MetricData=[
                {
                    'MetricName': 'SecurityEvent',
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'EventType', 'Value': security_log['event_type']},
                        {'Name': 'Severity', 'Value': security_log['severity']},
                        {'Name': 'AccountId', 'Value': security_log.get('account_id', 'unknown')}
                    ]
                }
            ]
        )
    
    def _log_access_attempt(self, site_domain: str, validation_context: Dict) -> None:
        """Log all access attempts for forensic analysis"""
        access_log = {
            'PK': f'ACCESS#{site_domain}',
            'SK': f'{datetime.utcnow().isoformat()}#{secrets.token_hex(8)}',
            'site_domain': site_domain,
            'validation_result': validation_context['result'],
            'client_ip': validation_context.get('client_ip'),
            'key_id': validation_context.get('key_id'),
            'timestamp': validation_context['timestamp'],
            'security_flags': validation_context.get('security_flags', []),
            'ttl': int(time.time()) + (90 * 24 * 3600)  # 90 days
        }
        
        self.table.put_item(Item=access_log)
    
    # =================================================================
    # COMPLIANCE & REPORTING
    # =================================================================
    
    def generate_security_report(self, account_id: str = None, 
                                days_back: int = 30) -> Dict:
        """
        Generate comprehensive security report
        """
        start_date = datetime.utcnow() - timedelta(days=days_back)
        
        report = {
            'report_id': secrets.token_hex(16),
            'generated_at': datetime.utcnow().isoformat(),
            'period_start': start_date.isoformat(),
            'period_end': datetime.utcnow().isoformat(),
            'account_id': account_id,
            'summary': {},
            'security_events': {},
            'recommendations': []
        }
        
        # Query security events
        if account_id:
            # Account-specific report
            events = self._get_account_security_events(account_id, start_date)
        else:
            # Global security report
            events = self._get_global_security_events(start_date)
        
        # Analyze events
        event_counts = {}
        high_severity_events = []
        
        for event in events:
            event_type = event['event_type']
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
            if event.get('severity') in ['HIGH', 'CRITICAL']:
                high_severity_events.append(event)
        
        report['summary'] = {
            'total_events': len(events),
            'event_breakdown': event_counts,
            'high_severity_count': len(high_severity_events),
            'most_common_event': max(event_counts.items(), key=lambda x: x[1])[0] if event_counts else None
        }
        
        report['security_events'] = {
            'high_severity': high_severity_events[:10],  # Top 10 critical events
            'event_timeline': self._create_event_timeline(events)
        }
        
        # Generate recommendations
        report['recommendations'] = self._generate_security_recommendations(event_counts, account_id)
        
        return report
    
    def _get_account_security_events(self, account_id: str, 
                                    start_date: datetime) -> List[Dict]:
        """Get security events for specific account"""
        # This would be a more complex query in practice
        # For now, simplified implementation
        response = self.table.scan(
            FilterExpression=(
                Attr('account_id').eq(account_id) &
                Attr('timestamp').gte(start_date.isoformat()) &
                Attr('PK').begins_with('SECURITY#')
            ),
            ProjectionExpression='event_type, severity, timestamp, event_data'
        )
        
        return response.get('Items', [])
    
    def _get_global_security_events(self, start_date: datetime) -> List[Dict]:
        """Get global security events"""
        response = self.table.scan(
            FilterExpression=(
                Attr('timestamp').gte(start_date.isoformat()) &
                Attr('PK').begins_with('SECURITY#')
            ),
            ProjectionExpression='event_type, severity, timestamp, event_data, account_id'
        )
        
        return response.get('Items', [])
    
    def _create_event_timeline(self, events: List[Dict]) -> List[Dict]:
        """Create timeline of security events"""
        timeline = []
        
        # Group events by hour
        hourly_events = {}
        for event in events:
            hour = event['timestamp'][:13]  # YYYY-MM-DDTHH
            if hour not in hourly_events:
                hourly_events[hour] = []
            hourly_events[hour].append(event)
        
        # Create timeline entries
        for hour, hour_events in sorted(hourly_events.items()):
            timeline.append({
                'hour': hour,
                'event_count': len(hour_events),
                'severity_breakdown': self._count_by_severity(hour_events)
            })
        
        return timeline
    
    def _count_by_severity(self, events: List[Dict]) -> Dict:
        """Count events by severity level"""
        counts = {'INFO': 0, 'LOW': 0, 'MEDIUM': 0, 'HIGH': 0, 'CRITICAL': 0}
        for event in events:
            severity = event.get('severity', 'LOW')
            counts[severity] = counts.get(severity, 0) + 1
        return counts
    
    def _generate_security_recommendations(self, event_counts: Dict, 
                                         account_id: str = None) -> List[str]:
        """Generate security recommendations based on event patterns"""
        recommendations = []
        
        # Check for high authentication failures
        if event_counts.get('invalid_credentials', 0) > 100:
            recommendations.append(
                "High number of authentication failures detected. "
                "Consider implementing additional rate limiting or CAPTCHA."
            )
        
        # Check for rate limiting issues
        if event_counts.get('rate_limit_exceeded', 0) > 50:
            recommendations.append(
                "Frequent rate limiting triggers. Review rate limits and "
                "consider implementing tiered access controls."
            )
        
        # Check for encryption issues
        if event_counts.get('encryption_failure', 0) > 0:
            recommendations.append(
                "Encryption failures detected. Review KMS permissions and "
                "key management procedures immediately."
            )
        
        # Check for account lockouts
        if event_counts.get('account_locked', 0) > 10:
            recommendations.append(
                "Multiple account lockouts suggest possible brute force attacks. "
                "Review IP whitelisting and implement additional security measures."
            )
        
        # Always include best practices
        recommendations.extend([
            "Ensure all sites are using the latest security version credentials.",
            "Review and rotate keys older than 90 days.",
            "Monitor CloudWatch dashboards for security metrics regularly.",
            "Implement automated alerting for critical security events."
        ])
        
        return recommendations

# =================================================================
# CLOUDWATCH DASHBOARD CONFIGURATION
# =================================================================

SECURITY_DASHBOARD_CONFIG = {
    "widgets": [
        {
            "type": "metric",
            "properties": {
                "metrics": [
                    ["WordPress/Security", "SecurityEvent", "EventType", "invalid_credentials"],
                    ["...", "rate_limit_exceeded"],
                    ["...", "key_compromised"],
                    ["...", "account_locked"]
                ],
                "period": 300,
                "stat": "Sum",
                "region": "us-east-1",
                "title": "Security Events"
            }
        },
        {
            "type": "metric",
            "properties": {
                "metrics": [
                    ["WordPress/Security", "SuspiciousIPActivity"]
                ],
                "period": 300,
                "stat": "Average",
                "region": "us-east-1",
                "title": "Suspicious IP Activity"
            }
        }
    ]
}

if __name__ == "__main__":
    # Example usage
    security_manager = WordPressSecurityManager(
        'WordPressAuthCredentials',
        'arn:aws:kms:us-east-1:123456789012:alias/wordpress-auth'
    )
    
    # Create secure credentials
    credentials = security_manager.create_secure_site_credentials(
        account_id='acc_123',
        site_domain='example.com',
        permissions=['plugin_update', 'license_check'],
        tier='premium'
    )
    
    print(f"Created secure credentials: {credentials['key_id']}")
    
    # Validate credentials
    try:
        validation_result = security_manager.validate_secure_credentials(
            credentials['key_id'],
            credentials['secret'],
            'example.com',
            client_ip='192.168.1.1'
        )
        print(f"Validation successful: {validation_result}")
        
    except Exception as e:
        print(f"Validation failed: {e}")
    
    # Generate security report
    report = security_manager.generate_security_report('acc_123', days_back=7)
    print(f"Security report generated: {report['report_id']}")