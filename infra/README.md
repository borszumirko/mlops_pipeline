# AWS deployment runbook

This runbook creates deployment from scratch in Stockholm
(`eu-north-1`). Run commands from the repository root in the same Bash or Zsh
session. The recorded demo was successfully tested and then destroyed; its
repository, image, logs, and runtime no longer exist in AWS.

## Architecture and prerequisites

Terraform manages ECR, an ECS cluster and Fargate service, an execution role,
CloudWatch logs, and a VPC with a public subnet and internet gateway. One task
uses 1 vCPU and 2 GB RAM. Port 8000 is restricted to your public IPv4 address;
outbound TCP 443 permits image pulls and logging. The model is bundled in the
image. There is no NAT gateway or load balancer.

Install Docker, uv with Python 3.13, AWS CLI v2 supporting `aws login`, and
Terraform compatible with `versions.tf`. Your AWS account must permit the services above and creation of
IAM roles. Configure MFA and a cost budget before provisioning resources.
Applying the full configuration starts compute and other metered usage; eligible
credits may cover it. A budget is an alert, not a hard spending cap.

## 1. Authenticate and initialize

Replace `your-profile` with your AWS CLI profile name. Use your project's assigned
region if it differs from the example, and set `aws_region` in your local
Terraform variables to match.

```bash
export AWS_PROFILE=your-profile
export AWS_REGION=eu-north-1
aws configure set region "$AWS_REGION" --profile "$AWS_PROFILE"
aws login --profile "$AWS_PROFILE" --region "$AWS_REGION"
aws sts get-caller-identity --no-cli-pager
terraform -chdir=infra init
terraform -chdir=infra validate
```

Check that the identity is for the intended account. Login credentials are
temporary; repeat `aws login` when needed. Do not put credentials in Terraform.

## 2. Set local variables and bootstrap ECR

Get your current public IPv4 address and create the ignored local variable file.
This overwrites `infra/terraform.tfvars`; preserve any custom settings first. Keep the task count at zero until the real image is pushed.

```bash
CLIENT_IP=$(curl -4 -fsS https://checkip.amazonaws.com)
cat > infra/terraform.tfvars <<EOF
aws_region          = "$AWS_REGION"
allowed_client_cidr = "$CLIENT_IP/32"
image_digest        = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
desired_count       = 0
EOF

terraform -chdir=infra plan -target=aws_ecr_repository.sentiment_api
terraform -chdir=infra apply -target=aws_ecr_repository.sentiment_api
```

Review the plan before typing `yes`. Targeting is used only for this initial
registry bootstrap: the service needs an image that cannot be pushed until the
repository exists. Terraform may warn that a targeted apply is incomplete; the
full plan in step 5 covers the remaining infrastructure.

```bash
ECR_URL=$(terraform -chdir=infra output -raw ecr_repository_url)
ECR_REGISTRY="${ECR_URL%%/*}"
```

## 3. Build and test the image locally

Run the existing API tests and real-model evaluation before deploying:

```bash
uv sync --locked
uv run pytest -v
uv run python -m mlops_pipeline.evaluate
```

The real-model evaluator needs access to Hugging Face on its first run.
Build and test the same image that will be pushed to AWS:

```bash
IMAGE_TAG="demo-$(date -u +%Y%m%dT%H%M%SZ)"
docker build --platform linux/amd64 -t "sentiment-api-mlops:$IMAGE_TAG" .
docker run -d --name sentiment-aws-demo \
  --memory=2g --cpus=1 \
  -p 127.0.0.1:8000:8000 \
  "sentiment-api-mlops:$IMAGE_TAG"
docker logs -f sentiment-aws-demo
```

After `Application startup complete`, press Ctrl+C to exit log following; the
container continues running. Then verify the API:

```bash
curl -fsS http://127.0.0.1:8000/ready
curl -fsS http://127.0.0.1:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"text":"I love deploying on AWS!"}'
docker stop sentiment-aws-demo
docker rm sentiment-aws-demo
```

The Docker build downloads the pinned model as the runtime user. Serving uses
that cache with offline mode enabled, avoiding a model download during startup.

## 4. Push the tested image and save its digest

```bash
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"
docker tag "sentiment-api-mlops:$IMAGE_TAG" "$ECR_URL:$IMAGE_TAG"
docker push "$ECR_URL:$IMAGE_TAG"

IMAGE_DIGEST=$(aws ecr describe-images \
  --repository-name sentiment-api-mlops \
  --image-ids "imageTag=$IMAGE_TAG" \
  --query 'imageDetails[0].imageDigest' --output text --no-cli-pager)
```

Check that the returned digest matches `docker push`. Replace the placeholder
while retaining the local client restriction and stopped default:

```bash
cat > infra/terraform.tfvars <<EOF
aws_region          = "$AWS_REGION"
allowed_client_cidr = "$CLIENT_IP/32"
image_digest        = "$IMAGE_DIGEST"
desired_count       = 0
EOF
```

ECR tags are immutable. Use a new tag for each build. Terraform deploys by digest
so the task runs the exact pushed image.

## 5. Deploy and verify

```bash
terraform -chdir=infra plan -var='desired_count=1'
terraform -chdir=infra apply -var='desired_count=1'
```

With only the ECR repository already created, expect 15 additions and no changes
or deletions. Review the region, digest, and allowed client CIDR before approving.
Terraform waits for the service to reach a steady state. On errors or timeouts,
inspect the service and its events: a failed apply can leave running resources.

In ECS, open **Clusters → sentiment-api-mlops → Tasks**, select the running task,
and copy its public IP from Networking. Set it below:

```bash
TASK_PUBLIC_IP=REPLACE_WITH_TASK_PUBLIC_IP
curl -fsS --connect-timeout 10 "http://$TASK_PUBLIC_IP:8000/ready"
curl -fsS --connect-timeout 10 "http://$TASK_PUBLIC_IP:8000/predict" \
  -H 'Content-Type: application/json' \
  -d '{"text":"I love deploying on AWS!"}'
```

Open `http://TASK_PUBLIC_IP:8000/docs` for interactive documentation, substituting
the actual IP. Only the allowed client IP can reach the API. If your network or
VPN changes, update `allowed_client_cidr` and review/apply the change.

Inspect logs from the terminal or open the `/ecs/sentiment-api-mlops` log group
in CloudWatch:

```bash
aws logs tail /ecs/sentiment-api-mlops --since 30m --no-cli-pager
```

ECS should report a running, healthy task. Capture startup logs and successful
requests, redacting personal IP addresses and identifiers before publication.
The repository's [deployment evidence](../README.md#deployment-evidence) records
the completed demo.

## 6. Stop compute

```bash
terraform -chdir=infra apply -var='desired_count=0'
aws ecs describe-services \
  --cluster sentiment-api-mlops --services sentiment-api \
  --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount}' \
  --no-cli-pager
```

Confirm all three counts are zero. The local variable file keeps
`desired_count = 0`, so ordinary applies keep it stopped. To run another demo,
use `-var='desired_count=1'` explicitly and retrieve its new public IP.
ECR image storage and retained logs can still incur usage while compute is stopped.

## 7. Delete images and destroy infrastructure

After stopping compute, remove the image pushed in this session:

```bash
aws ecr batch-delete-image --repository-name sentiment-api-mlops \
  --image-ids "imageDigest=$IMAGE_DIGEST" --no-cli-pager
aws ecr list-images --repository-name sentiment-api-mlops --no-cli-pager
```

If other images remain, explicitly delete those too before proceeding. For a
new terminal session, retrieve digests using `list-images` rather than relying
on the old shell variable. The repository uses `force_delete = false`, so
Terraform refuses to delete a repository that still contains images.

```bash
terraform -chdir=infra plan -destroy
terraform -chdir=infra destroy
terraform -chdir=infra state list
```

Review the plan; a complete deployment has 16 managed resources. After destruction,
`state list` should produce no output. Confirm the demo's ECS cluster, ECR
repository, CloudWatch log group, and VPC no longer exist. Terraform deregisters
the task definition; its inactive record does not run compute and can be deleted
separately in ECS. Check billing after usage data updates; past usage can appear
after resources are deleted.

Finish by removing local registry credentials and signing out of the CLI:

```bash
docker logout "$ECR_REGISTRY"
aws logout --profile "$AWS_PROFILE"
```

Sign out of the browser console separately.

## State and limitations

State is local for this single-developer demo. Keep `terraform.tfstate` and its
backup until cleanup is complete; they identify resources needed for teardown.
State, plans, local variable files, and downloaded providers are ignored by Git.
Commit `.terraform.lock.hcl`. Never commit credentials or state.

This deployment uses HTTP, a changing public task IP, one Availability Zone,
and one task. Updates stop the old task before starting a replacement to limit
compute usage, accepting downtime. Logs have three-day retention. The execution
role is restricted to image pulls and this log group; the application has no
separate task IAM role. GitHub Actions currently tests, evaluates, and publishes
to Docker Hub; AWS delivery is manual.