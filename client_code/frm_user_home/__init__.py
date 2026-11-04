from ._anvil_designer import frm_user_homeTemplate
from anvil import *
import anvil.server
import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from .. import Globals


class frm_user_home(frm_user_homeTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    super().__init__(**properties)

    # Get the user properties
    user_props = anvil.server.call('get_user_preferences')

    self.chk_priority_notify.checked = user_props['notify_priority']
    self.chk_routine_notify.checked = user_props['notify_routine']

    self.drop_default_team.items = Globals.sort_dropdown_items(Globals.teams)
    self.drop_default_team.selected_value = user_props['default_team']


  @handle("btn_save", "click")
  def btn_save_click(self, **event_args):
    anvil.server.call('modify_user_preferences', self.chk_routine_notify.checked,
                       self.chk_priority_notify.checked, self.drop_default_team.selected_value)
    Globals.default_team = self.drop_default_team.selected_value
