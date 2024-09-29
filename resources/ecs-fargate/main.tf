# VPC Networking Resources
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = {
    Name = "ndnp-open-ocr-vpc"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags = {
    Name = "ndnp-open-ocr-igw"
  }
}

resource "aws_route_table" "main" {
  vpc_id = aws_vpc.main.id
  route {
    # Allow all outbound internet access
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = {
    Name = "ndnp-open-ocr-route-table"
  }
}

resource "aws_route_table_association" "a" {
  subnet_id      = aws_subnet.subnet_1.id
  route_table_id = aws_route_table.main.id
}

resource "aws_route_table_association" "b" {
  subnet_id      = aws_subnet.subnet_2.id
  route_table_id = aws_route_table.main.id
}

resource "aws_subnet" "subnet_1" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "us-east-2a"
  map_public_ip_on_launch = true
  tags = {
    Name = "ndnp-open-ocr-subnet-1"
  }
}

resource "aws_subnet" "subnet_2" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "us-east-2b"
  map_public_ip_on_launch = true
  tags = {
    Name = "ndnp-open-ocr-subnet-2"
  }
}

resource "aws_security_group" "main_sg" {
  vpc_id = aws_vpc.main.id

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "ndnp-open-ocr-sg"
  }
}

resource "aws_ecr_repository" "repo" {
  name = "ndnp-open-ocr-container-repo"
}

# CloudWatch Log Group for AWS Batch
resource "aws_cloudwatch_log_group" "log_group" {
  name              = "/aws/batch/job"
  retention_in_days = 90
}

# AWS Batch Service Role
resource "aws_iam_role" "batch_service_role" {
  name = "ndnp-open-ocr-batch-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = { Service = "batch.amazonaws.com" },
      Action   = "sts:AssumeRole"
    }]
  })

  tags = {
    Name = "ndnp-open-ocr-batch-service-role"
  }
}

resource "aws_iam_role_policy_attachment" "batch_service_role_policy" {
  role       = aws_iam_role.batch_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

# AWS Batch Execution Role
resource "aws_iam_role" "batch_execution_role" {
  name = "ndnp-open-ocr-batch-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = { Service = "ecs-tasks.amazonaws.com" },
      Action   = "sts:AssumeRole"
    }]
  })

  tags = {
    Name = "ndnp-open-ocr-batch-execution-role"
  }
}

resource "aws_iam_role_policy_attachment" "batch_execution_role_policy" {
  role       = aws_iam_role.batch_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# AWS Batch Job Role (for your container to access AWS resources)
resource "aws_iam_role" "batch_job_role" {
  name = "ndnp-open-ocr-batch-job-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = { Service = "ecs-tasks.amazonaws.com" },
      Action   = "sts:AssumeRole"
    }]
  })

  tags = {
    Name = "ndnp-open-ocr-batch-job-role"
  }
}

# Attach necessary policies to the job role
resource "aws_iam_role_policy_attachment" "batch_job_role_policy" {
  role       = aws_iam_role.batch_job_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

# AWS Batch Compute Environment
resource "aws_batch_compute_environment" "batch_compute_environment" {
  compute_environment_name = "ndnp-open-ocr-batch-compute-environment"
  type                     = "MANAGED"
  service_role             = aws_iam_role.batch_service_role.arn

  compute_resources {
    type                = "FARGATE"
    max_vcpus           = 500
    subnets             = [aws_subnet.subnet_1.id, aws_subnet.subnet_2.id]
    security_group_ids  = [aws_security_group.main_sg.id]
  }

  tags = {
    Name = "ndnp-open-ocr-batch-compute-environment"
  }
}

# AWS Batch Job Queue
resource "aws_batch_job_queue" "batch_job_queue" {
  name     = "ndnp-open-ocr-batch-job-queue"
  state    = "ENABLED"
  priority = 1

  compute_environments = [
    aws_batch_compute_environment.batch_compute_environment.arn
  ]

  tags = {
    Name = "ndnp-open-ocr-batch-job-queue"
  }
}


# AWS Batch Job Definition
resource "aws_batch_job_definition" "batch_job_definition" {
  name = "ndnp-open-ocr-batch-job-definition"
  type = "container"

  # Fargate as the compute platform
  platform_capabilities = ["FARGATE"]

  container_properties = jsonencode({
    image                = "${aws_ecr_repository.repo.repository_url}:latest"
    executionRoleArn     = aws_iam_role.batch_execution_role.arn
    jobRoleArn           = aws_iam_role.batch_job_role.arn
    resourceRequirements = [
      {
        type  = "VCPU"
        value = "1"  # Adjust based on your job's CPU needs
      },
      {
        type  = "MEMORY"
        value = "2048"  # Adjust based on your job's memory needs
      }
    ]
    environment          = [
      {
        name  = "AWS_REGION",
        value = "us-east-2"
      },
      {
        name  = "OUTPUT_BUCKET_NAME",
        value = var.aws_s3_output_bucket
      }
    ]
    networkConfiguration = {
      assignPublicIp = "DISABLED"
    }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/aws/batch/job"
        "awslogs-region"        = "us-east-2"
        "awslogs-stream-prefix" = "batch"
      }
    }
  })

  retry_strategy {
    attempts = 3
  }

  tags = {
    Name = "ndnp-open-ocr-batch-job-definition"
  }
}
