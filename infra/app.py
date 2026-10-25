import os

import aws_cdk as cdk

from dynamic_forms_infra.stack import DynamicFormsStack

app = cdk.App()
DynamicFormsStack(
    app,
    "DynamicFormsStack",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "ca-central-1"),
    ),
)
app.synth()
