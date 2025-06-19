"""This module contains the main process of the robot."""

import os
import json
from io import BytesIO
from typing import List, Tuple
import hashlib
from requests.exceptions import HTTPError
from dataclasses import dataclass

from openpyxl import Workbook
import pyodbc
from hvac import Client

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from itk_dev_shared_components.smtp import smtp_util
from python_serviceplatformen import digital_post
from python_serviceplatformen.authentication import KombitAccess
from python_serviceplatformen.models.message import create_nemsms, Sender, Recipient

from robot_framework import config


@dataclass
class RegistrationStatus:
    """Data class representing registration status for Digital Post and NemSMS services.

    Attributes:
        digital_post: Whether the user is registered for Digital Post service.
        nemsms: Whether the user is registered for NemSMS service.
        cpr: The unencrypted CPR number for the user.
    """
    digital_post: bool
    nemsms: bool
    cpr: str


def process(orchestrator_connection: OrchestratorConnection) -> None:
    """ Do the primary process of the robot."""
    orchestrator_connection.log_trace("Running process.")
    process_arguments = json.loads(orchestrator_connection.process_arguments)

    # Access Keyvault
    vault_auth = orchestrator_connection.get_credential(config.KEYVAULT_CREDENTIALS)
    vault_uri = orchestrator_connection.get_constant(config.KEYVAULT_URI).value
    vault_client = Client(vault_uri)
    token = vault_client.auth.approle.login(role_id=vault_auth.username, secret_id=vault_auth.password)
    vault_client.token = token['auth']['client_token']

    # Get certificate
    read_response = vault_client.secrets.kv.v2.read_secret_version(mount_point='rpa', path=config.KEYVAULT_PATH, raise_on_deleted_version=True)
    certificate = read_response['data']['data']['cert']

    # Because KombitAccess requires a file, we save and delete the certificate after we use it
    certificate_path = "certificate.pem"
    with open(certificate_path, 'w', encoding='utf-8') as cert_file:
        cert_file.write(certificate)

    # Prepare access to service platform
    kombit_access = KombitAccess(config.CVR, certificate_path)

    # Receive queue item list of people who weren't registered last time
    queue_elements = orchestrator_connection.get_queue_elements(config.QUEUE_NAME, limit=99999999)

    # Find current list of people with unknown address and get their registration status for Digital Post
    current_status = get_registration_status_from_query(kombit_access, orchestrator_connection, config.DATABASE)
    changes = []

    # Check status of people who are registered on last run against people who weren't registered before
    for row in queue_elements:
        if not row.data:
            continue
        last_registration = json.loads(row.data)
        current_registration = current_status.get(row.reference, None)
        if current_registration:
            # If person is still in the database of unknown addresses, update the queue element.
            orchestrator_connection.delete_queue_element(row.id)
            orchestrator_connection.create_queue_element(
                config.QUEUE_NAME,
                reference=row.reference,
                data=json.dumps(
                    {"digital_post": current_registration.digital_post,
                     "nemsms": current_registration.nemsms}
                )
            )
            # If status has changed since last run, add data to return excel.
            if current_registration.digital_post != last_registration["digital_post"] or current_registration.nemsms != last_registration["nemsms"]:
                changes.append(
                    [current_registration.cpr,
                     status_from_bool(current_registration.digital_post, last_registration["digital_post"]),
                     status_from_bool(current_registration.nemsms, last_registration["nemsms"])]
                )
                if current_registration.nemsms:
                    send_sms(kombit_access, current_registration.cpr)
            current_status.pop(row.reference)
        else:
            orchestrator_connection.delete_queue_element(row.id)

    # Add queue elements for registrations that didn't exists before
    for key, current_registration in current_status.items():
        orchestrator_connection.create_queue_element(config.QUEUE_NAME,
                                                     reference=key,
                                                     data=json.dumps({"digital_post": current_registration.digital_post,
                                                                      "nemsms": current_registration.nemsms}))
        if current_registration.digital_post or current_registration.nemsms:
            changes.append([current_registration.cpr + " (ny)",
                           status_from_bool(current_registration.digital_post, last_registration["digital_post"]),
                           status_from_bool(current_registration.nemsms, last_registration["nemsms"])])

        # If citizen is registered with NemSMS, send them an SMS
        if current_registration.nemsms:
            send_sms(kombit_access, current_registration.cpr)

    # Send an email with list of people whose status has changed
    if len(changes) > 0:
        return_sheet = write_data_to_output_excel(changes)
        _send_status_email(process_arguments["data_recipient"].split(";"), return_sheet)


def send_sms(kombit_access: KombitAccess, recipient: str):
    """Send an SMS to the CPR recipient.

    Args:
        kombit_access: Access token for Kombit.
        recipient: CPR of citizen to recieve SMS.
    """
    sender = Sender(senderID=config.CVR, idType="CVR", label="Aarhus Kommune")
    recipient = Recipient(recipientID=recipient, idType="CPR")
    message = create_nemsms(config.SMS_HEADER, config.SMS_TEXT_DA, sender, recipient)
    digital_post.send_message("NemSMS", message, kombit_access)
    message = create_nemsms(config.SMS_HEADER, config.SMS_TEXT_EN, sender, recipient)
    digital_post.send_message("NemSMS", message, kombit_access)


def status_from_bool(current_status: bool, previous_status: bool) -> str:
    """Return a text describing status of registration and whether it has changed

    Args:
        current_status: Current status of registration
        previous_status: Previous status of registration
    Return:
        A text describing registration status as either Tilmeldt (registered) or Ikke Tilmeldt (not registered)"""

    status = "Tilmeldt" if current_status else "Ikke Tilmeldt"
    if previous_status != current_status:
        status += " (ændret)"
    return status


def write_data_to_output_excel(data: List[Tuple[str, bool, bool]]) -> BytesIO:
    """ Add data to excel sheet.

    Args:
        data: A list of tuples with cpr, status for digital post and nem sms
        target_sheet: A sheet with id's in the first row
    """
    wb = Workbook()
    ws = wb.active
    ws.append(["CPR", "Digital Post", "NemSMS"])

    for row in data:
        ws.append(row)

    excel_buffer = BytesIO()
    wb.save(excel_buffer)
    excel_buffer.seek(0)

    return excel_buffer


def encrypt_data(cpr: str, first_name: str) -> str:
    """Take CPR and first name from citizen and encrypt using the name as salt.

    Args:
        cpr: CPR of the citizen.
        first_name: First name of the citizen.
    """
    salted_data = f"{cpr}{first_name}"
    hash_obj = hashlib.sha256(salted_data.encode())
    return hash_obj.hexdigest()


def _send_status_email(recipient: str, file: BytesIO):
    """ Send an email to the requesting party and to the controller.

    Args:
        email: The email that has been processed.
    """
    smtp_util.send_email(
        recipient,
        config.EMAIL_STATUS_SENDER,
        config.EMAIL_SUBJECT,
        config.EMAIL_BODY,
        config.SMTP_SERVER,
        config.SMTP_PORT,
        False,
        [smtp_util.EmailAttachment(file, config.EMAIL_ATTACHMENT)]
    )


def get_registration_status_from_query(
    kombit_access: KombitAccess, 
    orchestrator_connection: OrchestratorConnection, 
    sql_connection: str
) -> dict[str, RegistrationStatus]:
    """Execute SQL query against database and lookup registration status for each user.

    Args:
        kombit_access: Access token for Kombit API authentication
        orchestrator_connection: Connection object for error logging
        sql_connection: Database connection string

    Returns:
        Dictionary mapping encrypted CPR numbers to RegistrationStatus objects

    Raises:
        pyodbc.Error: If database connection or query execution fails
    """
    query = config.REGISTRATION_QUERY
    connection = pyodbc.connect(sql_connection)
    cursor = connection.cursor()
    cursor.execute(query)

    status_dict: dict[str, RegistrationStatus] = {}

    for row in cursor:
        try:
            # Fetch registration status from external services
            post = digital_post.is_registered(
                id_=row.CPR,
                service="digitalpost",
                kombit_access=kombit_access
            )
            nemsms = digital_post.is_registered(
                id_=row.CPR,
                service="nemsms",
                kombit_access=kombit_access
            )
            
            # Create RegistrationStatus data object
            status = RegistrationStatus(
                digital_post=post,
                nemsms=nemsms,
                cpr=row.CPR
            )
            
            # Use encrypted CPR as dictionary key
            encrypted_id = encrypt_data(row.CPR, row.Fornavn)
            status_dict[encrypted_id] = status
            
        except HTTPError as e:
            orchestrator_connection.log_error(f"Failed to fetch registration status for CPR {row.CPR}: {e.response.text}")
    return status_dict


if __name__ == '__main__':
    conn_string = os.getenv("OpenOrchestratorConnString")
    crypto_key = os.getenv("OpenOrchestratorKey")
    mail = input("Please enter your email to receive a test response:\n")
    PROCESS_VARIABLES = f'{{"service_cvr": "55133018", "data_recipient": "{mail}"}}'
    oc = OrchestratorConnection("Udtræk Tilmelding Digital Post", conn_string, crypto_key, PROCESS_VARIABLES)
    process(oc)
