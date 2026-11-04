import os.path
import csv
import glob
import hashlib
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/calendar']


def batch_callback(request_id, response, exception):
    if exception is not None:
        # Catch the 409 Conflict error which indicates the event ID already exists
        if isinstance(exception, HttpError) and exception.resp.status == 409:
            print(f"Event skipped (already exists): Request ID {request_id}")
        else:
            print(f"Error creating event: {exception}")
    else:
        print(f"Event created: {response.get('summary')} | Link: {response.get('htmlLink')}")


def main():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('calendar', 'v3', credentials=creds)
        events_to_create = []

        # Find up to 15 CSV files in the directory
        csv_files = glob.glob('*.csv')[:15]

        if not csv_files:
            print("No CSV files found in the directory.")
            return

        print(f"Loading {len(csv_files)} CSV files...")

        # Loop through the selected CSV files
        for file_path in csv_files:
            with open(file_path, mode='r', encoding='utf-8-sig') as file:
                csv_reader = csv.DictReader(file)

                for row in csv_reader:
                    # Generate a deterministic ID based on summary and start time
                    unique_string = f"{row['summary']}_{row['start_datetime']}".encode('utf-8')
                    event_id = hashlib.sha256(unique_string).hexdigest()

                    event = {
                        'id': event_id,
                        'summary': row['summary'],
                        'location': row['location'],
                        'description': row['description'],
                        'start': {
                            'dateTime': row['start_datetime'],
                            'timeZone': row['timezone'],
                        },
                        'end': {
                            'dateTime': row['end_datetime'],
                            'timeZone': row['timezone'],
                        },
                    }
                    events_to_create.append(event)

        print(f"Uploading {len(events_to_create)} total events in batches of 10...")

        batch = service.new_batch_http_request(callback=batch_callback)

        for i, event in enumerate(events_to_create):
            batch.add(service.events().insert(calendarId='primary', body=event))

            if (i + 1) % 20 == 0:
                batch.execute()
                batch = service.new_batch_http_request(callback=batch_callback)

        # Fixed logic from modulo 20 to modulo 10 to match the batch size
        if len(events_to_create) % 10 != 0:
            batch.execute()

        print("All events processed.")

    except Exception as error:
        print(f"An error occurred: {error}")


if __name__ == '__main__':
    main()