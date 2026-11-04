from ._anvil_designer import row_template_otherTemplate
from anvil import *
import anvil.server
import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from ...dlg_process import dlg_process
from .. import Globals


class row_template_other(row_template_otherTemplate):
  # Item template for panel_other (dg_other). Logic is identical to
  # row_template_priority/row_template_spot, but each backs a separate
  # DataGrid with its own independently-generated column ids, so merging
  # these would mean realigning all three DataGrids' column definitions too.
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)

    for lbl, key in [(self.lbl_rcm_check, 'rcm_check'), (self.lbl_im_check, 'im_check')]:
      checked = self.item.get(key)
      lbl.text = 'Yes' if checked else 'No'
      lbl.role = 'status-done' if checked else 'status-pending'

    Globals.setup_doc_link(self.lnk_document, self.item)

  @handle("btn_process", "click")
  def btn_process_click(self, **event_args):
    dialog = dlg_process(details=self.item, hide_send_to_qc=True)
    result = alert(content=dialog,
                   title="Process", large=True, buttons=[
                     ("Save", "Save"),
                     ("Cancel", "Cancel")
                   ])
    if result == "Save":
      self.btn_process.enabled = False
      try:
        fields_to_update = {}
        collection = Globals.collection_for_type(dialog.txt_type.text)

        fields_to_update['title'] = dialog.txt_title.text
        fields_to_update['im_check'] = dialog.chk_im.checked
        fields_to_update['rcm_check'] = dialog.chk_rcm.checked
        fields_to_update['metadata'] = [tag for tag in dialog.txt_added_metadata.text.split(",") if tag]
        fields_to_update['hl_pipeline'] = dialog.chk_hl_pipeline.checked
        if dialog.chk_send_to_qc.checked:
          fields_to_update['status'] = "qc_check"

        # fields_to_update deliberately never gets an "outputs" key here -
        # mongo.modify_document rejects it for stories, since changing a
        # story's outputs requires process_report's two-way inputs/outputs sync.
        anvil.server.call('modify_document', collection, self.item['_id'], fields_to_update)

        Globals.current_form.refresh_reports()
      finally:
        self.btn_process.enabled = True

  @handle("btn_disseminate", "click")
  def btn_disseminate_click(self, **event_args):
    self.btn_disseminate.enabled = False
    try:
      fields_to_update = {}
      collection = Globals.collection_for_type(self.item['type'])

      fields_to_update['status'] = "disseminate"

      # If it is a story we need to append the document using append_document_contents(source_document_name, target_document_name).
      # Do this before flipping the status, so a failed merge leaves the story
      # in qc_check (visible and retryable) instead of silently vanishing as
      # "disseminated" with its content never actually appended.
      if collection == "story":
        anvil.server.call('finalise_story', self.item['_id'])

      anvil.server.call('modify_document', collection, self.item['_id'], fields_to_update)

      Globals.current_form.refresh_reports()
    finally:
      self.btn_disseminate.enabled = True
