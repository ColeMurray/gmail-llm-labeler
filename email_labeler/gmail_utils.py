"""
Gmail utility functions shared across the email processing pipeline.
Centralizes common Gmail API operations to reduce code duplication.
"""

import base64
import logging
import os
import os.path
from typing import Dict, List, Optional, Union

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

# Gmail API Scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]

# Default file paths
TOKEN_FILE = "token.json"
CREDENTIALS_FILE = "credentials.json"

logger = logging.getLogger(__name__)


def get_gmail_client(
    token_file: str = TOKEN_FILE,
    credentials_file: str = CREDENTIALS_FILE,
    scopes: Optional[List[str]] = None,
    port: int = 0,
) -> Resource:
    """
    Creates and returns an authenticated Gmail API client.

    Args:
        token_file: Path to the token file for storing credentials
        credentials_file: Path to the OAuth2 credentials file
        scopes: List of Gmail API scopes (defaults to SCOPES)
        port: Port for the local server during OAuth flow (0 for auto)

    Returns:
        Authenticated Gmail API client resource

    Raises:
        FileNotFoundError: If credentials file doesn't exist
        HttpError: If API authentication fails
    """
    if scopes is None:
        scopes = SCOPES

    if not os.path.exists(credentials_file):
        raise FileNotFoundError(f"Credentials file not found: {credentials_file}")

    creds = None

    # Load existing token if available
    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, scopes)
        except Exception as e:
            logger.warning(f"Failed to load credentials from {token_file}: {e}")
            creds = None

    # Refresh or create new credentials if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("Credentials refreshed successfully")
            except Exception as e:
                logger.error(f"Failed to refresh credentials: {e}")
                creds = None

        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, scopes)
            creds = flow.run_local_server(port=port)
            logger.info("New credentials obtained successfully")

        # Save credentials for future use
        with open(token_file, "w") as token:
            token.write(creds.to_json())
            logger.debug(f"Credentials saved to {token_file}")

    return build("gmail", "v1", credentials=creds)


def fetch_emails(
    gmail: Resource,
    query: Optional[str] = None,
    max_results: Optional[int] = None,
    page_token: Optional[str] = None,
    include_spam_trash: bool = False,
) -> List[dict]:
    """
    Fetches emails from Gmail based on the given query.

    Args:
        gmail: Authenticated Gmail API client
        query: Gmail search query (e.g., "is:unread", "from:example@email.com")
        max_results: Maximum number of results to return
        page_token: Token for pagination
        include_spam_trash: Whether to include spam and trash messages

    Returns:
        List of email message dictionaries containing 'id' and 'threadId'

    Raises:
        HttpError: If the API request fails
    """
    try:
        request_params = {"userId": "me", "includeSpamTrash": include_spam_trash}

        if query:
            request_params["q"] = query
        if max_results:
            request_params["maxResults"] = max_results
        if page_token:
            request_params["pageToken"] = page_token

        results = gmail.users().messages().list(**request_params).execute()
        messages = results.get("messages", [])

        # Handle pagination if needed
        if max_results is None and "nextPageToken" in results:
            while "nextPageToken" in results:
                request_params["pageToken"] = results["nextPageToken"]
                results = gmail.users().messages().list(**request_params).execute()
                messages.extend(results.get("messages", []))

        logger.info(f"Fetched {len(messages)} emails with query: {query}")
        return messages  # type: ignore[no-any-return]

    except HttpError as error:
        logger.error(f"Failed to fetch emails: {error}")
        raise


def parse_email_body(message_payload: dict) -> str:
    """
    Extracts and decodes the email body from a message payload.

    Args:
        message_payload: The 'payload' portion of a Gmail message

    Returns:
        Decoded email body as string
    """
    body = ""

    # Check for simple body data
    if "body" in message_payload and "data" in message_payload["body"]:
        body = base64.urlsafe_b64decode(message_payload["body"]["data"]).decode(
            "utf-8", errors="ignore"
        )
        return body

    # Process multipart messages
    parts = message_payload.get("parts", [])
    for part in parts:
        mime_type = part.get("mimeType", "")

        # Prefer text/plain over text/html
        if mime_type == "text/plain" and "data" in part.get("body", {}):
            body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
            break
        elif mime_type == "text/html" and not body and "data" in part.get("body", {}):
            body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
        # Handle nested multipart
        elif "parts" in part:
            for subpart in part["parts"]:
                if "data" in subpart.get("body", {}):
                    body = base64.urlsafe_b64decode(subpart["body"]["data"]).decode(
                        "utf-8", errors="ignore"
                    )
                    if subpart.get("mimeType") == "text/plain":
                        break

    return body


def get_email_content(
    gmail: Resource,
    email_id: str,
    format: str = "full",
    metadata_headers: Optional[List[str]] = None,
) -> Dict[str, Union[str, List[str]]]:
    """
    Retrieves the complete content of an email including headers and body.

    Args:
        gmail: Authenticated Gmail API client
        email_id: The ID of the email to retrieve
        format: Format for the message (minimal, full, raw, metadata)
        metadata_headers: List of headers to include when format is 'metadata'

    Returns:
        Dictionary containing email data with keys:
            - subject: Email subject
            - from: Sender email address
            - to: Recipient email address(es)
            - date: Date sent
            - body: Email body content
            - labels: List of label IDs
            - id: Message ID

    Raises:
        HttpError: If the API request fails
    """
    try:
        request_params = {"userId": "me", "id": email_id, "format": format}

        if metadata_headers and format == "metadata":
            request_params["metadataHeaders"] = metadata_headers  # type: ignore[assignment]

        message = gmail.users().messages().get(**request_params).execute()

        email_data = {
            "id": email_id,
            "labels": message.get("labelIds", []),
            "snippet": message.get("snippet", ""),
        }

        # Extract headers
        headers = message.get("payload", {}).get("headers", [])
        header_dict = {h["name"].lower(): h["value"] for h in headers}

        email_data["subject"] = header_dict.get("subject", "")
        email_data["from"] = header_dict.get("from", "")
        email_data["to"] = header_dict.get("to", "")
        email_data["date"] = header_dict.get("date", "")

        # Extract body
        if format in ["full", "raw"]:
            email_data["body"] = parse_email_body(message.get("payload", {}))

        return email_data

    except HttpError as error:
        logger.error(f"Failed to retrieve email {email_id}: {error}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error when processing email {email_id}: {e}")
        raise


def get_or_create_label(
    gmail: Resource,
    label_name: str,
    label_list_visibility: str = "labelShow",
    message_list_visibility: str = "show",
) -> Optional[str]:
    """
    Gets an existing label ID or creates a new label if it doesn't exist.

    Args:
        gmail: Authenticated Gmail API client
        label_name: Name of the label to get or create
        label_list_visibility: Visibility in label list (labelShow, labelShowIfUnread, labelHide)
        message_list_visibility: Visibility in message list (show, hide)

    Returns:
        Label ID string, or None if operation fails

    Raises:
        HttpError: If the API request fails
    """
    try:
        # First, try to find existing label
        results = gmail.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])

        for label in labels:
            if label["name"] == label_name:
                logger.debug(f"Found existing label: {label_name} (ID: {label['id']})")
                return label["id"]  # type: ignore[no-any-return]

        # Label doesn't exist, create it
        label_object = {
            "name": label_name,
            "labelListVisibility": label_list_visibility,
            "messageListVisibility": message_list_visibility,
        }

        created_label = gmail.users().labels().create(userId="me", body=label_object).execute()

        logger.info(f"Created new label: {label_name} (ID: {created_label['id']})")
        return created_label["id"]  # type: ignore[no-any-return]

    except HttpError as error:
        logger.error(f"Failed to get or create label '{label_name}': {error}")
        return None


def add_labels_to_email(
    gmail: Resource,
    email_id: str,
    label_ids: List[str],
    remove_label_ids: Optional[List[str]] = None,
) -> bool:
    """
    Adds (and optionally removes) labels from an email.

    Args:
        gmail: Authenticated Gmail API client
        email_id: The ID of the email to modify
        label_ids: List of label IDs to add
        remove_label_ids: Optional list of label IDs to remove

    Returns:
        True if successful, False otherwise

    Raises:
        HttpError: If the API request fails
    """
    try:
        body = {}
        if label_ids:
            body["addLabelIds"] = label_ids
        if remove_label_ids:
            body["removeLabelIds"] = remove_label_ids

        if not body:
            logger.warning("No labels to add or remove")
            return True

        gmail.users().messages().modify(userId="me", id=email_id, body=body).execute()

        logger.debug(f"Modified labels for email {email_id}")
        return True

    except HttpError as error:
        logger.error(f"Failed to modify labels for email {email_id}: {error}")
        return False


def remove_from_inbox(gmail: Resource, email_id: str) -> bool:
    """
    Removes an email from the inbox (archives it).

    Args:
        gmail: Authenticated Gmail API client
        email_id: The ID of the email to archive

    Returns:
        True if successful, False otherwise
    """
    return add_labels_to_email(gmail, email_id, [], ["INBOX"])


def mark_as_read(gmail: Resource, email_id: str) -> bool:
    """
    Marks an email as read.

    Args:
        gmail: Authenticated Gmail API client
        email_id: The ID of the email to mark as read

    Returns:
        True if successful, False otherwise
    """
    return add_labels_to_email(gmail, email_id, [], ["UNREAD"])


def mark_as_unread(gmail: Resource, email_id: str) -> bool:
    """
    Marks an email as unread.

    Args:
        gmail: Authenticated Gmail API client
        email_id: The ID of the email to mark as unread

    Returns:
        True if successful, False otherwise
    """
    return add_labels_to_email(gmail, email_id, ["UNREAD"], [])


def batch_modify_messages(
    gmail: Resource,
    message_ids: List[str],
    add_label_ids: Optional[List[str]] = None,
    remove_label_ids: Optional[List[str]] = None,
) -> bool:
    """
    Batch modifies multiple messages at once (more efficient for bulk operations).

    Args:
        gmail: Authenticated Gmail API client
        message_ids: List of message IDs to modify
        add_label_ids: Label IDs to add to all messages
        remove_label_ids: Label IDs to remove from all messages

    Returns:
        True if successful, False otherwise
    """
    try:
        body = {"ids": message_ids}
        if add_label_ids:
            body["addLabelIds"] = add_label_ids
        if remove_label_ids:
            body["removeLabelIds"] = remove_label_ids

        gmail.users().messages().batchModify(userId="me", body=body).execute()

        logger.info(f"Batch modified {len(message_ids)} messages")
        return True

    except HttpError as error:
        logger.error(f"Failed to batch modify messages: {error}")
        return False
