"""
Lambda-based CDK Stack for Cassidy AI Journaling Assistant
Serverless architecture with API Gateway + Lambda + RDS
"""
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_ec2 as ec2,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_rds as rds,
    aws_ssm as ssm,
    aws_secretsmanager as secrets,
    aws_iam as iam,
    aws_logs as logs,
    aws_certificatemanager as acm,
    aws_route53 as route53,
)
from constructs import Construct


class CassidyLambdaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Configuration
        self.app_name = "cassidy"
        self.app_environment = self.node.try_get_context("environment") or "prod"
        self.domain_name = self.node.try_get_context("domain_name")  # Optional
        
        # Create VPC with minimal resources for cost optimization
        self.vpc = self._create_vpc()
        
        # Create RDS PostgreSQL database
        self.database = self._create_database()
        
        # Create parameter store values for configuration
        self._create_parameters()
        
        # Create Lambda function and API Gateway
        self.lambda_function = self._create_lambda_function()
        self.api_gateway = self._create_api_gateway()
        
        # Create outputs
        self._create_outputs()

    def _create_vpc(self) -> ec2.Vpc:
        """Create VPC with database subnets only (no NAT gateway needed for Lambda)"""
        return ec2.Vpc(
            self,
            "CassidyVpc",
            vpc_name=f"{self.app_name}-vpc",
            max_azs=2,  # Minimize costs with 2 AZs
            nat_gateways=0,  # No NAT gateway needed for Lambda
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Database",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
            enable_dns_hostnames=True,
            enable_dns_support=True,
        )

    def _create_database(self) -> rds.DatabaseInstance:
        """Create RDS PostgreSQL database with security best practices"""
        
        # Create security group for database
        db_security_group = ec2.SecurityGroup(
            self,
            "DatabaseSecurityGroup",
            vpc=self.vpc,
            description="Security group for Cassidy database",
            allow_all_outbound=False,
        )

        # Create database subnet group
        db_subnet_group = rds.SubnetGroup(
            self,
            "DatabaseSubnetGroup",
            description="Subnet group for Cassidy database",
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
        )

        # Generate database password
        db_password = secrets.Secret(
            self,
            "DatabasePassword",
            description="Password for Cassidy database",
            generate_secret_string=secrets.SecretStringGenerator(
                secret_string_template='{"username": "cassidy"}',
                generate_string_key="password",
                exclude_characters=' %+~`#$&*()|[]{}:;<>?!\'/@"\\',
                password_length=32,
            ),
        )

        # Create database instance (smaller for Lambda use case)
        database = rds.DatabaseInstance(
            self,
            "Database",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO  # t3.micro
            ),
            allocated_storage=20,  # Minimum 20 GB
            max_allocated_storage=100,  # Auto-scaling up to 100 GB
            storage_type=rds.StorageType.GP2,
            database_name="cassidy",
            credentials=rds.Credentials.from_secret(db_password),
            vpc=self.vpc,
            subnet_group=db_subnet_group,
            security_groups=[db_security_group],
            backup_retention=Duration.days(7),
            deletion_protection=True,
            auto_minor_version_upgrade=True,
            multi_az=False,  # Single AZ for cost optimization
            publicly_accessible=False,
            storage_encrypted=True,
            monitoring_interval=Duration.seconds(0),  # Disable enhanced monitoring
            enable_performance_insights=False,  # Disable for cost optimization
            removal_policy=RemovalPolicy.SNAPSHOT,
        )

        # Store database secret ARN in Parameter Store
        ssm.StringParameter(
            self,
            "DatabaseSecretArn",
            parameter_name=f"/{self.app_name}/database/secret-arn",
            string_value=db_password.secret_arn,
        )

        return database

    def _create_parameters(self) -> None:
        """Create SSM parameters for application configuration"""
        
        # Application parameters
        parameters = {
            "app-name": self.app_name,
            "environment": self.app_environment,
            "cors-origins": "https://yourdomain.com",  # Update this
            "jwt-algorithm": "HS256",
            "jwt-access-token-expire-hours": "24",
            "debug": "false",
            "anthropic-default-model": "claude-sonnet-4-20250514",
            "anthropic-structuring-model": "claude-sonnet-4-20250514",
        }

        for key, value in parameters.items():
            ssm.StringParameter(
                self,
                f"Parameter{key.replace('-', '').title()}",
                parameter_name=f"/{self.app_name}/{key}",
                string_value=value,
            )

        # Reference existing secure SSM parameters (managed outside CDK)
        # Parameters should be created manually or through separate process
        # For example: aws ssm put-parameter --name "/cassidy/jwt-secret-key" --value "your-secret" --type "SecureString"
        secure_parameter_names = {
            "jwt-secret-key": f"/{self.app_name}/jwt-secret-key",
            "anthropic-api-key": f"/{self.app_name}/anthropic-api-key",
        }

    def _create_lambda_function(self) -> lambda_.Function:
        """Create Lambda function for the API"""
        
        # Create Lambda execution role
        lambda_role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaVPCAccessExecutionRole"),
            ],
        )

        # Grant Lambda access to SSM parameters and secrets
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "ssm:GetParametersByPath",
                ],
                resources=[
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter/{self.app_name}/*"
                ],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                ],
                resources=[
                    self.database.secret.secret_arn
                ],
            )
        )

        # Create Lambda function with container deployment for pydantic-ai compatibility
        lambda_function = lambda_.Function(
            self,
            "CassidyFunction",
            function_name=f"{self.app_name}-api-container",  # New name for container deployment
            runtime=lambda_.Runtime.FROM_IMAGE,
            handler=lambda_.Handler.FROM_IMAGE,
            code=lambda_.Code.from_asset_image("../backend"),
            timeout=Duration.seconds(30),  # 30 seconds for AI operations
            memory_size=1024,  # Increased memory for pydantic-ai
            role=lambda_role,
            environment={
                "APP_ENV": "production",
                "CASSIDY_APP_NAME": f"{self.app_name}-api-container",
                "PYDANTIC_AI_SLIM": "true",  # Use slim version
            },
            # Removed VPC configuration - Lambda doesn't need VPC for this use case
            log_retention=logs.RetentionDays.ONE_WEEK,
            tracing=lambda_.Tracing.ACTIVE,  # Enable X-Ray tracing
        )

        # Note: Lambda is not in VPC, so it will use SQLite in /tmp
        # Database connectivity would require VPC configuration

        return lambda_function

    def _create_lambda_security_group(self) -> ec2.SecurityGroup:
        """Create security group for Lambda function"""
        return ec2.SecurityGroup(
            self,
            "LambdaSecurityGroup",
            vpc=self.vpc,
            description="Security group for Cassidy Lambda function",
            allow_all_outbound=True,  # Lambda needs outbound for API calls to Anthropic
        )

    def _create_api_gateway(self) -> apigateway.RestApi:
        """Create API Gateway with Lambda integration"""
        
        # Create API Gateway
        api = apigateway.RestApi(
            self,
            "CassidyApi",
            rest_api_name=f"{self.app_name}-api",
            description="Cassidy AI Journaling Assistant API",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=["http://cassidy-frontend-1748872354.s3-website-us-east-1.amazonaws.com"],  # ✅ SPECIFIC DOMAIN ONLY
                allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                allow_headers=["Content-Type", "Authorization"],
                allow_credentials=True,  # ✅ ENABLE CREDENTIALS FOR SECURE COOKIES
            ),
            deploy_options=apigateway.StageOptions(
                stage_name="prod",
                throttling_rate_limit=1000,  # Requests per second
                throttling_burst_limit=2000,  # Burst capacity
                logging_level=apigateway.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True,
            ),
        )

        # Create Lambda integration
        lambda_integration = apigateway.LambdaIntegration(
            self.lambda_function,
            proxy=True,  # Proxy all requests to Lambda
            allow_test_invoke=False,
        )

        # Add proxy resource to catch all paths
        api.root.add_proxy(
            default_integration=lambda_integration,
            any_method=True,
        )

        # Set up custom domain if provided
        if self.domain_name:
            certificate = acm.Certificate(
                self,
                "Certificate",
                domain_name=f"api.{self.domain_name}",
                validation=acm.CertificateValidation.from_dns(),
            )

            domain = api.add_domain_name(
                "CustomDomain",
                domain_name=f"api.{self.domain_name}",
                certificate=certificate,
            )

            # Create Route53 record if hosted zone exists
            try:
                hosted_zone = route53.HostedZone.from_lookup(
                    self, "HostedZone", domain_name=self.domain_name
                )
                route53.ARecord(
                    self,
                    "ApiRecord",
                    zone=hosted_zone,
                    record_name="api",
                    target=route53.RecordTarget.from_alias(domain),
                )
            except:
                # Hosted zone doesn't exist, skip DNS setup
                pass

        return api

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs"""
        
        api_url = f"https://{self.api_gateway.rest_api_id}.execute-api.{self.region}.amazonaws.com/prod"
        
        CfnOutput(
            self,
            "ApiUrl",
            value=api_url,
            description="API Gateway URL",
        )

        if self.domain_name:
            CfnOutput(
                self,
                "CustomDomainUrl",
                value=f"https://api.{self.domain_name}",
                description="Custom domain URL",
            )

        CfnOutput(
            self,
            "DatabaseEndpoint",
            value=self.database.instance_endpoint.hostname,
            description="RDS database endpoint",
        )

        CfnOutput(
            self,
            "DatabaseName",
            value="cassidy",
            description="RDS database name",
        )

        CfnOutput(
            self,
            "LambdaFunctionName",
            value=self.lambda_function.function_name,
            description="Lambda function name",
        )