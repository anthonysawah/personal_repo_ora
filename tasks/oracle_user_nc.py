#!/usr/bin/python



import sys
import getopt
import json

__metaclass__ = type

# Read from ora_user.json

with open("ora_user.json") as jsonFile:
    data = json.load(jsonFile)
    jsonData = data["Users"]

# Generate SQL statement from ora_user.json

for user in data['Users']:
    createUsersql = 'create user ' +  (user['username'])
    createUsersql += ' identified by ' + '"' + (user['password']) + '"'
    if str(user['tablespace']) != "":
        createUsersql += ' default tablespace '  + (user['tablespace'])
    else: createUsersql += ' default tablespace USERS '
    if str(user['profile']) != "":
        createUsersql += ' profile  ' (user['profile'])
    else: createUsersql += ' profile DEFAULT'
 
# Write Grant SQL statements to sqlfile for execution

with open("create_user_" +(user['username']) + ".sql", "w") as outfile:
    outfile.write(createUsersql)
