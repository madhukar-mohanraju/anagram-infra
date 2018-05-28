'''
Created on 27-May-2018

@author: Madhukar
'''
import argparse
import logging
import subprocess
import shlex
import time
import json
#from os import environ
import sys
import random
import string
import boto3

my_logger = logging.getLogger('MyLogger')
my_logger.setLevel(logging.INFO)
cHandler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
cHandler.setFormatter(formatter)
my_logger.addHandler(cHandler)

#
#
def log(log_type,log_message):
    
    if log_type == "info":
        my_logger.info(log_message)
    elif log_type == "debug":
        my_logger.debug(log_message)
    elif log_type == "warn":
        my_logger.warning(log_message)
    elif log_type == "err":
        my_logger.error(log_message)
        my_logger.error("-"*120)
        sys.exit(1)

# Get the status of the CFN stack
# return value: CFN Stack status
def getCfnStackStatus(stack_name, region):
    
    try:
        client = boto3.client('cloudformation', region_name=region)
        response = client.describe_stacks(
            StackName=stack_name,
        )
        for x in response.iteritems():
            if x[0] == 'Stacks':
                stack_status = x[1][0]['StackStatus']
                #print(stack_status)
        if stack_status:
            return stack_status
        else:
            return 'unknown'

    except Exception,e:
        return 'unknown'

#
# 
def drop_cfn_stack(stack_name, region):
    try:
        cfn_cli = boto3.client('cloudformation', region_name=region)

        response = cfn_cli.delete_stack(
            StackName=stack_name,
        )
        #print(response)
        resp = response.get('ResponseMetadata')
        #print(resp)
        if resp is not None:
            http_code = resp.get('HTTPStatusCode')
            if http_code == 200:
                time.sleep(10)
                waiter = cfn_cli.get_waiter('stack_delete_complete')
                waiter.wait(
                    StackName=stack_name,
                )
                return (True, '')
            else:
                return (False, 'Invalid response code <{0}>'.format(http_code))
        else:
            return (False, 'Deletion of stack <{0}> in region <{1}> failed'.format(stack_name, region))

    except Exception as e:
        return (False, str(e))

#
#
def executeCfnTemplate(env, stack_name, region, url):
    
    try:
        stack_status = getCfnStackStatus(stack_name, region)
        if stack_status == 'ROLLBACK_COMPLETE':
            return (False, 'Existing Stack Status is Invalid')
        
        # call the CFN template. the template folder is workspace_dir.
        client = boto3.client('cloudformation', region_name=region)
        with open(workspace_dir +'/stack.yaml') as f:
            response = client.create_stack(
                StackName=stack_name,
                TemplateBody=f.read(),
                Parameters=[
                    {
                        'ParameterKey': 'Environment',
                        'ParameterValue': env,
                    },
                    {
                        'ParameterKey': 'Region',
                        'ParameterValue': region.replace('-','').upper(),
                    },
                    {
                        'ParameterKey': 'DNS',
                        'ParameterValue': url,
                    },                            
                ],
            )        
        # check the response code of the above code. if 200 then success. 
        # check if stack is in CREATE_IN_PROGRESS. if yes,then wait till CREATE_COMPLETE else throw error.
        resp = response.get('ResponseMetadata')
        if resp is not None:
            http_code = resp.get('HTTPStatusCode')
            if http_code == 200:
                time.sleep(10)
                stack_status = getCfnStackStatus(stack_name, region)
                if stack_status == 'CREATE_IN_PROGRESS':
                    waiter = client.get_waiter('stack_create_complete')
                    waiter.wait(
                        StackName=stack_name,
                    )
                    stack_status = getCfnStackStatus(stack_name, region)
                    if stack_status == 'CREATE_COMPLETE':
                        return (True, '')
                    else:
                        return (False, 'Stack creation timed out')
                else:
                    return (False, 'Created Stack Status is Invalid: {0}'.format(stack_status))
            else:
                return (False, 'Invalid Response code: {0}'.format(http_code))

    except Exception,e:
        return (False, str(e))

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--env', help='environment', choices=['test', 'integ', 'prod'], required=True)
    parser.add_argument('--stack_name', help='cfn stack name', required=True)
    parser.add_argument('--region', help='cluster region', required=True)
    parser.add_argument('--url', help='route53 aurora url', required=False)
    #parser.add_argument('--tags', help='tags in json string', type=json.loads, required=False)
    parser.add_argument('--workspace', help='workspace directory', required=True)
    parser.add_argument('--delete', help='delete stack', required=False, action="store_true")
    
    args = parser.parse_args()    
    
    env = args.env.upper()
    stack_name = args.stack_name
    region = args.region
    r53_url = args.url
    workspace_dir = args.workspace
    delete_flag = args.delete

    if not delete_flag:
        log("info", "Creating stack: <{0}> in region: <{1}>".format(stack_name, region))
        return_status,return_err = executeCfnTemplate(env, stack_name, region, r53_url)
        if not return_status:
            log("err", "Creating stack: Failed\n{0}".format(return_err))
        else:
            log("info", "Creating stack: Succeeded")
    
    else:
        log("info", "Deleting stack: <{0}> in region: <{1}>".format(stack_name, region))
        return_status,return_err = drop_cfn_stack(stack_name, region)
        if not return_status:
            log("err", "Deleting stack: Failed\n{0}".format(return_err))
        else:
            log("info", "Deleting stack: Succeeded")        
    