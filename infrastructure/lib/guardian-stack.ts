import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

/**
 * Week 1 foundation: storage only. Week 2 adds the Step Functions workflow,
 * Lambda analyzers, and Bedrock permissions; Week 3 adds the webhook entry
 * point and Secrets Manager wiring.
 *
 * Data-minimization: DynamoDB holds analysis *metadata* (scores, timings,
 * status), S3 holds sanitized reports. Raw repository source is never stored.
 */
export class GuardianStack extends cdk.Stack {
  public readonly analysesTable: dynamodb.Table;
  public readonly reportsBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    this.analysesTable = new dynamodb.Table(this, 'AnalysesTable', {
      tableName: 'guardian-analyses',
      // pk: "REPO#<owner/repo>#PR#<number>", sk: "TS#<iso-timestamp>#<analysisId>"
      partitionKey: { name: 'pk', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'sk', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // Dashboard access pattern: recent analyses per repository.
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
        {
          id: 'expire-raw-artifacts',
          prefix: 'artifacts/',
          expiration: cdk.Duration.days(90),
        },
      ],
    });

    new cdk.CfnOutput(this, 'AnalysesTableName', { value: this.analysesTable.tableName });
    new cdk.CfnOutput(this, 'ReportsBucketName', { value: this.reportsBucket.bucketName });
  }
}
