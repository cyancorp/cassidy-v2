"""
Main CDK Stack for Cassidy AI Journaling Assistant
Minimal, secure, cost-effective AWS deployment
"""
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_rds as rds,
    aws_ssm as ssm,
    aws_secretsmanager as secrets,
    aws_iam as iam,
    aws_logs as logs,
    aws_certificatemanager as acm,
    aws_route53 as route53,
    aws_elasticloadbalancingv2 as elbv2,
)
from constructs import Construct


class CassidyStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Configuration
        self.app_name = "cassidy"
        self.environment = self.node.try_get_context("environment") or "prod"
        self.domain_name = self.node.try_get_context("domain_name")  # Optional
        
        # Create VPC with minimal resources for cost optimization
        self.vpc = self._create_vpc()
        
        # Create RDS PostgreSQL database
        self.database = self._create_database()
        
        # Create parameter store values for configuration
        self._create_parameters()
        
        # Create ECS cluster and service
        self.ecs_service = self._create_ecs_service()
        
        # Create outputs
        self._create_outputs()

    def _create_vpc(self) -> ec2.Vpc:
        """Create VPC with public and private subnets"""
        return ec2.Vpc(
            self,
            "CassidyVpc",
            vpc_name=f"{self.app_name}-vpc",
            max_azs=2,  # Minimize costs with 2 AZs
            nat_gateways=1,  # Single NAT gateway for cost optimization
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
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

        # Create database instance
        database = rds.DatabaseInstance(
            self,
            "Database",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15_4
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO  # t3.micro for cost optimization
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
            monitoring_interval=Duration.seconds(60),
            enable_performance_insights=False,  # Disable for cost optimization
            removal_policy=RemovalPolicy.SNAPSHOT,
            parameter_group=rds.ParameterGroup.from_parameter_group_name(
                self, "DefaultParameterGroup", "default.postgres15"
            ),
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
            "environment": self.environment,
            "cors-origins": "https://yourdomain.com",  # Update this
            "jwt-algorithm": "HS256",
            "jwt-access-token-expire-hours": "24",
            "debug": "false",
            "anthropic-default-model": "claude-sonnet-4-20250514",
            "anthropic-structuring-model": "claude-sonnet-4-20250514",
            "api-host": "0.0.0.0",
            "api-port": "8000",
        }

        for key, value in parameters.items():
            ssm.StringParameter(
                self,
                f"Parameter{key.replace('-', '').title()}",
                parameter_name=f"/{self.app_name}/{key}",
                string_value=value,
            )

        # Secure parameters (stored as SecureString)
        secure_parameters = {
            "jwt-secret-key": "CHANGE_THIS_IN_PRODUCTION_TO_RANDOM_256_BIT_KEY",
            "anthropic-api-key": "YOUR_ANTHROPIC_API_KEY_HERE",
        }

        for key, value in secure_parameters.items():
            ssm.StringParameter(
                self,
                f"SecureParameter{key.replace('-', '').title()}",
                parameter_name=f"/{self.app_name}/{key}",
                string_value=value,
                type=ssm.ParameterType.SECURE_STRING,
            )

    def _create_ecs_service(self) -> ecs_patterns.ApplicationLoadBalancedFargateService:
        """Create ECS Fargate service with Application Load Balancer"""
        
        # Create ECS cluster
        cluster = ecs.Cluster(
            self,
            "Cluster",
            vpc=self.vpc,
            cluster_name=f"{self.app_name}-cluster",
            enable_fargate_capacity_providers=True,
        )

        # Create task execution role
        execution_role = iam.Role(
            self,
            "TaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
            ],
        )

        # Create task role with necessary permissions
        task_role = iam.Role(
            self,
            "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        # Grant task role access to SSM parameters and secrets
        task_role.add_to_policy(
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

        task_role.add_to_policy(
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

        # Create log group
        log_group = logs.LogGroup(
            self,
            "LogGroup",
            log_group_name=f"/ecs/{self.app_name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create Fargate service with ALB
        service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "Service",
            cluster=cluster,
            service_name=f"{self.app_name}-service",
            cpu=256,  # 0.25 vCPU for cost optimization
            memory_limit_mib=512,  # 512 MB RAM for cost optimization
            desired_count=1,  # Single instance for cost optimization
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_registry("nginx"),  # Placeholder, will be updated
                container_port=8000,
                task_role=task_role,
                execution_role=execution_role,
                log_driver=ecs.LogDrivers.aws_logs(
                    stream_prefix="cassidy",
                    log_group=log_group,
                ),
                environment={
                    "APP_ENV": "production",
                },
                secrets={
                    "DATABASE_URL": ecs.Secret.from_secrets_manager(self.database.secret, "url"),
                    "ANTHROPIC_API_KEY": ecs.Secret.from_ssm_parameter(
                        ssm.StringParameter.from_string_parameter_name(
                            self, "AnthropicApiKeyParam", f"/{self.app_name}/anthropic-api-key"
                        )
                    ),
                    "JWT_SECRET_KEY": ecs.Secret.from_ssm_parameter(
                        ssm.StringParameter.from_string_parameter_name(
                            self, "JwtSecretKeyParam", f"/{self.app_name}/jwt-secret-key"
                        )
                    ),
                },
            ),
            public_load_balancer=True,
            redirect_http=True,
            protocol=elbv2.ApplicationProtocol.HTTPS,
            domain_zone=route53.HostedZone.from_lookup(
                self, "Zone", domain_name=self.domain_name
            ) if self.domain_name else None,
            domain_name=f"api.{self.domain_name}" if self.domain_name else None,
            certificate=acm.Certificate.from_certificate_arn(
                self, "Certificate", 
                f"arn:aws:acm:{self.region}:{self.account}:certificate/YOUR_CERT_ARN"
            ) if self.domain_name else None,
        )

        # Allow ECS service to connect to database
        self.database.connections.allow_from(
            service.service,
            ec2.Port.tcp(5432),
            "Allow ECS service to connect to database"
        )

        # Configure health check
        service.target_group.configure_health_check(
            path="/health",
            healthy_http_codes="200",
            healthy_threshold_count=2,
            unhealthy_threshold_count=5,
            timeout=Duration.seconds(30),
            interval=Duration.seconds(60),
        )

        # Set up auto scaling
        scaling = service.service.auto_scale_task_count(
            min_capacity=1,
            max_capacity=3,  # Maximum 3 instances for cost control
        )

        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=80,
            scale_in_cooldown=Duration.minutes(5),
            scale_out_cooldown=Duration.minutes(2),
        )

        return service

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs"""
        
        CfnOutput(
            self,
            "LoadBalancerUrl",
            value=f"https://{self.ecs_service.load_balancer.load_balancer_dns_name}",
            description="URL of the Application Load Balancer",
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
            "EcsClusterName",
            value=self.ecs_service.cluster.cluster_name,
            description="ECS cluster name",
        )

        CfnOutput(
            self,
            "EcsServiceName",
            value=self.ecs_service.service.service_name,
            description="ECS service name",
        )