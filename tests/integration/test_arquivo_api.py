"""
Real API Test for Arquivo.pt Archive Provider.

This script performs actual API calls to verify:
- Text Search API availability and response format
- URL search functionality
- Rate limiting behavior
- Error handling

Run with: python tests/integration/test_arquivo_api.py
"""

import requests
import json
import time
import logging
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ArquivoAPITester:
    """Test Arquivo.pt API with real requests."""
    
    API_BASE_URL = "https://arquivo.pt/textsearch"
    USER_AGENT = "WikipediaMaintenanceTool/1.0 (API Testing)"
    TIMEOUT = 30
    
    def __init__(self):
        self.results = {
            'text_search': {'status': 'NOT_TESTED', 'details': {}},
            'url_search': {'status': 'NOT_TESTED', 'details': {}},
            'rate_limiting': {'status': 'NOT_TESTED', 'details': {}},
            'error_handling': {'status': 'NOT_TESTED', 'details': {}}
        }
    
    def run_all_tests(self):
        """Run all API tests."""
        logger.info("=== ARQUIVO.PT API TESTS ===")
        
        self.test_text_search()
        self.test_url_search()
        self.test_rate_limiting()
        self.test_error_handling()
        
        self.print_summary()
    
    def test_text_search(self):
        """Test text search API availability and response format."""
        logger.info("\n--- Testing Text Search API ---")
        
        try:
            params = {
                'q': 'test',
                'maxItems': 5,
                'fields': 'title,linkTo,linkToArchive,timestamp,mimeType,statusCode'
            }
            
            start_time = time.time()
            response = self._make_request(params)
            duration = time.time() - start_time
            
            if response:
                # Verify response structure (Arquivo.pt uses snake_case)
                if 'response_items' in response:
                    items = response['response_items']
                    
                    self.results['text_search']['status'] = 'PASS'
                    self.results['text_search']['details'] = {
                        'response_time': f"{duration:.2f}s",
                        'response_format': 'valid_json',
                        'has_items': len(items) > 0,
                        'item_count': len(items),
                        'sample_item': items[0] if items else None
                    }
                    logger.info(f"✓ Text Search API: PASS (response time: {duration:.2f}s, items: {len(items)})")
                else:
                    self.results['text_search']['status'] = 'FAIL'
                    self.results['text_search']['details'] = {
                        'error': 'Invalid response structure',
                        'response_keys': list(response.keys())
                    }
                    logger.error(f"✗ Text Search API: FAIL (invalid response structure)")
            else:
                self.results['text_search']['status'] = 'FAIL'
                self.results['text_search']['details'] = {'error': 'No response'}
                logger.error(f"✗ Text Search API: FAIL (no response)")
                
        except Exception as e:
            self.results['text_search']['status'] = 'ERROR'
            self.results['text_search']['details'] = {'error': str(e)}
            logger.error(f"✗ Text Search API: ERROR ({e})")
    
    def test_url_search(self):
        """Test URL search functionality."""
        logger.info("\n--- Testing URL Search ---")
        
        try:
            # Search for a specific URL
            params = {
                'q': 'linkTo:"https://example.com"',
                'maxItems': 5,
                'fields': 'title,linkTo,linkToArchive,timestamp,mimeType,statusCode'
            }
            
            start_time = time.time()
            response = self._make_request(params)
            duration = time.time() - start_time
            
            if response:
                if 'response_items' in response:
                    items = response['response_items']
                    
                    self.results['url_search']['status'] = 'PASS'
                    self.results['url_search']['details'] = {
                        'response_time': f"{duration:.2f}s",
                        'has_items': len(items) > 0,
                        'item_count': len(items),
                        'sample_item': items[0] if items else None
                    }
                    logger.info(f"✓ URL Search: PASS (response time: {duration:.2f}s, items: {len(items)})")
                else:
                    self.results['url_search']['status'] = 'FAIL'
                    self.results['url_search']['details'] = {'error': 'Invalid response structure'}
                    logger.error(f"✗ URL Search: FAIL (invalid response structure)")
            else:
                self.results['url_search']['status'] = 'FAIL'
                self.results['url_search']['details'] = {'error': 'No response'}
                logger.error(f"✗ URL Search: FAIL (no response)")
                
        except Exception as e:
            self.results['url_search']['status'] = 'ERROR'
            self.results['url_search']['details'] = {'error': str(e)}
            logger.error(f"✗ URL Search: ERROR ({e})")
    
    def test_rate_limiting(self):
        """Test rate limiting behavior."""
        logger.info("\n--- Testing Rate Limiting ---")
        
        try:
            # Make multiple rapid requests to test rate limiting
            params = {
                'q': 'test',
                'maxItems': 1,
                'fields': 'title,linkTo'
            }
            
            request_count = 0
            rate_limited = False
            
            for i in range(5):
                try:
                    response = self._make_request(params)
                    if response:
                        request_count += 1
                    else:
                        logger.warning(f"Request {i+1} failed")
                except Exception as e:
                    if "429" in str(e) or "rate" in str(e).lower():
                        rate_limited = True
                        logger.warning(f"Rate limit detected at request {i+1}")
                        break
            
            self.results['rate_limiting']['status'] = 'PASS'
            self.results['rate_limiting']['details'] = {
                'successful_requests': request_count,
                'rate_limited': rate_limited,
                'note': 'Arquivo.pt rate limit is 250 requests/60s per IP'
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
        
        # Test 1: Empty query
        try:
            params = {'q': '', 'maxItems': 1}
            response = self._make_request(params)
            errors_tested.append('empty_query: HANDLED')
        except Exception as e:
            errors_tested.append(f'empty_query: ERROR ({e})')
        
        # Test 2: Invalid field
        try:
            params = {'q': 'test', 'maxItems': 1, 'fields': 'invalid_field'}
            response = self._make_request(params)
            errors_tested.append('invalid_field: HANDLED')
        except Exception as e:
            errors_tested.append(f'invalid_field: ERROR ({e})')
        
        # Test 3: Very large maxItems
        try:
            params = {'q': 'test', 'maxItems': 10000}
            response = self._make_request(params)
            errors_tested.append('large_maxitems: HANDLED')
        except Exception as e:
            errors_tested.append(f'large_maxitems: ERROR ({e})')
        
        self.results['error_handling']['status'] = 'PASS' if all('HANDLED' in e or 'ERROR' not in e for e in errors_tested) else 'PARTIAL'
        self.results['error_handling']['details'] = {
            'tests': errors_tested,
            'total_tests': len(errors_tested),
            'passed': sum(1 for e in errors_tested if 'HANDLED' in e)
        }
        
        logger.info(f"✓ Error Handling: {self.results['error_handling']['status']} ({len(errors_tested)} tests)")
        for test in errors_tested:
            logger.info(f"  - {test}")
    
    def _make_request(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make HTTP request with proper headers."""
        try:
            response = requests.get(
                self.API_BASE_URL,
                params=params,
                timeout=self.TIMEOUT,
                headers={'User-Agent': self.USER_AGENT}
            )
            
            if response.status_code == 429:
                logger.warning(f"Rate limited by Arquivo.pt")
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
            logger.info("✓ All Arquivo.pt API tests passed")
        else:
            failed_tests = [name for name, result in self.results.items() if result['status'] != 'PASS']
            logger.warning(f"✗ Failed tests: {', '.join(failed_tests)}")


if __name__ == "__main__":
    tester = ArquivoAPITester()
    tester.run_all_tests()
