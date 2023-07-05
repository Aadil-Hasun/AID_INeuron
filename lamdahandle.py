import boto3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def lambda_handler(event, context):
    bucket_name = "ineuron-img-dwnld"
    print(event)
    user_name = event['user_name']
    user_email = event['user_email']
    zipfile_name = event['zipfile_name']
    rule_name = event['rule_name']
    object_key = "Images/" + user_name + "/" + zipfile_name
    # get download link
    download_link = get_s3_download_link(bucket_name, object_key)

    ses_client = boto3.client('ses')
    # Create a message container
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'AID: Download Link For Your Scrapped Data'
    msg['From'] = 'aadilhasun@gmail.com'
    msg['To'] = user_email

    # Create the HTML body
    html_body = f"""
    <html>
        <body>
            <p>Hi User,</p>
            <p>Please click the following link to download your data:</p>
            <p><a href="{download_link}">Download Your Data</a></p>
            <p><em>Please note that this link is valid for 1 hour only.</em></p>
        </body>
    </html>
    """

    # Attach the HTML body to the message
    msg.attach(MIMEText(html_body, 'html'))

    # Convert the message to a raw string
    raw_message = msg.as_string()

    # Send the email
    response = ses_client.send_raw_email(
        Source=msg['From'],
        Destinations=[msg['To']],
        RawMessage={'Data': raw_message}
    )

    remove_targets_from_rule(rule_name)

    delete_event_rule(rule_name)


def get_s3_download_link(bucket_name, object_key):
    s3_client = boto3.client('s3')
    params = {'Bucket': bucket_name, 'Key': object_key}
    # Generate a presigned URL with a limited time validity (e.g., 1 hour)
    presigned_url = s3_client.generate_presigned_url('get_object', Params=params, ExpiresIn=3600)
    return presigned_url


def delete_event_rule(rule_name):
    client = boto3.client('events')
    response = client.delete_rule(Name=rule_name)
    print(f"Event rule '{rule_name}' deleted successfully.")


def remove_targets_from_rule(rule_name):
    client = boto3.client('events')

    response = client.list_targets_by_rule(Rule=rule_name)
    targets = response['Targets']

    for target in targets:
        target_id = target['Id']
        client.remove_targets(Rule=rule_name, Ids=[target_id])

