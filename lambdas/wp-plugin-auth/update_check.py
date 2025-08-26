"""
Update Check Lambda for Form-Bridge WordPress Plugin
Handles plugin version checking and secure update distribution.
"""

import json
import os
import hashlib
import hmac
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from packaging import version
import urllib.parse

logger = Logger()
tracer = Tracer()
metrics = Metrics()

# AWS clients
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')
secrets_client = boto3.client('secretsmanager')
table = dynamodb.Table(os.environ['TABLE_NAME'])

# Configuration
PLUGIN_BUCKET = os.environ.get('PLUGIN_BUCKET', 'form-bridge-plugin-releases')
SIGNING_SECRET_NAME = os.environ.get('SIGNING_SECRET_NAME', 'form-bridge/plugin-signing-key')
UPDATE_CHECK_CACHE_TTL = 3600  # 1 hour
MAX_DOWNLOAD_ATTEMPTS = 3

@logger.inject_lambda_context
@tracer.capture_lambda_handler  
@metrics.log_metrics
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle WordPress plugin update checks
    
    Expected query parameters:
    - current_version: Current plugin version (e.g., "1.2.3")
    - wp_version: WordPress version
    - php_version: PHP version (optional)
    - site_id: Site identifier for tracking
    """
    try:
        # Extract query parameters
        params = event.get('queryStringParameters') or {}
        current_version = params.get('current_version', '').strip()
        wp_version = params.get('wp_version', '').strip()
        php_version = params.get('php_version', '').strip()
        site_id = params.get('site_id', '').strip()
        
        # Validate required parameters
        if not current_version:
            return _error_response(400, "MISSING_VERSION", "current_version parameter is required")
        
        if not _is_valid_version(current_version):
            return _error_response(400, "INVALID_VERSION", "Invalid version format")
        
        # Get site information from authorizer context (if authenticated)
        auth_context = event.get('requestContext', {}).get('authorizer', {})
        authenticated_site_id = auth_context.get('site_id')
        authenticated_domain = auth_context.get('domain')
        
        # Use authenticated site_id if available, otherwise use provided site_id
        effective_site_id = authenticated_site_id or site_id
        
        # Get latest available version
        latest_version_info = _get_latest_version()
        if not latest_version_info:
            return _error_response(503, "VERSION_UNAVAILABLE", "Unable to check for updates at this time")
        
        latest_version = latest_version_info['version']
        
        # Compare versions
        update_available = version.parse(latest_version) > version.parse(current_version)
        
        # Log update check
        _log_update_check(effective_site_id, current_version, latest_version, update_available, authenticated_domain)
        
        # Prepare response
        response_data = {
            'current_version': current_version,
            'latest_version': latest_version,
            'update_available': update_available,
            'checked_at': datetime.utcnow().isoformat() + 'Z'
        }
        
        # If update is available, include update details
        if update_available:
            # Check compatibility
            compatibility_check = _check_compatibility(latest_version_info, wp_version, php_version)
            
            if compatibility_check['compatible']:
                # Generate secure download URL (if site is authenticated)
                if authenticated_site_id:
                    download_info = _generate_download_info(authenticated_site_id, latest_version_info)
                    response_data.update(download_info)
                
                response_data.update({
                    'compatibility': compatibility_check,
                    'changelog_url': latest_version_info.get('changelog_url'),
                    'release_notes': latest_version_info.get('release_notes'),
                    'release_date': latest_version_info.get('release_date'),
                    'requires_wp': latest_version_info.get('requires_wp'),
                    'requires_php': latest_version_info.get('requires_php'),
                    'tested_up_to': latest_version_info.get('tested_up_to')
                })
            else:
                response_data['compatibility_warning'] = compatibility_check['warning']
        
        metrics.add_metric(name="UpdateChecks", unit=MetricUnit.Count, value=1)
        metrics.add_metadata(key="site_id", value=effective_site_id or "anonymous")
        metrics.add_metadata(key="update_available", value=str(update_available))
        
        return _success_response(response_data)
        
    except Exception as e:
        logger.exception("Update check error")
        metrics.add_metric(name="UpdateCheckErrors", unit=MetricUnit.Count, value=1)
        return _error_response(500, "INTERNAL_ERROR", "Update check temporarily unavailable")

def _is_valid_version(version_str: str) -> bool:
    """Validate version string format"""
    try:
        version.parse(version_str)
        return True
    except version.InvalidVersion:
        return False

def _get_latest_version() -> Optional[Dict[str, Any]]:
    """Get latest plugin version information with caching"""
    try:
        cache_key = 'PLUGIN_VERSION#latest'
        
        # Try to get from cache first
        cached_response = table.get_item(
            Key={
                'PK': cache_key,
                'SK': 'INFO'
            }
        )
        
        cached_item = cached_response.get('Item')
        if cached_item and not _is_cache_expired(cached_item.get('cached_at'), UPDATE_CHECK_CACHE_TTL):
            return cached_item['version_info']
        
        # Fetch latest version from S3 metadata
        version_info = _fetch_latest_from_s3()
        if not version_info:
            return cached_item.get('version_info') if cached_item else None
        
        # Update cache
        table.put_item(
            Item={
                'PK': cache_key,
                'SK': 'INFO',
                'version_info': version_info,
                'cached_at': datetime.utcnow().isoformat() + 'Z',
                'ttl': int((datetime.utcnow() + timedelta(seconds=UPDATE_CHECK_CACHE_TTL * 2)).timestamp())
            }
        )
        
        return version_info
        
    except Exception as e:
        logger.warning("Failed to get latest version", extra={'error': str(e)})
        return None

def _fetch_latest_from_s3() -> Optional[Dict[str, Any]]:
    """Fetch latest version information from S3"""
    try:
        # List objects in the releases folder
        response = s3.list_objects_v2(
            Bucket=PLUGIN_BUCKET,
            Prefix='releases/',
            Delimiter='/'
        )
        
        # Extract version numbers from folder names
        versions = []
        for common_prefix in response.get('CommonPrefixes', []):
            folder_name = common_prefix['Prefix'].replace('releases/', '').rstrip('/')
            if _is_valid_version(folder_name):
                versions.append(folder_name)
        
        if not versions:
            return None
        
        # Sort versions and get the latest
        sorted_versions = sorted(versions, key=lambda x: version.parse(x), reverse=True)
        latest = sorted_versions[0]
        
        # Get version metadata
        try:
            metadata_response = s3.get_object(
                Bucket=PLUGIN_BUCKET,
                Key=f'releases/{latest}/metadata.json'
            )
            metadata = json.loads(metadata_response['Body'].read().decode('utf-8'))
        except Exception:
            # Fallback to basic version info
            metadata = {}
        
        return {
            'version': latest,
            'release_date': metadata.get('release_date', datetime.utcnow().isoformat() + 'Z'),
            'changelog_url': metadata.get('changelog_url', f'https://form-bridge.com/changelog/{latest}'),
            'release_notes': metadata.get('release_notes', f'Form-Bridge plugin version {latest}'),
            'requires_wp': metadata.get('requires_wp', '5.0'),
            'requires_php': metadata.get('requires_php', '7.4'),
            'tested_up_to': metadata.get('tested_up_to', '6.4'),
            'download_url': f's3://{PLUGIN_BUCKET}/releases/{latest}/form-bridge.zip',
            'package_hash': metadata.get('package_hash'),
            'file_size': metadata.get('file_size')
        }
        
    except Exception as e:
        logger.warning("Failed to fetch from S3", extra={'error': str(e)})
        return None

def _check_compatibility(version_info: Dict[str, Any], wp_version: str, php_version: str) -> Dict[str, Any]:
    """Check compatibility with WordPress and PHP versions"""
    try:
        compatible = True
        warnings = []
        
        # Check WordPress compatibility
        if wp_version and version_info.get('requires_wp'):
            try:
                if version.parse(wp_version) < version.parse(version_info['requires_wp']):
                    compatible = False
                    warnings.append(f"Requires WordPress {version_info['requires_wp']} or higher (you have {wp_version})")
            except version.InvalidVersion:
                pass  # Skip if versions can't be parsed
        
        # Check PHP compatibility
        if php_version and version_info.get('requires_php'):
            try:
                if version.parse(php_version) < version.parse(version_info['requires_php']):
                    compatible = False
                    warnings.append(f"Requires PHP {version_info['requires_php']} or higher (you have {php_version})")
            except version.InvalidVersion:
                pass  # Skip if versions can't be parsed
        
        return {
            'compatible': compatible,
            'warning': '; '.join(warnings) if warnings else None
        }
        
    except Exception as e:
        logger.warning("Compatibility check failed", extra={'error': str(e)})
        return {'compatible': True}  # Assume compatible if check fails

def _generate_download_info(site_id: str, version_info: Dict[str, Any]) -> Dict[str, Any]:
    """Generate secure download information for authenticated sites"""
    try:
        download_token = _generate_download_token(site_id, version_info['version'])
        
        # Create presigned URL for S3 download
        download_url = _create_presigned_download_url(version_info['version'], download_token)
        
        return {
            'download_url': download_url,
            'download_token': download_token,
            'package_hash': version_info.get('package_hash'),
            'file_size': version_info.get('file_size'),
            'download_expires_at': (datetime.utcnow() + timedelta(hours=1)).isoformat() + 'Z'
        }
        
    except Exception as e:
        logger.warning("Failed to generate download info", extra={'error': str(e)})
        return {}

def _generate_download_token(site_id: str, version: str) -> str:
    """Generate secure download token"""
    try:
        # Get signing secret
        secret_response = secrets_client.get_secret_value(SecretId=SIGNING_SECRET_NAME)
        signing_key = json.loads(secret_response['SecretString'])['key'].encode()
        
        # Create token payload
        expires_at = int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        payload = f"{site_id}:{version}:{expires_at}"
        
        # Sign the payload
        signature = hmac.new(signing_key, payload.encode(), hashlib.sha256).hexdigest()
        
        # Encode token
        token_data = {
            'site_id': site_id,
            'version': version,
            'expires_at': expires_at,
            'signature': signature
        }
        
        return base64.urlsafe_b64encode(json.dumps(token_data).encode()).decode()
        
    except Exception as e:
        logger.error("Failed to generate download token", extra={'error': str(e)})
        raise

def _create_presigned_download_url(version: str, download_token: str) -> str:
    """Create presigned URL for secure download"""
    try:
        # Generate presigned URL
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': PLUGIN_BUCKET,
                'Key': f'releases/{version}/form-bridge.zip'
            },
            ExpiresIn=3600  # 1 hour
        )
        
        # Add download token as query parameter
        separator = '&' if '?' in presigned_url else '?'
        return f"{presigned_url}{separator}token={urllib.parse.quote(download_token)}"
        
    except Exception as e:
        logger.error("Failed to create presigned URL", extra={'error': str(e)})
        raise

def _log_update_check(site_id: str, current_version: str, latest_version: str, update_available: bool, domain: str = None):
    """Log update check for analytics"""
    try:
        if not site_id:
            return
        
        table.put_item(
            Item={
                'PK': f'UPDATE_CHECK#{site_id}',
                'SK': f'TIME#{int(datetime.utcnow().timestamp())}',
                'GSI1PK': f'UPDATES#{latest_version}',
                'GSI1SK': f'SITE#{site_id}',
                'site_id': site_id,
                'domain': domain,
                'current_version': current_version,
                'latest_version': latest_version,
                'update_available': update_available,
                'checked_at': datetime.utcnow().isoformat() + 'Z',
                'ttl': int((datetime.utcnow() + timedelta(days=90)).timestamp())  # Keep for 90 days
            }
        )
    except Exception as e:
        logger.warning("Failed to log update check", extra={'error': str(e)})

def _is_cache_expired(cached_at: str, ttl_seconds: int) -> bool:
    """Check if cache entry is expired"""
    try:
        cached_time = datetime.fromisoformat(cached_at.replace('Z', '+00:00'))
        now = datetime.utcnow().replace(tzinfo=cached_time.tzinfo)
        return (now - cached_time).total_seconds() > ttl_seconds
    except Exception:
        return True

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
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Cache-Control': 'public, max-age=300'  # Cache for 5 minutes
    }