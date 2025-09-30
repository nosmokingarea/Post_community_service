# 기존 VPC 참조
data "aws_vpc" "community_vpc" {
  filter {
    name   = "tag:Name"
    values = ["community-vpc"]
  }
}

# 기존 ALB Security Group 참조
data "aws_security_group" "alb_sg" {
  filter {
    name   = "group-name"
    values = ["alb-sg"]
  }
  vpc_id = data.aws_vpc.community_vpc.id
}

# 기존 RDS Security Group 참조
data "aws_security_group" "rds_sg" {
  filter {
    name   = "group-name"
    values = ["rds-sg"]
  }
  vpc_id = data.aws_vpc.community_vpc.id
}

# EKS Node Security Group (ALB와 통신용)
resource "aws_security_group" "eks_nodes_sg" {
  name        = "eks-nodes-sg"
  description = "Security group for EKS nodes"
  vpc_id      = data.aws_vpc.community_vpc.id

  # ALB에서 EKS Node로의 트래픽 허용 (NodePort 범위)
  ingress {
    from_port       = 30000
    to_port         = 32767
    protocol        = "tcp"
    security_groups = [data.aws_security_group.alb_sg.id]
    description     = "ALB to EKS Node communication"
  }

  # SSH 접근 (관리용)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
    description = "SSH access from VPC"
  }

  # 모든 아웃바운드 트래픽 허용
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = {
    Name = "eks-nodes-sg"
    Project = "post-service"
    Env = "dev"
  }
}

# ALB Security Group 업데이트 - EKS Node와 통신 허용
resource "aws_security_group_rule" "alb_to_eks_nodes" {
  type                     = "egress"
  from_port                = 30000
  to_port                  = 32767
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.eks_nodes_sg.id
  security_group_id        = data.aws_security_group.alb_sg.id
  description              = "ALB to EKS Node communication"
}

# EKS Node에서 RDS 접근 허용
resource "aws_security_group_rule" "eks_nodes_to_rds" {
  type                     = "ingress"
  from_port                = 3306
  to_port                  = 3306
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.eks_nodes_sg.id
  security_group_id        = data.aws_security_group.rds_sg.id
  description              = "EKS Node to RDS communication"
}

# CloudFront에서 ALB로의 트래픽 허용 (CloudFront IP 범위)
resource "aws_security_group_rule" "cloudfront_to_alb" {
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = [
    "13.32.0.0/15",
    "13.35.0.0/16",
    "18.238.0.0/15",
    "18.244.0.0/15",
    "18.252.0.0/16",
    "204.246.164.0/22",
    "204.246.168.0/22",
    "204.246.174.0/23",
    "204.246.176.0/20",
    "205.251.192.0/19",
    "205.251.249.0/24",
    "205.251.250.0/23",
    "205.251.252.0/23",
    "205.251.254.0/24",
    "216.137.32.0/19"
  ]
  security_group_id = data.aws_security_group.alb_sg.id
  description       = "CloudFront to ALB communication"
}
