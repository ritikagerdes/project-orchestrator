import os
import requests
from typing import Dict, Any, Optional

HUBSPOT_TOKEN = os.getenv("HUBSPOT_API_KEY")  # expected to be a bearer token

def create_contact(name: str, email: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not HUBSPOT_TOKEN:
        raise RuntimeError("HUBSPOT_API_KEY not configured")
    url = "https://api.hubapi.com/crm/v3/objects/contacts"
    headers = {"Authorization": f"Bearer {HUBSPOT_TOKEN}", "Content-Type": "application/json"}
    props = {"email": email, "firstname": name}
    if extra:
        props.update(extra)
    payload = {"properties": props}
    r = requests.post(url, json=payload, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()

def create_note_for_contact(contact_id: str, note_text: str) -> Dict[str, Any]:
    """
    Create a note and associate it with the contact (simple approach).
    """
    if not HUBSPOT_TOKEN:
        raise RuntimeError("HUBSPOT_API_KEY not configured")
    # create note
    url = "https://api.hubapi.com/crm/v3/objects/notes"
    headers = {"Authorization": f"Bearer {HUBSPOT_TOKEN}", "Content-Type": "application/json"}
    payload = {"properties": {"hs_note_body": note_text}}
    r = requests.post(url, json=payload, headers=headers, timeout=10)
    r.raise_for_status()
    note = r.json()
    # associate with contact
    assoc_url = f"https://api.hubapi.com/crm/v3/objects/notes/{note['id']}/associations/contact/{contact_id}/note_to_contact"
    assoc_r = requests.put(assoc_url, headers=headers, timeout=10)
    assoc_r.raise_for_status()
    return note