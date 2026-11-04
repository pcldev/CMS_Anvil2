from ._anvil_designer import row_template_resultTemplate
from anvil import *
import anvil.server
import anvil.users
from ...dlg_process import dlg_process
from .. import Globals


class row_template_result(row_template_resultTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)

    Globals.setup_doc_link(self.lnk_document, self.item)

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

      fields_to_update['title'] = dialog.txt_title.text
      fields_to_update['im_check'] = dialog.chk_im.checked
      fields_to_update['rcm_check'] = dialog.chk_rcm.checked
      fields_to_update['metadata'] = [tag for tag in dialog.txt_added_metadata.text.split(",") if tag]
      fields_to_update['hl_pipeline'] = dialog.chk_hl_pipeline.checked
      if dialog.chk_send_to_qc.checked:
        fields_to_update['status'] = "qc_check"

      fields_to_update['outputs'] = {
        "daily": dialog.drop_outputs_daily.selected,
        "weekly": dialog.drop_outputs_weekly.selected,
        "other": dialog.drop_outputs_other.selected,
      }

      anvil.server.call('process_report', 'story', self.item['_id'], fields_to_update)

      Globals.current_form.refresh_results()
