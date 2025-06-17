"""
Fixed Lambda-based CDK Stack for Cassidy AI Journaling Assistant
Serverless architecture with proper VPC networking for Lambda internet access
"""
import os
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
)
from constructs import Construct


class CassidyLambdaStackFixed(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Configuration
        self.app_name = "cassidy"
        self.app_environment = self.node.try_get_context("environment") or "prod"
        
        # Create VPC with public subnets for Lambda and private subnets for database
        self.vpc = self._create_vpc()
        
        # Create VPC endpoints for AWS services
        self._create_vpc_endpoints()
        
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
        """Create VPC with public subnets for Lambda and private subnets for database"""
        return ec2.Vpc(
            self,
            "CassidyVpc",
            vpc_name=f"{self.app_name}-vpc",
            ip_addresses=ec2.IpAddresses.cidr("10.1.0.0/16"),  # Non-conflicting CIDR
            max_azs=2,  # Minimize costs with 2 AZs
            nat_gateways=0,  # No NAT gateway to save costs
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,  # 10.1.0.0/24, 10.1.1.0/24
                ),
                ec2.SubnetConfiguration(
                    name="Database",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,  # 10.1.2.0/24, 10.1.3.0/24
                ),
            ],
            enable_dns_hostnames=True,
            enable_dns_support=True,
        )

    def _create_vpc_endpoints(self) -> None:
        """Create VPC endpoints for AWS services access from private subnets"""
        
        # Security group for VPC endpoints
        vpc_endpoint_sg = ec2.SecurityGroup(
            self,
            "VpcEndpointSecurityGroup",
            vpc=self.vpc,
            description="Security group for VPC endpoints",
            allow_all_outbound=False,
        )
        
        # Allow HTTPS traffic from Lambda subnets
        vpc_endpoint_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS from VPC"
        )
        
        # Store the VPC endpoint security group for later use
        self.vpc_endpoint_sg = vpc_endpoint_sg
        
        # Secrets Manager VPC endpoint
        self.vpc.add_interface_endpoint(
            "SecretsManagerEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[vpc_endpoint_sg],
        )

    def _create_database(self) -> rds.DatabaseInstance:
        """Create RDS PostgreSQL database with security best practices"""
        
        # Create security group for Lambda
        lambda_security_group = ec2.SecurityGroup(
            self,
            "LambdaSecurityGroup",
            vpc=self.vpc,
            description="Security group for Cassidy Lambda function",
            allow_all_outbound=True,  # Lambda needs outbound for API calls to Anthropic
        )
        
        # Create security group for database
        db_security_group = ec2.SecurityGroup(
            self,
            "DatabaseSecurityGroup",
            vpc=self.vpc,
            description="Security group for Cassidy database",
            allow_all_outbound=False,
        )
        
        # Allow Lambda to access database
        db_security_group.add_ingress_rule(
            peer=lambda_security_group,
            connection=ec2.Port.tcp(5432),
            description="Allow Lambda access to PostgreSQL"
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

        # Create database instance
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
            vpc=self.vpc,
            subnet_group=db_subnet_group,
            security_groups=[db_security_group],
            backup_retention=Duration.days(7),
            deletion_protection=True,
            auto_minor_version_upgrade=True,
            multi_az=False,  # Single AZ for cost optimization
            publicly_accessible=False,
            storage_encrypted=True,
            monitoring_interval=Duration.seconds(0),
            enable_performance_insights=False,
            removal_policy=RemovalPolicy.SNAPSHOT,
        )

        # Store Lambda security group for reuse
        self.lambda_security_group = lambda_security_group

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

        # Create Lambda function with container deployment
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
            # CRITICAL FIX: Lambda in public subnets for internet access
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_groups=[self.lambda_security_group],
            allow_public_subnet=True,  # Required for public subnet placement
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

        # FIXED: Add root path handler first
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