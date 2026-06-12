# Deploy to AWS with Terraform + GitHub Actions (OIDC)

Terraform provisions AWS infrastructure. GitHub Actions deploys via **OIDC** (short-lived credentials — no long-lived AWS access keys in GitHub).

## Architecture

```
GitHub Actions  ──OIDC──▶  IAM Role  ──▶  ECR + ECS

Internet  ──▶  ALB
               ├── /api/*, /ws/*  →  FastAPI (ECS Fargate)
               └── /*             →  Next.js (ECS Fargate)
                        ↓
                 Supabase Postgres
```

## Prerequisites

- AWS account with MFA on root (no root access keys)
- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.6
- [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) with `aws login` support
- Supabase `DATABASE_URL`

---

## 1. Local Terraform (use `aws login`, not root keys)

Amazon recommends **short-lived credentials** for local development:

```bash
aws login
```

Then run Terraform:

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit: database_url, secrets, github_owner, github_repo

terraform init
terraform plan
terraform apply
```

Save outputs:

```bash
terraform output alb_dns_name
terraform output github_actions_role_arn
```

After first apply, set `frontend_origin` in `terraform.tfvars` to the ALB URL (`http://<alb_dns>`) and run `terraform apply` again for CORS.

### GitHub OIDC provider already exists?

If `terraform apply` errors because the OIDC provider exists:

```bash
terraform import aws_iam_openid_connect_provider.github \
  arn:aws:iam::YOUR_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com
terraform apply
```

---

## 2. GitHub repository variables (no AWS secrets needed)

Settings → Secrets and variables → Actions → **Variables**:

| Variable | Value |
|---|---|
| `AWS_REGION` | `eu-west-2` |
| `PROJECT_NAME` | `squaddraft` |
| `ENVIRONMENT` | `prod` |
| `AWS_DEPLOY_ROLE_ARN` | From `terraform output github_actions_role_arn` |
| `PUBLIC_API_URL` | `http://<alb-dns>/api/v1` |
| `PUBLIC_WS_URL` | `ws://<alb-dns>/ws` |

**Do not** add `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` — OIDC replaces them.

`PUBLIC_API_URL` / `PUBLIC_WS_URL` are baked into the Next.js Docker build at deploy time.

---

## 3. Deploy flow

1. Push to `main`
2. **CI** — backend tests
3. **Deploy** — GitHub assumes IAM role via OIDC → build images → push ECR → redeploy ECS

Manual: Actions → Deploy → Run workflow.

### First deploy bootstrap

ECS services need images in ECR before they become healthy:

1. `terraform apply` (creates ECR repos + ECS services)
2. Set GitHub variables (especially `AWS_DEPLOY_ROLE_ARN`)
3. Push to `main` or run Deploy workflow manually

---

## 4. Security model

| Actor | Recommended auth |
|---|---|
| You (local Terraform) | `aws login` or IAM Identity Center (SSO) |
| GitHub Actions | OIDC → `squaddraft-prod-github-actions` IAM role |
| Root account | MFA only, **no access keys** |

The GitHub role can only:
- Push to this project's ECR repos
- Redeploy services in this ECS cluster
- Run from `repo:<owner>/<repo>:*` (configured in `terraform.tfvars`)

---

## 5. HTTPS & custom domain (later)

- ACM certificate + Route53
- ALB HTTPS listener
- Update `PUBLIC_API_URL` / `PUBLIC_WS_URL` to `https://` / `wss://`

---

## 6. Remote Terraform state (recommended)

Uncomment the S3 backend in `versions.tf` and create a state bucket + DynamoDB lock table.

---

## Cost ballpark

~**$30–50/month** (ALB + 2× Fargate + ECR). Supabase billed separately.

---

## Local Docker smoke test

```bash
docker build -t squaddraft-api backend
docker build -t squaddraft-web \
  --build-arg NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1 \
  --build-arg NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000/ws \
  frontend
```
