import anvil.files
from anvil.files import data_files
import anvil.users
import anvil.secrets
import anvil.server
import hmac
import json
from urllib.parse import urlsplit, unquote
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.operations import SearchIndexModel
from datetime import datetime
from pymongo import ReturnDocument
from bson import ObjectId
from bson.errors import InvalidId

STORY_SEARCH_INDEX_NAME = "story_search"
STORY_SEARCH_FIELDS = ["name", "title", "team", "assignee", "country"]

# Connect to the MongoDB Database
_mongo_client = None

def mongo_connect():
  # Standard Function to connect to MongoDB. Reuses a single MongoClient
  # (and its internal connection pool) across calls within a running server
  # instance, instead of paying a fresh TLS/SRV-lookup/ping handshake on
  # every single server-callable invocation.
  global _mongo_client
  if _mongo_client is None:
    MONGO_DB = anvil.secrets.get_secret('MONGO_DB')
    uri = f"mongodb+srv://anvil:{MONGO_DB}@cms-production.n9s7km.mongodb.net/?appName=CMS-Production"
    client = MongoClient(uri, server_api=ServerApi('1'))

    # Send a ping to confirm a successful connection before caching it.
    try:
      client.admin.command('ping')
    except Exception as e:
      raise Exception(f"Database connection failed: {e}")
    _mongo_client = client

  return _mongo_client

def log_action(db, action, **details):
  # Record an audit entry for an action taken on a report. `db` is an
  # already-connected "prod" database, reused from the caller to avoid a
  # second Mongo connection per request.
  collection = db["universal_logs"]

  current_user = anvil.users.get_user()
  user_email = current_user['email'] if current_user else None

  log_entry = {
    "action": action,
    "user": user_email,
    "timestamp": datetime.now(),
    **details
  }

  collection.insert_one(log_entry)

# Report-document collections reachable through the generic get_document /
# modify_document / process_report endpoints. Keeping this as an allow-list
# stops a client from pointing those generic functions at collections like
# "users" or "universal_logs" that were never meant to be reachable that way.
_REPORT_COLLECTIONS = {"os_report_daily", "os_report_weekly", "os_report_other", "spot_report", "story"}

def _current_mongo_user():
  # Resolve the signed-in Anvil user's CMS role document from Mongo.
  anvil_user = anvil.users.get_user()
  if anvil_user is None:
    raise Exception("You must be signed in to perform this action.")
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  return db["users"].find_one({"email": anvil_user['email']})

def _require_role(role):
  user = _current_mongo_user()
  if not user or not user.get('roles', {}).get(role):
    raise Exception(f"You do not have permission to perform this action (requires the '{role}' role).")

_APP_ROLES = ("admin", "im", "qc", "optio")

def require_any_role():
  # Minimum authorization bar for the report-mutation endpoints below:
  # blocks a signed-in user who holds none of the app's roles (e.g. a
  # freshly-created account), without enforcing which specific role a
  # given status transition should require - that's deliberately out of
  # scope here, since it needs the actual transition rules confirmed first.
  user = _current_mongo_user()
  if not user or not any(user.get('roles', {}).get(role) for role in _APP_ROLES):
    raise Exception("You do not have permission to perform this action.")

def _object_id(id):
  # id is client-supplied; surface a clear error instead of an opaque
  # bson.errors.InvalidId crash when it's malformed, or a TypeError when
  # it's not a string/ObjectId at all (e.g. a list or dict).
  try:
    return ObjectId(id)
  except (InvalidId, TypeError):
    raise Exception(f"Invalid document id: {id!r}")

@anvil.server.callable(require_user=False)
def log_login_failure(error):
  # Called from frm_login when anvil.users.login_with_saml() raises, so a bad
  # IdP cert/misconfiguration ends up in the audit log instead of the sign-in
  # screen just silently resetting with no trace. No require_user, since
  # sign-in hasn't necessarily succeeded at this point.
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  log_action(db, "login_failed", error=str(error))

@anvil.server.callable(require_user=True)
def get_audit_logs(before_id=None, limit=20):
  _require_role('admin')
  # Keyset-paginated audit log feed, newest first. `before_id` is the "_id"
  # of the last entry on the previously fetched page - filtering on it keeps
  # each page an indexed range query instead of a skip()/offset scan.
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["universal_logs"]

  query = {"_id": {"$lt": _object_id(before_id)}} if before_id else {}

  entries = list(collection.find(query).sort("_id", -1).limit(limit))

  for entry in entries:
    entry['_id'] = str(entry['_id'])

  return entries

@anvil.server.callable(require_user=True)
def get_user():
  # Get the signed-in user's own details. Deliberately ignores any
  # caller-supplied email so this can't be used to look up (or, via a crafted
  # non-string argument, query-inject for) another user's record.
  anvil_user = anvil.users.get_user()

  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["users"]

  current_user = collection.find_one({'email': anvil_user['email']})



  # Make _id into a string
  if current_user is not None:
    current_user['_id'] = str(current_user['_id'])

  return current_user

@anvil.server.callable(require_user=True)
def get_all_users():
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["users"]

  all_users = collection.find({})

  user_emails = []
  for user in all_users:
    user_emails.append((user['display_name'], user['email']))

  return user_emails

@anvil.server.callable(require_user=True)
def get_users_with_role(role):
  # Users holding a given role, as (display_name, email) pairs for use in
  # reviewer-selection dropdowns. Unlike get_role_users, this is not
  # admin-only: any signed-in user picking a reviewer needs it.
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["users"]

  matched_users = collection.find({f"roles.{role}": True})

  return [(user['display_name'], user['email']) for user in matched_users]

@anvil.server.callable(require_user=True)
def get_all_tags():
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["tags"]

  all_tags = collection.find({})

  tags = []
  for tag in all_tags:
    tags.append((tag['tag_name']))

  return tags

@anvil.server.callable(require_user=True)
def get_login_bootstrap_data():
  # Bundles the handful of lookups every freshly-logged-in client needs into
  # a single round trip, instead of the client making 5 separate calls.
  return {
    'teams': get_teams(),
    'all_users': get_all_users(),
    'im_reviewers': get_users_with_role('im'),
    'qc_reviewers': get_users_with_role('qc'),
    'all_tags': get_all_tags(),
  }

@anvil.server.callable(require_user=True)
def create_user(display_name):
  # Deliberately ignores any caller-supplied email so this can't be used to
  # pre-provision a role set for another user's address (see get_user).
  email = anvil.users.get_user()['email']
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["users"]
  new_user = {
    "email": str(email),
    "display_name": str(display_name),
    "notify_priority": True,
    "notify_routine": True,
    "default_team": None,
    "roles": {
      "admin": False,
      "im": False,
      "qc": False,
      "optio": False
    }
  }

  created_user = collection.find_one_and_update(
    {"email": str(email)},               # Unique filter to avoid duplicates
    {"$setOnInsert": new_user},      # Only set data if document is new
    upsert=True,
    return_document=ReturnDocument.AFTER
  )

  return created_user['roles']

@anvil.server.callable(require_user=True)
def get_role_users(role):
  # Admin-only. Returns (users_with_role, users_without_role) email lists,
  # feeding the add/remove dropdown pair for this role in frm_admin.
  _require_role('admin')
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["users"]

  matched_users = collection.find({})

  users_with_role = []
  users_without_role = []

  for user in matched_users:
    if user.get('roles', {}).get(role) is True:
      users_with_role.append(user['email'])
    else:
      users_without_role.append(user['email'])

  return users_with_role, users_without_role

@anvil.server.callable(require_user=True)
def modify_user_role(user_email, role, status):
  # Upserts by email: other_role_defaults only takes effect via $setOnInsert
  # if this is the first time this user's email is touched (e.g. an admin
  # grants a role before the user has ever logged in to create their own doc).
  _require_role('admin')
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["users"]

  if role == "admin" and not status:
    current_user = collection.find_one({"email": str(user_email)})
    is_currently_admin = bool(current_user and current_user.get('roles', {}).get('admin'))
    if is_currently_admin and collection.count_documents({"roles.admin": True}) <= 1:
      raise Exception("Cannot remove the last remaining admin.")

  dict_to_update = "roles." + role
  default_roles = {"admin": False, "im": False, "qc": False, "optio": False}
  other_role_defaults = {
    "roles." + other_role: default_status
    for other_role, default_status in default_roles.items()
    if other_role != role
  }

  updated_user = collection.find_one_and_update(
    {"email": str(user_email)},
    {
      "$set": {dict_to_update: status},
      "$setOnInsert": other_role_defaults,
    },
    upsert=True,
    return_document=ReturnDocument.AFTER
  )


  return "Success"

@anvil.server.callable(require_user=True)
def get_user_preferences():
  # Deliberately ignores any caller-supplied email so this can't be used to
  # read another user's preferences (see get_user).
  email = anvil.users.get_user()['email']
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["users"]

  user = collection.find_one({'email': str(email)})

  if user is None:
    return None

  return {
    'notify_routine': user.get('notify_routine', True),
    'notify_priority': user.get('notify_priority', True),
    'default_team': user.get('default_team')
  }

def is_known_user(email):
  # Used by email.py's send_email to stop the CMS from being used as an
  # open relay to arbitrary external addresses - only accounts that exist
  # in our own users collection are valid recipients.
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  return db["users"].find_one({"email": str(email)}) is not None

def wants_notification(user_email, hl_pipeline):
  # Whether a user has opted in to this class of email notification.
  # hl_pipeline reports are gated on notify_priority, everything else on
  # notify_routine. Defaults to True if the user can't be found (e.g. they've
  # never logged in yet) or the preference predates this field, so an unknown
  # preference never silently swallows a notification.
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["users"]

  user = collection.find_one({'email': str(user_email)})
  if user is None:
    return True

  key = 'notify_priority' if hl_pipeline else 'notify_routine'
  return user.get(key, True)

@anvil.server.callable(require_user=True)
def modify_user_preferences(routine, priority, default_team):
  # Deliberately ignores any caller-supplied email so this can't be used to
  # modify another user's preferences (see get_user).
  email = anvil.users.get_user()['email']
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["users"]

  updated_user = collection.find_one_and_update(
    {"email": str(email)},
    {"$set": {'notify_routine' : routine, 'notify_priority' : priority, 'default_team': default_team}},
    return_document=ReturnDocument.AFTER
  )


  return "Success"

@anvil.server.callable(require_user=True)
def add_tag(tag):
  _require_role('admin')
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["tags"]

  new_tag = {
    "tag_name": str(tag),
    "created": datetime.now()
  }

  created_tag = collection.find_one_and_update(
    {"tag_name": str(tag)},               # Unique filter to avoid duplicates
    {"$setOnInsert": new_tag},      # Only set data if document is new
    upsert=True,
    return_document=ReturnDocument.AFTER
  )

  return created_tag['tag_name']

@anvil.server.callable(require_user=True)
def remove_tag(tag):
  _require_role('admin')
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["tags"]

  removed_tag = collection.find_one_and_delete(
    {"tag_name": str(tag)},
  )

  return "Success"

@anvil.server.callable(require_user=True)
def add_team(team):
  _require_role('admin')
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["teams"]

  new_team = {
    "team_name": str(team),
  }

  created_team = collection.find_one_and_update(
    {"team_name": str(team)},               # Unique filter to avoid duplicates
    {"$setOnInsert": new_team},      # Only set data if document is new
    upsert=True,
    return_document=ReturnDocument.AFTER
  )

  return created_team['team_name']

@anvil.server.callable(require_user=True)
def remove_team(team):
  _require_role('admin')
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["teams"]


  removed_team = collection.find_one_and_delete(
    {"team_name": str(team)},               # Unique filter to avoid duplicates
  )



  return "Success"

@anvil.server.callable(require_user=True)
def get_teams():
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["teams"]

  current_teams = collection.find({})

  teams = []
  for record in current_teams:
    teams.append(record['team_name'])

  return teams

@anvil.server.callable(require_user=True)
def get_all_templates():
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["templates"]

  all_templates = collection.find({})


  templates = []
  for record in all_templates:
    templates.append({'type': record['type'], 'name' : record['name']})

  return templates

@anvil.server.callable(require_user=True)
def save_template_location(template_type, template_name):
  _require_role('admin')
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["templates"]

  updated_template = collection.find_one_and_update(
    {"type": str(template_type)},
    {"$set": {'name' : template_name}},
    upsert=True,
    return_document=ReturnDocument.AFTER
  )


  return "Success"

@anvil.server.callable(require_user=True)
def get_template_location(template_type):
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["templates"]

  template = collection.find_one({"type": template_type})



  return template['name']

def _create_new_report(collection_name, report_type, team, name, title, document_link,
                        document_link_desktop, assignee, im, qc, country, extra_fields=None):
  # Shared body for create_new_story/create_new_os_report_daily/_weekly/_other/
  # create_new_spot_report: same base document shape, differing only by
  # collection, the "type" label, and a couple of type-specific fields (e.g.
  # story's "outputs" vs OS reports' "inputs"; spot reports have neither).
  client = mongo_connect()
  db = client["prod"]
  collection = db[collection_name]

  new_document = {
    "name": name,
    "title": title,
    "document_link": document_link,
    "document_link_desktop": document_link_desktop,
    "team": team,
    "type": report_type,
    "assignee": assignee,
    "im": im,
    "qc": qc,
    "country": country,
    "status": "In Progress",
    "rcm_check": False,
    "im_check": False,
    "finalised": False,
    "created": datetime.now(),
    **(extra_fields or {}),
  }

  result = collection.insert_one(new_document)

  log_action(db, "template_created", collection=collection_name, report_id=str(result.inserted_id),
             report_type=report_type, report_name=name, title=title, team=team)

@anvil.server.callable(require_user=True)
def create_new_story(team, name, title, document_link, document_link_desktop, assignee, im, qc, country):
  # Stories later get aggregated into a weekly/daily/other report via "outputs".
  require_any_role()
  _create_new_report("story", "Story", team, name, title, document_link, document_link_desktop,
                      assignee, im, qc, country, extra_fields={"metadata": [], "outputs": {}})

@anvil.server.callable(require_user=True)
def create_new_os_report_daily(team, name, title, document_link, document_link_desktop, assignee, im, qc, country):
  require_any_role()
  _create_new_report("os_report_daily", "OS Report - Daily", team, name, title, document_link,
                      document_link_desktop, assignee, im, qc, country, extra_fields={"metadata": [], "inputs": []})

@anvil.server.callable(require_user=True)
def create_new_os_report_weekly(team, name, title, document_link, document_link_desktop, assignee, im, qc, country):
  require_any_role()
  _create_new_report("os_report_weekly", "OS Report - Weekly", team, name, title, document_link,
                      document_link_desktop, assignee, im, qc, country, extra_fields={"metadata": [], "inputs": []})

@anvil.server.callable(require_user=True)
def create_new_os_report_other(team, name, title, document_link, document_link_desktop, assignee, im, qc, country):
  require_any_role()
  _create_new_report("os_report_other", "OS Report - Other", team, name, title, document_link,
                      document_link_desktop, assignee, im, qc, country, extra_fields={"metadata": [], "inputs": []})

@anvil.server.callable(require_user=True)
def create_new_spot_report(team, name, title, document_link, document_link_desktop, assignee, im, qc, country):
  require_any_role()
  _create_new_report("spot_report", "Spot Report", team, name, title, document_link,
                      document_link_desktop, assignee, im, qc, country)

# Ordered so reports display in a stable, consistent sequence; _REPORT_COLLECTIONS
# (above) is a set used for allow-list membership checks, not iteration order.
_REPORT_STATUS_COLLECTIONS = ["os_report_daily", "os_report_weekly", "os_report_other", "spot_report", "story"]

def _get_reports_by_status(status, team=None, format_created=False):
  # Shared body for get_in_progress_reports/get_qc_reports/get_disseminated_reports:
  # fetch every report-type collection filtered by status (and optionally team),
  # then make the result Anvil/UI-friendly (stringified _id, formatted created date).
  mongo_client = mongo_connect()
  db = mongo_client["prod"]

  query = {'status': status}
  if team is not None:
    query['team'] = team

  all_reports = []
  for collection_name in _REPORT_STATUS_COLLECTIONS:
    all_reports.extend(db[collection_name].find(query))

  for item in all_reports:
    item['_id'] = str(item['_id'])
    if format_created and isinstance(item.get('created'), datetime):
      item['created'] = item['created'].strftime('%b %d, %Y %I:%M %p')

  return all_reports

@anvil.server.callable(require_user=True)
def get_in_progress_reports(team):
  return _get_reports_by_status("In Progress", team=team)

def _get_reports_as_dropdown_items(collection_name, team):
  # Shared body for get_weekly_reports/get_daily_reports/get_other_reports:
  # in-progress reports of one type, shaped as (title, details) pairs for
  # dropdown items.
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  col = db[collection_name]
  reports = col.find({'team': team, 'status': "In Progress"})
  return [
    (report['title'], {
      'id': str(report['_id']),
      'link': report.get('document_link', ''),
      'desktop_link': report.get('document_link_desktop', ''),
      'hl_pipeline': report.get('hl_pipeline', False),
    })
    for report in reports
  ]

@anvil.server.callable(require_user=True)
def get_weekly_reports(team):
  return _get_reports_as_dropdown_items("os_report_weekly", team)

@anvil.server.callable(require_user=True)
def get_daily_reports(team):
  return _get_reports_as_dropdown_items("os_report_daily", team)

@anvil.server.callable(require_user=True)
def get_other_reports(team):
  return _get_reports_as_dropdown_items("os_report_other", team)

@anvil.server.callable(require_user=True)
def get_document(collection, id):
  if collection not in _REPORT_COLLECTIONS:
    raise Exception(f"Invalid collection: {collection!r}")
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  col = db[collection]

  document = col.find_one({"_id": _object_id(id)})

  if document is None:
    return None

  document['_id'] = str(document['_id'])
  return document

def _status_action(data, default_action):
  # Both modify_document and process_report are generic "update this report"
  # entry points; the meaningful audit event is the status transition they
  # carry, not the raw field diff.
  status = data.get("status")
  if status == "disseminate":
    return "disseminated"
  if status == "qc_check":
    return "sent_to_qc"
  return default_action

@anvil.server.callable(require_user=True)
def modify_document(collection, id, data):
  require_any_role()
  if collection not in _REPORT_COLLECTIONS:
    raise Exception(f"Invalid collection: {collection!r}")
  if collection == "story" and "outputs" in data:
    # Story outputs drive a two-way inputs/outputs sync that only
    # process_report performs; setting it here would desync linked reports.
    raise Exception("Use process_report to modify a story's outputs.")

  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  col = db[collection]

  current_doc = col.find_one({"_id": _object_id(id)})
  report_name = current_doc.get("name") if current_doc else None

  updated_document = col.find_one_and_update(
    {"_id": _object_id(id)},
    {"$set": data}
  )

  log_action(db, _status_action(data, "report_updated"), collection=collection, report_id=id,
             report_name=report_name, fields=data)

  return "Done"

@anvil.server.callable(require_user=True)
def process_report(collection, id, data):
  require_any_role()
  if collection not in _REPORT_COLLECTIONS:
    raise Exception(f"Invalid collection: {collection!r}")
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  col = db[collection]

  current_doc = col.find_one({"_id": _object_id(id)})
  report_name = current_doc.get("name") if current_doc else None
  action = _status_action(data, "report_processed")

  if collection != "story":
    # Simple case: just update the document
    col.find_one_and_update(
      {"_id": _object_id(id)},
      {"$set": data}
    )
    log_action(db, action, collection=collection, report_id=id, report_name=report_name, fields=data)
    return "Done"

  # Story case: handle two-way relationships in 'outputs'
  current_outputs = current_doc.get("outputs", {"daily": [], "weekly": [], "other": []}) if current_doc else {}
  new_outputs = data.get("outputs", {})

  report_collections = {
    "daily": "os_report_daily",
    "weekly": "os_report_weekly",
    "other": "os_report_other"
  }

  for key, report_col_name in report_collections.items():
    current_ids = set(current_outputs.get(key, []))
    new_ids = set(new_outputs.get(key, []))
    added_ids = new_ids - current_ids
    removed_ids = current_ids - new_ids

    for related_id in added_ids:
      db[report_col_name].find_one_and_update(
        {"_id": _object_id(related_id)},
        {"$addToSet": {"inputs": id}}
      )

    for related_id in removed_ids:
      db[report_col_name].find_one_and_update(
        {"_id": _object_id(related_id)},
        {"$pull": {"inputs": id}}
      )

  col.find_one_and_update(
    {"_id": _object_id(id)},
    {"$set": data}
  )
  log_action(db, action, collection=collection, report_id=id, report_name=report_name, fields=data)
  return "Done"

@anvil.server.callable(require_user=True)
def get_qc_reports():
  return _get_reports_by_status("qc_check", format_created=True)


@anvil.server.callable(require_user=True)
def get_disseminated_reports():
  return _get_reports_by_status("disseminate", format_created=True)

@anvil.server.callable(require_user=True)
def finalise_story(id):
  # Append this story's text into every report it's linked to via "outputs",
  # so disseminating the story also updates whichever daily/weekly/other
  # reports already reference it.
  require_any_role()
  story = get_document("story", id)
  if story is None:
    raise Exception(f"Story {id} not found")
  story_name = story['name']
  reports_to_modify = story.get('outputs', {})

  report_collections = {
    "daily": "os_report_daily",
    "weekly": "os_report_weekly",
    "other": "os_report_other"
  }

  for key, collection_name in report_collections.items():
    for report_id in reports_to_modify.get(key, []):
      doc = get_document(collection_name, report_id)
      if doc is not None:
        anvil.server.call('append_document_contents', story_name, doc['name'])

  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  log_action(db, "story_finalised", collection="story", report_id=id, report_name=story_name)

  return "Done"

@anvil.server.callable(require_user=True)
def get_report_inputs(collection, id):

  parent_report = get_document(collection, id)
  if parent_report is None:
    raise Exception(f"Document {id} not found in {collection}")
  report_inputs = parent_report.get('inputs', [])

  all_input_reports = []
  for report in report_inputs:
    input_report = get_document('story', report)
    if input_report is not None:
      all_input_reports.append(input_report)



  return all_input_reports

@anvil.server.callable(require_user=True)
def ensure_story_search_index():
  # Idempotently provision the Atlas Search index used by search_stories.
  # Not called on every search - this is a one-off/admin action against the
  # live cluster, since Atlas builds new indexes asynchronously.
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["story"]

  existing = list(collection.list_search_indexes(STORY_SEARCH_INDEX_NAME))
  if existing:
    return existing[0]

  definition = {
    "mappings": {
      "dynamic": False,
      "fields": {
        field: {"type": "autocomplete"} for field in STORY_SEARCH_FIELDS
      },
    },
  }

  collection.create_search_index(SearchIndexModel(definition, name=STORY_SEARCH_INDEX_NAME))

  return list(collection.list_search_indexes(STORY_SEARCH_INDEX_NAME))[0]

@anvil.server.callable(require_user=True)
def get_story_search_index_status():
  # Poll while the index is building; returns None if it hasn't been created yet.
  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["story"]

  existing = list(collection.list_search_indexes(STORY_SEARCH_INDEX_NAME))
  return existing[0] if existing else None

@anvil.server.callable(require_user=True)
def search_stories(query):
  # Full-text lookup of Story documents via Atlas Search, matching regardless
  # of status so in-progress, QC, and disseminated stories are all findable.
  query = (query or "").strip()
  if not query:
    return []

  mongo_client = mongo_connect()
  db = mongo_client["prod"]
  collection = db["story"]

  results = collection.aggregate([
    {"$search": {
      "index": STORY_SEARCH_INDEX_NAME,
      "compound": {
        "should": [
          {"autocomplete": {"query": query, "path": field}}
          for field in STORY_SEARCH_FIELDS
        ],
        "minimumShouldMatch": 1,
      },
    }},
    {"$limit": 50},
  ])

  stories = list(results)
  for story in stories:
    story['_id'] = str(story['_id'])

  return stories

# --- Word add-in sync webhook -----------------------------------------------
# Public endpoint for the Word add-in's middle-tier service. The add-in itself
# never calls this directly - the middle tier authenticates the Word user via
# SSO, stamps who/when, and forwards the status changes here.

# Word task-pane checkbox id -> the report field it drives directly. `qc` is
# handled separately below since it's a status transition, not a plain field.
_WORD_SYNC_STATUS_FIELDS = {
  "completeIM": "im_check",
  "completeRCM": "rcm_check",
  "requestIM": "im_requested",
  "proofed": "proofed",
}

def _json_response(status, payload):
  return anvil.server.HttpResponse(
    status=status,
    body=json.dumps(payload),
    headers={"Content-Type": "application/json"}
  )

def _get_header(request, name):
  # route()'s HttpRequest only exposes a plain `headers` dict (no get_header
  # method, unlike the legacy http_endpoint `request`), and HTTP header
  # names are case-insensitive, so match case-insensitively ourselves.
  name_lower = name.lower()
  for key, value in request.headers.items():
    if key.lower() == name_lower:
      return value
  return None

def _filename_from_document_url(url):
  # Report documents store `name` without an extension, but document_url is a
  # full SharePoint/OneDrive URL ending in the (URL-encoded) filename.
  if not url:
    return None
  last_segment = urlsplit(url).path.rsplit('/', 1)[-1]
  filename = unquote(last_segment)
  if filename.lower().endswith('.docx'):
    filename = filename[:-len('.docx')]
  return filename or None

def _word_sync_find_by_document_id(db, document_id):
  for collection_name in _REPORT_COLLECTIONS:
    report = db[collection_name].find_one({"word_metadata.document_id": document_id})
    if report is not None:
      return collection_name, report
  return None, None

def _word_sync_find_by_name(db, name):
  for collection_name in _REPORT_COLLECTIONS:
    report = db[collection_name].find_one({"name": name})
    if report is not None:
      return collection_name, report
  return None, None

@anvil.server.route("/word-sync", methods=["POST"])
def word_sync(**kwargs):
  request = anvil.server.request

  api_key = _get_header(request, "X-Api-Key") or ""
  expected_key = anvil.secrets.get_secret('WORD_SYNC_API_KEY')
  if not hmac.compare_digest(api_key, expected_key):
    return _json_response(401, {"status": "error", "message": "Invalid API key"})

  payload = request.body_json or {}
  document_id = payload.get("document_id")
  if not document_id:
    return _json_response(400, {"status": "error", "message": "document_id is required"})

  document_url = payload.get("document_url")
  statuses = payload.get("statuses") or {}
  changed = payload.get("changed") or []
  changed_by = payload.get("changed_by") or {}
  changed_at = payload.get("changed_at")

  mongo_client = mongo_connect()
  db = mongo_client["prod"]

  collection_name, report = _word_sync_find_by_document_id(db, document_id)
  if report is None:
    filename = _filename_from_document_url(document_url)
    if filename:
      collection_name, report = _word_sync_find_by_name(db, filename)
    if report is None:
      return _json_response(404, {"status": "error", "message": "No matching report found"})
    # First sync for this report: pin the add-in's id so future syncs match
    # directly even if the document is later renamed or moved.
    db[collection_name].update_one(
      {"_id": report["_id"]},
      {"$set": {"word_metadata.document_id": document_id}}
    )

  updates = {}
  for word_key, mongo_field in _WORD_SYNC_STATUS_FIELDS.items():
    if word_key in statuses:
      updates[mongo_field] = bool(statuses[word_key])

  if statuses.get("qc"):
    # Mirrors the CMS's own "Send to QC" precondition (dlg_process): only
    # im_check gates the transition. Check the post-update value, since
    # completeIM may have arrived in this same request.
    im_check_after = updates.get("im_check", report.get("im_check", False))
    if im_check_after:
      updates["status"] = "qc_check"

  if updates:
    db[collection_name].update_one({"_id": report["_id"]}, {"$set": updates})

  log_action(db, "word_sync", collection=collection_name, report_id=str(report["_id"]),
             report_name=report.get("name"), changed=changed,
             changed_by=changed_by.get("email"), changed_by_name=changed_by.get("name"),
             changed_at=changed_at)

  return _json_response(200, {
    "status": "ok",
    "document_id": document_id,
    "collection": collection_name,
    "report_id": str(report["_id"]),
  })

@anvil.server.route("/word-status", methods=["GET"])
def word_status(**kwargs):
  # Read-only counterpart to word_sync: lets the add-in pull the CMS's
  # current state for a document (e.g. on task-pane open, or a manual
  # "Refresh" action), rather than only ever pushing its own local state.
  request = anvil.server.request

  api_key = _get_header(request, "X-Api-Key") or ""
  expected_key = anvil.secrets.get_secret('WORD_SYNC_API_KEY')
  if not hmac.compare_digest(api_key, expected_key):
    return _json_response(401, {"status": "error", "message": "Invalid API key"})

  document_id = request.query_params.get("document_id")
  document_url = request.query_params.get("document_url")
  if not document_id and not document_url:
    return _json_response(400, {"status": "error", "message": "document_id or document_url is required"})

  mongo_client = mongo_connect()
  db = mongo_client["prod"]

  collection_name, report = (None, None)
  if document_id:
    collection_name, report = _word_sync_find_by_document_id(db, document_id)

  if report is None:
    filename = _filename_from_document_url(document_url)
    if filename:
      collection_name, report = _word_sync_find_by_name(db, filename)
    if report is not None and document_id:
      # The add-in already has an id we hadn't seen before (e.g. a pull
      # before any push has ever happened) - pin it for future fast-path hits.
      db[collection_name].update_one(
        {"_id": report["_id"]},
        {"$set": {"word_metadata.document_id": document_id}}
      )

  if report is None:
    return _json_response(404, {"status": "error", "message": "No matching report found"})

  resolved_document_id = report.get("word_metadata", {}).get("document_id") or document_id

  return _json_response(200, {
    "status": "ok",
    "document_id": resolved_document_id,
    "collection": collection_name,
    "report_id": str(report["_id"]),
    "statuses": {
      "requestIM": bool(report.get("im_requested", False)),
      "completeRCM": bool(report.get("rcm_check", False)),
      "completeIM": bool(report.get("im_check", False)),
      "qc": report.get("status") in ("qc_check", "disseminate", "Completed"),
      "proofed": bool(report.get("proofed", False)),
    },
  })