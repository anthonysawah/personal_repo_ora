#!/bin/ksh

#Set Oracle Environment Variables

export TWO_TASK=;

for instname in `cat /etc/oratab| grep -v "^#"|cut -f1 -d: -s`
do

    export ORACLE_SID=$instname
    ORACLE_HOME=`cat /etc/oratab | grep ^${ORACLE_SID}: | grep -v ^$ | cut -d":" -f 2 | grep -v ASM | uniq`
    export ORACLE_HOME
    export PATH=$ORACLE_HOME/bin:$PATH
    export LD_LIBRARY_PATH=${SAVE_LLP}:${ORACLE_HOME}/LD_LIBRARY_PATH

#Then connect to db
sqlplus '/ as sysdba' << eof
spool $1.log
set lines 300
set pages 50000
set echo on
set timing on
@$1
exit;
eof
done
