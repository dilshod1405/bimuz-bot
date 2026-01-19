"""Utility functions for the bot."""
from typing import List, Dict, Any, Optional


def extract_list_from_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract list from API response.
    Handles different response formats:
    - Format 1: {'success': True, 'data': [...]}
    - Format 2: {'count': ..., 'next': ..., 'results': [...]} (pagination)
    - Format 3: {'success': True, 'data': {'results': [...]}} (nested pagination)
    """
    # Direct pagination format (no 'success' field)
    if 'results' in response and not response.get('success'):
        return response.get('results', [])
    
    # Success response format
    if response.get('success'):
        data = response.get('data', [])
        
        # If data is a dict with 'results' (nested pagination)
        if isinstance(data, dict) and 'results' in data:
            return data.get('results', [])
        
        # If data is a list, return it
        if isinstance(data, list):
            return data
        
        # If data is a dict but no 'results', return empty list
        if isinstance(data, dict):
            return []
    
    # Fallback: return empty list
    return []


def truncate_message(text: str, max_length: int = 4000) -> str:
    """
    Truncate message to fit Telegram's 4096 character limit.
    Leaves some buffer for formatting and error messages.
    """
    if len(text) <= max_length:
        return text
    
    # Truncate and add indicator
    truncated = text[:max_length - 50]
    # Try to cut at a newline if possible
    last_newline = truncated.rfind('\n')
    if last_newline > max_length - 200:  # If we have a reasonable newline position
        truncated = truncated[:last_newline]
    
    return truncated + "\n\n... (xabar qisqartirildi)"


def format_error_message(message: str, errors: Dict[str, Any] = None, max_length: int = 4000) -> str:
    """
    Format error message with validation errors, ensuring it doesn't exceed Telegram's limit.
    """
    error_msg = f"❌ Xatolik: {message}"
    
    if errors:
        error_list = []
        for key, value_list in errors.items():
            if isinstance(value_list, list) and len(value_list) > 0:
                error_list.append(f"- {key}: {value_list[0]}")
        
        if error_list:
            errors_text = "\n\nXatolar:\n" + "\n".join(error_list)
            # Limit number of errors shown to prevent message from being too long
            if len(error_list) > 10:
                errors_text = "\n\nXatolar (faqat birinchi 10 tasi):\n" + "\n".join(error_list[:10])
                errors_text += f"\n\n... va yana {len(error_list) - 10} ta xato"
            
            full_message = error_msg + errors_text
            return truncate_message(full_message, max_length)
    
    return truncate_message(error_msg, max_length)


def truncate_alert_message(text: str, max_length: int = 200) -> str:
    """
    Truncate message for Telegram alert popup (callback.answer with show_alert=True).
    Telegram alert messages have a 200 character limit.
    """
    if len(text) <= max_length:
        return text
    
    # Truncate and add indicator
    truncated = text[:max_length - 20]
    # Try to cut at a space or punctuation if possible
    last_space = truncated.rfind(' ')
    last_punct = max(truncated.rfind('.'), truncated.rfind(','), truncated.rfind(':'))
    cut_point = max(last_space, last_punct)
    
    if cut_point > max_length - 50:  # If we have a reasonable cut point
        truncated = truncated[:cut_point]
    
    return truncated + "..."


def escape_html(text: str) -> str:
    """
    Escape HTML special characters to prevent parsing errors.
    Escapes: < > & "
    Telegram HTML parse_mode supports: <b>bold</b>, <i>italic</i>, <u>underline</u>, 
    <s>strikethrough</s>, <code>code</code>, <pre>preformatted</pre>, <a href="URL">text</a>
    """
    if text is None:
        return ""
    
    # Convert to string if not already
    text = str(text)
    
    # Escape HTML special characters
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    
    return text


def safe_html_text(text: str) -> str:
    """
    Safely format text for HTML parse_mode by escaping user data.
    This prevents HTML parsing errors from special characters in user data.
    Use this for all user-provided data when using HTML parse_mode.
    """
    if not text:
        return ""
    
    text = str(text)
    # Escape HTML special characters
    return escape_html(text)


def validate_phone(phone: str) -> tuple[bool, str]:
    """
    Validate phone number format: +998901234567
    - Must start with +
    - No spaces or dashes
    - Exactly 13 characters
    """
    if not phone:
        return False, "Telefon raqami bo'sh bo'lishi mumkin emas."
    
    phone = phone.strip()
    
    # Must start with +
    if not phone.startswith('+'):
        return False, "Telefon raqami '+' belgisi bilan boshlanishi kerak."
    
    # No spaces or dashes
    if ' ' in phone or '-' in phone:
        return False, "Telefon raqamida probel yoki tire bo'lmasligi kerak."
    
    # Check length (exactly 13: +998901234567)
    if len(phone) != 13:
        return False, f"Telefon raqami 13 belgi bo'lishi kerak. Hozirgi uzunlik: {len(phone)}"
    
    # Check if rest are digits
    if not phone[1:].isdigit():
        return False, "Telefon raqamida '+' dan keyin faqat raqamlar bo'lishi kerak."
    
    return True, ""


def validate_passport(passport: str) -> tuple[bool, str]:
    """
    Validate passport format: AA0000000
    - 2 letters at start (can be any letters)
    - 7 digits after
    - Exactly 9 characters
    - No spaces or special characters
    """
    if not passport:
        return False, "Passport seriya raqami bo'sh bo'lishi mumkin emas."
    
    passport = passport.strip().upper()
    
    # Check length (exactly 9: AA0000000)
    if len(passport) != 9:
        return False, f"Passport seriya raqami 9 belgi bo'lishi kerak. Hozirgi uzunlik: {len(passport)}"
    
    # Check if first 2 are letters
    if not passport[:2].isalpha():
        return False, "Passport seriya raqami 2 ta harf bilan boshlanishi kerak."
    
    # Check if last 7 are digits
    if not passport[2:].isdigit():
        return False, "Passport seriya raqamida harflardan keyin 7 ta raqam bo'lishi kerak."
    
    # Check for spaces or special characters (should already be caught, but double check)
    if ' ' in passport or not passport.isalnum():
        return False, "Passport seriya raqamida probel yoki maxsus belgilar bo'lmasligi kerak."
    
    return True, ""
