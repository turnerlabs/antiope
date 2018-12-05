# Cloudfront Auth Stack


## What is it?

The CF auth stack is a AWS stack that uses Cognito auth to secure an S3 bucket by restricting access of the bucket to a specific user pool.

### Inputs
The unique inputs (not in other Antiope stacks) are as follows:

- pUserPoolId: This should typically come from the User Pool defined in the Cognito Stack
- pAuthBucketDomainName: This is the bucket you would like to protect
- pCognitoPoolDomainName: This is the domain name that you have set your User Pool, as far as I know you have to manually find this

### Deploying
Right now auto packaging hasn't been implemented.
    1. `cd cloudfront-auth/lambda/`
    2). `npm install`
    3). `cd ..`
    4). `make deploy`

You will also have to manually configure a few items at this moment.
    1). Go to your User Pool, and click on app client settings.
    2). Look for the client titled `antiope-auth-client-id`
    3). Toggle `Enable Identity Providers`
    4). Set the callback URL to `https://{YOUR_DISTRO}.cloudfront.net/public/index.html`
    5). Tick `Authorization code grant` and `Implicit code grant` for Allowed OAuth flows
    6). Set `Email` and `OpenId` for allowed OAuth scopes

If you are updating an existing lambda, you will also have to manually deploy the Lambda to the distro.
Simply go to the Lambda console -> Actions -> Deploy to Lambda@Edge.

You will also have to manually upload the index html file that all auth redirects to.
    1). `cd cloudfront-auth/`
    2). `aws s3 cp html/index.html s3://{YOUR_BUCKET}/public/index.html`

