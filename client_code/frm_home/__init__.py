from ._anvil_designer import frm_homeTemplate
from anvil import *
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.users
import anvil.server
from anvil.designer import in_designer
import anvil.users
from .. import Globals


class frm_home(frm_homeTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)
    self.content_panel.clear()



  
    if not in_designer:

      # Teams/users/reviewers/tags are populated at login (see
      # frm_login._complete_login), since not every role lands on this form.

      # Want to set visibility of forms based on permissions
      user_role = Globals.user_role

      if user_role.get('admin') is True:
        self.lnk_admin.visible = True
      else:
        self.lnk_admin.visible = False

      if user_role.get('im') is True:
        self.lnk_im.visible = True
      else:
        self.lnk_im.visible = False

      if user_role.get('qc') is True:
        self.lnk_qc.visible = True
      else:
        self.lnk_qc.visible = False

      if user_role.get('optio') is True:
        self.lnk_optio.visible = True
      else:
        self.lnk_optio.visible = False


  # Nav links get a 'selected' role on click; every link's "show" event calls
  # this first so only the one just clicked ends up highlighted.
  def reset_links(self, **event_args):
    self.lnk_im.role = 'title'
    self.lnk_optio.role = 'title'
    self.lnk_qc.role = 'title'
    self.lnk_admin.role = 'title'
    self.lnk_search.role = 'title'
    
  @handle("lnk_im", "click")
  def lnk_im_click(self, **event_args):
    open_form('frm_im')
    self.lnk_im.role = 'selected'

  @handle("lnk_qc", "click")
  def lnk_qc_click(self, **event_args):
    open_form('frm_qc')
    self.lnk_qc.role = 'selected'

  @handle("lnk_optio", "click")
  def lnk_optio_click(self, **event_args):
    open_form('frm_optio')
    self.lnk_optio.role = 'selected'

  @handle("lnk_search", "click")
  def lnk_search_click(self, **event_args):
    open_form('frm_search')
    self.lnk_search.role = 'selected'

  @handle("lnk_im", "show")
  def lnk_im_show(self, **event_args):
    self.reset_links()

  @handle("lnk_qc", "show")
  def lnk_qc_show(self, **event_args):
    self.reset_links()

  @handle("lnk_optio", "show")
  def lnk_optio_show(self, **event_args):
    self.reset_links()

  @handle("lnk_search", "show")
  def lnk_search_show(self, **event_args):
    self.reset_links()

  @handle("lnk_admin", "show")
  def lnk_admin_show(self, **event_args):
    self.reset_links()

  @handle("lnk_admin", "click")
  def lnk_admin_click(self, **event_args):
    open_form('frm_admin')
    self.lnk_admin.role = 'selected'

  @handle("lnk_user_home", "click")
  def lnk_user_home_click(self, **event_args):
    open_form('frm_user_home')



  