"""
services/mpesa_service.py
M-Pesa STK Push (Buy Goods / till) via Safaricom Daraja.

Env vars used:
  MPESA_ENV              sandbox | production
  MPESA_CONSUMER_KEY
  MPESA_CONSUMER_SECRET
  MPESA_SHORTCODE        Daraja shortcode (signs the request)
  MPESA_TILL             till number that receives the money (PartyB)
  MPESA_PASSKEY
  MPESA_CALLBACK_URL     public https URL of the callback route
Optional:
  MPESA_TXN_TYPE         defaults to CustomerBuyGoodsOnline
"""
import base64
import math
import os
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


class MpesaError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


_token_cache = {"value": None, "expires_at": 0.0}


def _base_url() -> str:
    if os.environ.get("MPESA_ENV", "sandbox").lower() == "production":
        return "https://api.safaricom.co.ke"
    return "https://sandbox.safaricom.co.ke"


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MpesaError(f"{name} is not set", 500)
    return value


def get_access_token() -> str:
    """OAuth token, cached until shortly before it expires (they last ~1 hour)."""
    if _token_cache["value"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["value"]

    key = _require_env("MPESA_CONSUMER_KEY")
    secret = _require_env("MPESA_CONSUMER_SECRET")
    try:
        resp = requests.get(
            f"{_base_url()}/oauth/v1/generate?grant_type=client_credentials",
            auth=(key, secret),
            timeout=20,
        )
    except requests.RequestException as e:
        raise MpesaError(f"Could not reach M-Pesa: {e}")

    if resp.status_code != 200:
        raise MpesaError(f"M-Pesa auth failed ({resp.status_code}). Check consumer key/secret and MPESA_ENV.")

    data = resp.json()
    _token_cache["value"] = data["access_token"]
    _token_cache["expires_at"] = time.time() + int(data.get("expires_in", 3599)) - 60
    return _token_cache["value"]


def normalize_phone(phone: str) -> str:
    """Turns 0712345678 / +254712345678 / 712345678 into 254712345678."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    elif len(digits) == 9 and digits[0] in "71":
        digits = "254" + digits
    if not re.fullmatch(r"254[17]\d{8}", digits):
        raise MpesaError("Enter a valid Safaricom number, e.g. 0712 345 678", 400)
    return digits


def stk_push(phone: str, amount, order_id: str) -> dict:
    """Sends the payment prompt to the customer's phone.
    Returns {"checkout_request_id", "merchant_request_id", "customer_message"}."""
    shortcode = _require_env("MPESA_SHORTCODE")
    till = _require_env("MPESA_TILL")
    passkey = _require_env("MPESA_PASSKEY")
    callback = _require_env("MPESA_CALLBACK_URL")

    phone = normalize_phone(phone)
    amount = max(1, math.ceil(float(amount)))  # Daraja only accepts whole shillings

    timestamp = datetime.now(ZoneInfo("Africa/Nairobi")).strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": os.environ.get("MPESA_TXN_TYPE", "CustomerBuyGoodsOnline"),
        "Amount": amount,
        "PartyA": phone,
        "PartyB": till,
        "PhoneNumber": phone,
        "CallBackURL": callback,
        "AccountReference": f"ZALMA{str(order_id)[:6]}"[:12],  # max 12 chars
        "TransactionDesc": "ZALMA order"[:13],                  # max 13 chars
    }

    try:
        resp = requests.post(
            f"{_base_url()}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers={"Authorization": f"Bearer {get_access_token()}"},
            timeout=30,
        )
        data = resp.json()
    except requests.RequestException as e:
        raise MpesaError(f"Could not reach M-Pesa: {e}")
    except ValueError:
        raise MpesaError("M-Pesa returned an unreadable response")

    if resp.status_code != 200 or str(data.get("ResponseCode")) != "0":
        detail = data.get("errorMessage") or data.get("ResponseDescription") or "Request rejected"
        raise MpesaError(f"M-Pesa: {detail}")

    return {
        "checkout_request_id": data["CheckoutRequestID"],
        "merchant_request_id": data.get("MerchantRequestID"),
        "customer_message": data.get("CustomerMessage", "Check your phone to enter your M-Pesa PIN."),
    }


def parse_callback(body: dict) -> dict:
    """Flattens Safaricom's callback JSON.
    result_code == 0 means paid; anything else means failed/cancelled/timed out."""
    cb = (body or {}).get("Body", {}).get("stkCallback")
    if not cb:
        raise MpesaError("Malformed callback", 400)

    result = {
        "checkout_request_id": cb.get("CheckoutRequestID"),
        "result_code": int(cb.get("ResultCode", -1)),
        "result_desc": cb.get("ResultDesc"),
        "receipt": None,
        "amount": None,
        "phone": None,
    }
    if result["result_code"] == 0:
        for item in cb.get("CallbackMetadata", {}).get("Item", []):
            name, value = item.get("Name"), item.get("Value")
            if name == "MpesaReceiptNumber":
                result["receipt"] = value
            elif name == "Amount":
                result["amount"] = value
            elif name == "PhoneNumber":
                result["phone"] = str(value)
    return result


def stk_query(checkout_request_id: str) -> dict:
    """Asks Safaricom what happened to an STK push.
    Returns {"result_code": int | None, "result_desc": str}.
      result_code 0      -> the customer paid
      result_code other  -> cancelled / failed / timed out (1032, 1037, 2001 ...)
      result_code None   -> no final answer yet (still processing, or Safaricom could not tell)
    Raises MpesaError only if Safaricom cannot be reached or rejects our login."""
    shortcode = _require_env("MPESA_SHORTCODE")
    passkey = _require_env("MPESA_PASSKEY")

    timestamp = datetime.now(ZoneInfo("Africa/Nairobi")).strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()

    try:
        resp = requests.post(
            f"{_base_url()}/mpesa/stkpushquery/v1/query",
            json={
                "BusinessShortCode": shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id,
            },
            headers={"Authorization": f"Bearer {get_access_token()}"},
            timeout=30,
        )
    except requests.RequestException as e:
        raise MpesaError(f"Could not reach M-Pesa: {e}")

    try:
        data = resp.json()
    except ValueError:
        return {"result_code": None, "result_desc": "Unreadable response"}

    if "ResultCode" in data:
        try:
            return {"result_code": int(data["ResultCode"]), "result_desc": data.get("ResultDesc", "")}
        except (TypeError, ValueError):
            pass
    return {"result_code": None, "result_desc": data.get("errorMessage") or data.get("ResultDesc") or ""}