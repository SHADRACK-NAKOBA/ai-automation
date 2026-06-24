"""
shared/snow_client.py
=====================
ServiceNow REST API client — used by ALL agents.

WHY A SHARED CLIENT:
  Without this, each agent duplicates HTTP setup, auth headers, and
  error handling. One bug gets fixed once here, not in 7 places.

MODES:
  - LIVE MODE: Reads and writes to your real ServiceNow instance
  - SYNTHETIC MODE: Loads data from data/synthetic/tickets.json
    Use synthetic mode when you have no ServiceNow access yet,
    or when running tests.

HOW TO USE:
  from shared.snow_client import ServiceNowClient
  client = ServiceNowClient(config)
  tickets = client.get_unclassified_tickets()
"""

import base64
import json
import os
from pathlib import Path
from typing import Optional

import requests

from shared.logger import get_logger

logger = get_logger("snow_client")


class ServiceNowClient:
    def __init__(self, config: dict):
        self.base = config["snow_base"]
        self.dry_run = config.get("dry_run", True)
        self.use_synthetic = not config.get("snow_username") and not config.get("snow_token")

        # Build auth header
        if config.get("snow_token"):
            # Pre-built token (base64 of user:pass)
            self.headers = {
                "Authorization": f"Basic {config['snow_token']}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        elif config.get("snow_username") and config.get("snow_password"):
            # Build basic auth from username + password
            creds = f"{config['snow_username']}:{config['snow_password']}"
            token = base64.b64encode(creds.encode()).decode()
            self.headers = {
                "Authorization": f"Basic {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        else:
            self.headers = {}
            logger.warning(
                "No ServiceNow credentials found. Running in SYNTHETIC mode. "
                "Set SNOW_USERNAME + SNOW_PASSWORD in your .env to connect to a real instance."
            )
            self.use_synthetic = True

        self.session = requests.Session()
        self.session.headers.update(self.headers)

        mode = "SYNTHETIC" if self.use_synthetic else "LIVE"
        dry = " + DRY_RUN" if self.dry_run else ""
        logger.info(f"ServiceNowClient initialized [{mode}{dry}]")

    # ------------------------------------------------------------------ #
    # READ OPERATIONS
    # ------------------------------------------------------------------ #

    def get_unclassified_tickets(self, limit: int = 50) -> list:
        """
        Fetch tickets that have no category set.
        This is the main feed for the Ticket Classifier agent.
        """
        if self.use_synthetic:
            return self._load_synthetic_tickets()

        params = {
            "sysparm_query": "category=^state!=6^state!=7",
            "sysparm_limit": limit,
            "sysparm_fields": (
                "sys_id,number,short_description,description,"
                "opened_at,priority,state,caller_id,cmdb_ci"
            ),
            "sysparm_display_value": "true",
        }
        try:
            resp = self.session.get(
                f"{self.base}/api/now/table/incident",
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            tickets = resp.json().get("result", [])
            logger.info(f"Fetched {len(tickets)} unclassified tickets from ServiceNow")
            return tickets
        except requests.RequestException as e:
            logger.error(f"Failed to fetch tickets: {e}")
            return []

    def get_incident(self, sys_id: str) -> dict:
        """Fetch a single incident by sys_id."""
        if self.use_synthetic:
            tickets = self._load_synthetic_tickets()
            return next((t for t in tickets if t["sys_id"] == sys_id), {})

        try:
            resp = self.session.get(
                f"{self.base}/api/now/table/incident/{sys_id}",
                params={"sysparm_display_value": "true"},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json().get("result", {})
        except requests.RequestException as e:
            logger.error(f"Failed to fetch incident {sys_id}: {e}")
            return {}

    # ------------------------------------------------------------------ #
    # WRITE OPERATIONS (blocked in dry_run mode)
    # ------------------------------------------------------------------ #

    def update_incident(self, sys_id: str, payload: dict) -> bool:
        """
        Update a ticket in ServiceNow.

        In DRY_RUN mode: logs what would happen, never actually writes.
        WHY: You should always test with dry_run=True before enabling live writes.
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would update {sys_id} with: {json.dumps(payload, indent=2)}")
            return True

        if self.use_synthetic:
            logger.info(f"[SYNTHETIC] Skipping write for {sys_id}")
            return True

        try:
            resp = self.session.patch(
                f"{self.base}/api/now/table/incident/{sys_id}",
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            logger.info(f"Updated ticket {sys_id}")
            return True
        except requests.RequestException as e:
            logger.error(f"Failed to update ticket {sys_id}: {e}")
            return False

    def add_work_note(self, sys_id: str, note: str) -> bool:
        """Add an internal work note to a ticket."""
        return self.update_incident(sys_id, {"work_notes": note})

    # ------------------------------------------------------------------ #
    # SYNTHETIC DATA (when no ServiceNow access)
    # ------------------------------------------------------------------ #

    def _load_synthetic_tickets(self) -> list:
        """Load synthetic tickets from the local data file."""
        path = Path("data/synthetic/tickets.json")
        if not path.exists():
            logger.warning(f"Synthetic data not found at {path}. Run: python tools/seed_data.py")
            return []
        with open(path) as f:
            tickets = json.load(f)
        logger.info(f"Loaded {len(tickets)} synthetic tickets from {path}")
        return tickets

    def test_connection(self) -> bool:
        """Verify ServiceNow connectivity. Used by test_connections.py"""
        if self.use_synthetic:
            logger.info("Connection test: SYNTHETIC mode (no real ServiceNow)")
            return True
        try:
            resp = self.session.get(
                f"{self.base}/api/now/table/incident",
                params={"sysparm_limit": 1},
                timeout=10,
            )
            if resp.ok:
                logger.info("✅ ServiceNow connection: OK")
                return True
            else:
                logger.error(f"❌ ServiceNow connection failed: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ ServiceNow connection error: {e}")
            return False

    def get_incidents(self, query: str = "", limit: int = 50) -> list:
        """Fetch multiple incidents matching a query string."""
        if self.use_synthetic:
            return self._load_synthetic_tickets()
        params = {"sysparm_limit": limit, "sysparm_display_value": "true"}
        if query:
            params["sysparm_query"] = query
        try:
            resp = self.session.get(
                f"{self.base}/api/now/table/incident",
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            tickets = resp.json().get("result", [])
            logger.info(f"get_incidents: fetched {len(tickets)} tickets")
            return tickets
        except requests.RequestException as e:
            logger.error(f"get_incidents failed: {e}")
            return []
