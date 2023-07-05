import boto3
from datetime import datetime
import json

from src.logger import logging
from src.exception import CustomException


def create_cloudwatch_event_rule(zipfile_name, user_name, schedule_time, user_email):
    logging.info("Initializing: Event scheduling process initiated.")

    try:
        with open('config.json', 'r') as config_file:
            config = json.load(config_file)

        region = config['region']
        current_datetime = datetime.now()
        rule_name = f"ISER-{current_datetime.strftime('%Y%m%d%H%M%S')}"
        boto3.setup_default_session(region_name=region)
        client = boto3.client('events')
        lambda_client = boto3.client('lambda')

        event_pattern = {
            "detail": {
                "user_name": ["wizard"],
                "user_email": ["aadilhasun.i@gmail.com"],
                "rule_name": ["ISER-alaiteio93"],
                "zipfile_name": ["test.zip"]
            }
        }

        function_arn = config['function_arn']
        function_name = config['function_name']

        input_transformer = {
            "InputPathsMap": {
                "name": "$.detail.event_name"
            },
            "InputTemplate": f"{{\"user_name\": \"{user_name}\", \"user_email\": \"{user_email}\", \"rule_name\": \"{rule_name}\", \"zipfile_name\": \"{zipfile_name}\"}}"
        }
        response = client.put_rule(
            Name=rule_name,
            ScheduleExpression=f'cron({schedule_time})',
            EventPattern=json.dumps(event_pattern),
            State='ENABLED'
        )
        logging.info("Step 1 Completed: Successfully created an EventBridge rule with the specified time.")
        rule_arn = response['RuleArn']

        response_lambda = lambda_client.add_permission(
            FunctionName=function_name,
            StatementId='EventBridgeInvokePermission' + rule_name,
            Action='lambda:InvokeFunction',
            Principal='events.amazonaws.com',
            SourceArn=rule_arn
        )

        logging.info("Step 2 Completed: Successfully added Invoke permission on the rule for the lambda function")
        # Create the target for the rule
        target_response = client.put_targets(
            Rule=rule_name,
            Targets=[
                {
                    'Id': '1',
                    'Arn': function_arn,
                    'InputTransformer': {
                        'InputPathsMap': input_transformer['InputPathsMap'],
                        'InputTemplate': input_transformer['InputTemplate']
                    }
                }
            ]
        )

        logging.info("Step 3 completed: Successfully added the lambda function as target to the EventBridge rule")
        print(target_response)
        return rule_arn

    except CustomException as e:
        logging.error(f"Error Occurred while scheduling an EventBridge for the Lambda function. {e}")
        print(f"Error Occurred: {e}")
