from ._anvil_designer import RowTemplate2Template
from anvil import *
import anvil.server
import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from .. import Globals


class RowTemplate2(RowTemplate2Template):
  # Item template for panel_input_daily - same layout as RowTemplate1, just
  # bound to the daily OS report's input list instead of the weekly one.
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    super().__init__(**properties)

    Globals.setup_doc_link(self.lnk_document, self.item)


    status = self.item.get('status') or ''
    status_map = {
      'In Progress': ('In Progress', 'status-in-progress'),
      'qc_check':    ('QC Check',    'status-qc'),
      'disseminate': ('Disseminate', 'status-disseminate'),
    }
    label, role = status_map.get(status, (status, ''))
    self.lbl_status.text = label
    if role:
      self.lbl_status.role = role
