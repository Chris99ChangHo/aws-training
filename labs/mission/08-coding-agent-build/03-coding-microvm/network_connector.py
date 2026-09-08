"""VPC egress 통제 (도전 과제) — MicroVM의 아웃바운드를 VPC egress
네트워크 커넥터로 통제한다.

기본적으로 MicroVM 아웃바운드는 퍼블릭 인터넷이 열려 있다. 이 스크립트는
VpcEgressConfiguration 커넥터를 만들어 보안 그룹으로 좁힌 서브넷을 통해서만
나가도록 강제한다. run_microvm의 egressNetworkConnectors에 이 ARN을
넣으면 적용된다 (ingressNetworkConnectors와는 별개 파라미터).
"""
from __future__ import annotations

import boto3

REGION = "us-west-2"

ec2_client = boto3.client("ec2", region_name=REGION)
microvms_client = boto3.client("lambda-microvms", region_name=REGION)


def find_default_vpc_network() -> tuple[str, list[str], str]:
    """기본 VPC의 서브넷 2개와 보안 그룹 1개를 찾는다."""
    vpcs = ec2_client.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])
    vpc_id = vpcs["Vpcs"][0]["VpcId"]

    subnets = ec2_client.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
    subnet_ids = [s["SubnetId"] for s in subnets["Subnets"][:2]]

    sgs = ec2_client.describe_security_groups(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}, {"Name": "group-name", "Values": ["default"]}]
    )
    sg_id = sgs["SecurityGroups"][0]["GroupId"]

    return vpc_id, subnet_ids, sg_id


def create_egress_connector(subnet_ids: list[str], sg_id: str) -> str:
    """VPC egress 네트워크 커넥터를 만들고 ARN을 반환한다."""
    response = microvms_client.create_network_connector(
        name="microvm-vpc-egress",
        vpcEgressConfiguration={
            "subnetIds": subnet_ids,
            "securityGroupIds": [sg_id],
            "associatedComputeResourceTypes": ["MicroVm"],
        },
    )
    return response["networkConnectorArn"]


if __name__ == "__main__":
    vpc_id, subnet_ids, sg_id = find_default_vpc_network()
    print(f"VPC: {vpc_id}, 서브넷: {subnet_ids}, 보안 그룹: {sg_id}")

    connector_arn = create_egress_connector(subnet_ids, sg_id)
    print(f"Egress 커넥터 ARN: {connector_arn}")
    print(
        "\n사용법: run_microvm 호출 시 egressNetworkConnectors=[이 ARN]을 추가하면 "
        "MicroVM의 아웃바운드가 이 VPC의 보안 그룹 규칙으로 제한됩니다."
    )
