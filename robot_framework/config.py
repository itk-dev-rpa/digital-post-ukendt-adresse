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
QUEUE_NAME = "Udtræk af Tilmelding til Digital Post Ukendt Adresse"
GRAPH_API = "Graph API"
EMAIL_STATUS_SENDER = "itk-rpa@mkb.aarhus.dk"
EMAIL_ATTACHMENT = "Ændringer på Tilmelding af Digital Post.xlsx"

DATABASE = "Driver={ODBC Driver 17 for SQL Server};Server=FaellesSQL;Trusted_Connection=yes;"
