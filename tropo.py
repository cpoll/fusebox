import os

import yaml
from troposphere import Base64, Join, Ref, Template, GetAtt, Output, Export, Tags, Split, Select, ImportValue
from troposphere import (
    ec2, elasticloadbalancingv2, autoscaling, iam, ecs, s3, cloudwatch, sns, kms, certificatemanager, route53, cloudfront)

from util import create_or_update_stack


# Load stack config
stack_config_file = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    'stack_config.yml')
CONFIG = yaml.load(open(stack_config_file), Loader=yaml.Loader)['config']

###
# Initialize template
###
t = Template()
t.add_version('2010-09-09')

###
# Shared Tags
###
shared_tags_args = {
    'Stack': CONFIG['STACK_NAME'],
}


###
# VPC
###

FuseboxVPC = t.add_resource(ec2.VPC(
    'FuseboxVPC',
    CidrBlock=CONFIG['FUSEBOX_VPC_CIDR_BLOCK'],
    EnableDnsSupport='true',
    EnableDnsHostnames='true',
    Tags=Tags(Name=f'{CONFIG["STACK_NAME"]}-app-vpc', **shared_tags_args),
))

# Internet Gateway
FuseboxIGW = t.add_resource(ec2.InternetGateway(
    'FuseboxIGW',
    Tags=Tags(Name=f'{CONFIG["STACK_NAME"]}-fusebox-igw', **shared_tags_args),
))
FuseboxIGWAttachment = t.add_resource(ec2.VPCGatewayAttachment(
    'FuseboxIGWAttachment',
    VpcId=Ref(FuseboxVPC),
    InternetGatewayId=Ref(FuseboxIGW),
))

# Route Table
FuseboxRouteTable = t.add_resource(ec2.RouteTable(
    'FuseboxRouteTable',
    VpcId=Ref(FuseboxVPC),
    Tags=Tags(Name=f'{CONFIG["STACK_NAME"]}-fusebox-rtb', **shared_tags_args),
))
t.add_resource(ec2.Route(
    'FuseboxRouteToIGW',
    RouteTableId=Ref(FuseboxRouteTable),
    GatewayId=Ref(FuseboxIGW),
    DestinationCidrBlock='0.0.0.0/0',
    DependsOn=[FuseboxIGWAttachment],
))

# Subnets
FuseboxVPCSubnet = t.add_resource(ec2.Subnet(
    'FuseboxVPCSubnet',
    VpcId=Ref(FuseboxVPC),
    CidrBlock=CONFIG['FUSEBOX_VPC_CIDR_BLOCK'],
    AvailabilityZone=CONFIG['VPC_SUBNET_AZ'],
    MapPublicIpOnLaunch='true',
    Tags=Tags(Name=f'{CONFIG["STACK_NAME"]}-app-subnet-1a', **shared_tags_args),
))
t.add_resource(ec2.SubnetRouteTableAssociation(
    'FuseboxVPCSubnetAssociation',
    SubnetId=Ref(FuseboxVPCSubnet),
    RouteTableId=Ref(FuseboxRouteTable),
))

# ACL Omitted



###
# EC2 Instance
###

FuseboxRole = t.add_resource(iam.Role(
    'FuseboxRole',
    Path='/',
    ManagedPolicyArns=[
        'arn:aws:iam::aws:policy/service-role/AmazonEC2RoleforSSM'
    ],
    AssumeRolePolicyDocument={
        'Version': '2012-10-17',
        'Statement': [
            {
                'Action': 'sts:AssumeRole',
                'Principal': {'Service': 'ec2.amazonaws.com'},
                'Effect': 'Allow',
            }
        ]
    }
))
FuseboxInstanceProfile = t.add_resource(iam.InstanceProfile(
    'FuseboxInstanceProfile',
    Path='/',
    Roles=[Ref(FuseboxRole)],
))

# SG
FuseboxSecurityGroup = t.add_resource(ec2.SecurityGroup(
    'FuseboxSecurityGroup',
    GroupDescription='Fusebox security group',
    VpcId=Ref(FuseboxVPC),
    Tags=Tags(shared_tags_args),
))
# t.add_resource(ec2.SecurityGroupIngress(
#     'FuseboxSecurityGroupIngressSSHPorts',
#     GroupId=Ref(FuseboxSecurityGroup),
#     CidrIp=CONFIG['FUSEBOX_INBOUND_IP'],
#     IpProtocol='tcp',
#     FromPort=22,
#     ToPort=22,
#     DependsOn=[FuseboxSecurityGroup],
# ))

FuseboxEC2Instance = t.add_resource(ec2.Instance(
    'FuseboxInstance',
    AvailabilityZone=CONFIG['VPC_SUBNET_AZ'],
    SubnetId=Ref(FuseboxVPCSubnet),
    # BlockDeviceMappings= TODO? Or just S3 + ephemeral,
    # CreditSpecification=,
    DisableApiTermination=True,
    EbsOptimized=False,
    IamInstanceProfile=Ref(FuseboxInstanceProfile),
    ImageId=CONFIG['FUSEBOX_AMI'],
    InstanceInitiatedShutdownBehavior='stop',
    InstanceType='t2.micro',
    KeyName=CONFIG['FUSEBOX_SSH_KEY_NAME'],
    # LaunchTemplate=,
    Monitoring=False,  # No detailed monitoring
    SecurityGroupIds=[GetAtt(FuseboxSecurityGroup, 'GroupId')],
    SourceDestCheck=True,
    Tenancy='default',
    Tags=Tags(
        Name=f'{CONFIG["STACK_NAME"]}-Fusebox',
        InstanceResponsibility='Fusebox',
        **shared_tags_args)
))

FuseboxEIP = t.add_resource(ec2.EIP(
    'FuseboxEIP',
    InstanceId=Ref(FuseboxEC2Instance),
    Domain='vpc',
    DependsOn=Ref(FuseboxVPC)
))

###
# Route 53
###
HostedZone = t.add_resource(route53.HostedZone(
    'HostedZone',
    Name=CONFIG['DOMAIN_NAME'],
    HostedZoneConfig=route53.HostedZoneConfiguration(
        Comment=f'{CONFIG["STACK_NAME"]} stack HostedZone'
    ),
))

t.add_resource(route53.RecordSetGroup(
    'FuseboxRecordSetGroup',
    HostedZoneId=Ref(HostedZone),
    RecordSets=[route53.RecordSet(
        'HostedZoneAliasToFusebox',
        Name=f'{CONFIG["DOMAIN_NAME"]}.',
        Type='A',
        ResourceRecords=[Ref(FuseboxEIP)],
        TTL=300)]
))

###
# S3 Bucket
###
StorageBucketName = CONFIG["STORAGE_BUCKET_NAME"]
StorageBucket = t.add_resource(s3.Bucket(
    'StorageBucket',
    BucketName=StorageBucketName,
    DeletionPolicy='Retain',
    # LoggingConfiguration=s3.LoggingConfiguration(
    #     LogFilePrefix='s3-server-access-logs/'
    # ),
    AccessControl="Private",
    VersioningConfiguration=s3.VersioningConfiguration(
        Status='Enabled'
    ),
    Tags=Tags(**shared_tags_args),
))
t.add_resource(s3.BucketPolicy(
    'StorageBucketPolicy',
    Bucket=Ref(StorageBucket),
    PolicyDocument={
        "Statement": [
            {
                "Action": "s3:*",
                "Effect": "Allow",
                "Resource": [
                    Join("", ["arn:aws:s3:::", Ref(StorageBucket), "/*"]),
                    Join("", ["arn:aws:s3:::", Ref(StorageBucket)]),
                ],
                "Principal": {
                    "AWS": GetAtt(FuseboxRole, 'Arn')
                },
            }
        ]
    },
))

###
# Outputs
###
t.add_output(Output(
    'Fusebox url',
    Description='Fusebox url',
    Value=CONFIG["DOMAIN_NAME"]
))


if __name__ == '__main__':

    stack_policy = '''{ "Statement" : [
        {
            "Effect" : "Allow",
            "Principal" : "*",
            "Action" : "Update:*",
            "Resource" : "*"
        }
    ]}'''

    create_or_update_stack(
        stack_name=CONFIG['STACK_NAME'],
        template=t,
        stack_policy=stack_policy,
        aws_region_name=CONFIG['AWS_REGION_NAME'],
        notification_arn=CONFIG.get('CLOUDFORMATION_NOTIFICATION_ARN'),
        cf_template_bucket=CONFIG['CF_TEMPLATE_BUCKET'])