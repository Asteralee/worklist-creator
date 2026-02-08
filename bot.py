import os
import requests
import re
from datetime import datetime

API_URL = "https://simple.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "OrphanWorklistSeeder/1.0"}

WORKLIST_TITLE = "User:AsteraBot/Pages to fix"
QUARRY_JSON_URL = "https://quarry.wmcloud.org/run/1069502/output/0/json"


def login_and_get_session(username, password):
    session = requests.Session()
    session.headers.update(HEADERS)

    r1 = session.get(API_URL, params={
        "action": "query",
        "meta": "tokens",
        "type": "login",
        "format": "json"
    })
    token = r1.json()["query"]["tokens"]["logintoken"]

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
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"Edit failed: {data['error']}")
    print("Worklist updated successfully")


def main():
    username = os.getenv("WIKI_USER")
    password = os.getenv("WIKI_PASS")
    if not username or not password:
        raise RuntimeError("Missing WIKI_USER or WIKI_PASS environment variables")

    session = login_and_get_session(username, password)
    csrf = get_csrf_token(session)

    # Load Quarry JSON
    r = requests.get(QUARRY_JSON_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    quarry_data = r.json()

    quarry_pages = [row[0] for row in quarry_data.get("rows", [])]
    print(f"Loaded {len(quarry_pages)} pages from Quarry.")

    if not quarry_pages:
        print("No pages found — exiting.")
        return

    current_text = fetch_worklist(session, WORKLIST_TITLE)

    current_items = set(
        re.findall(r"^\*\s*\[\[([^\]|]+)", current_text, re.MULTILINE)
    )

    new_items = set(quarry_pages) - current_items
    if not new_items:
        print("No new pages to add — worklist is up to date.")
        return

    print(f"Adding {len(new_items)} new pages.")

    new_lines = "\n".join(f"* [[{title}]]" for title in sorted(new_items))

    # If page is being created, add full timestamp header
    if not current_text.strip():
        timestamp = datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")
        header = f"'''Last updated:''' {timestamp}\n\n"
        new_text = header + new_lines + "\n"
    else:
        new_text = current_text.rstrip() + "\n" + new_lines + "\n"

    save_worklist(
        session,
        new_text,
        WORKLIST_TITLE,
        f"Bot: added {len(new_items)} new pages from Quarry",
        csrf
    )


if __name__ == "__main__":
    main()
