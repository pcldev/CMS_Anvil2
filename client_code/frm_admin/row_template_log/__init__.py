from ._anvil_designer import row_template_logTemplate
from anvil import *
import json


ACTION_LABELS = {
  "template_created": "Template Created",
  "sent_to_qc": "Sent to QC",
  "disseminated": "Disseminated",
  "report_processed": "Report Processed",
  "report_updated": "Report Updated",
  "story_finalised": "Story Finalised",
}

# Everything already shown in the summary row - the rest of the log entry is
# rendered as the expandable "Details" blob.
_SUMMARY_KEYS = {"_id", "action", "user", "timestamp", "report_name", "report_type", "collection", "report_id"}


class row_template_log(row_template_logTemplate):
  def __init__(self, **properties):
    self.init_components(**properties)

    action = str(self.item.get('action') or '')

    self.lbl_timestamp.text = str(self.item.get('timestamp', ''))
    self.lbl_user.text = self.item.get('user') or 'Unknown user'
    self.lbl_action.text = ACTION_LABELS.get(action, action)

    report_name = self.item.get('report_name') or '—'
    report_type = self.item.get('report_type') or self.item.get('collection') or ''
    self.lbl_report.text = f"{report_name} ({report_type})" if report_type else report_name

    details = {k: v for k, v in self.item.items() if k not in _SUMMARY_KEYS}
    self.txt_details.text = json.dumps(details, indent=2, default=str) if details else "No additional details"
    self.txt_details.visible = False

  @handle("btn_toggle_details", "click")
  def btn_toggle_details_click(self, **event_args):
    self.txt_details.visible = not self.txt_details.visible
    self.btn_toggle_details.text = "Hide Details" if self.txt_details.visible else "Details"
