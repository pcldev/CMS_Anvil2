from ._anvil_designer import dlg_assign_prooferTemplate
from anvil import *
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.users
import anvil.server
from .. import Globals


class dlg_assign_proofer(dlg_assign_prooferTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)
    self.drop_assign_to.items = Globals.sort_dropdown_items(Globals.all_users)

