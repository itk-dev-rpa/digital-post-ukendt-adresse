"""This module contains the main process of the robot."""

import os
import json
from io import BytesIO
from typing import List, Tuple
import hashlib

from openpyxl import Workbook
import pyodbc

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from itk_dev_shared_components.smtp import smtp_util
from python_serviceplatformen import digital_post
from python_serviceplatformen.authentication import KombitAccess

from robot_framework import config


def process(orchestrator_connection: OrchestratorConnection) -> None:
    """ Do the primary process of the robot."""
    orchestrator_connection.log_trace("Running process.")
    process_arguments = json.loads(orchestrator_connection.process_arguments)

    # Prepare access to service platform
    kombit_access = KombitAccess(process_arguments["service_cvr"], process_arguments["certificate_path"], True)

    # Receive queue item list of people who weren't registered last time
    queue_elements = orchestrator_connection.get_queue_elements(config.QUEUE_NAME)

    # Find current list of people with unknown address and get their registration status for Digital Post
    query = "SELECT * FROM [DWH].[Mart].[AdresseAktuel] WHERE Vejkode = 9901 AND Myndighed = 751"
    current_status = get_registration_status_from_query(kombit_access, config.DATABASE, query)
    changes = []

    # Check status of people who are registered against people who weren't registered before
    for row in queue_elements:
        data = json.loads(row.data)
        current_value = current_status.get(row.reference, None)
        if current_value:
            # If a change has occured since last run, update queue element and prepare to send line to case worker
            if current_value["digital_post"] != data["digital_post"] or current_value["nemsms"] != data["nemsms"]:
                orchestrator_connection.delete_queue_element(row.id)
                orchestrator_connection.create_queue_element(config.QUEUE_NAME, reference=row.reference, data=json.dumps({"digital_post": current_value["digital_post"], "nemsms": current_value["nemsms"]}))
                changes.append([current_value["cpr"], current_value["digital_post"], current_value["nemsms"]])
            current_status.pop(row.reference)
        else:
            orchestrator_connection.delete_queue_element(row.id)

    # Send an email with list of people whose status has changed
    if len(changes) > 0:
        return_sheet = write_data_to_output_excel(changes)
        _send_status_email(process_arguments["data_recipient"], return_sheet)

    # Add queue elements for elements that didn't exists before
    for key, current_value in current_status.items():
        orchestrator_connection.create_queue_element(config.QUEUE_NAME, reference=key, data=json.dumps({"digital_post": current_value["digital_post"], "nemsms": current_value["nemsms"]}))


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


def encrypt_data(cpr, first_name) -> str:
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
        "RPA: Udtræk om Tilmelding til Digital Post",
        "Robotten har nu udtrukket information om tilmelding til digital post i den forespurgte liste.\n\nVedhæftet denne mail finder du et excel-ark, som indeholder CPR-numre på navngivne borgere med ændringer i deres tilmeldingsstatus for digital post og/eller NemSMS. Arket viser, hvilke services borgeren er tilmeldt.\n\n Mvh. ITK RPA",
        config.SMTP_SERVER,
        config.SMTP_PORT,
        False,
        [smtp_util.EmailAttachment(file, config.EMAIL_ATTACHMENT)]
    )


def get_registration_status_from_query(kombit_access: KombitAccess, sql_connection: str, query: str) -> dict[str, dict[str, bool]]:
    """Make an SQL request against a database and lookup their registration status.

    Args:
        kombit_access: Access token for Kombit

    Returns:
        A dictionary of encrypted CPRs containing a dictionary with:
            - Status for registration on Digital Post and NemSMS
            - An unencrypted CPR to add to response email if changes are found
    """
    connection = pyodbc.connect(sql_connection)
    cursor = connection.cursor()
    cursor.execute(query)

    status_list = {}
    for row in cursor:
        post = digital_post.is_registered(cpr=row.CPR, service="digitalpost", kombit_access=kombit_access)
        nemsms = digital_post.is_registered(cpr=row.CPR, service="nemsms", kombit_access=kombit_access)
        encrypted_id = encrypt_data(row.CPR, row.Fornavn)
        status_list[encrypted_id] = {"digital_post": post, "nemsms": nemsms, "cpr": row.CPR}
    return status_list


if __name__ == '__main__':
    conn_string = os.getenv("OpenOrchestratorConnString")
    crypto_key = os.getenv("OpenOrchestratorKey")
    mail = input("Please enter your email to receive a test response:\n")
    PROCESS_VARIABLES = f'{{"service_cvr": "55133018", "certificate_path": "{r"c:\\tmp\\serviceplatformen_test.pem"}", "data_recipient": "{mail}"}}'
    oc = OrchestratorConnection("Udtræk Tilmelding Digital Post", conn_string, crypto_key, PROCESS_VARIABLES)
    process(oc)
