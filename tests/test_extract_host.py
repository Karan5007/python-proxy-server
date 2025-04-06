from src.proxy import ProxyServer
import pytest 
import socket

@pytest.fixture
def proxy_server():
    # Find an available port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()
    
    # Create a proxy server with the available port
    return ProxyServer(port=port)

def test_extract_host(proxy_server):
    host = proxy_server.extract_host(b"GET /www.example.com/path HTTP/1.1")
    assert host == "www.example.com"

def test_extract_host_no_host(proxy_server):
    host = proxy_server.extract_host(b"GET /path HTTP/1.1")
    assert host is None

def test_extract_host_invalid_request(proxy_server):
    host = proxy_server.extract_host(b"GET /path HTTP/1.1")
    assert host is None

def test_extract_host_multiple_slashes(proxy_server):
    host = proxy_server.extract_host(b"GET /www.example.com//path HTTP/1.1")
    assert host == "www.example.com"

def test_extract_host_trailing_slash(proxy_server):
    host = proxy_server.extract_host(b"GET /www.example.com/ HTTP/1.1")
    assert host == "www.example.com"
    
# def test_extract_host_favicon(proxy_server):
#     host = proxy_server.extract_host(b"GET /favicon.ico HTTP/1.1")
#     assert host is None
    
def test_basic_request(proxy_server):
    host = proxy_server.extract_host(b"GET /www.example.org HTTP/1.1")
    assert host == "www.example.org"
    
def test_basic_request_with_port(proxy_server):
    host = proxy_server.extract_host(b"GET /www.example.com:8080/path HTTP/1.1")
    assert host == "www.example.com:8080"