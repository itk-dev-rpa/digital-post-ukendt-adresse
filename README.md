# Udtræk af tilmelding til Digital Post (Ukendt adresse)

From a list of people without a known address, the robot checks for registrations of Digital Post and NemSMS, sending a list of current status and changes to a list of recipients, set in process variables. If the citizen has registered NemSMS, the robot will send two SMS's, one in english and one in danish, to get the citizen to call us.

## Process Variables

This robot requires the following process variables set in OpenOrchestrator:
```
'{"service_cvr":"YOUR_CVR", , "data_recipient":"email1@mail.dk;en_anden_email@åbenpostbud.dk"}'
```
