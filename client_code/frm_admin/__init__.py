from ._anvil_designer import frm_adminTemplate
from anvil import *
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.users
import anvil.server
from .. import Globals



class frm_admin(frm_adminTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)

    # Teams for the remove-team dropdown, loaded from Globals
    self.drop_team_remove.items = Globals.sort_dropdown_items(Globals.teams)

    self.drop_remove_tag.items = Globals.sort_dropdown_items(anvil.server.call('get_all_tags'))

    # We need to get all the data from the Users table to fill the boxes
    self._refresh_role_dropdowns('im', self.drop_user_im_add, self.drop_user_im_remove)
    self._refresh_role_dropdowns('qc', self.drop_user_qc_add, self.drop_user_qc_remove)
    self._refresh_role_dropdowns('optio', self.drop_user_optio_add, self.drop_user_optio_remove)
    self._refresh_role_dropdowns('admin', self.drop_user_admin_add, self.drop_user_admin_remove)

    # Get the report template names
    report_names = anvil.server.call('get_all_templates')
    self.txt_report_os.text = next((d["name"] for d in report_names if d["type"] == "os_report"), None)
    self.txt_report_spot.text = next((d["name"] for d in report_names if d["type"] == "spot_report"), None)
    self.txt_report_story.text = next((d["name"] for d in report_names if d["type"] == "story"), None)

    # Audit log pagination. log_cursors[i] is the "before_id" needed to fetch
    # page i; it's recorded the first time we page forward past it, so paging
    # back to an already-seen page reuses the recorded cursor instead of
    # re-deriving it.
    self.log_page_index = 0
    self.log_cursors = [None]
    self._load_log_page(0)

  def _refresh_role_dropdowns(self, role, drop_add, drop_remove):
    users_with_role, users_without_role = anvil.server.call('get_role_users', role)
    drop_add.items = Globals.sort_dropdown_items(users_without_role)
    drop_remove.items = Globals.sort_dropdown_items(users_with_role)

  def _toggle_role(self, role, drop_add, drop_remove, grant, btn):
    selected_value = drop_add.selected_value if grant else drop_remove.selected_value
    btn.enabled = False
    try:
      anvil.server.call('modify_user_role', selected_value, role, grant)
      self._refresh_role_dropdowns(role, drop_add, drop_remove)
    finally:
      btn.enabled = True

  def _load_log_page(self, index):
    entries = anvil.server.call('get_audit_logs', self.log_cursors[index], 20)

    self.log_page_index = index
    self.panel_audit_log.items = entries
    self.lbl_audit_log_empty.visible = len(entries) == 0

    has_next_page = len(entries) == 20
    if has_next_page and index + 1 == len(self.log_cursors):
      self.log_cursors.append(entries[-1]['_id'])

    self.btn_audit_log_prev.enabled = index > 0
    self.btn_audit_log_next.enabled = has_next_page

  @handle("btn_audit_log_prev", "click")
  def btn_audit_log_prev_click(self, **event_args):
    self._load_log_page(self.log_page_index - 1)

  @handle("btn_audit_log_next", "click")
  def btn_audit_log_next_click(self, **event_args):
    self._load_log_page(self.log_page_index + 1)

  @handle("btn_user_im_add", "click")
  def btn_user_im_add_click(self, **event_args):
    self._toggle_role("im", self.drop_user_im_add, self.drop_user_im_remove, True, self.btn_user_im_add)

  @handle("btn_user_im_remove", "click")
  def btn_user_im_remove_click(self, **event_args):
    self._toggle_role("im", self.drop_user_im_add, self.drop_user_im_remove, False, self.btn_user_im_remove)

  @handle("btn_user_qc_add", "click")
  def btn_user_qc_add_click(self, **event_args):
    self._toggle_role("qc", self.drop_user_qc_add, self.drop_user_qc_remove, True, self.btn_user_qc_add)

  @handle("btn_user_qc_remove", "click")
  def btn_user_qc_remove_click(self, **event_args):
    self._toggle_role("qc", self.drop_user_qc_add, self.drop_user_qc_remove, False, self.btn_user_qc_remove)

  @handle("btn_user_optio_add", "click")
  def btn_user_optio_add_click(self, **event_args):
    self._toggle_role("optio", self.drop_user_optio_add, self.drop_user_optio_remove, True, self.btn_user_optio_add)

  @handle("btn_user_optio_remove", "click")
  def btn_user_optio_remove_click(self, **event_args):
    self._toggle_role("optio", self.drop_user_optio_add, self.drop_user_optio_remove, False, self.btn_user_optio_remove)

  @handle("btn_user_admin_add", "click")
  def btn_user_admin_add_click(self, **event_args):
    self._toggle_role("admin", self.drop_user_admin_add, self.drop_user_admin_remove, True, self.btn_user_admin_add)

  @handle("btn_user_admin_remove", "click")
  def btn_user_admin_remove_click(self, **event_args):
    if self.drop_user_admin_remove.selected_value == Globals.user_email:
      if not confirm("You are about to remove your own admin role. Continue?"):
        return
    self._toggle_role("admin", self.drop_user_admin_add, self.drop_user_admin_remove, False, self.btn_user_admin_remove)

  @handle("btn_team_add", "click")
  def btn_team_add_click(self, **event_args):
    self.btn_team_add.enabled = False
    try:
      anvil.server.call('add_team', self.txt_team_add.text)
      self.txt_team_add.text = ""
      # Need to refresh Globals so other open forms pick up the new team
      Globals.teams = anvil.server.call('get_teams')
      self.drop_team_remove.items = Globals.sort_dropdown_items(Globals.teams)
    finally:
      self.btn_team_add.enabled = True

  @handle("btn_team_remove", "click")
  def btn_team_remove_click(self, **event_args):
    # Only removes the team from the teams list - any existing reports still
    # carry this team name and aren't deleted or reassigned, they just become
    # unreachable through the team-filtered dropdowns everywhere else in the app.
    self.btn_team_remove.enabled = False
    try:
      anvil.server.call('remove_team', self.drop_team_remove.selected_value)
      # Need to refresh Globals so other open forms pick up the removal
      Globals.teams = anvil.server.call('get_teams')
      self.drop_team_remove.items = Globals.sort_dropdown_items(Globals.teams)
    finally:
      self.btn_team_remove.enabled = True

  @handle("btn_spot_save", "click")
  def btn_spot_save_click(self, **event_args):
    anvil.server.call('save_template_location', 'spot_report', self.txt_report_spot.text)

  @handle("btn_os_save", "click")
  def btn_os_save_click(self, **event_args):
    anvil.server.call('save_template_location', 'os_report', self.txt_report_os.text)

  @handle("btn_story_save", "click")
  def btn_story_save_click(self, **event_args):
    anvil.server.call('save_template_location', 'story', self.txt_report_story.text)

  @handle("btn_add_tag", "click")
  def btn_add_tag_click(self, **event_args):
    self.btn_add_tag.enabled = False
    try:
      anvil.server.call('add_tag', self.txt_add_tag.text)
      self.txt_add_tag.text = ""
      self.drop_remove_tag.items = Globals.sort_dropdown_items(anvil.server.call('get_all_tags'))
    finally:
      self.btn_add_tag.enabled = True

  @handle("btn_remove_tag", "click")
  def btn_remove_tag_click(self, **event_args):
    self.btn_remove_tag.enabled = False
    try:
      anvil.server.call('remove_tag', self.drop_remove_tag.selected_value)
      self.drop_remove_tag.items = Globals.sort_dropdown_items(anvil.server.call('get_all_tags'))
    finally:
      self.btn_remove_tag.enabled = True
    
