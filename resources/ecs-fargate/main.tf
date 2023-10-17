# VPC Networking Resources to Deploy Fargate Into:

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

  # Inbound connections
  ingress {
    from_port   = 0
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Outbound connections
  egress {
    from_port   = 0
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "ndnp-open-ocr-sg"
  }
}


resource "aws_ecr_repository" "repo" {
  name = "ndnp-open-ocr-container-repo"

  tags = {
    Name = "ndnp-open-ocr"
  }
}

resource "aws_ecr_lifecycle_policy" "example" {
  repository = aws_ecr_repository.repo.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire images older than 30 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 30
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

resource "aws_ecs_cluster" "cluster" {
  name = "ndnp-open-ocr-fargate-cluster"

  tags = {
    Name = "ndnp-open-ocr"
  }
}

resource "aws_cloudwatch_log_group" "log_group" {
  name              = "/ecs/ndnp-open-ocr"
  retention_in_days = 30 # adjust as necessary
}

resource "aws_ecs_task_definition" "task_def" {
  family                   = var.task_family
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([{
    name  = var.container_name
    image = "420280634985.dkr.ecr.us-east-2.amazonaws.com/ndnp-open-ocr-container-repo:latest"
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
        value = var.table_name
      },
      {
        name  = "ECS_AVAILABLE_LOGGING_DRIVERS",
        value = "awslogs"
      },
      {
        name  = "OUTPUT_BUCKET_NAME",
        value = var.aws_s3_output_bucket
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-create-group"  = "true",
        "awslogs-group"         = "/ecs/ndnp-open-ocr1",
        "awslogs-region"        = "us-east-2", # Replace with your AWS region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])

<<<<<<< HEAD
  tags = {
    Name = "ndnp-open-ocr"
=======
resource "aws_ecs_service" "service" {
  name            = var.service_name
  cluster         = aws_ecs_cluster.cluster.id
  task_definition = aws_ecs_task_definition.task_def.arn
  launch_type     = "FARGATE"
  desired_count   = var.desired_count

  network_configuration {
    subnets          = [aws_subnet.subnet_1.id, aws_subnet.subnet_2.id]
    security_groups  = [aws_security_group.main_sg.id]
    assign_public_ip = true
  }

  force_new_deployment = true

  # triggers = {
  #   redeployment = timestamp()
  # }
}

# // AUTOSCALING FOR FARGATE TASKS
resource "aws_cloudwatch_metric_alarm" "sqs_alarm" {
  alarm_name          = "SQSMessagesVisibleAlarm"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = "1"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = "60"
  statistic           = "Average"
  threshold           = "10" # Adjust this threshold based on when you want scaling to occur
  alarm_description   = "Alarm when SQS messages are too high"
  alarm_actions       = [aws_appautoscaling_policy.scale_out.arn]
  ok_actions          = [aws_appautoscaling_policy.scale_in.arn]

  dimensions = {
    QueueName = var.sqs_queue_name # Make sure you have the queue name variable
  }
}

resource "aws_appautoscaling_target" "ecs_target" {
  max_capacity       = 10 # Adjust based on your max tasks
  min_capacity       = 1  # Adjust based on your min tasks
  resource_id        = "service/${aws_ecs_cluster.cluster.name}/${aws_ecs_service.service.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "scale_out" {
  name               = "ecs-service-scale-out"
  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace
  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
  resource_id        = aws_appautoscaling_target.ecs_target.resource_id
  policy_type        = "StepScaling"

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 300
    metric_aggregation_type = "Average"

    step_adjustment {
      metric_interval_lower_bound = 0
      scaling_adjustment          = 5 # Increase by 2 tasks. Adjust as necessary.
    }
  }
}

resource "aws_appautoscaling_policy" "scale_in" {
  name               = "ecs-service-scale-in"
  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace
  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
  resource_id        = aws_appautoscaling_target.ecs_target.resource_id
  policy_type        = "StepScaling"

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 300
    metric_aggregation_type = "Average"

    step_adjustment {
      metric_interval_upper_bound = 0
      scaling_adjustment          = -5 # Decrease by 1 task. Adjust as necessary.
    }
>>>>>>> CHRONAM-2278-fargate-migrate
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