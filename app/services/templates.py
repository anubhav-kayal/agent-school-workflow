"""Bodies of our WhatsApp templates (mirrors docs/whatsapp_templates.md).

Used to store the rendered text of each template we send, so the conversation history the
assistant sees and the dashboard both show what the parent actually received.
"""

from __future__ import annotations

TEMPLATES: dict[tuple[str, str], str] = {
    ("enquiry_first_response", "en"): (
        "Hello {1}, thank you for your enquiry with {2} for {3} admission. I'm the school's "
        "admission assistant. I can share details about the school or book a campus visit for "
        "you. How can I help?"
    ),
    ("enquiry_first_response", "hi"): (
        "नमस्ते {1}, {2} में {3} एडमिशन के लिए पूछताछ करने के लिए धन्यवाद। मैं स्कूल का एडमिशन "
        "असिस्टेंट हूँ। मैं आपको स्कूल की जानकारी दे सकता हूँ या कैंपस विज़िट बुक कर सकता हूँ। "
        "बताइए, मैं कैसे मदद करूँ?"
    ),
    ("visit_reminder_day_before", "en"): (
        "Hi {1}, a reminder that your campus visit at {2} is tomorrow at {3}. "
        "We look forward to meeting you."
    ),
    ("visit_reminder_day_before", "hi"): (
        "नमस्ते {1}, याद दिला दें कि {2} में आपकी कैंपस विज़िट कल {3} बजे है। हमें आपसे मिलने का इंतज़ार रहेगा।"
    ),
    (
        "visit_reminder_morning",
        "en",
    ): "Good morning {1}! See you today at {2} at {3}. Directions: {4}",
    ("visit_reminder_morning", "hi"): "सुप्रभात {1}! आज {2} बजे {3} में मिलते हैं। रास्ता: {4}",
    ("counselor_lead_alert", "en"): (
        'New lead needs attention: {1} – {2}, {3}. Reason: {4}. Last message: "{5}". '
        "Tap a button to update the status."
    ),
}

QUICK_REPLIES: dict[tuple[str, str], list[tuple[str, str]]] = {
    ("enquiry_first_response", "en"): [
        ("book_visit", "Book a campus visit"),
        ("ask", "Ask a question"),
        ("optout", "Stop messages"),
    ],
    ("enquiry_first_response", "hi"): [
        ("book_visit", "कैंपस विज़िट बुक करें"),
        ("ask", "सवाल पूछें"),
        ("optout", "मैसेज बंद करें"),
    ],
}

ALL_TEMPLATE_KEYS = frozenset(TEMPLATES)


def render(name: str, language: str, variables: list[str]) -> str:
    body = TEMPLATES.get((name, language)) or TEMPLATES[(name, "en")]
    for index, value in enumerate(variables, start=1):
        body = body.replace("{" + str(index) + "}", value)
    return body
