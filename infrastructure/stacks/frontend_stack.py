from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    CfnOutput,
    RemovalPolicy,
)
from constructs import Construct
import os


class FrontendStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, api_url: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # S3 bucket for static website hosting
        website_bucket = s3.Bucket(
            self,
            "WebsiteBucket",
            bucket_name=f"cassidy-frontend-{self.account}",
            website_index_document="index.html",
            website_error_document="index.html",  # SPA routing
            public_read_access=True,
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                block_public_policy=False,
                ignore_public_acls=False,
                restrict_public_buckets=False,
            ),
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # CloudFront distribution for HTTPS and caching
        distribution = cloudfront.Distribution(
            self,
            "WebsiteDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(website_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=None,
                ),
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=None,
                ),
            ],
        )

        # Deploy frontend build to S3
        frontend_path = os.path.join(os.path.dirname(__file__), "../../frontend/dist")
        
        # Create environment config file with API URL
        env_config = f"""window.ENV = {{
  REACT_APP_API_URL: "{api_url}"
}};"""
        
        # Read the original index.html and add env-config.js script
        import os
        index_html_path = os.path.join(frontend_path, "index.html")
        
        # Read the built index.html
        try:
            with open(index_html_path, 'r') as f:
                index_content = f.read()
                
            # Insert the env-config.js script before the main script
            modified_index = index_content.replace(
                '<script type="module" src="/src/main.tsx"></script>',
                '<script src="/env-config.js"></script>\n    <script type="module" src="/src/main.tsx"></script>'
            )
            
            # If the pattern wasn't found (built version), try the built pattern
            if modified_index == index_content:
                # Look for built script pattern (contains hash)
                import re
                modified_index = re.sub(
                    r'<script type="module" crossorigin src="[^"]*"></script>',
                    lambda m: f'<script src="/env-config.js"></script>\n    {m.group(0)}',
                    index_content
                )
                
        except FileNotFoundError:
            # If index.html doesn't exist yet, create a basic one
            modified_index = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Cassidy AI</title>
  </head>
  <body>
    <div id="root"></div>
    <script src="/env-config.js"></script>
  </body>
</html>"""
        
        s3deploy.BucketDeployment(
            self,
            "DeployWebsite",
            sources=[
                s3deploy.Source.asset(frontend_path),
                s3deploy.Source.data("env-config.js", env_config),
                s3deploy.Source.data("index.html", modified_index),
            ],
            destination_bucket=website_bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )

        # Outputs
        CfnOutput(
            self,
            "WebsiteURL",
            value=f"https://{distribution.distribution_domain_name}",
            description="CloudFront distribution URL",
        )

        CfnOutput(
            self,
            "S3WebsiteURL", 
            value=website_bucket.bucket_website_url,
            description="S3 static website URL",
        )

        CfnOutput(
            self,
            "BucketName",
            value=website_bucket.bucket_name,
            description="S3 bucket name",
        )