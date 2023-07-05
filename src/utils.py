import os.path
from src.logger import logging
from src.exception import CustomException
import zipfile
import boto3
import json

cur_dir = os.path.curdir
zip_file_path = os.path.join(cur_dir, "zipfile.zip")

with open('config.json', 'r') as config_file:
    config = json.load(config_file)

region = config["region"]
boto3.setup_default_session(region_name=region)


def save_image_to_s3(image_data, user_name, filename):
    logging.info("Initializing: Upload zip to S3 bucket")
    try:
        s3_client = boto3.client('s3')

        s3_key = f"Images/{user_name}/{filename}"
        print(f"Inside save_image_s3: {s3_key}")
        s3_client.put_object(Body=image_data, Bucket="ineuron-img-dwnld", Key=s3_key)
        logging.info("Completed: Successfully uploaded zip to S3 bucket")
    except Exception as e:
        logging.error("Error occurred while uploading the zip file to S3")
        print(f"Error Occurred: {e}")


def zip_images_folder(folder_path, file_name):
    logging.info("Initializing: Compressing scrapped images to a single zip file")

    zip_filename = f"{file_name}.zip"
    try:
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.relpath(file_path, folder_path))
        logging.info("Completed: Successfully zipped images")
    except CustomException as e:
        logging.error("Error occurred while zipping the images")
        print(f"Error occurred: {e}")

    return zip_filename


def delete_files(folder_path):
    logging.info("Initializing: Deleting downloaded files")
    try:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    print(f"Deleted file: {file_path}")
                except CustomException as e:
                    logging.error(f"Error occurred while deleting a file: {file_path}")
                    print(f"Error Occurred: {e}")
        logging.info("Completed: Successfully deleted all files")
    except CustomException as e:
        logging.error(f"Error Occurred while deleting files: {e}")
        print(f"Error Occurred: {e}")
        raise CustomException


def is_email_verified(email_address):
    logging.info("Initializing: Verification of email address")
    try:
        ses_client = boto3.client('ses')
        response = ses_client.list_verified_email_addresses()
        verified_emails = response['VerifiedEmailAddresses']
        if email_address in verified_emails:
            logging.info("Completed: Email has been verified.")
            return True
        else:
            logging.info("Completed: Email is not verified.")
            return False
    except CustomException as e:
        logging.error(f"Error Occurred while verifying email address: {e}")
        print(f"Error Occurred: {e}")


def verify_email(email_address):
    logging.info("Initializing: Email verification process")
    try:
        ses_client = boto3.client("ses")

        response = ses_client.verify_email_address(
            EmailAddress=email_address,
        )
        logging.info("Completed: Send an email-verification mail to the user.")
    except CustomException as e:
        logging.error(f"Error occurred in the Email verification process. {e}")
        print(f"Error Occurred: {e}")
