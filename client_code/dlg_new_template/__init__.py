from ._anvil_designer import dlg_new_templateTemplate
from anvil import *
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.users
import anvil.server
from .. import Globals


# (component_name, label) for every field required to create a template.
# txt_country and chk_alert are intentionally excluded: they are optional.
REQUIRED_FIELDS = [
  ("drop_type", "Type"),
  ("drop_team", "Team"),
  ("txt_name", "File Name"),
  ("txt_title", "Title"),
  ("drop_assign_to", "Assign To"),
  ("drop_im_reviewer", "IM Reviewer"),
  ("drop_qc_reviewer", "QC Reviewer"),]


class dlg_new_template(dlg_new_templateTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)

    self.drop_type.items = Globals.sort_dropdown_items(self.drop_type.items)
    self.drop_assign_to.items = Globals.sort_dropdown_items(Globals.all_users)
    self.drop_im_reviewer.items = Globals.sort_dropdown_items(Globals.im_reviewers)
    self.drop_qc_reviewer.items = Globals.sort_dropdown_items(Globals.qc_reviewers)
    self.drop_team.items = Globals.sort_dropdown_items(Globals.teams)

  def get_missing_fields(self):
    """Return the labels of any required fields that are still empty."""
    missing = []
    for component_name, label in REQUIRED_FIELDS:
      component = getattr(self, component_name)
      value = component.text if isinstance(component, TextBox) else component.selected_value
      if not value:
        missing.append(label)
    return missing
