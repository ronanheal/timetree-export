import os
import argparse
import logging
import dropbox
import requests
from icalendar import Calendar
from timetree_exporter import TimeTreeEvent, ICalEventFormatter, __version__
from timetree_exporter.api.auth import login
from timetree_exporter.api.calendar import TimeTreeCalendar

# Setup loggers
logger = logging.getLogger(__name__)
package_logger = logging.getLogger(__package__)

def get_access_token():
    """Get Dropbox access token using refresh token"""
    dbx_refresh_token = os.getenv('DROPBOX_REFRESH_TOKEN')
    dbx_client_id = os.getenv('DROPBOX_CLIENT_ID')
    dbx_client_secret = os.getenv('DROPBOX_CLIENT_SECRET')
    
    if not dbx_refresh_token:
        raise ValueError("Dropbox refresh token is missing")

    url = "https://api.dropbox.com/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": dbx_refresh_token,
        "client_id": dbx_client_id,
        "client_secret": dbx_client_secret,
    }

    response = requests.post(url, data=data)
    
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        raise ValueError(f"Failed to retrieve access token: {response.json()}")

def get_events(email: str, password: str):
    """Get events from the Timetree API."""
    session_id = login(email, password)
    calendar = TimeTreeCalendar(session_id)
    metadatas = calendar.get_metadata()

    # Filter out deactivated calendars
    metadatas = [
        metadata for metadata in metadatas if metadata["deactivated_at"] is None
    ]

    if len(metadatas) == 0:
        logger.error("No active calendars found")
        raise ValueError("No active calendars found.")

    # Select the first calendar (defaulting to 1)
    calendar_num = 1
    idx = calendar_num - 1  # Adjust for zero-based index

    # Get events from the selected calendar
    calendar_id = metadatas[idx]["id"]
    calendar_name = metadatas[idx]["name"]

    return calendar.get_events(calendar_id, calendar_name)

def upload_to_dropbox(file_path: str, dropbox_path: str):
    """Upload the generated iCal file to Dropbox."""
    access_token = get_access_token()

    # Connect to Dropbox
    dbx = dropbox.Dropbox(access_token)

    # Open the file to upload
    with open(file_path, "rb") as f:
        # Upload file
        try:
            dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode.overwrite)
            logger.info(f"File uploaded successfully to Dropbox: {dropbox_path}")
        except dropbox.exceptions.ApiError as e:
            logger.error(f"Failed to upload to Dropbox: {e}")
            raise

def main():
    """Main function for the Timetree Exporter."""
    # Get email and password from environment variables (or fallback to args)
    email = os.getenv('TIMETREE_EMAIL')
    password = os.getenv('TIMETREE_PASSWORD')

    if not email or not password:
        raise ValueError("Email and password must be provided through environment variables.")

    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Convert Timetree events to iCal format",
        prog="timetree_exporter",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Path to the output iCal file",
        default=os.path.join(os.getcwd(), "timetree.ics"),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Increase output verbosity",
        action="store_true",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        package_logger.setLevel(logging.DEBUG)

    # Initialize iCalendar object
    cal = Calendar()
    events = get_events(email, password)

    logger.info("Found %d events", len(events))

    # Add events to calendar
    for event in events:
        time_tree_event = TimeTreeEvent.from_dict(event)
        formatter = ICalEventFormatter(time_tree_event)
        ical_event = formatter.to_ical()
        if ical_event is None:
            continue
        cal.add_component(ical_event)

    logger.info(
        "A total of %d/%d events are added to the calendar",
        len(cal.subcomponents),
        len(events),
    )

    # Write calendar to file
    with open(args.output, "wb") as f:
        f.write(cal.to_ical())
        logger.info(
            "The .ics calendar file is saved to %s", os.path.abspath(args.output)
        )

    # Upload the file to Dropbox
    dropbox_path = '/TimeTree/calendar.ics'  # Dropbox path where the file will be uploaded
    upload_to_dropbox(args.output, dropbox_path)

if __name__ == "__main__":
    main()
