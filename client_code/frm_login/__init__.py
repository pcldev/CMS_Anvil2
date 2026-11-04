from ._anvil_designer import frm_loginTemplate
from anvil import *
import anvil.server
import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from anvil.designer import in_designer
from .. import Globals
import anvil.saml.auth


class frm_login(frm_loginTemplate):
  def __init__(self, **properties):
    self.init_components(**properties)
    if not in_designer:
      if anvil.users.get_user():
        # Returning from SAML redirect or active session
        card    = self.dom_nodes['login_card']
        loading = self.dom_nodes['login_loading']
        btn     = self.dom_nodes['btn_signin']
        try:
          self._complete_login()
        finally:
          card.style.display   = ''
          loading.style.display = ''
          btn.disabled = False

  def btn_signin_click(self, event):
    card    = self.dom_nodes['login_card']
    loading = self.dom_nodes['login_loading']
    btn     = self.dom_nodes['btn_signin']

    btn.disabled         = True
    card.style.display   = 'none'
    loading.style.display = 'flex'

    try:
      anvil.users.login_with_saml()
    except Exception as e:
      card.style.display   = ''
      loading.style.display = ''
      btn.disabled = False
      anvil.server.call('log_login_failure', str(e))
      alert("Sign-in failed. Please try again or contact support.")
      return

    try:
      self._complete_login()
    finally:
      card.style.display   = ''
      loading.style.display = ''
      btn.disabled = False

  def _complete_login(self):
    user_email = anvil.users.get_user()['email']
    Globals.user_email = user_email
    db_user = anvil.server.call('get_user')
    if db_user is None:
      display_name = self._get_display_name(user_email)
      new_user_role = anvil.server.call('create_user', display_name)
      Globals.user_role = new_user_role
    else:
      Globals.user_role = db_user['roles']
      Globals.default_team = db_user.get('default_team')

    # Populate shared lookup data before routing - whichever form the user
    # lands on (frm_im/frm_qc/frm_optio/frm_home) may need it immediately,
    # and not every role lands on frm_home to pick it up there. Bundled into
    # one call so the client pays for one round trip, not five.
    bootstrap_data = anvil.server.call('get_login_bootstrap_data')
    Globals.teams = bootstrap_data['teams']
    Globals.all_users = bootstrap_data['all_users']
    Globals.im_reviewers = bootstrap_data['im_reviewers']
    Globals.qc_reviewers = bootstrap_data['qc_reviewers']
    Globals.all_tags = bootstrap_data['all_tags']

    open_form(self._default_form())

  def _default_form(self):
    # Route straight to the highest-priority view the user has access to,
    # instead of landing on frm_home with an empty main_slot.
    role = Globals.user_role
    if role.get('im'):
      return 'frm_im'
    if role.get('qc'):
      return 'frm_qc'
    if role.get('optio'):
      return 'frm_optio'
    return 'frm_home'

  def _get_display_name(self, user_email):
    # SAML IdPs vary in whether/how they send this claim, and some libraries
    # return a single-valued attribute as a bare string rather than a list.
    # Fall back to the email address so a Mongo profile always gets created.
    user_attributes = anvil.saml.auth.get_user_attributes() or {}
    claim = user_attributes.get('http://schemas.microsoft.com/identity/claims/displayname')
    if isinstance(claim, list):
      return claim[0] if claim else user_email
    return claim or user_email
