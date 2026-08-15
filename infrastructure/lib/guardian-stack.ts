import { execFileSync } from 'node:child_process';
import * as path from 'node:path';
import * as cdk from 'aws-cdk-lib';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import { Construct } from 'constructs';

export interface GuardianStackProps extends cdk.StackProps {
  /**
   * Bedrock model id used for AI analysis. Must be enabled in the account.
   */
  readonly bedrockModelId?: string;
  /**
   * Point-in-time recovery for the analyses table. Recommended for
   * production; disable in dev sandboxes to shave cost.
   */
  readonly pointInTimeRecovery?: boolean;
}

/**
 * Week 2: full analysis workflow — Step Functions orchestrating the analyze
 * and store Lambdas, with Bedrock access, CloudWatch metrics/alarms, and the
 * Week 1 storage. Week 3 adds the webhook entry point and GitHub publishing.
 *
 * Data-minimization: DynamoDB holds analysis *metadata*; S3 holds sanitized
 * reports (evidence excerpts only). Raw repository source is never stored,
 * and Lambda logs carry metadata only.
 */
export class GuardianStack extends cdk.Stack {
  public readonly analysesTable: dynamodb.Table;
  public readonly reportsBucket: s3.Bucket;
  public readonly stateMachine: sfn.StateMachine;

  constructor(scope: Construct, id: string, props?: GuardianStackProps) {
    super(scope, id, props);

    const bedrockModelId = props?.bedrockModelId ?? 'anthropic.claude-sonnet-5';

    // ------------------------------------------------------------- storage
    this.analysesTable = new dynamodb.Table(this, 'AnalysesTable', {
      // No explicit tableName: a generated name avoids collisions when the
      // stack is deployed more than once per account. Lambdas get it via env.
      partitionKey: { name: 'pk', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'sk', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecoverySpecification: {
        pointInTimeRecoveryEnabled: props?.pointInTimeRecovery ?? true,
      },
      // Webhook delivery-id dedup records expire via TTL.
      timeToLiveAttribute: 'ttl',
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    this.analysesTable.addGlobalSecondaryIndex({
      indexName: 'byRepository',
      partitionKey: { name: 'repository', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'timestamp', type: dynamodb.AttributeType.STRING },
    });

    this.reportsBucket = new s3.Bucket(this, 'ReportsBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [
        { id: 'expire-raw-artifacts', prefix: 'artifacts/', expiration: cdk.Duration.days(90) },
        // Reports are write-once; without this, versioning accumulates
        // storage forever.
        { id: 'expire-noncurrent-versions', noncurrentVersionExpiration: cdk.Duration.days(30) },
      ],
    });

    // ------------------------------------------------------------- secrets
    // {"token": "<PAT or app token>", "webhook_secret": "<generated>"}
    // The webhook_secret is generated at deploy; copy it into the GitHub
    // webhook settings. Replace REPLACE_ME with a real token after deploy —
    // never commit tokens.
    const githubSecret = new secretsmanager.Secret(this, 'GitHubSecret', {
      description: 'AI-SDLC Guardian: GitHub API token and webhook secret',
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ token: 'REPLACE_ME' }),
        generateStringKey: 'webhook_secret',
        excludePunctuation: true,
        passwordLength: 48,
      },
    });

    // ------------------------------------------------------------- lambdas
    const metricsNamespace = 'AiSdlcGuardian';
    const commonEnv = {
      GUARDIAN_TABLE: this.analysesTable.tableName,
      GUARDIAN_BUCKET: this.reportsBucket.bucketName,
      GUARDIAN_METRICS_NAMESPACE: metricsNamespace,
      GUARDIAN_BEDROCK_MODEL_ID: bedrockModelId,
      GUARDIAN_BEDROCK_REGION: this.region,
    };

    // Bundles the guardian package + pydantic into the asset. Preferred path
    // is host pip cross-installing linux/arm64 wheels (works without Docker,
    // and pydantic-core needs the correct platform binary); Docker bundling
    // is the fallback when host pip is unavailable.
    const backendDir = path.join(__dirname, '..', '..', 'backend');
    const hostPipBundling: cdk.ILocalBundling = {
      tryBundle(outputDir: string): boolean {
        try {
          execFileSync(
            'python3',
            [
              '-m', 'pip', 'install', '--quiet', '--no-cache-dir', backendDir,
              '-t', outputDir,
              '--platform', 'manylinux2014_aarch64',
              '--only-binary=:all:',
              '--python-version', '3.12',
              '--implementation', 'cp',
            ],
            { stdio: ['ignore', 'inherit', 'inherit'] },
          );
          return true;
        } catch {
          return false; // fall back to Docker bundling
        }
      },
    };
    const backendCode = lambda.Code.fromAsset(backendDir, {
      bundling: {
        image: lambda.Runtime.PYTHON_3_12.bundlingImage,
        platform: 'linux/arm64',
        command: [
          'bash', '-c',
          'pip install --no-cache-dir . -t /asset-output && find /asset-output -name "*.pyc" -delete',
        ],
        local: hostPipBundling,
      },
    });

    const makeFunction = (name: string, handlerPath: string, timeout: cdk.Duration, memory: number) => {
      const logGroup = new logs.LogGroup(this, `${name}Logs`, {
        retention: logs.RetentionDays.ONE_MONTH,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      });
      return new lambda.Function(this, name, {
        runtime: lambda.Runtime.PYTHON_3_12,
        architecture: lambda.Architecture.ARM_64, // ~20% cheaper than x86
        code: backendCode,
        handler: handlerPath,
        timeout,
        memorySize: memory,
        environment: commonEnv,
        logGroup,
      });
    };

    const fetchFn = makeFunction('FetchFunction', 'guardian.handlers.fetch.handler', cdk.Duration.minutes(2), 512);
    const analyzeFn = makeFunction('AnalyzeFunction', 'guardian.handlers.analyze.handler', cdk.Duration.minutes(5), 1024);
    const storeFn = makeFunction('StoreFunction', 'guardian.handlers.store.handler', cdk.Duration.minutes(1), 512);
    const commentFn = makeFunction('CommentFunction', 'guardian.handlers.comment.handler', cdk.Duration.minutes(2), 512);

    for (const fn of [fetchFn, commentFn]) {
      fn.addEnvironment('GUARDIAN_GITHUB_SECRET_ARN', githubSecret.secretArn);
      githubSecret.grantRead(fn);
    }
    this.reportsBucket.grantPut(fetchFn, 'artifacts/*');
    this.reportsBucket.grantRead(commentFn, 'reports/*');
    commentFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['cloudwatch:PutMetricData'],
        resources: ['*'],
        conditions: { StringEquals: { 'cloudwatch:namespace': metricsNamespace } },
      }),
    );

    // Least privilege: analyze reads artifacts + invokes exactly one model;
    // store writes the table/bucket and publishes to one metric namespace.
    this.reportsBucket.grantRead(analyzeFn, 'artifacts/*');
    analyzeFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeModel'],
        resources: [
          `arn:${this.partition}:bedrock:${this.region}::foundation-model/${bedrockModelId}`,
          `arn:${this.partition}:bedrock:${this.region}:${this.account}:inference-profile/*.${bedrockModelId}`,
        ],
      }),
    );
    this.analysesTable.grantWriteData(storeFn);
    this.reportsBucket.grantPut(storeFn, 'reports/*');
    storeFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['cloudwatch:PutMetricData'],
        resources: ['*'],
        conditions: { StringEquals: { 'cloudwatch:namespace': metricsNamespace } },
      }),
    );

    // ------------------------------------------------------ state machine
    const fetchTask = new tasks.LambdaInvoke(this, 'FetchPRDiff', {
      lambdaFunction: fetchFn,
      outputPath: '$.Payload',
      taskTimeout: sfn.Timeout.duration(cdk.Duration.minutes(3)),
    });
    fetchTask.addRetry({
      // GitHub 5xx/rate limits surface as handler errors; retry with backoff.
      errors: ['States.ALL'],
      interval: cdk.Duration.seconds(10),
      maxAttempts: 3,
      backoffRate: 2,
    });

    const analyzeTask = new tasks.LambdaInvoke(this, 'RunAnalysis', {
      lambdaFunction: analyzeFn,
      outputPath: '$.Payload',
      taskTimeout: sfn.Timeout.duration(cdk.Duration.minutes(6)),
    });
    analyzeTask.addRetry({
      errors: ['Lambda.ServiceException', 'Lambda.TooManyRequestsException', 'States.Timeout'],
      interval: cdk.Duration.seconds(5),
      maxAttempts: 2,
      backoffRate: 2,
    });

    const storeTask = new tasks.LambdaInvoke(this, 'StoreResults', {
      lambdaFunction: storeFn,
      outputPath: '$.Payload',
      taskTimeout: sfn.Timeout.duration(cdk.Duration.minutes(2)),
    });
    storeTask.addRetry({
      errors: ['States.ALL'],
      interval: cdk.Duration.seconds(3),
      maxAttempts: 3,
      backoffRate: 2,
    });

    const commentTask = new tasks.LambdaInvoke(this, 'PublishComment', {
      lambdaFunction: commentFn,
      outputPath: '$.Payload',
      taskTimeout: sfn.Timeout.duration(cdk.Duration.minutes(3)),
    });
    commentTask.addRetry({
      errors: ['States.ALL'],
      interval: cdk.Duration.seconds(10),
      maxAttempts: 3,
      backoffRate: 2,
    });

    const failed = new sfn.Fail(this, 'AnalysisFailed', {
      causePath: '$.Cause',
      errorPath: '$.Error',
    });
    fetchTask.addCatch(failed, { errors: ['States.ALL'] });
    analyzeTask.addCatch(failed, { errors: ['States.ALL'] });
    storeTask.addCatch(failed, { errors: ['States.ALL'] });
    commentTask.addCatch(failed, { errors: ['States.ALL'] });

    const definition = fetchTask
      .next(analyzeTask)
      .next(storeTask)
      .next(commentTask)
      .next(new sfn.Succeed(this, 'AnalysisComplete'));

    const sfnLogs = new logs.LogGroup(this, 'WorkflowLogs', {
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    this.stateMachine = new sfn.StateMachine(this, 'AnalysisWorkflow', {
      definitionBody: sfn.DefinitionBody.fromChainable(definition),
      timeout: cdk.Duration.minutes(15),
      tracingEnabled: true,
      logs: { destination: sfnLogs, level: sfn.LogLevel.ERROR },
    });

    // ------------------------------------------------------------- webhook
    // Function URL instead of API Gateway: one endpoint, no per-request
    // cost. authType NONE is deliberate — HMAC signature verification with
    // the shared webhook secret is the authentication (ADR-003).
    const webhookFn = makeFunction('WebhookFunction', 'guardian.handlers.webhook.handler', cdk.Duration.seconds(15), 256);
    webhookFn.addEnvironment('GUARDIAN_GITHUB_SECRET_ARN', githubSecret.secretArn);
    webhookFn.addEnvironment('GUARDIAN_STATE_MACHINE_ARN', this.stateMachine.stateMachineArn);
    githubSecret.grantRead(webhookFn);
    this.analysesTable.grantWriteData(webhookFn); // delivery-id dedup records
    this.stateMachine.grantStartExecution(webhookFn);
    webhookFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['cloudwatch:PutMetricData'],
        resources: ['*'],
        conditions: { StringEquals: { 'cloudwatch:namespace': metricsNamespace } },
      }),
    );

    const webhookUrl = webhookFn.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
    });

    // ------------------------------------------------------------- alarms
    new cloudwatch.Alarm(this, 'WebhookErrorsAlarm', {
      metric: webhookFn.metricErrors({ period: cdk.Duration.minutes(5) }),
      threshold: 1,
      evaluationPeriods: 1,
      alarmDescription: 'The AI-SDLC Guardian webhook receiver is throwing errors.',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    new cloudwatch.Alarm(this, 'WorkflowFailuresAlarm', {
      metric: this.stateMachine.metricFailed({ period: cdk.Duration.minutes(5) }),
      threshold: 1,
      evaluationPeriods: 1,
      alarmDescription: 'An AI-SDLC Guardian analysis workflow execution failed.',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    new cdk.CfnOutput(this, 'AnalysesTableName', { value: this.analysesTable.tableName });
    new cdk.CfnOutput(this, 'ReportsBucketName', { value: this.reportsBucket.bucketName });
    new cdk.CfnOutput(this, 'StateMachineArn', { value: this.stateMachine.stateMachineArn });
    new cdk.CfnOutput(this, 'WebhookUrl', {
      value: webhookUrl.url,
      description: 'Set as the GitHub webhook Payload URL (content type application/json)',
    });
    new cdk.CfnOutput(this, 'GitHubSecretArn', {
      value: githubSecret.secretArn,
      description: 'Put a real GitHub token in this secret; copy webhook_secret into GitHub',
    });
  }
}
