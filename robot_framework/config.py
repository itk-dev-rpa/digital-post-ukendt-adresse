"""This module contains configuration constants used across the framework"""

# The number of times the robot retries on an error before terminating.
MAX_RETRY_COUNT = 3

# Whether the robot should be marked as failed if MAX_RETRY_COUNT is reached.
FAIL_ROBOT_ON_TOO_MANY_ERRORS = True

# Error screenshot config
SMTP_SERVER = "smtp.aarhuskommune.local"
SMTP_PORT = 25
SCREENSHOT_SENDER = "robot@friend.dk"

# Constant/Credential names
ERROR_EMAIL = "Error Email"
KEYVAULT_CREDENTIALS = "Keyvault"
KEYVAULT_URI = "Keyvault URI"
KEYVAULT_PATH = "Digital_Post_Ukendt_Adresse"

# Process specific values
CVR = "55133018"
QUEUE_NAME = "Udtræk af Tilmelding til Digital Post Ukendt Adresse"
GRAPH_API = "Graph API"
EMAIL_STATUS_SENDER = "itk-rpa@mkb.aarhus.dk"
EMAIL_ATTACHMENT = "Ændringer på Tilmelding af Digital Post.xlsx"
EMAIL_SUBJECT = "RPA: Udtræk om Tilmelding til Digital Post (ukendt adresse)"
EMAIL_BODY = """Robotten har nu udtrukket information om tilmelding til digital post for borgere med ukendt adresse.

Vedhæftet denne mail finder du et excel-ark, som indeholder CPR-numre på borgere med ændringer i deres tilmeldingsstatus for digital post og/eller NemSMS. Arket viser, hvilke services borgeren er tilmeldt.

Følgende borgere har fået tilsendt en SMS:
{SMS_SENT}

Mvh. ITK RPA"""
SMS_HEADER = "Aarhus Kommune"
SMS_TEXT_DA = "Har du læst vores brev i din digitale postkasse vedrørende din bopælsregistrering? Du kan kontakte os på tlf. 89 40 41 60. Med venlig hilsen Aarhus Kommune."
SMS_TEXT_EN = "Did you read our letter in your public mailbox (borger.dk) about your residence registration? You can contact us at 89 40 41 60. Best regards Aarhus Kommune."
