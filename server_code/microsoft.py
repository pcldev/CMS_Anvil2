import anvil.files
from anvil.files import data_files
import anvil.secrets
import anvil.server
import msal
import requests
from typing import Any, Optional
from docx import Document
from docx.oxml.ns import qn
import io
import mongo

def _get_graph_access_token():
  """Acquire an app-only Microsoft Graph access token via the SharePoint app registration."""
  tenant_id = anvil.secrets.get_secret('SP_TENANT_ID')
  client_id = anvil.secrets.get_secret('SP_CLIENT_ID')
  client_secret = anvil.secrets.get_secret('SP_CLIENT_SECRET')

  authority = f"https://login.microsoftonline.com/{tenant_id}"
  app = msal.ConfidentialClientApplication(client_id, client_credential=client_secret, authority=authority)
  token_response = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

  if "access_token" not in token_response:
    raise RuntimeError("Failed to acquire access token")
  return token_response['access_token']

@anvil.server.callable(require_user=True)
def create_document(origin_template_name, new_document_name):
  """Find origin_template_name on the SharePoint site and duplicate it as new_document_name."""

  mongo.require_any_role()
  SHAREPOINT_SITE_PATH = "https://graph.microsoft.com/v1.0/sites/praetorianconnections.sharepoint.com:/sites/CMS/"

  ACCESS_TOKEN = _get_graph_access_token()
  headers = {'Authorization': f"Bearer {ACCESS_TOKEN}"}

  # Get Site ID
  site_resp = requests.get(SHAREPOINT_SITE_PATH, headers=headers)
  _raise_for_status(site_resp)
  site_id = site_resp.json().get('id')

  # Drive ID
  files_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
  drives_resp = requests.get(files_url, headers=headers)
  _raise_for_status(drives_resp)
  items = drives_resp.json().get('value', [])

  for item in items:
    drive_url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{item["id"]}/root/children'
    documents_resp = requests.get(drive_url, headers=headers)
    _raise_for_status(documents_resp)
    documents = documents_resp.json().get('value', [])

    for document in documents:
      if document['name'] == origin_template_name:
        result = duplicate_document_with_properties(
          site_id=site_id,
          headers=headers,
          source_item_id=document['id'],   # replace with real item id
          new_name=str(new_document_name) + ".docx",
          custom_properties={
            "IM_Requested": "FALSE",
            "RCM_Requested": "FALSE",
            "IM_Completed": "FALSE",
            "RCM_Complete": "FALSE",
            "Proofed": "FALSE",
            "QC": "FALSE"
          },
          access_token=ACCESS_TOKEN,
          destination_folder_path="/",
          drive_id=item["id"]
        )

        # webUrl is the Office-Online/browser link; the desktop ms-word:ofe|u|
        # scheme needs webDavUrl instead, or Word rejects it with "doesn't
        # recognize the command" even though the browser link opens fine.
        return {
          "web_url": result.get("webUrl"),
          "desktop_url": result.get("webDavUrl"),
        }

  raise RuntimeError(f"Template document '{origin_template_name}' not found")


def duplicate_document_with_properties(
  site_id: str,
  headers: dict,
  source_item_id: str,
  new_name: str,
  custom_properties: dict[str, Any],
  access_token: str,
  drive_id: str,
  destination_folder_path: str = "/",
  ) -> dict[str, Any]:
  """Copy source_item_id, then stash custom_properties in the copy's description field."""

  # Step 1 - copy the document
  new_item = duplicate_document(
    site_id=site_id,
    headers=headers,
    source_item_id=source_item_id,
    new_name=new_name,
    access_token=access_token,
    destination_folder_path=destination_folder_path,
    drive_id=drive_id,
  )

  # The copy operation returns slightly different shapes depending on whether
  # it resolved synchronously or via polling; normalise to get the item id.
  new_item_id = (
    new_item.get("id")                          # sync / resourceLocation
    or new_item.get("resourceId")               # async completed payload
  )
  if not new_item_id:
    raise RuntimeError(
      f"Could not determine the new item ID from copy response: {new_item}"
    )

  # Step 2 - store metadata in the description field
  if custom_properties:
    return set_description_metadata(
      item_id=new_item_id,
      headers=headers,
      metadata=custom_properties,
      access_token=access_token,
      drive_id=drive_id,
    )

  return new_item

def duplicate_document(
  site_id: str,
  headers: dict,
  source_item_id: str,
  new_name: str,
  access_token: str,
  drive_id: str,
  destination_folder_path: str = "/",
) -> dict[str, Any]:
  """Copy a document to destination_folder_path and return the new item's metadata (including its id).

  Graph's /copy endpoint is async, so this polls the Location header it
  returns until the operation completes (or raises on failure).
  """

  # Build the parentReference for the destination folder
  parent_ref: dict[str, str] = {"driveId": drive_id}
  if destination_folder_path and destination_folder_path != "/":
    # Resolve the folder path to an item id
    encoded_path = destination_folder_path.strip("/")
    folder_url = (
      f"https://graph.microsoft.com/v1.0/drives/{drive_id}"
      f"/root:/{encoded_path}"
    )
    folder_resp = requests.get(folder_url, headers=headers)
    _raise_for_status(folder_resp)
    parent_ref["id"] = folder_resp.json()["id"]
  else:
    # Use root
    root_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root"
    root_resp = requests.get(root_url, headers=headers)
    _raise_for_status(root_resp)
    parent_ref["id"] = root_resp.json()["id"]

  # Issue the copy request
  copy_url = (
    f"https://graph.microsoft.com/v1.0/drives/{drive_id}"
    f"/items/{source_item_id}/copy"
  )
  payload = {
    "name": new_name,
    "parentReference": parent_ref,
  }
  copy_resp = requests.post(copy_url, json=payload, headers=headers)

  if copy_resp.status_code == 409 and _graph_error_code(copy_resp) == "nameAlreadyExists":
    raise RuntimeError(
      f"A document named '{new_name}' already exists in that location. "
      "Please choose a different name."
    )

  # Graph returns 202 Accepted with a monitor URL in Location
  if copy_resp.status_code not in (202, 200, 201):
    _raise_for_status(copy_resp)

  # Poll the async operation until it finishes
  monitor_url = copy_resp.headers.get("Location")
  if not monitor_url:
    # Some tenants resolve synchronously (200/201)
    return copy_resp.json()

  return _poll_async_operation(monitor_url, headers=headers, drive_id=drive_id, access_token=access_token)

def _raise_for_status(response: requests.Response) -> None:
  """Raise a descriptive RuntimeError on non-2xx responses."""
  if not response.ok:
    raise RuntimeError(
      f"Graph API error {response.status_code} – "
      f"{response.url}\n{response.text}"
    )

def _graph_error_code(response: requests.Response) -> Optional[str]:
  """Extract the Graph API error code (e.g. 'nameAlreadyExists') from a response, if present."""
  try:
    return response.json().get("error", {}).get("code")
  except ValueError:
    return None

def _is_resource_locked(response: requests.Response) -> bool:
  return response.status_code == 423 and _graph_error_code(response) == "resourceLocked"

def _request_with_lock_retry(
  request_fn,
  item_name: str,
  max_attempts: int = 5,
  base_delay_seconds: float = 3.0,
) -> requests.Response:
  """
  Call ``request_fn`` (a zero-arg callable issuing one Graph request), retrying
  with backoff while the target item is locked (HTTP 423 resourceLocked). This
  usually means someone has the document open in Word/SharePoint and the lock
  clears within seconds, so a short retry avoids surfacing a transient failure
  to the user. Raises a friendly, actionable RuntimeError naming the document
  if it's still locked after all attempts.
  """
  import time

  for attempt in range(max_attempts):
    response = request_fn()
    if not _is_resource_locked(response):
      return response
    if attempt < max_attempts - 1:
      time.sleep(base_delay_seconds * (attempt + 1))

  raise RuntimeError(
    f"'{item_name}' is currently locked in SharePoint (it may be open in Word "
    "for someone else). Please close it and try Disseminate again shortly."
  )

def _poll_async_operation(
  monitor_url: str,
  headers: dict,
  drive_id: str,
  access_token: str,
  max_attempts: int = 30,
  interval_seconds: float = 2.0,
) -> dict[str, Any]:
  """Poll a Graph async-operation monitor URL until completion."""
  import time

  for attempt in range(max_attempts):
    poll_resp = requests.get(monitor_url)
    _raise_for_status(poll_resp)
    data = poll_resp.json()

    status = data.get("status", "").lower()
    if status == "completed":
      # The resourceId field contains the new item's id; fetch full metadata
      resource_location = data.get("resourceLocation")
      if resource_location:
        meta_resp = requests.get(resource_location, headers=headers)
        if meta_resp.ok:
          return meta_resp.json()
      
      resource_id = data.get("resourceId")
      if resource_id and drive_id:
        item_url = (
          f"https://graph.microsoft.com/v1.0/drives/{drive_id}"
          f"/items/{resource_id}?$select=id,name,webUrl,webDavUrl,description"
        )
        item_resp = requests.get(item_url, headers=headers)
        if item_resp.ok:
          return item_resp.json()
      
      return data

    if status in ("failed", "deletedwithoutpermission"):
      raise RuntimeError(f"Copy operation failed: {data}")

    time.sleep(interval_seconds)

  raise TimeoutError(
    f"Copy operation did not complete after {max_attempts} polls."
  )

def set_description_metadata(
  item_id: str,
  headers: dict,
  metadata: dict[str, Any],
  access_token: str,
  drive_id: str,
) -> dict[str, Any]:
  """Serialise metadata as JSON and store it in the drive item's description field (~1024 char limit)."""
  import json

  payload = json.dumps(metadata, separators=(",", ":"))
  if len(payload) > 1024:
    raise ValueError(
      f"Serialised metadata is {len(payload)} chars, which exceeds the "
      "1024-character limit of the description field. Reduce the payload."
    )

  url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}?$select=id,name,webUrl,webDavUrl,description"
  resp = requests.patch(url, json={"description": payload}, headers=headers)
  _raise_for_status(resp)

  item = resp.json()
  item["web_url"] = item.get("webUrl")  # convenience alias
  item["web_dav_url"] = item.get("webDavUrl")  # convenience alias
  return item


@anvil.server.callable(require_user=True)
def append_document_contents(source_document_name, target_document_name):
  """Append source_document_name to the bottom of target_document_name. Both are looked up by name across every drive on the site."""

  mongo.require_any_role()
  mongo_client = mongo.mongo_connect()
  db = mongo_client["prod"]

  mongo.log_action(db, "document_append_started",
    source_document_name=source_document_name, target_document_name=target_document_name)

  try:
    SHAREPOINT_SITE_PATH = "https://graph.microsoft.com/v1.0/sites/praetorianconnections.sharepoint.com:/sites/CMS/"

    ACCESS_TOKEN = _get_graph_access_token()
    headers = {'Authorization': f"Bearer {ACCESS_TOKEN}"}

    site_resp = requests.get(SHAREPOINT_SITE_PATH, headers=headers)
    _raise_for_status(site_resp)
    site_id = site_resp.json().get('id')

    drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
    drives_resp = requests.get(drives_url, headers=headers)
    _raise_for_status(drives_resp)
    drives = drives_resp.json().get('value', [])

    # Documents are created with a ".docx" suffix (see create_document), but
    # callers pass around the bare name stored in Mongo, so match on the
    # filename that will actually exist in SharePoint.
    source_file_name = source_document_name if source_document_name.lower().endswith('.docx') else f"{source_document_name}.docx"
    target_file_name = target_document_name if target_document_name.lower().endswith('.docx') else f"{target_document_name}.docx"

    source_item = None
    target_item = None
    source_drive_id = None
    target_drive_id = None

    # Search all drives for both documents
    for drive in drives:
      drive_id = drive['id']
      drive_url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root/children'
      documents_resp = requests.get(drive_url, headers=headers)
      _raise_for_status(documents_resp)
      documents = documents_resp.json().get('value', [])

      for document in documents:
        if document['name'] == source_file_name:
          source_item = document
          source_drive_id = drive_id
        if document['name'] == target_file_name:
          target_item = document
          target_drive_id = drive_id

    if not source_item:
      raise RuntimeError(f"Source document '{source_document_name}' not found")
    if not target_item:
      raise RuntimeError(f"Target document '{target_document_name}' not found")

    # Download both documents
    source_bytes = _download_drive_item(source_item['id'], source_drive_id, headers, source_file_name)
    target_bytes = _download_drive_item(target_item['id'], target_drive_id, headers, target_file_name)

    # Pull the plain text out of the source so the log records what was
    # actually appended, not just that an append happened.
    source_text = "\n".join(p.text for p in Document(io.BytesIO(source_bytes)).paragraphs)
    mongo.log_action(db, "document_append_text_extracted",
      source_document_name=source_document_name, target_document_name=target_document_name,
      appended_text_length=len(source_text), appended_text_preview=source_text[:2000])

    # Merge using python-docx
    merged_bytes = _append_docx(target_bytes, source_bytes)

    # Upload the merged document back, overwriting the target
    upload_url = (
      f"https://graph.microsoft.com/v1.0/drives/{target_drive_id}"
      f"/items/{target_item['id']}/content"
    )
    upload_resp = _request_with_lock_retry(
      lambda: requests.put(upload_url, data=merged_bytes, headers={
        **headers,
        'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      }),
      target_file_name,
    )
    _raise_for_status(upload_resp)

    web_url = upload_resp.json().get('webUrl')

    mongo.log_action(db, "document_append_completed",
      source_document_name=source_document_name, target_document_name=target_document_name,
      web_url=web_url)

    return web_url

  except Exception as e:
    mongo.log_action(db, "document_append_failed",
      source_document_name=source_document_name, target_document_name=target_document_name,
      error=str(e))
    raise


def _download_drive_item(item_id: str, drive_id: str, headers: dict, item_name: str) -> bytes:
  """Download the binary content of a drive item, retrying if it's locked."""
  url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/content"
  resp = _request_with_lock_retry(
    lambda: requests.get(url, headers=headers, allow_redirects=True),
    item_name,
  )
  _raise_for_status(resp)
  return resp.content


def _append_docx(target_bytes: bytes, source_bytes: bytes) -> bytes:
  """Append the contents of source into target and return the merged bytes."""
  target_doc = Document(io.BytesIO(target_bytes))
  source_doc = Document(io.BytesIO(source_bytes))

  # A body's final child must be a single sectPr (section properties), so
  # target_doc.element.body already ends with one. Appended source elements
  # must land *before* it, not after - .append() always adds at the very end,
  # which would strand target's sectPr mid-document (invalid docx; Word then
  # silently drops/repairs whatever follows it).
  target_sectPr = target_doc.element.body.find(qn('w:sectPr'))

  # list(...) snapshots the children up front - moving each element into
  # target_doc.element.body below reparents it out of source_doc.element.body,
  # which would otherwise mutate the sequence being iterated over and silently
  # skip every other element.
  for element in list(source_doc.element.body):
    # Copying the source's own trailing sectPr would leave two in the body,
    # with target's now stranded mid-document, producing an invalid docx.
    if element.tag == qn('w:sectPr'):
      continue
    if target_sectPr is not None:
      target_sectPr.addprevious(element)
    else:
      target_doc.element.body.append(element)

  output = io.BytesIO()
  target_doc.save(output)
  return output.getvalue()