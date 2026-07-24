import pytest
from nimcode.secret_scanner import SecretScanner

def test_secret_scanner_detects_aws():
    content = 'const AWS_KEY = "AKIA1234567890ABCDEF";'
    findings = SecretScanner.scan(content)
    assert len(findings) == 1
    assert "Prefixed Secret Key matched" in findings[0]

def test_secret_scanner_detects_openai():
    content = 'api_key="sk-abcdefghijklmnopqrstuvwxyz1234567890"'
    findings = SecretScanner.scan(content)
    assert len(findings) == 1
    assert "Prefixed Secret Key matched" in findings[0]
    
def test_secret_scanner_detects_bearer():
    content = 'Header: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
    findings = SecretScanner.scan(content)
    assert len(findings) == 1
    assert "Bearer Token detected" in findings[0]

def test_secret_scanner_allows_normal_code():
    content = '''
def calculate(a, b):
    return a + b
    
class SKTest:
    def akia_test(self): pass
'''
    findings = SecretScanner.scan(content)
    assert len(findings) == 0
