import re
import logging

logger = logging.getLogger(__name__)

class SecretScanner:
    # A few basic patterns to detect hardcoded secrets
    # This is a simplified list for demonstration/safety.
    PATTERNS = [
        # AWS Access Key
        re.compile(r'(?<![A-Z0-9])[A-Z0-9]{20}(?![A-Z0-9])'), 
        # AWS Secret Key (approx)
        re.compile(r'(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])'),
        # Generic API Key looking string (Bearer token, etc)
        re.compile(r'Bearer\s+[A-Za-z0-9\-\._~+/]+=*'),
        # RSA private key
        re.compile(r'-----BEGIN (?:RSA|OPENSSH) PRIVATE KEY-----')
    ]

    # Keys that often start with specific prefixes
    PREFIXED_PATTERNS = [
        re.compile(r'AKIA[0-9A-Z]{16}'), # AWS AKIA
        re.compile(r'sk-[a-zA-Z0-9]{32,}'), # OpenAI / generic secret key
    ]

    @classmethod
    def scan(cls, content: str) -> list[str]:
        """
        Scan content for potential secrets.
        Returns a list of matched descriptions.
        """
        findings = []
        
        for p in cls.PREFIXED_PATTERNS:
            if p.search(content):
                findings.append(f"Prefixed Secret Key matched: {p.pattern}")
                
        # For general entropy/length ones, we could be more careful,
        # but for this MVP scanner we will just run the prefixed patterns 
        # and standard RSA keys to avoid false positives in random hashes.
        
        if cls.PATTERNS[3].search(content):
            findings.append("RSA/OpenSSH Private Key detected")
            
        if cls.PATTERNS[2].search(content):
            findings.append("Bearer Token detected")
            
        return findings
