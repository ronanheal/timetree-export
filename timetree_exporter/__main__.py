import os
import argparse
import logging
from getpass import getpass
from icalendar import Calendar
from timetree_exporter import TimeTreeEvent, ICalEventFormatter, __version__
from timetree_exporter.api.auth import login
from timetree_exporter.api.calendar import TimeTreeCalendar

# Setup loggers
logger = logging.getLogger(__name__)
package_logger = logging.getLogger(__package__)

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

if __name__ == "__main__":
    main()
