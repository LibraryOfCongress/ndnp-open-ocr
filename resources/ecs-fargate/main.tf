resource "aws_ecr_repository" "repo" {
  name = "ndnp-open-ocr-container-repo"

  tags = {
    Name = "ndnp-open-ocr"
  }
}

resource "aws_ecs_cluster" "cluster" {
  name = "ndnp-open-ocr-fargate-cluster"

  tags = {
    Name = "ndnp-open-ocr"
  }
}

resource "aws_ecs_task_definition" "task_def" {
  family                   = var.task_family
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([{
    name  = var.container_name
    image = var.container_image
    portMappings = [{
      containerPort = var.container_port
      hostPort      = var.container_port
    }]
    environment = [
      {
        name  = "SQS_QUEUE_URL",
        value = var.sqs_queue_url
      },
      {
        name  = "TABLE_NAME",
        value = "AnotherValue"
      }
    ]
  }])

  tags = {
    Name = "ndnp-open-ocr"
  }
}

# resource "aws_ecs_service" "service" {
#   name            = var.service_name
#   cluster         = aws_ecs_cluster.cluster.id
#   task_definition = aws_ecs_task_definition.task_def.arn
#   launch_type     = "FARGATE"
#   desired_count   = var.desired_count

#   network_configuration {
#     subnets         = var.subnets
#     security_groups = var.security_groups
#   }

#   tags = {
#     Name = "ndnp-open-ocr"
#   }
# }

resource "aws_vpc" "vpc" {
  cidr_block = "10.0.0.0/16"

  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "ndnp-open-ocr"
  }
}

resource "aws_security_group" "ecs_tasks" {
  vpc_id = aws_vpc.vpc.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Add more ingress/egress rules as needed.

  tags = {
    Name = "ndnp-open-ocr"
  }
}