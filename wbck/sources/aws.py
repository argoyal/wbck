import boto3

from .base import BaseSource


class AwsSource(BaseSource):

    def __init__(self, config_data):
        super().__init__(config_data)
        self.AWS_KEY = self.source_settings["s3"]["aws_key"]
        self.AWS_SECRET = self.source_settings["s3"]["aws_secret"]

        self.BUCKET_NAME = self.source_settings["s3"]["bucket_name"]

    def backup_data(self):
        """
        backs up data to the AWS s3 bucket as per configuration
        """

        self.generate_compressed_data()

        print("======================> Uploading file {} to bucket {}".format(
            self.zip_name, self.BUCKET_NAME))

        s3 = boto3.client(
            's3',
            aws_access_key_id=self.AWS_KEY,
            aws_secret_access_key=self.AWS_SECRET
        )

        s3.upload_file(self.zip_name, self.BUCKET_NAME, self.zip_name)

        self.perform_cleanup()


    def restore_data(self):
        """
        restores data from AWS s3 bucket as per configuration
        """

        print("======================> Downloading file {} from bucket {}".format(
            self.zip_name, self.BUCKET_NAME))

        s3 = boto3.client(
            's3',
            aws_access_key_id=self.AWS_KEY,
            aws_secret_access_key=self.AWS_SECRET
        )

        s3.download_file(self.BUCKET_NAME, self.zip_name, self.zip_name)
        
        self.extract_from_compressed_data()

        self.perform_cleanup()
