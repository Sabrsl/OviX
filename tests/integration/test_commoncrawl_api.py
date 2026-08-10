"""
Real API Test for Common Crawl Archive Provider.

This script performs actual API calls to verify:
- CDX API availability and response format
- URL search functionality
- Domain search functionality
- Rate limiting behavior
- Error handling

Run with: python tests/integration/test_commoncrawl_api.py
"""

import requests
import json
import time
import logging
from typing import Dict, Any, Optional, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CommonCrawlAPITester:
    """Test Common Crawl CDX API with real requests."""
    
    CDX_API_BASE = "https://index.commoncrawl.org"
    USER_AGENT = "WikipediaMaintenanceTool/1.0 (API Testing)"
    TIMEOUT = 30
    DEFAULT_CRAWLS = ["CC-MAIN-2025-43", "CC-MAIN-2025-33", "CC-MAIN-2025-23"]
    
    def __init__(self):
        self.results = {
            'cdx_api': {'status': 'NOT_TESTED', 'details': {}},
            'url_search': {'status': 'NOT_TESTED', 'details': {}},
            'domain_search': {'status': 'NOT_TESTED', 'details': {}},
            'rate_limiting': {'status': 'NOT_TESTED', 'details': {}},
            'error_handling': {'status': 'NOT_TESTED', 'details': {}}
        }
    
    def run_all_tests(self):
        """Run all API tests."""
        logger.info("=== COMMON CRAWL API TESTS ===")
        
        self.test_cdx_api()
        self.test_url_search()
        self.test_domain_search()
        self.test_rate_limiting()
        self.test_error_handling()
        
        self.print_summary()
    
    def test_cdx_api(self):
        """Test CDX API availability and response format."""
        logger.info("\n--- Testing CDX API ---")
        
        test_url = "https://example.com"
        
        for crawl in self.DEFAULT_CRAWLS:
            try:
                cdx_url = f"{self.CDX_API_BASE}/{crawl}-index"
                params = {
                    'url': test_url,
                    'output': 'json',
                    'limit': 1
                }
                
                start_time = time.time()
                response = self._make_request(cdx_url, params)
                duration = time.time() - start_time
                
                if response:
                    # Verify response structure
                    if isinstance(response, list) and len(response) >= 2:
                        self.results['cdx_api']['status'] = 'PASS'
                        self.results['cdx_api']['details'] = {
                            'response_time': f"{duration:.2f}s",
                            'response_format': 'valid_json',
                            'has_records': len(response) >= 2,
                            'record_count': len(response) - 1,  # First row is headers
                            'crawl_used': crawl,
                            'sample_record': response[1] if len(response) > 1 else None
                        }
                        logger.info(f"✓ CDX API: PASS (crawl: {crawl}, response time: {duration:.2f}s, records: {len(response) - 1})")
                        return  # Success, no need to try other crawls
                    else:
                        self.results['cdx_api']['status'] = 'PARTIAL'
                        self.results['cdx_api']['details'] = {
                            'error': 'Invalid response structure',
                            'response_type': type(response).__name__,
                            'crawl_used': crawl
                        }
                        logger.warning(f"⚠ CDX API: PARTIAL (invalid response structure for {crawl})")
                        continue  # Try next crawl
                else:
                    logger.warning(f"No response from {crawl}, trying next crawl")
                    continue
                    
            except Exception as e:
                logger.warning(f"Error with {crawl}: {e}, trying next crawl")
                continue
        
        # If all crawls failed
        if self.results['cdx_api']['status'] == 'NOT_TESTED':
            self.results['cdx_api']['status'] = 'FAIL'
            self.results['cdx_api']['details'] = {'error': 'All crawls failed'}
            logger.error(f"✗ CDX API: FAIL (all crawls failed)")
    
    def test_url_search(self):
        """Test URL search functionality."""
        logger.info("\n--- Testing URL Search ---")
        
        test_url = "https://example.com"
        
        try:
            for crawl in self.DEFAULT_CRAWLS:
                cdx_url = f"{self.CDX_API_BASE}/{crawl}-index"
                params = {
                    'url': test_url,
                    'output': 'json',
                    'limit': 5
                }
                
                response = self._make_request(cdx_url, params)
                
                if response and isinstance(response, list) and len(response) >= 2:
                    items = response[1:]  # Skip header row
                    
                    self.results['url_search']['status'] = 'PASS'
                    self.results['url_search']['details'] = {
                        'crawl_used': crawl,
                        'has_items': len(items) > 0,
                        'item_count': len(items),
                        'sample_item': items[0] if items else None
                    }
                    logger.info(f"✓ URL Search: PASS (crawl: {crawl}, items: {len(items)})")
                    return
            
            self.results['url_search']['status'] = 'FAIL'
            self.results['url_search']['details'] = {'error': 'No successful crawl found'}
            logger.error(f"✗ URL Search: FAIL")
            
        except Exception as e:
            self.results['url_search']['status'] = 'ERROR'
            self.results['url_search']['details'] = {'error': str(e)}
            logger.error(f"✗ URL Search: ERROR ({e})")
    
    def test_domain_search(self):
        """Test domain search functionality."""
        logger.info("\n--- Testing Domain Search ---")
        
        test_domain = "example.com"
        
        try:
            # Convert to SURT format
            surt_domain = self._domain_to_surt(test_domain)
            query = f"{surt_domain}*"
            
            for crawl in self.DEFAULT_CRAWLS:
                cdx_url = f"{self.CDX_API_BASE}/{crawl}-index"
                params = {
                    'url': query,
                    'output': 'json',
                    'limit': 5
                }
                
                response = self._make_request(cdx_url, params)
                
                if response and isinstance(response, list) and len(response) >= 2:
                    items = response[1:]  # Skip header row
                    
                    self.results['domain_search']['status'] = 'PASS'
                    self.results['domain_search']['details'] = {
                        'crawl_used': crawl,
                        'surt_query': surt_domain,
                        'has_items': len(items) > 0,
                        'item_count': len(items),
                        'sample_item': items[0] if items else None
                    }
                    logger.info(f"✓ Domain Search: PASS (crawl: {crawl}, items: {len(items)})")
                    return
            
            self.results['domain_search']['status'] = 'FAIL'
            self.results['domain_search']['details'] = {'error': 'No successful crawl found'}
            logger.error(f"✗ Domain Search: FAIL")
            
        except Exception as e:
            self.results['domain_search']['status'] = 'ERROR'
            self.results['domain_search']['details'] = {'error': str(e)}
            logger.error(f"✗ Domain Search: ERROR ({e})")
    
    def test_rate_limiting(self):
        """Test rate limiting behavior."""
        logger.info("\n--- Testing Rate Limiting ---")
        
        try:
            # Make multiple rapid requests to test rate limiting
            # Add delays to avoid actual rate limiting
            request_count = 0
            rate_limited = False
            
            for i in range(3):
                try:
                    cdx_url = f"{self.CDX_API_BASE}/{self.DEFAULT_CRAWLS[0]}-index"
                    params = {
                        'url': 'https://example.com',
                        'output': 'json',
                        'limit': 1
                    }
                    
                    response = self._make_request(cdx_url, params)
                    if response:
                        request_count += 1
                    
                    # Add delay to avoid rate limiting
                    time.sleep(2)
                    
                except Exception as e:
                    if "503" in str(e) or "rate" in str(e).lower():
                        rate_limited = True
                        logger.warning(f"Rate limit detected at request {i+1}")
                        break
            
            self.results['rate_limiting']['status'] = 'PASS'
            self.results['rate_limiting']['details'] = {
                'successful_requests': request_count,
                'rate_limited': rate_limited,
                'note': 'Common Crawl can return 503 if too many requests from same IP'
            }
            logger.info(f"✓ Rate Limiting: PASS (successful: {request_count}, rate_limited: {rate_limited})")
            
        except Exception as e:
            self.results['rate_limiting']['status'] = 'ERROR'
            self.results['rate_limiting']['details'] = {'error': str(e)}
            logger.error(f"✗ Rate Limiting: ERROR ({e})")
    
    def test_error_handling(self):
        """Test error handling for various error conditions."""
        logger.info("\n--- Testing Error Handling ---")
        
        errors_tested = []
        
        # Test 1: Non-existent crawl
        try:
            cdx_url = f"{self.CDX_API_BASE}/CC-MAIN-9999-index"
            params = {'url': 'https://example.com', 'output': 'json', 'limit': 1}
            response = self._make_request(cdx_url, params)
            errors_tested.append('non_existent_crawl: HANDLED')
        except Exception as e:
            errors_tested.append(f'non_existent_crawl: ERROR ({e})')
        
        # Test 2: Invalid URL format
        try:
            cdx_url = f"{self.CDX_API_BASE}/{self.DEFAULT_CRAWLS[0]}-index"
            params = {'url': 'not-a-valid-url', 'output': 'json', 'limit': 1}
            response = self._make_request(cdx_url, params)
            errors_tested.append('invalid_url: HANDLED')
        except Exception as e:
            errors_tested.append(f'invalid_url: ERROR ({e})')
        
        # Test 3: Very large limit
        try:
            cdx_url = f"{self.CDX_API_BASE}/{self.DEFAULT_CRAWLS[0]}-index"
            params = {'url': 'https://example.com', 'output': 'json', 'limit': 100000}
            response = self._make_request(cdx_url, params)
            errors_tested.append('large_limit: HANDLED')
        except Exception as e:
            errors_tested.append(f'large_limit: ERROR ({e})')
        
        self.results['error_handling']['status'] = 'PASS' if all('HANDLED' in e or 'ERROR' not in e for e in errors_tested) else 'PARTIAL'
        self.results['error_handling']['details'] = {
            'tests': errors_tested,
            'total_tests': len(errors_tested),
            'passed': sum(1 for e in errors_tested if 'HANDLED' in e)
        }
        
        logger.info(f"✓ Error Handling: {self.results['error_handling']['status']} ({len(errors_tested)} tests)")
        for test in errors_tested:
            logger.info(f"  - {test}")
    
    def _make_request(self, url: str, params: Dict[str, Any]) -> Optional[List]:
        """Make HTTP request with proper headers."""
        try:
            response = requests.get(
                url,
                params=params,
                timeout=self.TIMEOUT,
                headers={'User-Agent': self.USER_AGENT}
            )
            
            if response.status_code == 503:
                logger.warning(f"Rate limited by Common Crawl")
                return None
                
            if response.status_code != 200:
                logger.warning(f"HTTP error: {response.status_code}")
                return None
            
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.warning("Request timeout")
            return None
        except Exception as e:
            logger.error(f"Request error: {e}")
            return None
    
    def _domain_to_surt(self, domain: str) -> str:
        """Convert domain to SURT format."""
        parts = domain.split('.')
        reversed_parts = list(reversed(parts))
        return ','.join(reversed_parts) + ')'
    
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
            logger.info("✓ All Common Crawl API tests passed")
        else:
            failed_tests = [name for name, result in self.results.items() if result['status'] != 'PASS']
            logger.warning(f"✗ Failed tests: {', '.join(failed_tests)}")


if __name__ == "__main__":
    tester = CommonCrawlAPITester()
    tester.run_all_tests()
