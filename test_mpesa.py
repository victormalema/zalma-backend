"""
Run from your project root:

  python test_mpesa.py            -> only checks your credentials (gets a token)
  python test_mpesa.py 0797824212 -> also sends a KES 1 STK push to that phone

Needs the MPESA_* env vars set in your shell (or a .env loaded by python-dotenv).
"""
import os
print("dotenv loaded:", 'load_dotenv' in globals())
print("key found:", bool(os.environ.get("MPESA_CONSUMER_KEY")))
print("shortcode:", os.environ.get("MPESA_SHORTCODE"))
print("working folder:", os.getcwd())
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from services.mpesa_service import MpesaError, get_access_token, stk_push

try:
    token = get_access_token()
    print("OK - credentials work. Token starts with:", token[:8] + "...")
    if len(sys.argv) > 1:
        result = stk_push(sys.argv[1], 1, "TEST0001")
        print("STK push sent:", result)
except MpesaError as e:
    print("FAILED:", e.message)
