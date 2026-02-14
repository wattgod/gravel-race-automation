#!/usr/bin/env python3
"""Create the Gravel God Racer Rating Google Form via API."""

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path

SCOPES = ['https://www.googleapis.com/auth/forms.body', 'https://www.googleapis.com/auth/drive']
CREDS_FILE = Path(__file__).parent.parent / 'credentials.json'


def create_gravel_god_form():
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)
    service = build('forms', 'v1', credentials=creds)

    # Create form
    form = service.forms().create(body={
        "info": {
            "title": "Rate This Race — Gravel God",
            "documentTitle": "Gravel God Race Rating",
        }
    }).execute()
    form_id = form['formId']
    print(f"Form created: {form_id}")

    # Update description + add all questions
    requests = [
        # Set description
        {"updateFormInfo": {
            "info": {
                "description": (
                    "Help fellow racers know what to expect. Takes 60 seconds.\n\n"
                    "Review guidelines: Keep it about the race. No personal attacks, "
                    "slurs, or hate speech. Reviews that violate guidelines won't be published."
                ),
            },
            "updateMask": "description",
        }},
        # 1. Race (Short Answer) — pre-filled via URL param
        {"createItem": {
            "item": {
                "title": "Race",
                "questionItem": {"question": {"required": True, "textQuestion": {}}},
            },
            "location": {"index": 0},
        }},
        # 2. What year did you race? (Dropdown)
        {"createItem": {
            "item": {
                "title": "What year did you race?",
                "questionItem": {"question": {
                    "required": True,
                    "choiceQuestion": {
                        "type": "DROP_DOWN",
                        "options": [
                            {"value": "2020"}, {"value": "2021"}, {"value": "2022"},
                            {"value": "2023"}, {"value": "2024"}, {"value": "2025"},
                            {"value": "2026"},
                        ],
                    },
                }},
            },
            "location": {"index": 1},
        }},
        # 3. Would you race again? (Multiple Choice)
        {"createItem": {
            "item": {
                "title": "Would you race again?",
                "questionItem": {"question": {
                    "required": True,
                    "choiceQuestion": {
                        "type": "RADIO",
                        "options": [{"value": "Yes"}, {"value": "No"}],
                    },
                }},
            },
            "location": {"index": 2},
        }},
        # 4. Overall experience (Linear Scale 1-5)
        {"createItem": {
            "item": {
                "title": "Overall experience",
                "questionItem": {"question": {
                    "required": True,
                    "scaleQuestion": {
                        "low": 1, "high": 5,
                        "lowLabel": "Terrible", "highLabel": "Outstanding",
                    },
                }},
            },
            "location": {"index": 3},
        }},
        # 5. Best thing (Paragraph)
        {"createItem": {
            "item": {
                "title": "Best thing about this race",
                "description": "280 characters max. What made this race worth it?",
                "questionItem": {"question": {"textQuestion": {"paragraph": True}}},
            },
            "location": {"index": 4},
        }},
        # 6. Worst thing (Paragraph)
        {"createItem": {
            "item": {
                "title": "Worst thing about this race",
                "description": "280 characters max. What would you change?",
                "questionItem": {"question": {"textQuestion": {"paragraph": True}}},
            },
            "location": {"index": 5},
        }},
        # 7. Where did you finish? (Dropdown)
        {"createItem": {
            "item": {
                "title": "Where did you finish?",
                "questionItem": {"question": {
                    "choiceQuestion": {
                        "type": "DROP_DOWN",
                        "options": [
                            {"value": "Top 10%"}, {"value": "Top quarter"},
                            {"value": "Mid-pack"}, {"value": "Back half"},
                            {"value": "DNF"},
                        ],
                    },
                }},
            },
            "location": {"index": 6},
        }},
    ]

    service.forms().batchUpdate(formId=form_id, body={'requests': requests}).execute()

    # Fetch the form to get question IDs for pre-fill URLs
    result = service.forms().get(formId=form_id).execute()
    print(f"\nEdit:  https://docs.google.com/forms/d/{form_id}/edit")
    print(f"View:  https://docs.google.com/forms/d/{form_id}/viewform")

    # Find the Race field's question ID for pre-fill
    for item in result.get('items', []):
        title = item.get('title', '')
        qid = item.get('questionItem', {}).get('question', {}).get('questionId', '')
        if title == 'Race' and qid:
            print(f"\nPre-fill URL for race slug:")
            print(f"  https://docs.google.com/forms/d/e/{form_id}/viewform?entry.{qid}=RACE_SLUG_HERE")
            print(f"\nEntry field ID: entry.{qid}")
            break

    print("\nDone! Go to Settings in the form editor to enable:")
    print("  - Limit to 1 response (requires sign-in)")
    print("  - Collect email addresses")


if __name__ == '__main__':
    create_gravel_god_form()
