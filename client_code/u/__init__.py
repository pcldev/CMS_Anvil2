from ._anvil_designer import uTemplate
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.users
import anvil.server
from anvil import *
from ..dlg_new_template import dlg_new_template
from .. import Globals
from ..dlg_assign_proofer import dlg_assign_proofer
from ..dlg_process import dlg_process


class u(uTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)

    self.drop_team.items = Globals.sort_dropdown_items(Globals.teams)

    if Globals.default_team in Globals.teams:
      self.drop_team.selected_value = Globals.default_team
      self.refresh_reports()

    Globals.current_form = self  # store reference to this form

  def _create_document(self, template_name, doc_name):
    """Create the document via Graph; show an actionable alert if the name is taken."""
    try:
      return anvil.server.call('create_document', template_name, doc_name)
    except RuntimeError as e:
      alert(str(e), title="Could not create document")
      return None

  @handle("btn_im_new_template", "click")
  def btn_im_new_template_click(self, **event_args):

    dialog = dlg_new_template()
    while True:
      result = alert(content=dialog,
                     title="Create a new Template", large=True, buttons=[
                       ("Create", "Create"),
                       ("Cancel", "Cancel")
                     ])
      if result != 'Create':
        break

      missing_fields = dialog.get_missing_fields()
      if missing_fields:
        alert(f"Please complete the following required fields: {', '.join(missing_fields)}",
              title="Missing required fields")
        continue

      # One branch per template type: duplicate the right SharePoint template
      # via Graph, then record the new report under the matching collection.
      if dialog.drop_type.selected_value == "OS Report (Daily)":
        template_name = anvil.server.call('get_template_location', "os_report")
        document = self._create_document(template_name, dialog.txt_name.text)
        if document is None:
          return

        anvil.server.call('create_new_os_report_daily',
                          dialog.drop_team.selected_value,
                          dialog.txt_name.text,
                          dialog.txt_title.text,
                          document['web_url'],
                          document['desktop_url'],
                          dialog.drop_assign_to.selected_value,
                          dialog.drop_im_reviewer.selected_value,
                          dialog.drop_qc_reviewer.selected_value,
                          dialog.txt_country.text)
      elif dialog.drop_type.selected_value == "OS Report (Weekly)":
        template_name = anvil.server.call('get_template_location', "os_report")
        document = self._create_document(template_name, dialog.txt_name.text)
        if document is None:
          return

        anvil.server.call('create_new_os_report_weekly',
                          dialog.drop_team.selected_value,
                          dialog.txt_name.text,
                          dialog.txt_title.text,
                          document['web_url'],
                          document['desktop_url'],
                          dialog.drop_assign_to.selected_value,
                          dialog.drop_im_reviewer.selected_value,
                          dialog.drop_qc_reviewer.selected_value,
                          dialog.txt_country.text)
      elif dialog.drop_type.selected_value == "OS Report (Other)":
        template_name = anvil.server.call('get_template_location', "os_report")
        document = self._create_document(template_name, dialog.txt_name.text)
        if document is None:
          return

        anvil.server.call('create_new_os_report_other',
                          dialog.drop_team.selected_value,
                          dialog.txt_name.text,
                          dialog.txt_title.text,
                          document['web_url'],
                          document['desktop_url'],
                          dialog.drop_assign_to.selected_value,
                          dialog.drop_im_reviewer.selected_value,
                          dialog.drop_qc_reviewer.selected_value,
                          dialog.txt_country.text)
      elif dialog.drop_type.selected_value == "Story":
        template_name = anvil.server.call('get_template_location', "story")
        document = self._create_document(template_name, dialog.txt_name.text)
        if document is None:
          return

        anvil.server.call('create_new_story',
                          dialog.drop_team.selected_value,
                          dialog.txt_name.text,
                          dialog.txt_title.text,
                          document['web_url'],
                          document['desktop_url'],
                          dialog.drop_assign_to.selected_value,
                          dialog.drop_im_reviewer.selected_value, 
                          dialog.drop_qc_reviewer.selected_value, 
                          dialog.txt_country.text)
      elif dialog.drop_type.selected_value == "Spot Report":
        template_name = anvil.server.call('get_template_location', "spot_report")
        document = self._create_document(template_name, dialog.txt_name.text)
        if document is None:
          return

        anvil.server.call('create_new_spot_report',
                          dialog.drop_team.selected_value,
                          dialog.txt_name.text,
                          dialog.txt_title.text,
                          document['web_url'],
                          document['desktop_url'],
                          dialog.drop_assign_to.selected_value,
                          dialog.drop_im_reviewer.selected_value, 
                          dialog.drop_qc_reviewer.selected_value, 
                          dialog.txt_country.text)
      else:
        raise ValueError(f"Unknown template type: {dialog.drop_type.selected_value!r}")

      # Notify the assignee
      anvil.server.call('send_email', dialog.drop_assign_to.selected_value, f"Please complete {document['web_url']}")

      self.refresh_reports()
      break

  @handle("drop_team", "change")
  def drop_team_change(self, **event_args):
    self.refresh_reports()

  def refresh_reports(self, **event_args):
    in_progress_reports = anvil.server.call('get_in_progress_reports', self.drop_team.selected_value)
    self.panel_in_progress.items = in_progress_reports
    self.lbl_empty_in_progress.visible = len(in_progress_reports) == 0

    weekly_reports = anvil.server.call('get_weekly_reports', self.drop_team.selected_value)
    self.drop_weekly.include_placeholder = True
    self.drop_weekly.placeholder = "Select a report..."
    self.drop_weekly.selected_value = None
    self.drop_weekly.items = Globals.sort_dropdown_items(weekly_reports)
    # Setting selected_value above doesn't raise drop_weekly's own "change"
    # event, so the dependent grid/link would otherwise keep showing the
    # previous team's report - clear it explicitly instead.
    self.drop_weekly_change()

    daily_reports = anvil.server.call('get_daily_reports', self.drop_team.selected_value)
    self.drop_daily.include_placeholder = True
    self.drop_daily.placeholder = "Select a report..."
    self.drop_daily.selected_value = None
    self.drop_daily.items = Globals.sort_dropdown_items(daily_reports)
    self.drop_daily_change()

    other_reports = anvil.server.call('get_other_reports', self.drop_team.selected_value)
    self.drop_other.include_placeholder = True
    self.drop_other.placeholder = "Select a report..."
    self.drop_other.selected_value = None
    self.drop_other.items = Globals.sort_dropdown_items(other_reports)
    self.drop_other_change()

  @handle("drop_weekly", "change")
  def drop_weekly_change(self, **event_args):
    val = self.drop_weekly.selected_value
    if val is None:
      self.panel_input_weekly.items = []
      self.btn_weekly_edit.visible = False
      return
    inputs = anvil.server.call('get_report_inputs', "os_report_weekly", val['id'])
    self.panel_input_weekly.items = inputs
    self.btn_weekly_edit.url = Globals.word_desktop_url(val['desktop_link'])
    self.btn_weekly_edit.visible = bool(val['desktop_link'])

  @handle("drop_daily", "change")
  def drop_daily_change(self, **event_args):
    val = self.drop_daily.selected_value
    if val is None:
      self.panel_input_daily.items = []
      self.btn_daily_edit.visible = False
      return
    inputs = anvil.server.call('get_report_inputs', "os_report_daily", val['id'])
    self.panel_input_daily.items = inputs
    self.btn_daily_edit.url = Globals.word_desktop_url(val['desktop_link'])
    self.btn_daily_edit.visible = bool(val['desktop_link'])

  @handle("drop_other", "change")
  def drop_other_change(self, **event_args):
    val = self.drop_other.selected_value
    if val is None:
      self.panel_input_other.items = []
      self.btn_other_edit.visible = False
      return
    inputs = anvil.server.call('get_report_inputs', "os_report_other", val['id'])
    self.panel_input_other.items = inputs
    self.btn_other_edit.url = Globals.word_desktop_url(val['desktop_link'])
    self.btn_other_edit.visible = bool(val['desktop_link'])

  @handle("btn_weekly_proof", "click")
  def btn_weekly_proof_click(self, **event_args):
    dialog = dlg_assign_proofer(details=self.drop_weekly.selected_value)
    result = alert(content=dialog,
                   title="Assign Proofer", large=True, buttons=[
                     ("Send", "Send"),
                     ("Cancel", "Cancel")
                   ])

    if result == "Send":
      link = self.drop_weekly.selected_value['link']
      hl_pipeline = self.drop_weekly.selected_value['hl_pipeline']
      anvil.server.call('send_email', dialog.drop_assign_to.selected_value, f"{dialog.txt_comment.text}\n\nDocument: {link}", hl_pipeline=hl_pipeline)

  @handle("btn_daily_proof", "click")
  def btn_daily_proof_click(self, **event_args):
    dialog = dlg_assign_proofer(details=self.drop_daily.selected_value)
    result = alert(content=dialog,
                   title="Assign Proofer", large=True, buttons=[
                     ("Send", "Send"),
                     ("Cancel", "Cancel")
                   ])

    if result == "Send":
      link = self.drop_daily.selected_value['link']
      hl_pipeline = self.drop_daily.selected_value['hl_pipeline']
      anvil.server.call('send_email', dialog.drop_assign_to.selected_value, f"{dialog.txt_comment.text}\n\nDocument: {link}", hl_pipeline=hl_pipeline)

  @handle("btn_other_proof", "click")
  def btn_other_proof_click(self, **event_args):
    dialog = dlg_assign_proofer(details=self.drop_other.selected_value)
    result = alert(content=dialog,
                   title="Assign Proofer", large=True, buttons=[
                     ("Send", "Send"),
                     ("Cancel", "Cancel")
                   ])

    if result == "Send":
      link = self.drop_other.selected_value['link']
      hl_pipeline = self.drop_other.selected_value['hl_pipeline']
      anvil.server.call('send_email', dialog.drop_assign_to.selected_value, f"{dialog.txt_comment.text}\n\nDocument: {link}", hl_pipeline=hl_pipeline)

  @handle("btn_weekly_process", "click")
  def btn_weekly_process_click(self, **event_args):
    if self.drop_weekly.selected_value is not None:
      full_record = anvil.server.call('get_document', 'os_report_weekly', self.drop_weekly.selected_value['id'])

      dialog = dlg_process(details=full_record)
      result = alert(content=dialog,
                    title="Process", large=True, buttons=[
                      ("Save", "Save"),
                      ("Cancel", "Cancel")
                    ])
      if result == "Save":
        fields_to_update = {}
        collection = "os_report_weekly"
  
        fields_to_update['title'] = dialog.txt_title.text
        fields_to_update['im_check'] = dialog.chk_im.checked
        fields_to_update['rcm_check'] = dialog.chk_rcm.checked
        fields_to_update['metadata'] = [tag for tag in dialog.txt_added_metadata.text.split(",") if tag]
        fields_to_update['hl_pipeline'] = dialog.chk_hl_pipeline.checked
        if dialog.chk_send_to_qc.checked:
          fields_to_update['status'] = "qc_check"
  
  
        anvil.server.call('process_report', collection, self.drop_weekly.selected_value['id'], fields_to_update)
  
        Globals.current_form.refresh_reports()

  @handle("btn_daily_process", "click")
  def btn_daily_process_click(self, **event_args):
    if self.drop_daily.selected_value is not None:
      full_record = anvil.server.call('get_document', 'os_report_daily', self.drop_daily.selected_value['id'])
      dialog = dlg_process(details=full_record)
      result = alert(content=dialog,
                    title="Process", large=True, buttons=[
                      ("Save", "Save"),
                      ("Cancel", "Cancel")
                    ])
      if result == "Save":
        fields_to_update = {}
        collection = "os_report_daily"
  
        fields_to_update['title'] = dialog.txt_title.text
        fields_to_update['im_check'] = dialog.chk_im.checked
        fields_to_update['rcm_check'] = dialog.chk_rcm.checked
        fields_to_update['metadata'] = [tag for tag in dialog.txt_added_metadata.text.split(",") if tag]
        fields_to_update['hl_pipeline'] = dialog.chk_hl_pipeline.checked
        if dialog.chk_send_to_qc.checked:
          fields_to_update['status'] = "qc_check"
  
  
        anvil.server.call('process_report', collection, self.drop_daily.selected_value['id'], fields_to_update)
  
        Globals.current_form.refresh_reports()

  @handle("btn_other_process", "click")
  def btn_other_process_click(self, **event_args):
    if self.drop_other.selected_value is not None:
      full_record = anvil.server.call('get_document', 'os_report_other', self.drop_other.selected_value['id'])
      dialog = dlg_process(details=full_record)
      result = alert(content=dialog,
                    title="Process", large=True, buttons=[
                      ("Save", "Save"),
                      ("Cancel", "Cancel")
                    ])
      if result == "Save":
        fields_to_update = {}
        collection = "os_report_other"
  
        fields_to_update['title'] = dialog.txt_title.text
        fields_to_update['im_check'] = dialog.chk_im.checked
        fields_to_update['rcm_check'] = dialog.chk_rcm.checked
        fields_to_update['metadata'] = [tag for tag in dialog.txt_added_metadata.text.split(",") if tag]
        fields_to_update['hl_pipeline'] = dialog.chk_hl_pipeline.checked
        if dialog.chk_send_to_qc.checked:
          fields_to_update['status'] = "qc_check"
  
  
        anvil.server.call('process_report', collection, self.drop_other.selected_value['id'], fields_to_update)
  
        Globals.current_form.refresh_reports()





