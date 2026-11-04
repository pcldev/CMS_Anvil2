from ._anvil_designer import dlg_processTemplate
from anvil import *
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.users
import anvil.server
from .. import Globals


class dlg_process(dlg_processTemplate):
  def __init__(self, hide_send_to_qc=False, **properties):
    self.init_components(**properties)

    self.chk_send_to_qc.visible = not hide_send_to_qc

    data = properties['details']
    self.txt_report_name.text = data.get('name', None)
    self.txt_title.text = data.get('title', None)
    self.txt_type.text = data.get('type', None)
    self.txt_assigned_to.text = data.get('assignee', None)
    self.txt_im.text = data.get('im', None)
    self.txt_qc.text = data.get('qc', None)
    self.chk_im.checked = data.get('im_check', False)
    self.chk_rcm.checked = data.get('rcm_check', False)
    self.chk_hl_pipeline.checked = data.get('hl_pipeline', False)

    outputs = data.get('outputs', {})
    self.drop_outputs_daily.selected = outputs.get('daily')
    self.drop_outputs_other.selected = outputs.get('other')
    self.drop_outputs_weekly.selected = outputs.get('weekly')

    # chips_metadata is a template-defined AutocompleteChips — just configure it.
    self.chips_metadata.suggestions = Globals.all_tags
    self.chips_metadata.chips = data.get('metadata', [])
    self.chips_metadata.set_event_handler("chips_changed", self.metadata_chips_changed)

    metadata_string = ", ".join(data.get('metadata', []))
    self.txt_added_metadata.text = metadata_string

    if data.get('type') == "Story":
      self.grd_outputs.visible = True
      # Outputs are stored as plain report IDs, so each dropdown's value must
      # be the ID string (not the {'id', 'link'} dict used elsewhere) or the
      # server's set()-based diffing of selected outputs breaks on unhashable dicts.
      self.drop_outputs_weekly.items = Globals.sort_dropdown_items([
        (title, value['id']) for title, value in anvil.server.call('get_weekly_reports', data.get('team'))
      ])
      self.drop_outputs_daily.items = Globals.sort_dropdown_items([
        (title, value['id']) for title, value in anvil.server.call('get_daily_reports', data.get('team'))
      ])
      self.drop_outputs_other.items = Globals.sort_dropdown_items([
        (title, value['id']) for title, value in anvil.server.call('get_other_reports', data.get('team'))
      ])

  def metadata_chips_changed(self, chips, **event_args):
    self.txt_added_metadata.text = ", ".join(chips)

  @handle("chk_send_to_qc", "change")
  def chk_send_to_qc_change(self, **event_args):
    if self.chk_send_to_qc.checked and not self.chk_im.checked:
      self.chk_send_to_qc.checked = False
      alert("IM must be completed before this can be sent to QC.", title="Cannot send to QC")

  @handle("chk_im", "change")
  def chk_im_change(self, **event_args):
    if not self.chk_im.checked:
      self.chk_send_to_qc.checked = False
