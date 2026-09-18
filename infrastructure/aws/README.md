# AWS Deployment

Documentation for deploying the Adaptive Learning Agent to AWS.

## Architecture
┌────────────────────────────────────────────────────────────┐
│ Client (Browser) │
└──────────────────────────┬─────────────────────────────────┘
│ HTTPS
▼
┌────────────────────────────────────────────────────────────┐
│ Application Load Balancer (ALB) │
│ - HTTPS via AWS Certificate Manager │
│ - Health checks │
│ - Auto-generated domain │
└──────────────────────────┬─────────────────────────────────┘
│ HTTP :8000
▼
┌────────────────────────────────────────────────────────────┐
│ ECS Fargate Service │
│ - Container: FastAPI app │
│ - 0.25 vCPU, 0.5 GB memory │
│ - Min 1, Max 20 tasks │
│ - Auto-scaling │
└──────────────────────────┬─────────────────────────────────┘
│
▼
┌────────────────────────────────────────────────────────────┐
│ Amazon ECR Repository │
│ - Container image storage │
│ - 129 MB compressed image │
└────────────────────────────────────────────────────────────┘

text

## Components

| Component | Purpose | Approximate Cost |
|-----------|---------|------------------|
| **ECR** | Container image registry | $0.10/GB/month |
| **ECS Fargate** | Container runtime | $14/month (0.25 vCPU, 0.5 GB) |
| **Application Load Balancer** | HTTPS endpoint + routing | $6/month |
| **CloudWatch Logs** | Application logs | $0.50/month |
| **Total** | | **~$20/month** |

## Deployment Steps

### 1. Build the Docker image

```bash
docker build -t adaptive-learning-agent:latest .
2. Authenticate to ECR
bash
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin \
    <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
3. Tag and push
bash
docker tag adaptive-learning-agent:latest \
    <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/adaptive-learning-agent:latest

docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/adaptive-learning-agent:latest
4. Create ECS service
Use the AWS Console → ECS → Express Mode → Create.

Environment variables needed:

APP_ENV=production

PORT=8000

LOG_LEVEL=INFO

DATABASE_URL=sqlite+aiosqlite:///./data/adaptive_learning.db

GROQ_API_KEY=<your-key>

GROQ_BASE_URL=https://api.groq.com/openai/v1

GROQ_MODEL=qwen/qwen3.8-27b

GROQ_MIN_REQUEST_INTERVAL=2.5

TAVILY_API_KEY=<your-key>

Stop and Restart
To stop (save costs)
bash
aws ecs update-service \
    --cluster adaptive-learning-agent \
    --service adaptive-learning-agent \
    --desired-count 0 \
    --region us-east-1
To restart
bash
aws ecs update-service \
    --cluster adaptive-learning-agent \
    --service adaptive-learning-agent \
    --desired-count 1 \
    --region us-east-1
Restart takes approximately 1-2 minutes.

Monitoring
Logs: CloudWatch Logs → /ecs/adaptive-learning-agent

Metrics: ECS Console → Service → Metrics

Health: Application URL → /api/v1/health

Cost Management
Budget alert configured: adaptive-learning-monthly ($5 threshold)

Credits available: $120 (182 days)

Recommended: stop service when not in use
