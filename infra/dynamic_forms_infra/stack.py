import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_rds as rds
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

USER_DATA = r"""#!/bin/bash
set -euxo pipefail
exec > >(tee /var/log/dynamic-forms-bootstrap.log) 2>&1

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y curl git nginx python3 python3-venv postgresql-client unzip build-essential jq
snap install aws-cli --classic

if [ ! -f /swapfile ]; then
  fallocate -l 3G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

sudo -iu ubuntu bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
sudo -iu ubuntu bash -c 'test -d ~/dynamic-forms || git clone --branch __BRANCH__ __REPO__ ~/dynamic-forms'

SECRET_JSON=$(aws secretsmanager get-secret-value --region __REGION__ --secret-id __DB_SECRET_ARN__ --query SecretString --output text)
XAI_KEY=$(aws secretsmanager get-secret-value --region __REGION__ --secret-id __XAI_SECRET__ --query SecretString --output text)
DB_URL=$(echo "$SECRET_JSON" | jq -r '"postgresql+psycopg2://\(.username):\(.password)@\(.host):\(.port)/\(.dbname)"')

APP=/home/ubuntu/dynamic-forms
cat > $APP/backend/.env <<ENV
LOG_LEVEL=INFO
LLM_PROVIDER=grok
XAI_API_KEY=$XAI_KEY
XAI_BASE_URL=https://api.x.ai/v1
XAI_MODEL=grok-4.20-0309-non-reasoning
AWS_REGION=__REGION__
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CHROMA_PERSIST_DIR=app/data/chroma
MATERIAL_SPEC_PATH=app/data/angular_material_capabilities.json
DATABASE_URL=$DB_URL
CORS_ORIGINS=["http://__PUBLIC_IP__"]
ENV
chown ubuntu:ubuntu $APP/backend/.env
chmod 600 $APP/backend/.env

sudo -iu ubuntu bash -c 'cd ~/dynamic-forms/backend && uv venv --python 3 && uv sync'

if [ ! -f /var/lib/dynamic-forms-schema-applied ]; then
  for i in $(seq 1 30); do
    psql "$(echo "$DB_URL" | sed 's/+psycopg2//')" -c 'SELECT 1' && break || sleep 10
  done
  PLAIN_URL=$(echo "$DB_URL" | sed 's/+psycopg2//')
  psql "$PLAIN_URL" -v ON_ERROR_STOP=1 -f $APP/db/sql/schema.sql
  for f in $(ls $APP/db/sql/migrations/*.sql | sort); do
    psql "$PLAIN_URL" -f "$f" || true
  done
  touch /var/lib/dynamic-forms-schema-applied
fi

cat > /etc/systemd/system/dynamic-forms-api.service <<UNIT
[Unit]
Description=Dynamic Forms FastAPI backend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=$APP/backend
EnvironmentFile=$APP/backend/.env
ExecStart=$APP/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

mkdir -p /var/www/dynamic-forms
cat > /etc/nginx/sites-available/dynamic-forms <<'NGINX'
server {
    listen 80 default_server;
    server_name _;
    root /var/www/dynamic-forms;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_read_timeout 180s;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    location = /health { proxy_pass http://127.0.0.1:8000/health; }
    location = /docs { proxy_pass http://127.0.0.1:8000/docs; proxy_set_header Host $host; }
    location = /openapi.json { proxy_pass http://127.0.0.1:8000/openapi.json; proxy_set_header Host $host; }
    location / { try_files $uri $uri/ /index.html; }
}
NGINX
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/dynamic-forms /etc/nginx/sites-enabled/dynamic-forms
nginx -t

systemctl daemon-reload
systemctl enable --now dynamic-forms-api
systemctl enable nginx
systemctl restart nginx
"""


class DynamicFormsStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        ctx = self.node.try_get_context
        instance_type = ctx("instance_type")
        xai_secret_name = ctx("xai_secret_name")
        ssh_cidr = ctx("ssh_cidr")
        key_name = ctx("key_name")

        vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="db", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED, cidr_mask=24),
            ],
        )

        web_sg = ec2.SecurityGroup(self, "WebSg", vpc=vpc, description="Nginx on EC2")
        web_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP")
        web_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS")
        if ssh_cidr:
            web_sg.add_ingress_rule(ec2.Peer.ipv4(ssh_cidr), ec2.Port.tcp(22), "SSH")

        db_sg = ec2.SecurityGroup(self, "DbSg", vpc=vpc, description="RDS PostgreSQL")
        db_sg.add_ingress_rule(web_sg, ec2.Port.tcp(5432), "Postgres from EC2")

        database = rds.DatabaseInstance(
            self,
            "Database",
            engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_16),
            instance_type=ec2.InstanceType("t4g.micro"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[db_sg],
            database_name="dynamic_forms",
            credentials=rds.Credentials.from_generated_secret(
                "dfadmin", secret_name="dynamic-forms/rds-credentials"
            ),
            allocated_storage=20,
            storage_encrypted=True,
            backup_retention=cdk.Duration.days(7),
            deletion_protection=True,
            removal_policy=cdk.RemovalPolicy.SNAPSHOT,
        )

        xai_secret = secretsmanager.Secret.from_secret_name_v2(self, "XaiSecret", xai_secret_name)

        role = iam.Role(self, "InstanceRole", assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"))
        role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"))
        database.secret.grant_read(role)
        xai_secret.grant_read(role)

        eip = ec2.CfnEIP(self, "Eip", domain="vpc")

        user_data = ec2.UserData.custom(
            USER_DATA.replace("__REPO__", ctx("repo_url"))
            .replace("__BRANCH__", ctx("repo_branch"))
            .replace("__REGION__", self.region)
            .replace("__DB_SECRET_ARN__", database.secret.secret_arn)
            .replace("__XAI_SECRET__", xai_secret_name)
            .replace("__PUBLIC_IP__", eip.ref)
        )

        instance = ec2.Instance(
            self,
            "Web",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            instance_type=ec2.InstanceType(instance_type),
            machine_image=ec2.MachineImage.from_ssm_parameter(
                "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id",
                os=ec2.OperatingSystemType.LINUX,
            ),
            security_group=web_sg,
            role=role,
            user_data=user_data,
            key_pair=ec2.KeyPair.from_key_pair_name(self, "KeyPair", key_name) if key_name else None,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/sda1",
                    volume=ec2.BlockDeviceVolume.ebs(
                        ctx("volume_size_gb"), volume_type=ec2.EbsDeviceVolumeType.GP3, encrypted=True
                    ),
                )
            ],
            require_imdsv2=True,
        )
        instance.node.add_dependency(database)

        ec2.CfnEIPAssociation(self, "EipAssoc", allocation_id=eip.attr_allocation_id, instance_id=instance.instance_id)

        cdk.CfnOutput(self, "PublicIp", value=eip.ref, description="Set as AWS_EC2_HOST in GitHub secrets")
        cdk.CfnOutput(self, "InstanceId", value=instance.instance_id, description="aws ssm start-session --target <id>")
        cdk.CfnOutput(self, "DbEndpoint", value=database.db_instance_endpoint_address)
        cdk.CfnOutput(self, "DbSecretArn", value=database.secret.secret_arn)
