import pytest
from old_proxy import parse_request

def test_parse_request():
    request = "GET /www.example.com/path HTTP/1.1"
    host, path = parse_request(request)
    assert host == "www.example.com"
    assert path == "/path"

def test_parse_request_with_port():
    request = "GET /www.example.com:8080/path HTTP/1.1"
    host, path = parse_request(request)
    assert host == "www.example.com:8080"
    assert path == "/path"

def test_parse_request_with_port_and_path():
    request = "GET /www.example.com:8080/path/to/resource HTTP/1.1"
    host, path = parse_request(request)
    assert host == "www.example.com:8080"
    assert path == "/path/to/resource"

    
def test_parse_request_with_invalid_request():
    request = "INVALID_REQUEST"
    host, path = parse_request(request)
    assert host is None
    assert path is None     
    
def test_parse_request_with_no_path():
    request = "GET / HTTP/1.1"
    host, path = parse_request(request)
    assert host is None
    assert path is None
    
    

