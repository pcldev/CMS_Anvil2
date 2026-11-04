from ._anvil_designer import frm_qcTemplate
from anvil import *
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.users
import anvil.server
from .. import Globals


class frm_qc(frm_qcTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)

    Globals.current_form = self  # store reference to this form

    self.refresh_reports()

  def refresh_reports(self, **event_args):
    qc_reports = anvil.server.call('get_qc_reports')

    spot_reports = []
    priority_reports = []
    other_reports = []

    for report in qc_reports:
      if report['hl_pipeline'] is True:
        priority_reports.append(report)
      elif report['type'] == "Spot Report":
        spot_reports.append(report)
      else:
        other_reports.append(report)

    self.panel_other.items = other_reports
    self.panel_priority.items = priority_reports
    self.panel_spot.items = spot_reports

    self.lbl_empty_spot.visible = len(spot_reports) == 0
    self.lbl_empty_priority.visible = len(priority_reports) == 0
    self.lbl_empty_other.visible = len(other_reports) == 0
