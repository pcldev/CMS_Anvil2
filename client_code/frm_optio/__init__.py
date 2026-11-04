from ._anvil_designer import frm_optioTemplate
from anvil import *
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.users
import anvil.server
from .. import Globals


class frm_optio(frm_optioTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)

    Globals.current_form = self  # store reference to this form

    self.refresh_reports()

  def refresh_reports(self, **event_args):
    reports = anvil.server.call('get_disseminated_reports')

    priority_reports = []
    routine_reports = []

    for report in reports:
      if report['hl_pipeline'] is True:
        priority_reports.append(report)

      else:
        routine_reports.append(report)

    self.panel_priority.items = priority_reports
    self.panel_routine.items = routine_reports

    self.lbl_empty_priority.visible = len(priority_reports) == 0
    self.lbl_empty_routine.visible = len(routine_reports) == 0

