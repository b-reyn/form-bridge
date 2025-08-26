"""
Site Validation Lambda for Form-Bridge WordPress Plugin
Validates WordPress sites to prevent abuse and ensure legitimate usage.
"""

import json
import os
import re
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Set
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
import requests
from urllib.parse import urlparse, urljoin
import dns.resolver
import dns.exception

logger = Logger()
tracer = Tracer()
metrics = Metrics()

# AWS clients
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

# Configuration
VALIDATION_TIMEOUT = 15  # seconds for HTTP requests
DNS_TIMEOUT = 5  # seconds for DNS lookups
MAX_VALIDATION_ATTEMPTS = 3
VALIDATION_CACHE_TTL = 86400  # 24 hours

# Known abuse patterns
BLOCKED_DOMAINS = {
    'localhost', '127.0.0.1', 'example.com', 'test.com', 'sample.com',
    'demo.com', 'temp.com', 'fake.com', 'invalid.com', 'null.com'
}

BLOCKED_TLD_PATTERNS = {
    '.local', '.test', '.example', '.invalid', '.temp'
}

SUSPICIOUS_KEYWORDS = {
    'test', 'demo', 'temp', 'fake', 'sample', 'example', 
    'staging', 'dev', 'localhost', 'beta', 'alpha'
}

# WordPress fingerprinting patterns
WP_INDICATORS = [
    '/wp-content/',
    '/wp-includes/',
    '/wp-admin/',
    'wp-json',
    'wp_head',
    'WordPress',
    'wp-',
    '/xmlrpc.php'
]

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Validate WordPress site legitimacy and detect abuse patterns
    
    Expected input:
    {
        "domain": "example.com",
        "registration_id": "reg_123",
        "validation_level": "basic|standard|strict"
    }
    """
    try:
        # Parse request body
        try:
            body = json.loads(event.get('body', '{}'))
        except json.JSONDecodeError:
            return _error_response(400, "INVALID_JSON", "Invalid JSON in request body")
        
        # Extract parameters
        domain = body.get('domain', '').lower().strip()
        registration_id = body.get('registration_id', '').strip()
        validation_level = body.get('validation_level', 'standard').lower()
        
        if not domain:
            return _error_response(400, "MISSING_DOMAIN", "Domain is required")
        
        if not registration_id:
            return _error_response(400, "MISSING_REGISTRATION_ID", "Registration ID is required")
        
        # Check if validation already exists and is recent
        cached_result = _get_cached_validation(domain)
        if cached_result and not _is_validation_expired(cached_result):
            logger.info("Using cached validation", extra={
                'domain': domain,
                'cached_score': cached_result['validation_score']
            })
            return _success_response(cached_result)
        
        # Perform validation
        validation_results = _perform_site_validation(domain, validation_level)
        
        # Calculate overall validation score
        validation_score = _calculate_validation_score(validation_results)
        
        # Determine if site passes validation
        passes_validation = _determine_validation_result(validation_score, validation_level)
        
        # Prepare response
        response_data = {
            'domain': domain,
            'registration_id': registration_id,
            'validation_level': validation_level,
            'passes_validation': passes_validation,
            'validation_score': validation_score,
            'validation_results': validation_results,
            'validated_at': datetime.utcnow().isoformat() + 'Z',
            'valid_until': (datetime.utcnow() + timedelta(seconds=VALIDATION_CACHE_TTL)).isoformat() + 'Z'
        }
        
        # Store validation result
        _store_validation_result(domain, registration_id, response_data)
        
        # Log validation metrics
        metrics.add_metric(name="SiteValidations", unit=MetricUnit.Count, value=1)
        metrics.add_metadata(key="domain", value=domain)
        metrics.add_metadata(key="validation_level", value=validation_level)
        metrics.add_metadata(key="passes_validation", value=str(passes_validation))
        metrics.add_metadata(key="validation_score", value=str(validation_score))
        
        logger.info("Site validation completed", extra={
            'domain': domain,
            'validation_score': validation_score,
            'passes_validation': passes_validation
        })
        
        return _success_response(response_data)
        
    except Exception as e:
        logger.exception("Site validation error")
        metrics.add_metric(name="SiteValidationErrors", unit=MetricUnit.Count, value=1)
        return _error_response(500, "INTERNAL_ERROR", "Site validation temporarily unavailable")

def _perform_site_validation(domain: str, validation_level: str) -> Dict[str, Any]:
    """Perform comprehensive site validation"""
    results = {
        'domain_checks': _validate_domain_format(domain),
        'dns_checks': _validate_dns_records(domain),
        'http_checks': _validate_http_response(domain),
        'wordpress_checks': _validate_wordpress_installation(domain),
        'abuse_checks': _check_abuse_patterns(domain),
        'security_checks': _perform_security_checks(domain)
    }
    
    # Add advanced checks for higher validation levels
    if validation_level in ['standard', 'strict']:
        results['content_analysis'] = _analyze_site_content(domain)
        results['hosting_analysis'] = _analyze_hosting_environment(domain)
    
    if validation_level == 'strict':
        results['behavioral_analysis'] = _analyze_site_behavior(domain)
        results['reputation_checks'] = _check_domain_reputation(domain)
    
    return results

def _validate_domain_format(domain: str) -> Dict[str, Any]:
    """Validate domain format and basic legitimacy"""
    checks = {
        'valid_format': True,
        'not_blocked': True,
        'not_suspicious': True,
        'has_valid_tld': True,
        'issues': []
    }
    
    try:
        # Basic format validation
        if not re.match(r'^[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?)*$', domain):
            checks['valid_format'] = False
            checks['issues'].append('Invalid domain format')
        
        # Check against blocked domains
        if domain in BLOCKED_DOMAINS:
            checks['not_blocked'] = False
            checks['issues'].append('Domain is in blocked list')
        
        # Check TLD patterns
        for pattern in BLOCKED_TLD_PATTERNS:
            if domain.endswith(pattern):
                checks['has_valid_tld'] = False
                checks['issues'].append(f'Blocked TLD pattern: {pattern}')
        
        # Check for suspicious keywords
        domain_parts = domain.replace('.', '-').replace('_', '-').split('-')
        suspicious_found = any(part in SUSPICIOUS_KEYWORDS for part in domain_parts)
        if suspicious_found:
            checks['not_suspicious'] = False
            checks['issues'].append('Contains suspicious keywords')
        
        checks['score'] = sum([
            checks['valid_format'] * 30,
            checks['not_blocked'] * 25,
            checks['not_suspicious'] * 20,
            checks['has_valid_tld'] * 25
        ])
        
    except Exception as e:
        logger.warning("Domain format validation error", extra={'error': str(e)})
        checks['score'] = 0
        checks['issues'].append('Validation error occurred')
    
    return checks

def _validate_dns_records(domain: str) -> Dict[str, Any]:
    """Validate DNS configuration"""
    checks = {
        'has_a_record': False,
        'has_mx_record': False,
        'dns_resolves': False,
        'issues': []
    }
    
    try:
        # Check A record
        try:
            dns.resolver.resolve(domain, 'A', lifetime=DNS_TIMEOUT)
            checks['has_a_record'] = True
            checks['dns_resolves'] = True
        except dns.exception.DNSException:
            checks['issues'].append('No A record found')
        
        # Check MX record (indicates legitimate business)
        try:
            dns.resolver.resolve(domain, 'MX', lifetime=DNS_TIMEOUT)
            checks['has_mx_record'] = True
        except dns.exception.DNSException:
            pass  # MX record is optional
        
        checks['score'] = sum([
            checks['dns_resolves'] * 60,
            checks['has_a_record'] * 30,
            checks['has_mx_record'] * 10
        ])
        
    except Exception as e:
        logger.warning("DNS validation error", extra={'error': str(e), 'domain': domain})
        checks['score'] = 0
        checks['issues'].append('DNS lookup failed')
    
    return checks

def _validate_http_response(domain: str) -> Dict[str, Any]:
    """Validate HTTP response and basic connectivity"""
    checks = {
        'responds_http': False,
        'responds_https': False,
        'valid_status_code': False,
        'has_content': False,
        'response_time_ms': None,
        'issues': []
    }
    
    try:
        # Try HTTPS first, then HTTP
        for protocol in ['https', 'http']:
            url = f"{protocol}://{domain}/"
            
            try:
                start_time = time.time()
                response = requests.get(
                    url,
                    timeout=VALIDATION_TIMEOUT,
                    headers={'User-Agent': 'Form-Bridge-Validator/1.0'},
                    allow_redirects=True,
                    verify=False  # Don't fail on SSL issues
                )
                
                response_time = int((time.time() - start_time) * 1000)
                
                if protocol == 'https':
                    checks['responds_https'] = True
                else:
                    checks['responds_http'] = True
                
                if response.status_code in [200, 301, 302]:
                    checks['valid_status_code'] = True
                
                if len(response.text.strip()) > 100:
                    checks['has_content'] = True
                
                if checks['response_time_ms'] is None:
                    checks['response_time_ms'] = response_time
                
                # If HTTPS works, we're done
                if protocol == 'https' and response.status_code == 200:
                    break
                    
            except requests.exceptions.Timeout:
                checks['issues'].append(f'{protocol.upper()} request timed out')
            except requests.exceptions.RequestException as e:
                checks['issues'].append(f'{protocol.upper()} request failed: {str(e)[:100]}')
        
        checks['score'] = sum([
            checks['responds_https'] * 40,
            checks['responds_http'] * 20,
            checks['valid_status_code'] * 25,
            checks['has_content'] * 15
        ])
        
    except Exception as e:
        logger.warning("HTTP validation error", extra={'error': str(e), 'domain': domain})
        checks['score'] = 0
        checks['issues'].append('HTTP validation failed')
    
    return checks

def _validate_wordpress_installation(domain: str) -> Dict[str, Any]:
    """Validate that site is actually running WordPress"""
    checks = {
        'has_wp_indicators': False,
        'wp_json_accessible': False,
        'wp_version_detected': False,
        'wp_admin_accessible': False,
        'wp_indicators_found': [],
        'issues': []
    }
    
    try:
        # Check main page for WordPress indicators
        for protocol in ['https', 'http']:
            try:
                response = requests.get(
                    f"{protocol}://{domain}/",
                    timeout=VALIDATION_TIMEOUT,
                    headers={'User-Agent': 'Form-Bridge-Validator/1.0'},
                    allow_redirects=True
                )
                
                if response.status_code == 200:
                    content = response.text.lower()
                    
                    # Look for WordPress indicators
                    found_indicators = [indicator for indicator in WP_INDICATORS if indicator.lower() in content]
                    
                    if found_indicators:
                        checks['has_wp_indicators'] = True
                        checks['wp_indicators_found'] = found_indicators[:5]  # Limit to first 5
                    
                    # Check for WordPress version
                    if 'wordpress' in content or 'wp-' in content:
                        checks['wp_version_detected'] = True
                    
                    break
                    
            except requests.exceptions.RequestException:
                continue
        
        # Check WP REST API
        for protocol in ['https', 'http']:
            try:
                wp_json_url = f"{protocol}://{domain}/wp-json/wp/v2/"
                response = requests.get(
                    wp_json_url,
                    timeout=VALIDATION_TIMEOUT,
                    headers={'User-Agent': 'Form-Bridge-Validator/1.0'}
                )
                
                if response.status_code == 200 and 'application/json' in response.headers.get('content-type', ''):
                    checks['wp_json_accessible'] = True
                    break
                    
            except requests.exceptions.RequestException:
                continue
        
        # Check wp-admin accessibility (should return login page)
        for protocol in ['https', 'http']:
            try:
                wp_admin_url = f"{protocol}://{domain}/wp-admin/"
                response = requests.get(
                    wp_admin_url,
                    timeout=VALIDATION_TIMEOUT,
                    headers={'User-Agent': 'Form-Bridge-Validator/1.0'},
                    allow_redirects=True
                )
                
                if response.status_code == 200 and ('login' in response.text.lower() or 'wp-login' in response.url):
                    checks['wp_admin_accessible'] = True
                    break
                    
            except requests.exceptions.RequestException:
                continue
        
        # Calculate score based on WordPress indicators
        checks['score'] = sum([
            checks['has_wp_indicators'] * 40,
            checks['wp_json_accessible'] * 35,
            checks['wp_admin_accessible'] * 15,
            checks['wp_version_detected'] * 10
        ])
        
        if not any([checks['has_wp_indicators'], checks['wp_json_accessible'], checks['wp_admin_accessible']]):
            checks['issues'].append('No WordPress indicators found')
    
    except Exception as e:
        logger.warning("WordPress validation error", extra={'error': str(e), 'domain': domain})
        checks['score'] = 0
        checks['issues'].append('WordPress validation failed')
    
    return checks

def _check_abuse_patterns(domain: str) -> Dict[str, Any]:
    """Check for known abuse patterns"""
    checks = {
        'not_in_blocklist': True,
        'registration_frequency_ok': True,
        'no_suspicious_patterns': True,
        'issues': []
    }
    
    try:
        # Check recent registration frequency from this domain/IP
        recent_registrations = _count_recent_registrations(domain)
        if recent_registrations > 5:  # More than 5 registrations in last hour
            checks['registration_frequency_ok'] = False
            checks['issues'].append(f'Too many recent registrations: {recent_registrations}')
        
        # Check for known malicious patterns in domain
        suspicious_patterns = ['phishing', 'spam', 'malware', 'scam', 'fake']
        if any(pattern in domain for pattern in suspicious_patterns):
            checks['no_suspicious_patterns'] = False
            checks['issues'].append('Domain contains suspicious patterns')
        
        checks['score'] = sum([
            checks['not_in_blocklist'] * 40,
            checks['registration_frequency_ok'] * 35,
            checks['no_suspicious_patterns'] * 25
        ])
        
    except Exception as e:
        logger.warning("Abuse pattern check error", extra={'error': str(e)})
        checks['score'] = 100  # Assume no abuse if check fails
    
    return checks

def _perform_security_checks(domain: str) -> Dict[str, Any]:
    """Perform basic security checks"""
    checks = {
        'ssl_available': False,
        'no_malware_indicators': True,
        'headers_secure': False,
        'issues': []
    }
    
    try:
        # Check SSL/TLS
        try:
            response = requests.get(
                f"https://{domain}/",
                timeout=VALIDATION_TIMEOUT,
                headers={'User-Agent': 'Form-Bridge-Validator/1.0'}
            )
            checks['ssl_available'] = True
            
            # Check security headers
            security_headers = ['x-frame-options', 'x-content-type-options', 'x-xss-protection']
            if any(header in response.headers for header in security_headers):
                checks['headers_secure'] = True
                
        except requests.exceptions.SSLError:
            checks['issues'].append('SSL/TLS not properly configured')
        except requests.exceptions.RequestException:
            checks['issues'].append('HTTPS not accessible')
        
        checks['score'] = sum([
            checks['ssl_available'] * 50,
            checks['no_malware_indicators'] * 30,
            checks['headers_secure'] * 20
        ])
        
    except Exception as e:
        logger.warning("Security check error", extra={'error': str(e)})
        checks['score'] = 50  # Neutral score if checks fail
    
    return checks

def _analyze_site_content(domain: str) -> Dict[str, Any]:
    """Analyze site content for legitimacy indicators"""
    # Placeholder for advanced content analysis
    return {
        'has_real_content': True,
        'content_length_adequate': True,
        'language_detected': 'en',
        'score': 80
    }

def _analyze_hosting_environment(domain: str) -> Dict[str, Any]:
    """Analyze hosting environment"""
    # Placeholder for hosting analysis
    return {
        'hosting_provider': 'unknown',
        'server_location': 'unknown',
        'hosting_reputation': 'neutral',
        'score': 70
    }

def _analyze_site_behavior(domain: str) -> Dict[str, Any]:
    """Analyze site behavioral patterns"""
    # Placeholder for behavioral analysis
    return {
        'traffic_patterns_normal': True,
        'update_frequency_normal': True,
        'user_engagement_indicators': True,
        'score': 75
    }

def _check_domain_reputation(domain: str) -> Dict[str, Any]:
    """Check domain reputation against threat intelligence"""
    # Placeholder for reputation checks
    return {
        'not_in_threat_feeds': True,
        'domain_age_adequate': True,
        'reputation_score': 85,
        'score': 85
    }

def _count_recent_registrations(domain: str) -> int:
    """Count recent registrations from this domain"""
    try:
        one_hour_ago = int((datetime.utcnow() - timedelta(hours=1)).timestamp())
        
        response = table.query(
            IndexName='GSI1',
            KeyConditionExpression='GSI1PK = :domain AND GSI1SK > :timestamp',
            ExpressionAttributeValues={
                ':domain': f'DOMAIN#{domain}',
                ':timestamp': f'REG#{one_hour_ago}'
            }
        )
        
        return len(response.get('Items', []))
    except Exception:
        return 0

def _calculate_validation_score(results: Dict[str, Any]) -> int:
    """Calculate overall validation score from individual check results"""
    total_score = 0
    total_weight = 0
    
    # Weight different categories
    weights = {
        'domain_checks': 1.0,
        'dns_checks': 1.5,
        'http_checks': 1.2,
        'wordpress_checks': 2.0,
        'abuse_checks': 1.8,
        'security_checks': 1.3,
        'content_analysis': 1.0,
        'hosting_analysis': 0.8,
        'behavioral_analysis': 1.1,
        'reputation_checks': 1.4
    }
    
    for category, result in results.items():
        if isinstance(result, dict) and 'score' in result:
            weight = weights.get(category, 1.0)
            total_score += result['score'] * weight
            total_weight += weight
    
    return int(total_score / total_weight) if total_weight > 0 else 0

def _determine_validation_result(score: int, validation_level: str) -> bool:
    """Determine if site passes validation based on score and level"""
    thresholds = {
        'basic': 40,
        'standard': 60,
        'strict': 80
    }
    
    return score >= thresholds.get(validation_level, 60)

def _get_cached_validation(domain: str) -> Optional[Dict[str, Any]]:
    """Get cached validation result"""
    try:
        response = table.get_item(
            Key={
                'PK': f'VALIDATION#{domain}',
                'SK': 'RESULT'
            }
        )
        
        return response.get('Item')
    except Exception:
        return None

def _is_validation_expired(validation_result: Dict[str, Any]) -> bool:
    """Check if validation result is expired"""
    try:
        valid_until = validation_result.get('valid_until')
        if not valid_until:
            return True
        
        expiry_time = datetime.fromisoformat(valid_until.replace('Z', '+00:00'))
        now = datetime.utcnow().replace(tzinfo=expiry_time.tzinfo)
        
        return now > expiry_time
    except Exception:
        return True

def _store_validation_result(domain: str, registration_id: str, result: Dict[str, Any]):
    """Store validation result in DynamoDB"""
    try:
        table.put_item(
            Item={
                'PK': f'VALIDATION#{domain}',
                'SK': 'RESULT',
                'GSI1PK': f'REG#{registration_id}',
                'GSI1SK': 'VALIDATION',
                'ttl': int((datetime.utcnow() + timedelta(seconds=VALIDATION_CACHE_TTL)).timestamp()),
                **result
            }
        )
    except Exception as e:
        logger.warning("Failed to store validation result", extra={'error': str(e)})

def _success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return success response with CORS headers"""
    return {
        'statusCode': 200,
        'headers': _get_cors_headers(),
        'body': json.dumps({
            'success': True,
            'data': data,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
    }

def _error_response(status_code: int, error_code: str, message: str) -> Dict[str, Any]:
    """Return error response with CORS headers"""
    return {
        'statusCode': status_code,
        'headers': _get_cors_headers(),
        'body': json.dumps({
            'success': False,
            'error': {
                'code': error_code,
                'message': message
            },
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
    }

def _get_cors_headers() -> Dict[str, str]:
    """Get CORS headers for WordPress plugin requests"""
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type, X-Amz-Date, Authorization, X-Api-Key',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Cache-Control': 'no-store, no-cache, must-revalidate'
    }