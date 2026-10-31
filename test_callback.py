import sys
import requests

if len(sys.argv) < 3:
    print("Usage: python test_callback.py YOUR_SECRET ws_CO_xxxxxxxx [fail]")
    sys.exit(1)

secret, request_id = sys.argv[1], sys.argv[2]
fail = len(sys.argv) > 3 and sys.argv[3] == "fail"

callback = {
    "MerchantRequestID": "x",
    "CheckoutRequestID": request_id,
    "ResultCode": 1032 if fail else 0,
    "ResultDesc": "Request cancelled by user" if fail else "ok",
}
if not fail:
    callback["CallbackMetadata"] = {"Item": [
        {"Name": "Amount", "Value": 1},
        {"Name": "MpesaReceiptNumber", "Value": "TEST123ABC"},
        {"Name": "PhoneNumber", "Value": 254797824212},
    ]}

r = requests.post(
    f"https://zalma-backend-1.onrender.com/api/payments/callback/{secret}",
    json={"Body": {"stkCallback": callback}},
    timeout=30,
)
print(r.status_code, r.text)