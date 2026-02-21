# AWS Deployment Guide

This guide details how to deploy the **Arabic AI Legal Case Analysis Assistant** to AWS using Docker and EC2.

## Prerequisites

1.  **AWS Account**: You need an active AWS account.
2.  **AWS CLI**: Installed and configured with your credentials (`aws configure`).
3.  **Docker**: Installed and running on your local machine.

---

## 🏗️ Step 1: Prepare the Docker Images

You can build the images locally to verify them.

```bash
# Build Backend
docker build -t legal-assistant-backend ./backend

# Build Frontend
docker build -t legal-assistant-frontend ./frontend
```

## ☁️ Step 2: Push Images to AWS ECR (Elastic Container Registry)

AWS ECR stores your Docker images so your EC2 instance can pull them.

1.  **Create Repositories**:
    Go to the AWS Console -> ECR -> Create Repository.
    Create two repositories:
    - `legal-assistant-backend`
    - `legal-assistant-frontend`

2.  **Login to ECR**:
    ```bash
    aws ecr get-login-password --region <your-region> | docker login --username AWS --password-stdin <your-account-id>.dkr.ecr.<your-region>.amazonaws.com
    ```

3.  **Tag and Push Backend**:
    ```bash
    docker tag legal-assistant-backend:latest <your-account-id>.dkr.ecr.<your-region>.amazonaws.com/legal-assistant-backend:latest
    docker push <your-account-id>.dkr.ecr.<your-region>.amazonaws.com/legal-assistant-backend:latest
    ```

4.  **Tag and Push Frontend**:
    ```bash
    docker tag legal-assistant-frontend:latest <your-account-id>.dkr.ecr.<your-region>.amazonaws.com/legal-assistant-frontend:latest
    docker push <your-account-id>.dkr.ecr.<your-region>.amazonaws.com/legal-assistant-frontend:latest
    ```

---

## 🖥️ Step 3: Launch AWS EC2 Instance

Since this application uses local LLMs, we need an instance with sufficient RAM.

1.  **Launch Instance**:
    Go to AWS Console -> EC2 -> Launch Instance.

2.  **Choose AMI**:
    Select **Ubuntu Server 22.04 LTS (HVM), SSD Volume Type**.

3.  **Choose Instance Type**:
    - **Recommended**: `t3.xlarge` or `m5.xlarge` (4 vCPU, 16 GB RAM).
    - **For GPU acceleration**: `g4dn.xlarge` (NVIDIA T4 GPU).

4.  **Configure Storage**:
    - Set the Root volume size to at least **50 GB** (gp3) to accommodate Docker images and AI models.

5.  **Configure Security Group**:
    - Allow **SSH (22)** from your IP.
    - Allow **HTTP (80)** from Anywhere (0.0.0.0/0).
    - Allow **Custom TCP (5000)** from Anywhere (optional, for backend checks).

6.  **Launch** and connect via SSH.

---

## 🚀 Step 4: Deploy on EC2

Once connected to your EC2 instance via SSH:

1.  **Install Docker & Docker Compose**:
    ```bash
    sudo apt-get update
    sudo apt-get install -y docker.io docker-compose
    sudo usermod -aG docker $USER
    # Log out and log back in for group changes to take effect
    ```

2.  **Authenticate with ECR**:
    (Run the same login command from Step 2 on the EC2 instance).

3.  **Copy `docker-compose.yml`**:
    You can transfer the file using `scp` or create it directly:
    ```bash
    nano docker-compose.yml
    # Paste the content of your docker-compose.yml here
    ```

4.  **Update `docker-compose.yml` Image Names**:
    Edit the `docker-compose.yml` to use your ECR image URIs instead of local build contexts.
    
    *Change:*
    ```yaml
    services:
      backend:
        build: ...
    ```
    *To:*
    ```yaml
    services:
      backend:
        image: <your-account-id>.dkr.ecr.<your-region>.amazonaws.com/legal-assistant-backend:latest
    ```
    (Repeat for frontend).

5.  **Run the Application**:
    ```bash
    docker-compose up -d
    ```

6.  **Verify**:
    Open your browser and visit the **Public IPv4 address** of your EC2 instance. The application should be live!

---

## 🔧 Troubleshooting

- **Models not loading?**: Check container logs `docker logs legal-assistant-backend`. Ensure the instance has enough RAM (16GB+).
- **Connection refused?**: Check EC2 Security Group rules for port 80.
