#!/bin/bash
# Розгортання PARCS-Python в AWS EC2 (запускати в AWS CloudShell).
#   bash deploy_aws.sh up     - створити master + 4 воркери
#   bash deploy_aws.sh down   - видалити всі VM parcs-* і групу безпеки parcs-sg
set -e
export AWS_PAGER=""
REGION=${REGION:-eu-north-1}
TYPE=${TYPE:-t3.micro}
WORKERS=${WORKERS:-4}
aws configure set region "$REGION"

ids_by_name() {
  aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=$1" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --query 'Reservations[].Instances[].InstanceId' --output text
}

up() {
  AMI=$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
        --query Parameter.Value --output text)
  SG=$(aws ec2 create-security-group --group-name parcs-sg --description "PARCS lab" --query GroupId --output text)
  aws ec2 authorize-security-group-ingress --group-id "$SG" --protocol all --source-group "$SG" > /dev/null
  aws ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port 8080 --cidr 0.0.0.0/0 > /dev/null
  aws ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port 22 --cidr 0.0.0.0/0 > /dev/null

  cat > master.sh <<'EOF'
#!/bin/bash
dnf install -y docker
systemctl enable --now docker
docker run -d --name parcs --restart unless-stopped --network host -e PARCS_ARGS="master" hummer12007/parcs-node
EOF
  MASTER_ID=$(aws ec2 run-instances --image-id "$AMI" --instance-type "$TYPE" --security-group-ids "$SG" \
      --user-data file://master.sh \
      --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=parcs-master}]' \
      --query 'Instances[0].InstanceId' --output text)
  aws ec2 wait instance-running --instance-ids "$MASTER_ID"
  MASTER_IP=$(aws ec2 describe-instances --instance-ids "$MASTER_ID" \
      --query 'Reservations[0].Instances[0].PrivateIpAddress' --output text)

  sed "s/\"master\"/\"worker $MASTER_IP\"/" master.sh > worker.sh
  aws ec2 run-instances --image-id "$AMI" --instance-type "$TYPE" --count "$WORKERS" --security-group-ids "$SG" \
      --user-data file://worker.sh \
      --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=parcs-worker}]' > /dev/null

  PUBLIC_IP=$(aws ec2 describe-instances --instance-ids "$MASTER_ID" \
      --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
  echo "Master: $MASTER_ID ($MASTER_IP)"
  echo "Веб-інтерфейс (через 3-4 хв): http://$PUBLIC_IP:8080"
}

down() {
  IDS="$(ids_by_name 'parcs-*')"
  if [ -n "$IDS" ]; then
    aws ec2 terminate-instances --instance-ids $IDS > /dev/null
    aws ec2 wait instance-terminated --instance-ids $IDS
  fi
  SG=$(aws ec2 describe-security-groups --filters Name=group-name,Values=parcs-sg \
       --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)
  if [ -n "$SG" ] && [ "$SG" != "None" ]; then
    aws ec2 delete-security-group --group-id "$SG"
  fi
  echo "Видалено"
}

case "$1" in
  up) up ;;
  down) down ;;
  *) echo "Використання: bash deploy_aws.sh up|down"; exit 1 ;;
esac
