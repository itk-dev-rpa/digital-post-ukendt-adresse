"""This module contains the main process of the robot."""

import os
import json
from io import BytesIO
from typing import List, Tuple
import hashlib
from requests.exceptions import HTTPError

from openpyxl import Workbook
import pyodbc
from hvac import Client

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from itk_dev_shared_components.smtp import smtp_util
from python_serviceplatformen import digital_post
from python_serviceplatformen.authentication import KombitAccess
from python_serviceplatformen.models.message import create_nemsms, Sender, Recipient

from robot_framework import config


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
    certificate_path = "C:\\tmp\\Certificate.pem"  # TODO: Don't
    with open(certificate_path, 'w', encoding='utf-8') as cert_file:
        cert_file.write(certificate)

    # Prepare access to service platform
    kombit_access = KombitAccess(config.CVR, certificate_path, True)

    # Receive queue item list of people who weren't registered last time
    queue_elements = orchestrator_connection.get_queue_elements(config.QUEUE_NAME, limit=99999999)

    # Find current list of people with unknown address and get their registration status for Digital Post
    current_status = get_registration_status_from_query(kombit_access, orchestrator_connection, config.DATABASE)
    changes = []

    # Check status of people who are registered against people who weren't registered before
    for row in queue_elements:
        if not row.data:
            continue
        data = json.loads(row.data)
        current_value = current_status.get(row.reference, None)
        if current_value:
            # If person is still in the database of unknown addresses, update the queue element.
            orchestrator_connection.delete_queue_element(row.id)
            orchestrator_connection.create_queue_element(
                config.QUEUE_NAME,
                reference=row.reference,
                data=json.dumps(
                    {"digital_post": current_value["digital_post"],
                     "nemsms": current_value["nemsms"]}
                )
            )
            # If status has changed since last run, add data to return excel.
            if current_value["digital_post"] != data["digital_post"] or current_value["nemsms"] != data["nemsms"]:
                changes.append(
                    [current_value["cpr"],
                     status_from_bool(current_value["digital_post"], data["digital_post"]),
                     status_from_bool(current_value["nemsms"], data["nemsms"])]
                )
            current_status.pop(row.reference)
        else:
            orchestrator_connection.delete_queue_element(row.id)

    # Add queue elements for elements that didn't exists before
    for key, current_value in current_status.items():
        orchestrator_connection.create_queue_element(config.QUEUE_NAME,
                                                     reference=key,
                                                     data=json.dumps({"digital_post": current_value["digital_post"],
                                                                      "nemsms": current_value["nemsms"]}))
        digital_post_status = current_value["digital_post"]
        nem_sms_status = current_value["nemsms"]
        if digital_post_status or nem_sms_status:
            changes.append([current_value["cpr"] + " (ny)",
                           status_from_bool(digital_post_status, digital_post_status),
                           status_from_bool(nem_sms_status, nem_sms_status)])

        # If citizen is registered with both SMS and DigitalPost, and one of them is new, send them an SMS
        if digital_post_status and nem_sms_status:
            sender = Sender(senderID=config.CVR, idType="CVR", label="Aarhus Kommune")
            recipient = Recipient(recipientID=current_value["cpr"], idType="CPR")
            message = create_nemsms(config.SMS_HEADER, config.SMS_TEXT, sender, recipient)
            digital_post.send_message("NemSMS", message, kombit_access)

    # Send an email with list of people whose status has changed
    if len(changes) > 0:
        return_sheet = write_data_to_output_excel(changes)
        _send_status_email(process_arguments["data_recipient"].split(";"), return_sheet)


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


def get_registration_status_from_query(kombit_access: KombitAccess, orchestrator_connection: OrchestratorConnection, sql_connection: str) -> dict[str, dict[str, bool]]:
    """Make an SQL request against a database and lookup their registration status.

    Args:
        kombit_access: Access token for Kombit
        sql_connection: Connection string for database

    Returns:
        A dictionary of encrypted CPRs containing a dictionary with:
            - Status for registration on Digital Post and NemSMS
            - An unencrypted CPR to add to response email if changes are found
    """
    query = "SELECT TOP 25 * FROM [DWH].[Mart].[AdresseAktuel] WHERE Vejkode = 9901 AND Myndighed = 751"
    connection = pyodbc.connect(sql_connection)
    cursor = connection.cursor()
    cursor.execute(query)

    status_list = {}
    for row in cursor:
        try:
            post = digital_post.is_registered(id_=row.CPR, service="digitalpost", kombit_access=kombit_access)
            nemsms = digital_post.is_registered(id_=row.CPR, service="nemsms", kombit_access=kombit_access)
            encrypted_id = encrypt_data(row.CPR, row.Fornavn)
            status_list[encrypted_id] = {"digital_post": post, "nemsms": nemsms, "cpr": row.CPR}
        except HTTPError as e:
            orchestrator_connection.log_error(f"An error occured: {e.response.text}")
    return status_list


if __name__ == '__main__':
    conn_string = os.getenv("OpenOrchestratorConnString")
    crypto_key = os.getenv("OpenOrchestratorKey")
    mail = input("Please enter your email to receive a test response:\n")
    PROCESS_VARIABLES = f'{{"service_cvr": "55133018", "data_recipient": "{mail}"}}'
    oc = OrchestratorConnection("Udtræk Tilmelding Digital Post", conn_string, crypto_key, PROCESS_VARIABLES)
    process(oc)
