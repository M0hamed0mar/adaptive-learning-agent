# ECR — Elastic Container Registry

Documentation for the ECR repository used by the project.

## Repository Details

- **Name:** `adaptive-learning-agent`
- **Region:** `us-east-1` (US East, N. Virginia)
- **URI:** `<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/adaptive-learning-agent`
- **Tag mutability:** `MUTABLE`
- **Scan on push:** Disabled
- **Encryption:** AES-256

## Image Details

- **Image tag:** `latest`
- **Image size:** ~129 MB (compressed)
- **Layers:** 14

## Common Commands

### List images

```bash
aws ecr describe-images \
    --repository-name adaptive-learning-agent \
    --region us-east-1
Delete an image by tag
bash
aws ecr batch-delete-image \
    --repository-name adaptive-learning-agent \
    --image-ids imageTag=latest \
    --region us-east-1
Lifecycle policy (recommended)
Keep only the last 5 images to reduce storage costs:

json
{
    "rules": [
        {
            "rulePriority": 1,
            "description": "Keep last 5 images",
            "selection": {
                "tagStatus": "any",
                "countType": "imageCountMoreThan",
                "countNumber": 5
            },
            "action": { "type": "expire" }
        }
    ]
}
Apply:

bash
aws ecr put-lifecycle-policy \
    --repository-name adaptive-learning-agent \
    --lifecycle-policy-text file://lifecycle-policy.json \
    --region us-east-1
