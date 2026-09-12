"""
Local HTTP Test Server for Dead Link Module Testing

This server provides deterministic endpoints to test various HTTP status codes
and error conditions for the Dead Link module.
"""

from flask import Flask, request, jsonify, redirect
import time
import threading

app = Flask(__name__)

# Routes for different HTTP status codes
@app.route('/test/200', methods=['GET', 'HEAD'])
def test_200():
    """Return HTTP 200 - Healthy link"""
    return '<html><head><title>Test Page 200</title></head><body><h1>Success</h1></body></html>', 200

@app.route('/test/301', methods=['GET', 'HEAD'])
def test_301():
    """Return HTTP 301 - Permanent redirect"""
    return redirect('http://localhost:5000/test/200', code=301)

@app.route('/test/302', methods=['GET', 'HEAD'])
def test_302():
    """Return HTTP 302 - Found (temporary redirect)"""
    return redirect('http://localhost:5000/test/200', code=302)

@app.route('/test/307', methods=['GET', 'HEAD'])
def test_307():
    """Return HTTP 307 - Temporary redirect"""
    return redirect('http://localhost:5000/test/200', code=307)

@app.route('/test/308', methods=['GET', 'HEAD'])
def test_308():
    """Return HTTP 308 - Permanent redirect"""
    return redirect('http://localhost:5000/test/200', code=308)

@app.route('/test/400', methods=['GET', 'HEAD'])
def test_400():
    """Return HTTP 400 - Bad Request (REVIEW_REQUIRED)"""
    return '<html><body><h1>Bad Request</h1></body></html>', 400

@app.route('/test/401', methods=['GET', 'HEAD'])
def test_401():
    """Return HTTP 401 - Unauthorized (REVIEW_REQUIRED)"""
    return '<html><body><h1>Unauthorized</h1></body></html>', 401

@app.route('/test/403', methods=['GET', 'HEAD'])
def test_403():
    """Return HTTP 403 - Forbidden (REVIEW_REQUIRED)"""
    return '<html><body><h1>Forbidden</h1></body></html>', 403

@app.route('/test/404', methods=['GET', 'HEAD'])
def test_404():
    """Return HTTP 404 - Not Found (DEAD)"""
    return '<html><body><h1>Not Found</h1></body></html>', 404

@app.route('/test/408', methods=['GET', 'HEAD'])
def test_408():
    """Return HTTP 408 - Request Timeout (TEMPORARY_ERROR)"""
    return '<html><body><h1>Request Timeout</h1></body></html>', 408

@app.route('/test/410', methods=['GET', 'HEAD'])
def test_410():
    """Return HTTP 410 - Gone (DEAD)"""
    return '<html><body><h1>Gone</h1></body></html>', 410

@app.route('/test/429', methods=['GET', 'HEAD'])
def test_429():
    """Return HTTP 429 - Too Many Requests (RATE_LIMITED)"""
    return '<html><body><h1>Too Many Requests</h1></body></html>', 429

@app.route('/test/500', methods=['GET', 'HEAD'])
def test_500():
    """Return HTTP 500 - Internal Server Error (TEMPORARY_ERROR)"""
    return '<html><body><h1>Internal Server Error</h1></body></html>', 500

@app.route('/test/502', methods=['GET', 'HEAD'])
def test_502():
    """Return HTTP 502 - Bad Gateway (TEMPORARY_ERROR)"""
    return '<html><body><h1>Bad Gateway</h1></body></html>', 502

@app.route('/test/503', methods=['GET', 'HEAD'])
def test_503():
    """Return HTTP 503 - Service Unavailable (TEMPORARY_ERROR)"""
    return '<html><body><h1>Service Unavailable</h1></body></html>', 503

@app.route('/test/504', methods=['GET', 'HEAD'])
def test_504():
    """Return HTTP 504 - Gateway Timeout (TEMPORARY_ERROR)"""
    return '<html><body><h1>Gateway Timeout</h1></body></html>', 504

@app.route('/test/timeout', methods=['GET', 'HEAD'])
def test_timeout():
    """Simulate timeout by delaying response"""
    time.sleep(15)  # Longer than default 10s timeout
    return '<html><body><h1>Delayed Response</h1></body></html>', 200

@app.route('/test/redirect_chain', methods=['GET', 'HEAD'])
def test_redirect_chain():
    """Test redirect chain: 301 -> 302 -> 200"""
    return redirect('http://localhost:5000/test/302', code=301)

@app.route('/test/redirect_different_domain', methods=['GET', 'HEAD'])
def test_redirect_different_domain():
    """Test redirect to different domain (should be rejected)"""
    # Redirect to a different domain - this should work
    return redirect('http://httpbin.org/redirect-to?url=http://httpbin.org/html', code=301)

@app.route('/test/redirect_different_path', methods=['GET', 'HEAD'])
def test_redirect_different_path():
    """Test redirect to different path (should be rejected)"""
    # Redirect to a completely different path on same domain
    return redirect('http://localhost:5000/other/page', code=301)

@app.route('/other/page', methods=['GET', 'HEAD'])
def other_page():
    """Target page for different path redirect test"""
    return '<html><head><title>Other Page</title></head><body><h1>Different Path</h1></body></html>', 200

@app.route('/test/same_domain_www', methods=['GET', 'HEAD'])
def test_same_domain_www():
    """Test redirect with www prefix change (should be accepted)"""
    return redirect('http://www.localhost:5000/test/200', code=301)

@app.route('/test/http_to_https', methods=['GET', 'HEAD'])
def test_http_to_https():
    """Test HTTP to HTTPS redirect (should be accepted if same domain)"""
    # Note: This would require HTTPS setup, skipping for local test
    return '<html><body><h1>HTTP to HTTPS redirect test skipped</h1></body></html>', 200

@app.route('/test/ssl_expired', methods=['GET', 'HEAD'])
def test_ssl_expired():
    """Simulate SSL expired error (requires actual SSL setup)"""
    # Cannot simulate locally without SSL certificate
    return '<html><body><h1>SSL expired test skipped</h1></body></html>', 200

@app.route('/test/dns_failure', methods=['GET', 'HEAD'])
def test_dns_failure():
    """Simulate DNS failure (requires actual DNS setup)"""
    # Cannot simulate locally
    return '<html><body><h1>DNS failure test skipped</h1></body></html>', 200

@app.route('/test/academic_403', methods=['GET', 'HEAD'])
def test_academic_403():
    """Simulate academic publisher 403 (should be TEMPORARY_ERROR)"""
    # This would require domain matching logic
    return '<html><body><h1>Academic 403</h1></body></html>', 403

@app.route('/test/content_match', methods=['GET', 'HEAD'])
def test_content_match():
    """Return content for testing content matching"""
    return '<html><head><title>Test Content Match</title></head><body><h1>Test Content</h1><p>This is test content for matching.</p></body></html>', 200

@app.route('/test/content_different', methods=['GET', 'HEAD'])
def test_content_different():
    """Return different content for testing content mismatch"""
    return '<html><head><title>Different Content</title></head><body><h1>Completely Different</h1><p>This is different content.</p></body></html>', 200

if __name__ == '__main__':
    print("Starting HTTP Test Server on http://localhost:5000")
    print("Available endpoints:")
    print("  /test/200 - HTTP 200 (HEALTHY)")
    print("  /test/301 - HTTP 301 (redirect)")
    print("  /test/302 - HTTP 302 (redirect)")
    print("  /test/307 - HTTP 307 (redirect)")
    print("  /test/308 - HTTP 308 (redirect)")
    print("  /test/400 - HTTP 400 (REVIEW_REQUIRED)")
    print("  /test/401 - HTTP 401 (REVIEW_REQUIRED)")
    print("  /test/403 - HTTP 403 (REVIEW_REQUIRED)")
    print("  /test/404 - HTTP 404 (DEAD)")
    print("  /test/408 - HTTP 408 (TEMPORARY_ERROR)")
    print("  /test/410 - HTTP 410 (DEAD)")
    print("  /test/429 - HTTP 429 (RATE_LIMITED)")
    print("  /test/500 - HTTP 500 (TEMPORARY_ERROR)")
    print("  /test/502 - HTTP 502 (TEMPORARY_ERROR)")
    print("  /test/503 - HTTP 503 (TEMPORARY_ERROR)")
    print("  /test/504 - HTTP 504 (TEMPORARY_ERROR)")
    print("  /test/timeout - Timeout simulation")
    print("  /test/redirect_chain - Redirect chain test")
    print("  /test/redirect_different_domain - Redirect to different domain")
    print("  /test/redirect_different_path - Redirect to different path")
    app.run(host='localhost', port=5000, debug=False)
