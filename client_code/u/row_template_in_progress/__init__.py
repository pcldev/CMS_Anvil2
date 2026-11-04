from ._anvil_designer import row_template_in_progressTemplate
from anvil import *
import anvil.server
import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from ...dlg_assign_proofer import dlg_assign_proofer
from ...dlg_process import dlg_process
from .. import Globals



class row_template_in_progress(row_template_in_progressTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    super().__init__(**properties)

    for lbl, key in [(self.lbl_rcm_check, 'rcm_check'), (self.lbl_im_check, 'im_check')]:
      checked = self.item.get(key)
      lbl.text = 'Yes' if checked else 'No'
      lbl.role = 'status-done' if checked else 'status-pending'

    Globals.setup_doc_link(self.lnk_document, self.item)


  @handle("btn_in_progress_proofing", "click")
  def btn_in_progress_proofing_click(self, **event_args):


    dialog = dlg_assign_proofer(details=self.item)
    result = alert(content=dialog,
                   title="Assign Proofer", large=True, buttons=[
                     ("Send", "Send"),
                     ("Cancel", "Cancel")
                   ])

    if result == "Send":
      link = self.item.get('document_link') or ''
      hl_pipeline = self.item.get('hl_pipeline', False)
      anvil.server.call('send_email', dialog.drop_assign_to.selected_value, f"{dialog.txt_comment.text}\n\nDocument: {link}", hl_pipeline=hl_pipeline)

  @handle("btn_process", "click")
  def btn_process_click(self, **event_args):
    dialog = dlg_process(details=self.item)
    result = alert(content=dialog,
                   title="Process", large=True, buttons=[
                     ("Save", "Save"),
                     ("Cancel", "Cancel")
                   ])
    if result == "Save":
      fields_to_update = {}
      collection = Globals.collection_for_type(dialog.txt_type.text)

      fields_to_update['title'] = dialog.txt_title.text
      fields_to_update['im_check'] = dialog.chk_im.checked
      fields_to_update['rcm_check'] = dialog.chk_rcm.checked
      fields_to_update['metadata'] = [tag for tag in dialog.txt_added_metadata.text.split(",") if tag]
      fields_to_update['hl_pipeline'] = dialog.chk_hl_pipeline.checked
      if dialog.chk_send_to_qc.checked:
        fields_to_update['status'] = "qc_check"

      if collection == "story":
        # process_report expects outputs as {"daily": [...], "weekly": [...], "other": [...]}
        # so it can diff against the story's current outputs and sync the
        # linked reports' "inputs" both ways (see mongo.process_report).
        daily_reports_to_add = dialog.drop_outputs_daily.selected
        weekly_reports_to_add = dialog.drop_outputs_weekly.selected
        other_report_to_add = dialog.drop_outputs_other.selected
        outputs_dict = {}
        outputs_dict["daily"] = daily_reports_to_add
        outputs_dict["weekly"] = weekly_reports_to_add
        outputs_dict["other"] = other_report_to_add

        fields_to_update['outputs'] = outputs_dict

      anvil.server.call('process_report', collection, self.item['_id'], fields_to_update)

      Globals.current_form.refresh_reports()

