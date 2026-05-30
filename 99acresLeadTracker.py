from bs4 import BeautifulSoup
import os
import re
import time
import imaplib
import email
from urllib.parse import quote

import requests
from dotenv import load_dotenv


# =========================
# Load Environment Variables
# =========================
load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

PROJECT_NAME = os.getenv("PROJECT_NAME", "Sai Sun City")


# =========================
# Telegram Sender
# =========================
def send_telegram_message(text: str):

    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
    }

    response = requests.post(url, json=payload, timeout=20)

    if response.status_code == 200:
        print("✅ Telegram message sent")

    else:
        print("❌ Telegram Error:", response.text)


# =========================
# Generate WhatsApp URL
# =========================
def generate_whatsapp_link(
    phone: str,
    full_name: str,
    property_type: str,
    budget: str
):

    # Clean phone number
    clean_phone = "".join(filter(str.isdigit, phone))

    # Add India country code if missing
    if clean_phone and not clean_phone.startswith("91"):
        clean_phone = f"91{clean_phone}"

    whatsapp_message = (
        f"Hi {full_name},\n\n"
        f"Regarding your enquiry on 99acres for the {property_type} property "
        f"within a budget of {budget}.\n\n"
        f"We do have similar and better-matching options available as well. \n\n"
        f"To guide you properly, may I know: \n"
        f"Is this for self-use or investment? \n\n"
        f"Also, are you currently staying "
        f"in Navi Mumbai or planning to shift here?"
    )

    encoded_message = quote(whatsapp_message)

    whatsapp_url = (
        f"https://wa.me/"
        f"{clean_phone}"
        f"?text={encoded_message}"
    )

    return whatsapp_url


# =========================
# Extract Lead Details
# =========================
def extract_lead_details(body: str):

    print("\n========== RAW EMAIL BODY ==========\n")
    print(body)

    # =========================
    # Extract Email
    # =========================
    email_match = re.search(
        r'[\w\.-]+@[\w\.-]+\.\w+',
        body
    )

    email_id = (
        email_match.group(0)
        if email_match else "N/A"
    )

    # =========================
    # Extract Phone
    # =========================
    phone_match = re.search(
        r'(\+91[-\s]?\d{10})',
        body
    )

    phone = (
        phone_match.group(1)
        if phone_match else "N/A"
    )

    # =========================
    # Extract Name
    # =========================
    name = "N/A"

    lines = [
        line.strip()
        for line in body.splitlines()
        if line.strip()
    ]

    for i, line in enumerate(lines):

        if email_id in line and i > 0:

            possible_name = lines[i - 1]

            if (
                "@" not in possible_name
                and "query" not in possible_name.lower()
            ):

                name = possible_name

            break

    # =========================
    # Extract Budget
    # =========================
    budget_match = re.search(
        r'(Rs[\d\sA-Za-z]+)',
        body
    )

    budget = (
        budget_match.group(1).strip()
        if budget_match else "N/A"
    )

    # =========================
    # Extract Property Details
    # =========================
    property_match = re.search(
        r'Flat/Apartment in (.*?)\(',
        body,
        re.DOTALL
    )

    property_type = (
        property_match.group(1)
        .replace("\n", " ")
        .strip()
        if property_match else "N/A"
    )

    print("\n========== EXTRACTED DATA ==========\n")
    print("Name:", name)
    print("Email:", email_id)
    print("Phone:", phone)
    print("Budget:", budget)
    print("Property:", property_type)

    return {
        "name": name,
        "email": email_id,
        "phone": phone,
        "property_type": property_type,
        "budget": budget,
    }


# =========================
# Build Telegram Message
# =========================
def build_telegram_message(lead):

    whatsapp_url = generate_whatsapp_link(
        lead["phone"],
        lead["name"],
        lead["property_type"],
        lead["budget"]
    )

    message = (
        f"🎉 New 99acres Lead\n\n"
        f"Name: {lead['name']}\n"
        f"Phone: {lead['phone']}\n"
        f"Property: {lead['property_type']}\n"
        f"Budget: {lead['budget']}\n\n"
        f"-------------------------------\n\n"
        f"WhatsApp Chat:\n"
        f"{whatsapp_url}"
    )

    return message


# =========================
# Extract Email Body
# =========================
def extract_email_body(msg):

    body = ""

    if msg.is_multipart():

        for part in msg.walk():

            content_type = part.get_content_type()

            print("Content Type:", content_type)

            # Extract HTML body
            if content_type == "text/html":

                html_content = (
                    part.get_payload(decode=True)
                    .decode(errors="ignore")
                )

                # Convert HTML to clean text
                soup = BeautifulSoup(
                    html_content,
                    "html.parser"
                )

                body = soup.get_text(
                    separator="\n",
                    strip=True
                )

                break

    else:

        content_type = msg.get_content_type()

        if content_type == "text/html":

            html_content = (
                msg.get_payload(decode=True)
                .decode(errors="ignore")
            )

            soup = BeautifulSoup(
                html_content,
                "html.parser"
            )

            body = soup.get_text(
                separator="\n",
                strip=True
            )

    return body


# =========================
# Fetch Latest 99acres Email
# =========================
def fetch_latest_99acres_email():

    print("\n📥 Checking emails...\n")

    mail = imaplib.IMAP4_SSL("imap.gmail.com")

    mail.login(
        EMAIL_ADDRESS,
        EMAIL_APP_PASSWORD
    )

    mail.select("inbox")
    mail.noop()

    # Fetch unread emails
    status, messages = mail.search(
        None,
        '(UNSEEN)'
    )

    email_ids = messages[0].split()

    if not email_ids:

        print("❌ No unread emails found")

        mail.logout()

        return

    # Check latest unread emails first
    for email_id in reversed(email_ids):

        _, msg_data = mail.fetch(
            email_id,
            "(RFC822)"
        )

        raw_email = msg_data[0][1]

        msg = email.message_from_bytes(raw_email)

        sender = msg.get("from", "")

        # Process ONLY 99acres emails
        if "99acres" not in sender.lower():

            print("⏭️ Skipping non-99acres email")

            continue

        print("✅ 99acres email found")

        # Extract BODY_PLAIN
        body = extract_email_body(msg)
        print("Body: ", body)

        if not body:

            print("❌ Empty email body")

            continue

        # Extract lead details
        lead = extract_lead_details(body)

        # Build Telegram message
        telegram_message = (
            build_telegram_message(lead)
        )

        # Send Telegram message
        send_telegram_message(
            telegram_message
        )

        # Mark email as read
        mail.store(
            email_id,
            '+FLAGS',
            '\\Seen'
        )

        print("✅ Email marked as read")

        # Stop after first valid lead
        break

    mail.logout()


# =========================
# Main Loop
# =========================
if __name__ == "__main__":

    print("🚀 99acres Lead Bot Started")

    while True:

        try:

            fetch_latest_99acres_email()

        except Exception as e:

            print("❌ ERROR:", str(e))

        # Check every 60 seconds
        time.sleep(60)