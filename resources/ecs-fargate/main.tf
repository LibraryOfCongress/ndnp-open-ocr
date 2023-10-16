resource "aws_ecr_repository" "repo" {
  name = "ndnp-open-ocr-container-repo"
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
}

resource "aws_cloudwatch_log_group" "log_group" {
  name              = "/ecs/ndnp-open-ocr"
  retention_in_days = 30  # adjust as necessary
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
        value = "AnotherValue"
      },
      {
        name = "ECS_AVAILABLE_LOGGING_DRIVERS",
        value = "awslogs"
      },
      {
        name = "OUTPUT_BUCKET_NAME",
        value="ndnp-open-ocr-output-bucket-test-2"
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-create-group"  = "true",
        "awslogs-group"         = "/ecs/ndnp-open-ocr1",
        "awslogs-region"        = "us-east-2",  # Replace with your AWS region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

resource "aws_ecs_service" "service" {
  name            = var.service_name
  cluster         = aws_ecs_cluster.cluster.id
  task_definition = aws_ecs_task_definition.task_def.arn
  launch_type     = "FARGATE"
  desired_count   = var.desired_count

  network_configuration {
    subnets         = var.subnets
    security_groups = var.security_groups
  }
}

# // AUTOSCALING FOR FARGATE TASKS
# resource "aws_cloudwatch_metric_alarm" "sqs_alarm" {
#   alarm_name          = "SQSMessagesVisibleAlarm"
#   comparison_operator = "GreaterThanOrEqualToThreshold"
#   evaluation_periods  = "1"
#   metric_name         = "ApproximateNumberOfMessagesVisible"
#   namespace           = "AWS/SQS"
#   period              = "300"
#   statistic           = "Average"
#   threshold           = "10" # Adjust this threshold based on when you want scaling to occur
#   alarm_description   = "Alarm when SQS messages are too high"
#   alarm_actions       = [aws_appautoscaling_policy.scale_out.arn]
#   ok_actions          = [aws_appautoscaling_policy.scale_in.arn]

#   dimensions = {
#     QueueName = var.sqs_queue_name # Make sure you have the queue name variable
#   }
# }
