import anvil.files
from anvil.files import data_files
import anvil.users
import anvil.secrets
import anvil.server
import html
import mongo
from mailersend import MailerSendClient, EmailBuilder


@anvil.server.callable(require_user=True)
def send_email(recipient, text, subject="Task assigned from CMS", hl_pipeline=False):
  mongo.require_any_role()

  if not recipient:
    raise Exception("No recipient email address provided")

  if not mongo.is_known_user(recipient):
    # Keeps this from being usable as an open relay to arbitrary external
    # addresses - recipients must be an existing user of this app.
    raise Exception(f"{recipient!r} is not a recognised user of this app")

  if not mongo.wants_notification(recipient, hl_pipeline):
    return

  requester = anvil.users.get_user()['email']
  text = f"{text}\n\nRequested by: {requester}"

  ms = MailerSendClient(api_key=anvil.secrets.get_secret('MAILER_SEND'))

  email = (EmailBuilder()
    .from_email("cms@praetorianconnections.com", "CMS")
    .to_many([{"email": recipient}])
    .subject(subject)
    .html(f"<h5>{html.escape(text)}</h5>")
    .text(text)
    .build())

  ms.emails.send(email)