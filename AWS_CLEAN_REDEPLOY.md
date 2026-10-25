# Clean Destroy and Redeploy Runbook

This runbook removes the `DynamicFormsStack` and creates it again in `ca-central-1`. It is intentionally specific to this repository and its current CDK stack.

## Read This First

Destroying the stack deletes the running RDS database and its data. The CDK stack is configured to take a final RDS snapshot, but the new deployment will create a new, empty database. Restoring the old data from that snapshot is a separate operation and is not covered by this clean-redeploy procedure.

Do not continue if you need the current database to remain live or need the new stack to use its data. Stop and plan a snapshot restore instead.

The stack also retains its fixed-name S3 artifacts bucket. A new stack cannot create that same bucket until it has been removed. The generated database secret has a fixed name too, so it may need immediate deletion before the new stack can create it.

This procedure does not delete the CDK bootstrap stack (`CDKToolkit`), the GitHub OIDC role/provider, or the separate xAI API key secret. Do not delete those as part of this runbook.

## 1. Prepare and Confirm the AWS Account

Use PowerShell from the repository. Confirm the changes you want are committed and pushed if you plan to deploy through GitHub Actions. The infrastructure workflow deploys the version on `master`.

```powershell
Set-Location "E:\Srikanth\Srikanth\Learning\Dynamic_Forms\infra"
.\.venv\Scripts\Activate.ps1
$Region = "ca-central-1"
$StackName = "DynamicFormsStack"
$AccountId = aws sts get-caller-identity --query Account --output text
$AccountId
```

The expected account for this deployment is `982751471336`. Stop if the displayed account is different. If you intentionally moved the deployment to another account, update the expected account only after verifying that is the intended destination.

```powershell
if ($AccountId -ne "982751471336") { throw "Wrong AWS account. Stop before continuing." }
```

Confirm the stack exists and record the retained bucket and RDS instance identifiers. These values are useful for verifying cleanup and finding the final snapshot.

```powershell
$BucketName = aws cloudformation describe-stacks `
  --stack-name $StackName `
  --query "Stacks[0].Outputs[?OutputKey=='ArtifactsBucket'].OutputValue | [0]" `
  --output text `
  --region $Region

$DbIdentifier = aws cloudformation list-stack-resources `
  --stack-name $StackName `
  --query "StackResourceSummaries[?ResourceType=='AWS::RDS::DBInstance'].PhysicalResourceId | [0]" `
  --output text `
  --region $Region

Write-Host "Account: $AccountId"
Write-Host "Region: $Region"
Write-Host "Stack: $StackName"
Write-Host "RDS instance: $DbIdentifier"
Write-Host "Retained bucket: $BucketName"
```

If either resource value is blank or `None`, stop and inspect the stack in the AWS CloudFormation console before proceeding.

## 2. Disable RDS Deletion Protection

The stack enables RDS deletion protection. CloudFormation cannot delete the DB instance while protection is on.

```powershell
aws rds modify-db-instance `
  --db-instance-identifier $DbIdentifier `
  --no-deletion-protection `
  --apply-immediately `
  --region $Region

aws rds wait db-instance-available `
  --db-instance-identifier $DbIdentifier `
  --region $Region
```

Check that protection is off before continuing:

```powershell
aws rds describe-db-instances `
  --db-instance-identifier $DbIdentifier `
  --query "DBInstances[0].{Status:DBInstanceStatus,DeletionProtection:DeletionProtection}" `
  --output table `
  --region $Region
```

Proceed only when `DeletionProtection` is `False` and the instance is available.

## 3. Destroy the CDK Stack

The command asks for confirmation. Read the prompt and confirm only if you are ready to remove the application resources and active database.

```powershell
cdk destroy $StackName
```

Do not use this command against `CDKToolkit`. The bootstrap stack is shared CDK infrastructure and is not part of this application stack.

Wait for the `DynamicFormsStack` stack to reach `DELETE_COMPLETE` in CloudFormation. The RDS removal policy is `SNAPSHOT`, so keep the final snapshot if there is any chance you will need the old data. The fresh deployment will not restore it automatically. Snapshots incur storage charges until deleted.

## 4. Remove Retained Resources for a Truly Clean Rebuild

These steps permanently remove the remaining fixed-name resources. Skip them only if you intend to keep and reuse those resources, and understand that the current CDK stack is not configured to import them.

### Delete the retained artifacts bucket

The bucket contains deployment artifacts and is retained when the stack is destroyed. `--force` deletes its objects before removing the bucket.

```powershell
aws s3 rb "s3://$BucketName" --force --region $Region
```

### Permanently delete the generated database secret

The RDS secret name is `dynamic-forms/rds-credentials`. CloudFormation may schedule it for deletion with a recovery window. The following command skips recovery and permanently removes it; use it only after confirming the stack has been destroyed and you do not need the old credentials.

```powershell
aws secretsmanager delete-secret `
  --secret-id "dynamic-forms/rds-credentials" `
  --force-delete-without-recovery `
  --region $Region
```

Do not delete `dynamic-forms/xai-api-key`; it is a separate secret used by the application.

### Optional: delete the final RDS snapshot

The final snapshot is the recovery path for the old database. Keep it unless you are certain the data is disposable. To permanently remove it, open **RDS -> Snapshots** in `ca-central-1`, verify that it belongs to the database you just destroyed, and delete that snapshot. Do not delete unrelated snapshots.

## 5. Deploy a Fresh Stack

Before deploying, confirm that the repository contains the code and SQL schema/migrations you want the new EC2 instance to use. The instance bootstrap clones the configured branch and applies the schema on its first launch.

Deploy locally from `infra/`:

```powershell
cdk synth
cdk diff $StackName
cdk deploy $StackName
```

Review the diff. For a fresh stack it should show the new resources. Confirm the deployment when CDK prompts. Alternatively, run **Deploy Infrastructure** from GitHub Actions after the desired `infra/**` changes are pushed to `master`.

If CDK reports that the environment is not bootstrapped, bootstrap only this account and region, then retry the deploy:

```powershell
cdk bootstrap "aws://$AccountId/$Region"
cdk deploy $StackName
```

Do not destroy the bootstrap stack as part of application cleanup.

## 6. Wait for the Application Instance and Deploy the App

CDK completion means CloudFormation created the resources; EC2 user data may still be installing packages and starting services. In AWS, wait until the new EC2 instance is online in **Systems Manager -> Fleet Manager -> Managed nodes**.

Then run these GitHub Actions workflows manually, in order:

1. **Deploy Backend**
2. **Deploy Frontend**

The workflows have `workflow_dispatch` triggers. A push that only changes the infrastructure workflow does not trigger the frontend or backend workflows. The initial EC2 bootstrap applies `db/sql/schema.sql` and migrations once, then the backend workflow syncs code/dependencies and restarts the API. The frontend workflow builds and publishes the Angular files.

If an SSM deployment fails because the instance is not online yet, wait for SSM registration and rerun the failed workflow.

## 7. Verify the New Deployment

In **CloudFormation -> DynamicFormsStack -> Outputs**, record `PublicIp` and `InstanceId`. Test:

- `http://<PublicIp>/` for the frontend
- `http://<PublicIp>/docs` for FastAPI documentation

If the backend is unhealthy, use an SSM session to inspect `/var/log/dynamic-forms-bootstrap.log` and `sudo journalctl -u dynamic-forms-api`. The bootstrap script currently ignores individual migration errors with `|| true`, so inspect the log if database-backed routes fail even when the service starts.

## Recovery and Cost Notes

- To preserve the old data, stop before destroying the stack or explicitly restore the final snapshot into a new RDS instance and update the infrastructure/application configuration to use it. A normal fresh deploy creates an empty database.
- Keep the final snapshot until the new application has been verified and you are certain the old data is no longer needed.
- Removing the EC2 and RDS stack does not remove the GitHub OIDC role, the CDK bootstrap resources, or the separate xAI secret.
- EC2, RDS, EBS, snapshots, and public IPv4 addresses can incur charges. Verify resources and snapshots in the AWS console after the run.

## AWS CLI References

- [Modify an RDS DB instance](https://docs.aws.amazon.com/cli/latest/reference/rds/modify-db-instance.html)
- [Delete a Secrets Manager secret](https://docs.aws.amazon.com/cli/latest/reference/secretsmanager/delete-secret.html)
- [Remove an S3 bucket](https://docs.aws.amazon.com/cli/latest/reference/s3/rb.html)