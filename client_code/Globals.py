import anvil.server
import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables

# The logged-in user's role; used for authorization
user_role = {}

# The logged-in user's email
user_email = ""

# The logged in user's default team, auto-selected in frm_im
default_team = None

# Teams loaded in database
teams = []

# All Users in CMS
all_users = []

# Users with the IM role, for IM reviewer dropdowns
im_reviewers = []

# Users with the QC role, for QC reviewer dropdowns
qc_reviewers = []

# All tags
all_tags = []

# Current Form, kept so other forms/dialogs can call back in to refresh its data
current_form = None

def word_desktop_url(url):
  # ms-word:ofe|u|<url> is the Office URI scheme that desktop Word registers;
  # navigating to it opens the document for editing in the desktop app instead
  # of Word Online. Per Microsoft's own Office URI Schemes spec, "|" is
  # deliberately NOT a reserved character here and must stay literal - percent
  # encoding it to %7C breaks the OS-level ofe|u|<url> command parsing
  # ("doesn't recognise the command it was given").
  #
  # `url` must be the item's Graph webDavUrl, not its webUrl - webUrl is the
  # Office-Online/browser link and desktop Word can't open it via ofe|u| even
  # though the command itself parses fine ("Sorry, we couldn't open '<url>'").
  #
  # Falls back to nothing if there's no document url.
  if not url:
    return ''
  escaped_url = url.replace('{', '%7B').replace('}', '%7D')
  return f"ms-word:ofe|u|{escaped_url}"

# Maps the human-readable type label shown in dialogs/rows to the Mongo
# collection it's stored in. Keep in sync with _REPORT_COLLECTIONS in the
# mongo server module.
_TYPE_TO_COLLECTION = {
  "OS Report - Daily": "os_report_daily",
  "OS Report - Weekly": "os_report_weekly",
  "OS Report - Other": "os_report_other",
  "Spot Report": "spot_report",
  "Story": "story",
}

def collection_for_type(report_type):
  try:
    return _TYPE_TO_COLLECTION[report_type]
  except KeyError:
    raise Exception(f"Unknown report type: {report_type!r}")

def sort_dropdown_items(items):
  # Sorts DropDown/MultiSelectDropDown items alphabetically by their display
  # label, case-insensitively. Items may be plain strings or (label, value)
  # tuples - both forms are used across the app's dropdowns.
  def label(item):
    display = item[0] if isinstance(item, (tuple, list)) else item
    return str(display).lower()
  return sorted(items, key=label)

def setup_doc_link(link, item):
  # Shared by every row/row-template that shows a report's "Open in Word"
  # link: shows it only when a desktop link exists, and wires it to the
  # ms-word:ofe|u| URL via word_desktop_url above.
  desktop_url = item.get('document_link_desktop') or ''
  link.visible = bool(desktop_url)
  if desktop_url:
    link.text = "Open in Word"
    link.url = word_desktop_url(desktop_url)
    link.role = 'doc-link'