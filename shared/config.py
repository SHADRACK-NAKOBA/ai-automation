"""
shared/config.py
================
Central configuration loader.

WHY THIS EXISTS:
  Every agent needs the same config. Without this, you'd scatter
  os.environ calls across 7 files. One bug fix here fixes all agents.

HOW IT WORKS:
  Loads from .env file (local dev) or real environment variables (production).
  Validates required keys exist before anything tries to run.
  Exposes a single get_config() call used by every module.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def get_config() -> dict:
    """
    Load and validate all configuration.
    Raises EnvironmentError if required keys are missing.
    """
    required = ["ANTHROPIC_API_KEY", "SNOW_BASE_URL"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {missing}\n"
            f"Copy .env.example to .env and fill in your values."
        )

    return {
        # AI
        "anthropic_key": os.environ["ANTHROPIC_API_KEY"],
        "ai_model": os.environ.get("AI_MODEL", "claude-sonnet-4-6"),
        "ai_max_tokens": int(os.environ.get("AI_MAX_TOKENS", "1000")),
        # Email settings
        "email_sender":    os.environ.get("EMAIL_SENDER", ""),
        "email_password":  os.environ.get("EMAIL_PASSWORD", ""),
        "email_recipient": os.environ.get("EMAIL_RECIPIENT", ""),
        "email_smtp_host": os.environ.get("EMAIL_SMTP_HOST", "smtp.gmail.com"),
        "email_smtp_port": int(os.environ.get("EMAIL_SMTP_PORT", "587")),

        # ServiceNow
        "snow_base": os.environ["SNOW_BASE_URL"].rstrip("/"),
        "snow_username": os.environ.get("SNOW_USERNAME", ""),
        "snow_password": os.environ.get("SNOW_PASSWORD", ""),
        "snow_token": os.environ.get("SNOW_TOKEN", ""),  # if using token auth

        # Thresholds
        "confidence_threshold": float(
            os.environ.get("CLASSIFIER_CONFIDENCE_THRESHOLD", "0.75")
        ),

        # Feature flags
        "dry_run": os.environ.get("DRY_RUN", "true").lower() == "true",
        "auto_apply_p1": os.environ.get("AUTO_APPLY_P1", "false").lower() == "true",

        # Notifications
        "slack_webhook": os.environ.get("SLACK_WEBHOOK_URL", ""),

        # Database
        "db_path": os.environ.get("DB_PATH", "data/metrics.db"),

        # Environment
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "log_level": os.environ.get("LOG_LEVEL", "INFO"),

        # Scheduler
        "classifier_poll_minutes": int(
            os.environ.get("CLASSIFIER_POLL_INTERVAL_MINUTES", "5")
        ),
    }
