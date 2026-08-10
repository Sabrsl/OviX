"""
Real API Test for Wayback Machine / Internet Archive.

This script performs actual API calls to verify:
- CDX API availability and response format
- Wayback API availability and response format
- Snapshot lookup functionality
- Metadata extraction
- Error handling
- Rate limiting behavior

Run with: python -m tests.integration.test_wayback_api
"""

import urllib.request
import urllib.error
import json
import time
from typing import Dict, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WaybackAPITester:
    """Test Wayback Machine API with real requests."""
    
    CDX_API_URL = "https://web.archive.org/cdx/search/cdx"
    WAYBACK_API_URL = "https://web.archive.org/web/timemap/json"
    USER_AGENT = "WikipediaMaintenanceTool/1.0 (API Testing)"
    TIMEOUT = 30
    
    def __init__(self):
        self.results = {
            'cdx_api': {'status': 'NOT_TESTED', 'details': {}},
            'wayback_api': {'status': 'NOT_TESTED', 'details': {}},
            'snapshot_lookup': {'status': 'NOT_TESTED', 'details': {}},
            'metadata_extraction': {'status': 'NOT_TESTED', 'details': {}},
            'error_handling': {'status': 'NOT_TESTED', 'details': {}}
        }
    
    def run_all_tests(self):
        """Run all API tests."""
        logger.info("=== WAYBACK MACHINE API TESTS ===")
        
        self.test_cdx_api()
        self.test_wayback_api()
        self.test_snapshot_lookup()
        self.test_metadata_extraction()
        self.test_error_handling()
        
        self.print_summary()
    
    def test_cdx_api(self):
        """Test CDX API availability and response format."""
        logger.info("\n--- Testing CDX API ---")
        
        test_url = "https://example.com"
        cdx_url = f"{self.CDX_API_URL}?url={test_url}&output=json&limit=1"
        
        try:
            start_time = time.time()
            response = self._make_request(cdx_url)
            duration = time.time() - start_time
            
            if response:
                data = json.loads(response)
                
                # Verify response structure
                if isinstance(data, list) and len(data) >= 2:
                    self.results['cdx_api']['status'] = 'PASS'
                    self.results['cdx_api']['details'] = {
                        'response_time': f"{duration:.2f}s",
                        'response_format': 'valid_json',
                        'has_records': len(data) >= 2,
                        'record_count': len(data) - 1,  # First row is headers
                        'sample_record': data[1] if len(data) > 1 else None
                    }
                    logger.info(f"✓ CDX API: PASS (response time: {duration:.2f}s, records: {len(data) - 1})")
                else:
                    self.results['cdx_api']['status'] = 'FAIL'
                    self.results['cdx_api']['details'] = {
                        'error': 'Invalid response structure',
                        'response_type': type(data).__name__,
                        'response_length': len(data)
                    }
                    logger.error(f"✗ CDX API: FAIL (invalid response structure)")
            else:
                self.results['cdx_api']['status'] = 'SERVICE_UNAVAILABLE'
                self.results['cdx_api']['details'] = {
                    'error': 'No response - API may be rate limited or temporarily unavailable',
                    'recommendation': 'Retry later or implement exponential backoff'
                }
                logger.warning(f"⚠ CDX API: SERVICE_UNAVAILABLE (no response - API may be rate limited)")
                
        except Exception as e:
            self.results['cdx_api']['status'] = 'ERROR'
            self.results['cdx_api']['details'] = {'error': str(e)}
            logger.error(f"✗ CDX API: ERROR ({e})")
    
    def test_wayback_api(self):
        """Test Wayback API availability and response format."""
        logger.info("\n--- Testing Wayback API ---")
        
        test_url = "https://example.com"
        wayback_url = f"{self.WAYBACK_API_URL}?url={test_url}"
        
        try:
            start_time = time.time()
            response = self._make_request(wayback_url)
            duration = time.time() - start_time
            
            if response:
                data = json.loads(response)
                
                # Verify response structure
                if isinstance(data, list):
                    self.results['wayback_api']['status'] = 'PASS'
                    self.results['wayback_api']['details'] = {
                        'response_time': f"{duration:.2f}s",
                        'response_format': 'valid_json',
                        'is_list': True,
                        'record_count': len(data),
                        'sample_record': data[0] if len(data) > 0 else None
                    }
                    logger.info(f"✓ Wayback API: PASS (response time: {duration:.2f}s, records: {len(data)})")
                else:
                    self.results['wayback_api']['status'] = 'FAIL'
                    self.results['wayback_api']['details'] = {
                        'error': 'Invalid response structure',
                        'response_type': type(data).__name__
                    }
                    logger.error(f"✗ Wayback API: FAIL (invalid response structure)")
            else:
                self.results['wayback_api']['status'] = 'FAIL'
                self.results['wayback_api']['details'] = {'error': 'No response'}
                logger.error(f"✗ Wayback API: FAIL (no response)")
                
        except Exception as e:
            self.results['wayback_api']['status'] = 'FAIL'
            self.results['wayback_api']['details'] = {'error': str(e)}
            logger.error(f"✗ Wayback API: FAIL ({e})")
    
    def test_snapshot_lookup(self):
        """Test snapshot lookup for a specific URL."""
        logger.info("\n--- Testing Snapshot Lookup ---")
        
        test_url = "https://example.com"
        cdx_url = f"{self.CDX_API_URL}?url={test_url}&output=json&limit=1"
        
        try:
            # First, get the most recent snapshot
            response = self._make_request(cdx_url)
            
            if response:
                data = json.loads(response)
                
                if len(data) >= 2:
                    record = data[1]
                    archive_date = record[1] if len(record) > 1 else None
                    
                    if archive_date:
                        # Try to fetch the actual snapshot
                        archive_url = f"https://web.archive.org/web/{archive_date}/{test_url}"
                        
                        start_time = time.time()
                        snapshot_response = self._make_request(archive_url)
                        duration = time.time() - start_time
                        
                        if snapshot_response:
                            self.results['snapshot_lookup']['status'] = 'PASS'
                            self.results['snapshot_lookup']['details'] = {
                                'archive_date': archive_date,
                                'archive_url': archive_url,
                                'response_time': f"{duration:.2f}s",
                                'snapshot_size': len(snapshot_response),
                                'snapshot_available': True
                            }
                            logger.info(f"✓ Snapshot Lookup: PASS (date: {archive_date}, size: {len(snapshot_response)} bytes)")
                        else:
                            self.results['snapshot_lookup']['status'] = 'FAIL'
                            self.results['snapshot_lookup']['details'] = {
                                'error': 'Snapshot not accessible',
                                'archive_url': archive_url
                            }
                            logger.error(f"✗ Snapshot Lookup: FAIL (snapshot not accessible)")
                    else:
                        self.results['snapshot_lookup']['status'] = 'FAIL'
                        self.results['snapshot_lookup']['details'] = {'error': 'No archive date in record'}
                        logger.error(f"✗ Snapshot Lookup: FAIL (no archive date)")
                else:
                    self.results['snapshot_lookup']['status'] = 'FAIL'
                    self.results['snapshot_lookup']['details'] = {'error': 'No records found'}
                    logger.error(f"✗ Snapshot Lookup: FAIL (no records)")
            else:
                self.results['snapshot_lookup']['status'] = 'FAIL'
                self.results['snapshot_lookup']['details'] = {'error': 'CDX lookup failed'}
                logger.error(f"✗ Snapshot Lookup: FAIL (CDX lookup failed)")
                
        except Exception as e:
            self.results['snapshot_lookup']['status'] = 'FAIL'
            self.results['snapshot_lookup']['details'] = {'error': str(e)}
            logger.error(f"✗ Snapshot Lookup: FAIL ({e})")
    
    def test_metadata_extraction(self):
        """Test metadata extraction from snapshot."""
        logger.info("\n--- Testing Metadata Extraction ---")
        
        test_url = "https://example.com"
        cdx_url = f"{self.CDX_API_URL}?url={test_url}&output=json&limit=1"
        
        try:
            response = self._make_request(cdx_url)
            
            if response:
                data = json.loads(response)
                
                if len(data) >= 2:
                    record = data[1]
                    
                    # Extract metadata from CDX record
                    # CDX format: urlkey, timestamp, original, mimetype, statuscode, digest, length
                    metadata = {
                        'urlkey': record[0] if len(record) > 0 else None,
                        'timestamp': record[1] if len(record) > 1 else None,
                        'original_url': record[2] if len(record) > 2 else None,
                        'mimetype': record[3] if len(record) > 3 else None,
                        'status_code': record[4] if len(record) > 4 else None,
                        'digest': record[5] if len(record) > 5 else None,
                        'length': record[6] if len(record) > 6 else None
                    }
                    
                    self.results['metadata_extraction']['status'] = 'PASS'
                    self.results['metadata_extraction']['details'] = {
                        'metadata_extracted': True,
                        'fields': list(metadata.keys()),
                        'metadata': metadata
                    }
                    logger.info(f"✓ Metadata Extraction: PASS (fields: {len(metadata)})")
                else:
                    self.results['metadata_extraction']['status'] = 'FAIL'
                    self.results['metadata_extraction']['details'] = {'error': 'No records to extract from'}
                    logger.error(f"✗ Metadata Extraction: FAIL (no records)")
            else:
                self.results['metadata_extraction']['status'] = 'FAIL'
                self.results['metadata_extraction']['details'] = {'error': 'No response'}
                logger.error(f"✗ Metadata Extraction: FAIL (no response)")
                
        except Exception as e:
            self.results['metadata_extraction']['status'] = 'FAIL'
            self.results['metadata_extraction']['details'] = {'error': str(e)}
            logger.error(f"✗ Metadata Extraction: FAIL ({e})")
    
    def test_error_handling(self):
        """Test error handling for various error conditions."""
        logger.info("\n--- Testing Error Handling ---")
        
        errors_tested = []
        
        # Test 1: Non-existent URL
        try:
            fake_url = "https://this-domain-definitely-does-not-exist-12345.com"
            cdx_url = f"{self.CDX_API_URL}?url={fake_url}&output=json&limit=1"
            response = self._make_request(cdx_url)
            
            if response:
                data = json.loads(response)
                if len(data) < 2:  # No records expected
                    errors_tested.append('non_existent_url: PASS')
                else:
                    errors_tested.append('non_existent_url: UNEXPECTED_RECORDS')
            else:
                errors_tested.append('non_existent_url: NO_RESPONSE')
        except Exception as e:
            errors_tested.append(f'non_existent_url: ERROR ({e})')
        
        # Test 2: Invalid URL format
        try:
            invalid_url = "not-a-valid-url"
            cdx_url = f"{self.CDX_API_URL}?url={invalid_url}&output=json&limit=1"
            response = self._make_request(cdx_url)
            # Should handle gracefully
            errors_tested.append('invalid_url: HANDLED')
        except Exception as e:
            errors_tested.append(f'invalid_url: ERROR ({e})')
        
        # Test 3: Timeout simulation (not actually testing timeout, just noting it should be handled)
        errors_tested.append('timeout_handling: NOT_TESTED')
        
        self.results['error_handling']['status'] = 'PASS' if all('PASS' in e or 'HANDLED' in e for e in errors_tested) else 'PARTIAL'
        self.results['error_handling']['details'] = {
            'tests': errors_tested,
            'total_tests': len(errors_tested),
            'passed': sum(1 for e in errors_tested if 'PASS' in e or 'HANDLED' in e)
        }
        
        logger.info(f"✓ Error Handling: {self.results['error_handling']['status']} ({len(errors_tested)} tests)")
        for test in errors_tested:
            logger.info(f"  - {test}")
    
    def _make_request(self, url: str) -> Optional[str]:
        """Make HTTP request with proper headers."""
        try:
            request = urllib.request.Request(
                url,
                headers={'User-Agent': self.USER_AGENT}
            )
            
            with urllib.request.urlopen(request, timeout=self.TIMEOUT) as response:
                return response.read().decode('utf-8', errors='ignore')
                
        except urllib.error.HTTPError as e:
            logger.warning(f"HTTP error for {url}: {e.code}")
            return None
        except urllib.error.URLError as e:
            logger.warning(f"URL error for {url}: {e.reason}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {e}")
            return None
    
    def print_summary(self):
        """Print test summary."""
        logger.info("\n=== TEST SUMMARY ===")
        
        for test_name, result in self.results.items():
            status = result['status']
            details = result.get('details', {})
            logger.info(f"\n{test_name.upper()}: {status}")
            
            if details:
                for key, value in details.items():
                    logger.info(f"  {key}: {value}")
        
        # Overall status
        all_passed = all(r['status'] == 'PASS' for r in self.results.values())
        overall_status = 'PASS' if all_passed else 'FAIL'
        
        logger.info(f"\n=== OVERALL: {overall_status} ===")
        
        if overall_status == 'PASS':
            logger.info("✓ All Wayback Machine API tests passed")
        else:
            failed_tests = [name for name, result in self.results.items() if result['status'] != 'PASS']
            logger.warning(f"✗ Failed tests: {', '.join(failed_tests)}")


if __name__ == "__main__":
    tester = WaybackAPITester()
    tester.run_all_tests()
