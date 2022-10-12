#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2014 Mikael Sandström <oravirt@gmail.com>
# Copyright: (c) 2021, Ari Stark <ari.stark@netcourrier.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)    
import sys
import getopt
import json

__metaclass__ = type

DOCUMENTATION = '''
module: oracle_user_nc
short_description: Manages Oracle user/schema.
'''

EXAMPLES = '''
- name: Create a new schema on a remote db by running the module on the controlmachine
  oracle_user_nc:
    hostname: "remote-db-server"
    service_name: "orcl"
    username: "system"
    password: "manager"
    schema_name: "myschema"
    schema_password: "mypass"
    default_tablespace: "test"
    state: "present"

'''

RETURN = '''
ddls:
    description: Ordered list of DDL requests executed during module execution.
    returned: always
    type: list
    elements: str
'''

###Uncomment for argumentative execution:
### Example: python3 oracle_user_nc.py -u myusername -pw mypw -d default

""" 

    
def myfunc(argv):
        arg_username = ""
        arg_password = ""
        arg_profile = ""
        arg_default_tablespace = ""
        arg_expired = ""
        arg_help = "{0} -u <username> -pw <password> -p <profile> -d default_tablespace (optional) -e expired (optional)".format(argv[0])
    
        try:
            opts, args = getopt.getopt(argv[1:], "h:u:P:p:d:e:", ["help", "username=", "password=", "profile=" ,"default_tablespace=" ,"expired="])
        except:
            print(arg_help)
            sys.exit(2)
        
        for opt, arg in opts:
            if opt in ("-h", "--help"):
                print(arg_help)  # print the help message
                sys.exit(2)
            elif opt in ("-u", "--username"):
                arg_username = arg
            elif opt in ("-pw", "--password"):
                arg_password = arg
            elif opt in ("-p", "--profile"):
                arg_profile = arg
            elif opt in ("-d", "--default_tablespace"):
                arg_default_tablespace = arg
            elif opt in ("-e", "--expired"):
                arg_expired = arg
 
 

 
        sql = 'create user %s ' % arg_username
#        if authentication_type == 'external':
#            sql += 'identified externally '
#        elif authentication_type == 'global':
#            sql += 'identified globally '
#        elif authentication_type == 'password':
        sql += 'identified by %s ' % arg_password
        if arg_default_tablespace:
            sql += 'default tablespace %s quota unlimited on %s ' % (arg_default_tablespace, arg_default_tablespace)
        if arg_profile:
            sql += 'profile %s ' % arg_profile
        if arg_expired == 'TRUE':
            sql += 'password expire '
            
        f = open('%s_creation.sql' % arg_username, "w")
        f.write(sql + ';')
        f.close()
        #print('%s_creation.sql' % arg_username,)
        print(sql+';') 
    
if __name__ == '__main__':
    myfunc(sys.argv)"""


with open("/Users/tonysawah/.ansible/plugins/modules/test.json") as jsonFile:
    data = json.load(jsonFile)
    jsonData = data["Users"]

for user in data['Users']:
    sql = 'create user ' +  (user['username'])
    sql += ' identified by ' + '"' + (user['password']) + '"'
    if str(user['tablespace']) != "":
        sql += ' default tablespace '  + (user['tablespace'])
    else: sql += ' default tablespace USERS '
    if str(user['profile']) != "":
        sql += ' profile %s ' % (user['profile'])
    else: sql += ' profile DEFAULT'
 #   sql += ';'
    print("'EXECUTE IMMEDIATE '" + sql + "';")

"""        sql = 'create user %s ' % arg_username
#        if authentication_type == 'external':
#            sql += 'identified externally '
#        elif authentication_type == 'global':
#            sql += 'identified globally '
#        elif authentication_type == 'password':
        sql += 'identified by %s ' % arg_password
        if arg_default_tablespace:
            sql += 'default tablespace %s quota unlimited on %s ' % (arg_default_tablespace, arg_default_tablespace)
        if arg_profile:
            sql += 'profile %s ' % arg_profile
        if arg_expired == 'TRUE':
            sql += 'password expire '
            
        f = open('%s_creation.sql' % arg_username, "w")
        f.write(sql + ';')
        f.close()
        #print('%s_creation.sql' % arg_username,)
        print(sql+';') """
    
#if __name__ == '__main__':
#    myfunc(sys.argv)

