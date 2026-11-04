from ._anvil_designer import RowTemplate3Template
from anvil import *
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.users
import anvil.server
from .. import Globals


class RowTemplate3(RowTemplate3Template):
  # Item template for panel_priority (high-priority disseminated reports).
  # Identical logic to RowTemplate4 (panel_routine), but dg_priority and
  # dg_routine have independently-generated column ids, so merging these
  # would mean realigning both DataGrids' column definitions too.
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)

    Globals.setup_doc_link(self.lnk_document, self.item)

  @handle("btn_disseminated", "click")
  def btn_disseminated_click(self, **event_args):
    if not confirm(f"Mark \"{self.item['name']}\" as disseminated?", title="Disseminated"):
      return

    self.btn_disseminated.enabled = False
    try:
      collection = Globals.collection_for_type(self.item['type'])

      anvil.server.call('modify_document', collection, self.item['_id'], {'status': 'Completed'})

      Globals.current_form.refresh_reports()
    finally:
      self.btn_disseminated.enabled = True

