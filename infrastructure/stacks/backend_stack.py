from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_rds as rds,
    aws_ec2 as ec2,
    aws_secretsmanager as secrets,
    aws_ssm as ssm,
    aws_logs as logs,
    aws_iam as iam,
    CfnOutput,
)
from constructs import Construct


class BackendStack(Stack):
    """Backend stack - NO VPC for Lambda, publicly accessible database"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Configuration
        self.app_name = "cassidy"
        self.app_environment = self.node.try_get_context("environment") or "prod"
        
        # Create database (publicly accessible, no VPC needed for Lambda)
        self.database = self._create_database()
        
        # Create parameter store values for configuration
        self._create_parameters()
        
        # Create Lambda function and API Gateway
        self.lambda_function = self._create_lambda_function()
        self.api_gateway = self._create_api_gateway()
        
        # Create outputs
        self._create_outputs()

    def _create_database(self) -> rds.DatabaseInstance:
        """Create publicly accessible RDS PostgreSQL database"""
        
        # Create minimal VPC just for database (required parameter)
        database_vpc = ec2.Vpc(
            self,
            "DatabaseVpc",
            vpc_name=f"{self.app_name}-db-vpc", 
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=2,
            nat_gateways=0,  # No NAT gateway needed for publicly accessible DB
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
            ],
        )
        
        # Create security group for database - allow all access since publicly accessible
        db_security_group = ec2.SecurityGroup(
            self,
            "DatabaseSecurityGroup", 
            vpc=database_vpc,
            description="Security group for publicly accessible database",
            allow_all_outbound=False,
        )
        
        # Allow PostgreSQL access from anywhere (since database is publicly accessible)
        db_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(5432),
            description="Allow PostgreSQL access from internet"
        )
        
        # Generate database password
        db_password = secrets.Secret(
            self,
            "DatabasePassword",
            description="Password for Cassidy database",
            generate_secret_string=secrets.SecretStringGenerator(
                secret_string_template='{"username": "cassidy"}',
                generate_string_key="password",
                exclude_characters=' %+~`#$&*()|[]{}:;<>?!\'/@"\\\\',
                password_length=32,
            ),
        )

        # Create database instance (publicly accessible, in default VPC)
        database = rds.DatabaseInstance(
            self,
            "Database",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO  # t3.micro
            ),
            allocated_storage=20,
            max_allocated_storage=100,
            storage_type=rds.StorageType.GP2,
            database_name="cassidy",
            credentials=rds.Credentials.from_secret(db_password),
            vpc=database_vpc,  # Required parameter - use minimal VPC
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_groups=[db_security_group],
            publicly_accessible=True,  # Allow access from internet
            backup_retention=Duration.days(7),
            deletion_protection=True,
            auto_minor_version_upgrade=True,
            multi_az=False,  # Single AZ for cost optimization
            storage_encrypted=True,
            monitoring_interval=Duration.seconds(0),
            enable_performance_insights=False,
            removal_policy=RemovalPolicy.SNAPSHOT,
        )

        return database

    def _create_parameters(self) -> None:
        """Create SSM parameters for application configuration"""
        
        # Application parameters
        parameters = {
            "app-name": self.app_name,
            "environment": self.app_environment,
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

    def _create_lambda_function(self) -> lambda_.Function:
        """Create Lambda function WITHOUT VPC for internet access"""
        
        # Create Lambda execution role
        lambda_role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AWSXRayDaemonWriteAccess"),
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

        # Create Lambda function with container deployment - NO VPC
        lambda_function = lambda_.Function(
            self,
            "CassidyFunction",
            runtime=lambda_.Runtime.FROM_IMAGE,  # Container deployment
            handler=lambda_.Handler.FROM_IMAGE,  # Handler defined in Dockerfile CMD
            code=lambda_.Code.from_asset_image("../backend"),
            architecture=lambda_.Architecture.X86_64,
            timeout=Duration.seconds(30),  # 30 seconds for AI operations
            memory_size=1024,  # Increased memory for pydantic-ai
            role=lambda_role,
            environment={
                "APP_ENV": "production",
                "CASSIDY_APP_NAME": f"{self.app_name}-api",
                "PYDANTIC_AI_SLIM": "true",
                "DATABASE_URL": f"postgresql+asyncpg://cassidy@{self.database.instance_endpoint.hostname}:5432/cassidy",
                "DB_SECRET_ARN": self.database.secret.secret_arn,
                "ANTHROPIC_API_KEY": "[REDACTED-API-KEY]",
                "ANTHROPIC_API_KEY_PARAM": f"/{self.app_name}/anthropic-api-key",
            },
            # NO VPC - Lambda runs in AWS managed VPC with full internet access
            log_retention=logs.RetentionDays.ONE_WEEK,
            tracing=lambda_.Tracing.ACTIVE,
        )

        return lambda_function

    def _create_api_gateway(self) -> apigateway.RestApi:
        """Create API Gateway with Lambda integration"""
        
        # Create API Gateway
        api = apigateway.RestApi(
            self,
            "CassidyApi",
            rest_api_name=f"{self.app_name}-api",
            description="Cassidy AI Journaling Assistant API",
            deploy_options=apigateway.StageOptions(
                stage_name="prod",
                throttling_rate_limit=1000,
                throttling_burst_limit=2000,
                logging_level=apigateway.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True,
            ),
        )

        # Create Lambda integration
        lambda_integration = apigateway.LambdaIntegration(
            self.lambda_function,
            proxy=True,
            allow_test_invoke=False,
        )

        # Add root path handler first
        api.root.add_method("ANY", lambda_integration)
        
        # Add proxy resource to catch all other paths
        api.root.add_proxy(
            default_integration=lambda_integration,
            any_method=True,
        )

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

        CfnOutput(
            self,
            "DatabaseEndpoint",
            value=self.database.instance_endpoint.hostname,
            description="RDS database endpoint",
        )

        CfnOutput(
            self,
            "LambdaFunctionName",
            value=self.lambda_function.function_name,
            description="Lambda function name",
        )