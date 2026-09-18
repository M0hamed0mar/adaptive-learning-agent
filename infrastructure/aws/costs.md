# Cost Breakdown

Detailed cost analysis for running the Adaptive Learning Agent on AWS.

## Monthly Costs (Running 24/7)

| Service | Specification | Monthly Cost |
|---------|---------------|--------------|
| **ECS Fargate** | 0.25 vCPU, 0.5 GB, 1 task | ~$14.00 |
| **Application Load Balancer** | 1 ALB, low traffic | ~$6.00 |
| **ECR** | 129 MB storage | ~$0.13 |
| **CloudWatch Logs** | ~100 MB/month | ~$0.50 |
| **Data Transfer** | Low (demo usage) | ~$0.10 |
| **Total** | | **~$20.75/month** |

## When Stopped

When the ECS service has `desired-count=0`:

| Service | Monthly Cost |
|---------|--------------|
| ECS Fargate | $0.00 |
| ALB | ~$6.00 (still running) |
| ECR | ~$0.13 |
| **Total** | **~$6.13/month** |

**Note:** The ALB continues to incur charges even when no tasks are running.

To eliminate ALB costs too, delete the service entirely.

## Credits

- **Available:** $120 (from AWS Free Tier)
- **Expiration:** 182 days from account creation
- **Coverage:** ~6 months at full usage, or many years if service is stopped between uses

## Recommendations

1. **For CV / demo purposes:** Stop the service when not actively used.
2. **Monitor the budget:** `adaptive-learning-monthly` ($5 threshold).
3. **Restart before interviews:** 1-2 minutes to restart.
4. **After 6 months:** The credits expire. Either top up or delete the service.

## Delete Everything (Full Cleanup)

```bash
# 1. Delete the ECS service
aws ecs delete-service \
    --cluster adaptive-learning-agent \
    --service adaptive-learning-agent \
    --force \
    --region us-east-1

# 2. Delete the ECS cluster
aws ecs delete-cluster \
    --cluster adaptive-learning-agent \
    --region us-east-1

# 3. Delete the ECR repository
aws ecr delete-repository \
    --repository-name adaptive-learning-agent \
    --force \
    --region us-east-1
Warning: This deletes all data permanently.
