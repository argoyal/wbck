import boto3

from .base import BaseSource


class AwsSource(BaseSource):

    def __init__(self, config_data):
        super().__init__(config_data)
        s3_config = self.source_settings["s3"]
        self.AWS_KEY = s3_config.get("aws_key", "")
        self.AWS_SECRET = s3_config.get("aws_secret", "")
        self.AWS_PROFILE = s3_config.get("aws_profile", "")

        self.BUCKET_NAME = s3_config["bucket_name"]

    def _get_s3_client(self):
        if self.AWS_PROFILE:
            return boto3.Session(profile_name=self.AWS_PROFILE).client('s3')
        if self.AWS_KEY and self.AWS_SECRET:
            return boto3.client(
                's3',
                aws_access_key_id=self.AWS_KEY,
                aws_secret_access_key=self.AWS_SECRET
            )
        raise ValueError(
            "S3 configuration requires either 'aws_profile' or both 'aws_key' and 'aws_secret'."
        )

    def backup_data(self):
        """
        backs up data to the AWS s3 bucket as per configuration
        """

        self.generate_compressed_data()

        print("======================> Uploading file {} to bucket {}".format(
            self.zip_name, self.BUCKET_NAME))

        s3 = self._get_s3_client()
        s3.upload_file(self.zip_name, self.BUCKET_NAME, self.zip_name)

        self.perform_cleanup()


    def restore_data(self):
        """
        restores data from AWS s3 bucket as per configuration
        """

        print("======================> Downloading file {} from bucket {}".format(
            self.zip_name, self.BUCKET_NAME))

        s3 = self._get_s3_client()
        s3.download_file(self.BUCKET_NAME, self.zip_name, self.zip_name)

        self.extract_from_compressed_data()

        self.perform_cleanup()
