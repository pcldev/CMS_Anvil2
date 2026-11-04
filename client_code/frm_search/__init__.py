from ._anvil_designer import frm_searchTemplate
from anvil import *
import anvil.server
import anvil.users
from .. import Globals


class frm_search(frm_searchTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)

    Globals.current_form = self  # store reference to this form

    self._last_query = ""
    self.panel_search_results.items = []

  def run_search(self, query):
    self._last_query = query
    query = query.strip()

    if not query:
      self.panel_search_results.items = []
      self.lbl_empty_search.text = "Search for a story by name, title, country, assignee or team."
      self.lbl_empty_search.visible = True
      return

    results = anvil.server.call('search_stories', query)
    self.panel_search_results.items = results
    self.lbl_empty_search.text = "No stories found."
    self.lbl_empty_search.visible = len(results) == 0

  def refresh_results(self, **event_args):
    self.run_search(self._last_query)

  @handle("btn_search", "click")
  def btn_search_click(self, **event_args):
    self.run_search(self.txt_search.text or "")

  @handle("txt_search", "pressed_enter")
  def txt_search_pressed_enter(self, **event_args):
    self.run_search(self.txt_search.text or "")
