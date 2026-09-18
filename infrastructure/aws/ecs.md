# ECS — Elastic Container Service

Documentation for the ECS cluster running the project.

## Cluster Details

- **Cluster name:** `adaptive-learning-agent`
- **Region:** `us-east-1`
- **Service name:** `adaptive-learning-agent`
- **Launch type:** Fargate (serverless)

## Service Configuration

| Setting | Value |
|---------|-------|
| **CPU** | 0.25 vCPU |
| **Memory** | 0.5 GB |
| **Container port** | 8000 |
| **Health check path** | `/api/v1/health` |
| **Min tasks** | 1 |
| **Max tasks** | 20 |
| **Auto-scaling metric** | Average CPU utilization |
| **Target value** | 60% |

## Environment Variables

| Variable | Value |
|----------|-------|
| `APP_ENV` | `production` |
| `PORT` | `8000` |
| `LOG_LEVEL` | `INFO` |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/adaptive_learning.db` |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` |
| `GROQ_MODEL` | `qwen/qwen3.8-27b` |
| `GROQ_MIN_REQUEST_INTERVAL` | `2.5` |
| `GROQ_API_KEY` | (secret) |
| `TAVILY_API_KEY` | `(secret)` |

## Useful Commands

### Describe the service

```bash
aws ecs describe-services \
    --cluster adaptive-learning-agent \
    --services adaptive-learning-agent \
    --region us-east-1
List running tasks
bash
aws ecs list-tasks \
    --cluster adaptive-learning-agent \
    --service-name adaptive-learning-agent \
    --region us-east-1
Force new deployment (rebuild)
bash
aws ecs update-service \
    --cluster adaptive-learning-agent \
    --service adaptive-learning-agent \
    --force-new-deployment \
    --region us-east-1
View recent logs
bash
aws logs tail /ecs/adaptive-learning-agent --follow \
    --region us-east-1
