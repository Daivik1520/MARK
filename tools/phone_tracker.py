"""
MARK — Phone Number Tracker
Extracts carrier, location, timezone, line type and other info from phone numbers.
Uses the phonenumbers library (Google's libphonenumber port).
"""

import phonenumbers
from phonenumbers import carrier, geocoder, timezone as pn_timezone, number_type


_TYPE_LABELS = {
    phonenumbers.PhoneNumberType.MOBILE: "Mobile",
    phonenumbers.PhoneNumberType.FIXED_LINE: "Fixed Line (Landline)",
    phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fixed Line or Mobile",
    phonenumbers.PhoneNumberType.TOLL_FREE: "Toll-Free",
    phonenumbers.PhoneNumberType.PREMIUM_RATE: "Premium Rate",
    phonenumbers.PhoneNumberType.SHARED_COST: "Shared Cost",
    phonenumbers.PhoneNumberType.VOIP: "VoIP",
    phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "Personal Number",
    phonenumbers.PhoneNumberType.PAGER: "Pager",
    phonenumbers.PhoneNumberType.UAN: "Universal Access Number",
    phonenumbers.PhoneNumberType.VOICEMAIL: "Voicemail",
    phonenumbers.PhoneNumberType.UNKNOWN: "Unknown",
}


def track_number(phone: str) -> str:
    """
    Track a phone number and return all available info.
    Accepts formats: +919876543210, 09876543210, 9876543210, +1-555-123-4567
    """
    if not phone or not phone.strip():
        return "Please provide a phone number to track."

    raw = phone.strip()

    # Auto-add country code if missing (assume Indian +91 for 10-digit numbers)
    if raw.replace(" ", "").replace("-", "").isdigit():
        digits = raw.replace(" ", "").replace("-", "")
        if len(digits) == 10:
            raw = "+91" + digits
        elif len(digits) == 11 and digits.startswith("0"):
            raw = "+91" + digits[1:]

    if not raw.startswith("+"):
        raw = "+" + raw

    try:
        parsed = phonenumbers.parse(raw, None)
    except phonenumbers.NumberParseException:
        return f"Could not parse '{phone}'. Use format: +919876543210 or +1-555-123-4567"

    if not phonenumbers.is_valid_number(parsed):
        possible = phonenumbers.is_possible_number(parsed)
        if not possible:
            return f"'{phone}' is not a valid phone number."

    # Gather info
    info = []
    info.append(f"📱 Phone Number Tracking Report")
    info.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Formatted number
    intl = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    national = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
    info.append(f"Number     : {intl}")
    info.append(f"National   : {national}")

    # Country
    country_code = parsed.country_code
    region = phonenumbers.region_code_for_number(parsed)
    info.append(f"Country    : {region} (+{country_code})")

    # Location / Region
    location = geocoder.description_for_number(parsed, "en")
    if location:
        info.append(f"Location   : {location}")

    # Carrier / Operator
    carrier_name = carrier.name_for_number(parsed, "en")
    if carrier_name:
        info.append(f"Carrier    : {carrier_name}")

    # Line type
    num_type = number_type(parsed)
    type_label = _TYPE_LABELS.get(num_type, "Unknown")
    info.append(f"Line Type  : {type_label}")

    # Timezone
    tz_list = pn_timezone.time_zones_for_number(parsed)
    if tz_list:
        info.append(f"Timezone   : {', '.join(tz_list)}")

    # Validity
    is_valid = phonenumbers.is_valid_number(parsed)
    is_possible = phonenumbers.is_possible_number(parsed)
    info.append(f"Valid      : {'Yes' if is_valid else 'No'}")
    info.append(f"Possible   : {'Yes' if is_possible else 'No'}")

    info.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(info)
