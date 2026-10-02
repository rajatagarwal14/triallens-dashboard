"""One place that builds HTTP clients for ClinicalTrials.gov.

httpx already honours HTTP(S)_PROXY / NO_PROXY and SSL_CERT_FILE. Managed Windows laptops
often add a company root certificate to the *Windows* certificate store instead; Python
does not read that store by default. Setting TRIALLENS_USE_SYSTEM_CERTS=1 (and installing
the optional `truststore` package, see requirements-optional.txt) makes TLS verification
use the operating-system store. Verification is never disabled.
"""
import os
import ssl
from typing import Union

import httpx


def _verify() -> Union[bool, ssl.SSLContext]:
    if os.environ.get("TRIALLENS_USE_SYSTEM_CERTS", "").lower() in ("1", "true", "yes"):
        try:
            import truststore  # optional dependency
            return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        except ImportError:
            raise RuntimeError(
                "TRIALLENS_USE_SYSTEM_CERTS is set but the 'truststore' package is not installed. "
                "Run: backend\\.venv\\Scripts\\python -m pip install truststore")
    return True


def client(timeout: float = 30.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout, verify=_verify())
