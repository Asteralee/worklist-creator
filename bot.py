import os
import json
import requests
import re

API_URL = "https://simple.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "OrphanWorklistSeeder/1.0"}

WORKLIST_TITLE = os.getenv(
    "WORKLIST_TITLE",
    "User:AsteraBot/Pages to fix"
)

# Path to your downloaded Quarry JSON file
QUARRY_JSON_FILE = os.getenv(
    "QUARRY_JSON_FILE",
    "quarry-101099-orphaned-articles-with-more-than-two-incoming-links-retest-run1069296 (1).json"
)

def login_and_get_session(username, password):
    session = requests.Session()
    session.headers.update(HEADERS)

    # Get login token
    r1 = session.get(API_URL, params={
        "action": "query",
        "meta": "tokens",
        "type": "login",
        "format": "json"
    })
    token = r1.json()["query"]["tokens"]["logintoken"]

    # Login
    r2 = session.post(API_URL, data={
        "action": "login",
        "lgname": username,
        "lgpassword": password,
        "lgtoken": token,
        "format": "json"
    })
    if r2.json()["login"]["result"] != "Success":
        raise RuntimeError(f"Login failed: {r2.json()['login']}")
    print(f"Logged in as {username}")
    return session


def get_csrf_token(session):
    r = session.get(API_URL, params={
        "action": "query",
        "meta": "tokens",
        "format": "json"
    })
    return r.json()["query"]["tokens"]["csrftoken"]


def fetch_worklist(session, title):
    r = session.get(API_URL, params={
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "titles": title,
        "format": "json"
    })
    pages = r.json()["query"]["pages"]
    page = next(iter(pages.values()))
    if "revisions" not in page:
        return ""
    return page["revisions"][0]["slots"]["main"]["*"]


def save_worklist(session, text, title, summary, token):
    r = session.post(API_URL, data={
        "action": "edit",
        "title": title,
        "text": text,
        "summary": summary,
        "token": token,
        "bot": True,
        "format": "json"
    })
    if "error" in r.json():
        print(f"Worklist edit failed: {r.json()['error']}")
    else:
        print("Worklist updated successfully")

def main():
    # Credentials from environment
    username = os.getenv("WIKI_USER")
    password = os.getenv("WIKI_PASS")
    if not username or not password:
        raise RuntimeError("Missing WIKI_USER or WIKI_PASS environment variables")

    # Login
    session = login_and_get_session(username, password)
    csrf = get_csrf_token(session)

    # Load Quarry JSON
    with open(QUARRY_JSON_FILE, "r", encoding="utf-8") as f:
        quarry_data = json.load(f)

    quarry_pages = [row["page_title"] for row in quarry_data]
    print(f"Loaded {len(quarry_pages)} pages from Quarry JSON.")

    if not quarry_pages:
        print("No pages found in the Quarry JSON — exiting.")
        return

    # Fetch worklist
    current_text = fetch_worklist(session, WORKLIST_TITLE)
    current_items = set(
        line[4:-2] for line in current_text.splitlines()
        if line.startswith("* [[") and line.endswith("]]")
    )

    # Determine new pages to add
    new_items = set(quarry_pages) - current_items
    if not new_items:
        print("No new pages to add — worklist is up to date.")
        return

    print(f"Adding {len(new_items)} new pages to worklist.")

    # Build new worklist text
    new_lines = "\n".join(f"* [[{t}]]" for t in sorted(new_items))
    new_text = current_text.rstrip() + "\n" + new_lines + "\n"

    # Save updated worklist
    save_worklist(
        session,
        new_text,
        WORKLIST_TITLE,
        f"Bot: added {len(new_items)} new pages from Quarry JSON",
        csrf
    )


if __name__ == "__main__":
    main()
