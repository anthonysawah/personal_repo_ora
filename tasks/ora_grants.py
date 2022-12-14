# Loading a JSON File to a Python Dictionary
import json

# Read from ora_user.json
with open("ora_user.json") as jsonFile:
        data = json.load(jsonFile)
        jsonData = data["Users"]

# Generate SQL statement from ora_user.json

for grantData in data['Users']:
    if str(grantData['syspriv']) != "":
        print("Grant " + str(grantData['syspriv']), " to " + (grantData['username']) + ";")
    if str(grantData['object']) != "":
        print("Grant " + str(grantData['object_priv']) + " ON " + str(grantData['object']) + " to " + (grantData['username']) + ";")
grantsql = ("Grant " + str(grantData['object_priv']) + " ON " + str(grantData['object']) + " to " + (grantData['username']) + ";")

# Write Grant SQL statements to sqlfile for execution
with open("create_user_" +(grantData['username']) + ".sql", "w") as sqlfile:
    sqlfile.write(f'\n{grantsql}')