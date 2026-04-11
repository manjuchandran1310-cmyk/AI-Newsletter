"""
Render the Jinja2 email template and deliver it via Resend.

Environment variables required:
  RESEND_API_KEY   — from resend.com dashboard
  RECIPIENT_EMAIL  — who receives the newsletter
  SENDER_EMAIL     — verified sender (default: onboarding@resend.dev for testing)
"""

import os
from datetime import datetime
from pathlib import Path

import resend
from jinja2 import Environment, FileSystemLoader

from pipeline.categorise import (
    AI_CATEGORIES,
    PRODUCT_CATEGORIES,
    FUNDING_CATEGORIES,
    COMMUNITY_CATEGORIES,
    get_top_story,
    get_section,
)

TEMPLATE_DIR = Path(__file__).parent
TEMPLATE_FILE = "template.html.j2"


def render_email(articles: list[dict], trending_topics: list[dict] | None = None) -> str:
    """
    Render the newsletter HTML from enriched article data.

    Args:
        articles:        List of Claude-enriched article dicts.
        trending_topics: Optional list from graph.queries.trending_topics_this_week().

    Returns:
        Rendered HTML string ready to send.
    """
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template(TEMPLATE_FILE)

    # Exclude the top story from section lists to avoid duplication
    top = get_top_story(articles)
    top_url = top["url"] if top else None
    rest = [a for a in articles if a.get("url") != top_url]

    return template.render(
        date=datetime.now().strftime("%B %d, %Y"),
        top_story=top,
        ai_articles=get_section(rest, AI_CATEGORIES, limit=6),
        product_articles=get_section(rest, PRODUCT_CATEGORIES, limit=4),
        funding_articles=get_section(rest, FUNDING_CATEGORIES, limit=4),
        community_articles=get_section(rest, COMMUNITY_CATEGORIES, limit=3),
        trending_topics=trending_topics or [],
    )


def send_email(html: str, subject: str | None = None) -> dict:
    """
    Send the rendered HTML email via Resend.

    Returns the Resend API response dict.
    """
    resend.api_key = os.environ["RESEND_API_KEY"]

    recipient = os.environ["RECIPIENT_EMAIL"]
    # Use onboarding@resend.dev during dev/testing (Resend's sandbox sender).
    # Set SENDER_EMAIL to your verified domain address in production.
    sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")

    if not subject:
        subject = f"AI Newsletter — {datetime.now().strftime('%B %d, %Y')}"

    params: resend.Emails.SendParams = {
        "from": sender,
        "to": [recipient],
        "subject": subject,
        "html": html,
    }

    response = resend.Emails.send(params)
    print(f"[email] Delivered → {recipient} (id: {response.get('id', '?')})")
    return response
