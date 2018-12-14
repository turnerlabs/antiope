# Cloudfront Auth Stack


## What is it?

The CF auth stack is a AWS stack that uses Cognito auth to secure an S3 bucket by restricting access of the bucket to a specific user pool.

### How it works?
The desired S3 bucket to protect is placed in front of a CloudFront distribution. The S3 bucket is then made private with only the special CloudFront access identity able to access content. This Cloudfront distribution has two behaviors, one for `public/index.html` and one for `*`.

The wildcard behavior is shown below:


![Alt Image](https://user-images.githubusercontent.com/14262055/49660211-0aa9f300-fa14-11e8-91fd-8c86e9ae746b.png)


As you can see, it essentially uses Lambda@Edge to check if the appropriate auth cookie has been set, and if not redirects the user to the Cognito login portal. On sucessful login, the user will be redirected to `public/index.html`.

The behavior for this is shown below:

![Alt Image](https://user-images.githubusercontent.com/14262055/49660212-0aa9f300-fa14-11e8-9d59-901eced101dc.png)

As you can see the page is *publicly available*, please keep this in mind. However, all it servers to do is to set the auth cookie if it is available after redirect from cognito.

Unfortunately, as of now, it does not redirect you back to the requested content, so you will have to revisit the content on sucessful login.

### Inputs
The unique inputs (not in other Antiope stacks) are as follows:

- pUserPoolId: This should typically come from the User Pool defined in the Cognito Stack
- pAuthBucketDomainName: This is the bucket you would like to protect
- pCognitoPoolDomainName: This is the domain name that you have set your User Pool, as far as I know you have to manually find this

### Deploying

**Make sure to set Stacktime out to 60m**

    1. `cd cloudfront-auth/`
    2). `make deploy`

You will also have to manually configure a few items at this moment.

    1). Go to your User Pool, and click on app client settings.

    2). Look for the client titled `antiope-auth-client-id`

    3). Toggle `Enable Identity Providers`

    4). Set the callback URL to `https://{YOUR_DISTRO}.cloudfront.net/public/index.html`

    5). Tick `Authorization code grant` and `Implicit code grant` for Allowed OAuth flows

    6). Set `Email` and `OpenId` for allowed OAuth scopes
Possible solution: [Custom Resources](https://github.com/rosberglinhares/CloudFormationCognitoCustomResources)

Another note, you may get a 503, if so this means that the server is still setting up its parameters. Because CF is caching this, any subsequent requests for a while will 503. If you 503, just invalidate the cache or wait a while.
Possible solution: If 503 -> no-cache header?

On top of deploying the CloudFormation template, the deploy task will also run two scripts. `bin/deploy-html.sh` and `bin/deploy-edge.sh`. These run after the CFM has finished. The former simply gets the S3 bucket associated with the cloudfront distribution, and copies the `html/index.html` file to the path `s3://{YOUR_BUCKET}/public/index.html`.
