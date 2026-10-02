"""Connectivity self-check for ClinicalTrials.gov — run via diagnose.bat / ./diagnose.sh.
Prints plain-language findings; never disables TLS verification."""
import os
import socket
import ssl
import sys
import time

import httpx

URL = "https://clinicaltrials.gov/api/v2/studies?pageSize=1&countTotal=true"
ok = True


def line(flag, msg):
    print(f"  [{flag}] {msg}")


print("\nTrialLens connection check\n--------------------------")
line("i", f"Python {sys.version.split()[0]}")
for var in ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "TRIALLENS_USE_SYSTEM_CERTS"):
    if os.environ.get(var):
        line("i", f"{var} = {os.environ[var]}")

try:
    ip = socket.gethostbyname("clinicaltrials.gov")
    line("OK", f"DNS: clinicaltrials.gov -> {ip}")
except OSError as e:
    ok = False
    line("!!", f"DNS lookup failed ({e}). Check internet access / ask IT whether the site is allowed.")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/backend")
try:
    from services.http import client
    verify = client()._transport  # noqa: F841  (builds the client to validate configuration)
except Exception as e:  # noqa: BLE001
    ok = False
    line("!!", f"Client configuration problem: {e}")

try:
    from services.http import _verify
    t0 = time.time()
    r = httpx.get(URL, timeout=20, verify=_verify())
    if r.status_code == 200:
        total = r.json().get("totalCount")
        line("OK", f"ClinicalTrials.gov API reachable ({total:,} studies registered; {time.time() - t0:.1f}s)")
    else:
        ok = False
        line("!!", f"ClinicalTrials.gov answered HTTP {r.status_code}.")
except Exception as e:  # noqa: BLE001
    ok = False
    blob = f"{type(e).__name__} {e}".lower()
    if "certificate" in blob or isinstance(e, ssl.SSLError):
        line("!!", "TLS certificate not trusted. Your network probably inspects HTTPS with a company certificate.")
        print("      Fix A: ask IT for the company root certificate (.pem) and set SSL_CERT_FILE to its full path.")
        print("      Fix B: pip install truststore, then set TRIALLENS_USE_SYSTEM_CERTS=1 (uses the Windows store).")
    elif "proxy" in blob or "407" in blob:
        line("!!", "Proxy problem. Set HTTPS_PROXY=http://proxy.company.com:8080 (ask IT for the address).")
    else:
        line("!!", f"Could not connect: {type(e).__name__}: {e}")
        print("      A firewall/proxy may be blocking clinicaltrials.gov. Ask IT to allow it.")

print()
print("  Everything looks fine." if ok else "  Some checks failed - see above. Send this output to IT or to whoever shared TrialLens.")
print()
sys.exit(0 if ok else 1)
