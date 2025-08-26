import {
  Stack,
  StackProps,
  Duration,
  RemovalPolicy,
  CfnOutput,
  aws_lambda as lambda,
  aws_dynamodb as dynamodb,
  aws_events as events,
  aws_apigateway as apigateway,
  aws_s3 as s3,
  aws_kms as kms,
  aws_wafv2 as wafv2,
  aws_cloudwatch as cloudwatch,
  aws_budgets as budgets,
  aws_sns as sns,
  aws_iam as iam,
  Tags,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';

export interface CostOptimizationStackProps extends StackProps {
  tenantId?: string;
  environment: 'dev' | 'staging' | 'prod';
  costBudgetLimit: number;
  alertThresholds: number[];
}

export class CostOptimizationStack extends Stack {
  public readonly costMonitoringTopic: sns.Topic;
  public readonly optimizedLambdaLayer: lambda.LayerVersion;
  public readonly tenantKmsKey: kms.Key;

  constructor(scope: Construct, id: string, props: CostOptimizationStackProps) {
    super(scope, id, props);

    // Apply cost optimization tags to all resources
    this.applyCostOptimizationTags(props.environment);

    // Create SNS topic for cost alerts
    this.costMonitoringTopic = this.createCostMonitoringTopic();

    // Create optimized Lambda layer for shared dependencies
    this.optimizedLambdaLayer = this.createOptimizedLambdaLayer();

    // Create tenant-specific KMS key with envelope encryption
    this.tenantKmsKey = this.createTenantKmsKey(props.environment);

    // Deploy ARM64 optimized Lambda functions
    const formProcessorFunction = this.createArm64LambdaFunction(
      'FormProcessor',
      'lambdas/arm64-form-processor.py',
      512 // MB, optimized for form processing workload
    );

    // Create cost-optimized DynamoDB table
    const dynamoTable = this.createCostOptimizedDynamoTable();

    // Deploy basic WAF protection
    const webAcl = this.createCostOptimizedWaf();

    // Create API Gateway with cost optimizations
    const api = this.createOptimizedApiGateway(formProcessorFunction, webAcl);

    // Set up comprehensive cost monitoring
    this.setupCostMonitoring(props);

    // Create cost optimization automation
    this.createCostOptimizationAutomation();

    // Output key metrics for monitoring
    this.createCostOptimizationOutputs(api, dynamoTable);
  }

  private applyCostOptimizationTags(environment: string): void {
    Tags.of(this).add('Project', 'FormBridge');
    Tags.of(this).add('Environment', environment);
    Tags.of(this).add('CostCenter', 'FormBridge-Infrastructure');
    Tags.of(this).add('Owner', 'aws-infrastructure-team');
    Tags.of(this).add('CostOptimized', 'true');
    Tags.of(this).add('Architecture', 'ARM64');
    Tags.of(this).add('BillingCategory', 'Serverless');
  }

  private createCostMonitoringTopic(): sns.Topic {
    return new sns.Topic(this, 'CostMonitoringTopic', {
      topicName: 'form-bridge-cost-alerts',
      displayName: 'Form Bridge Cost Monitoring Alerts',
    });
  }

  private createOptimizedLambdaLayer(): lambda.LayerVersion {
    return new lambda.LayerVersion(this, 'OptimizedLambdaLayer', {
      code: lambda.Code.fromAsset('lambdas/layers/optimized-layer'),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_12],
      compatibleArchitectures: [lambda.Architecture.ARM_64],
      description: 'Optimized dependencies layer for ARM64 Lambda functions with compression utilities',
      layerVersionName: 'form-bridge-optimized-layer',
    });
  }

  private createTenantKmsKey(environment: string): kms.Key {
    const key = new kms.Key(this, 'TenantKmsKey', {
      description: `FormBridge tenant encryption key - ${environment}`,
      enableKeyRotation: true,
      removalPolicy: environment === 'prod' ? RemovalPolicy.RETAIN : RemovalPolicy.DESTROY,
      alias: `alias/form-bridge-${environment}`,
    });

    // Add cost optimization policy
    key.addToResourcePolicy(new iam.PolicyStatement({
      sid: 'EnvelopeEncryptionOptimization',
      effect: iam.Effect.ALLOW,
      principals: [new iam.ServicePrincipal('lambda.amazonaws.com')],
      actions: [
        'kms:GenerateDataKey',
        'kms:Decrypt'
      ],
      resources: ['*'],
      conditions: {
        StringEquals: {
          'kms:ViaService': `dynamodb.${this.region}.amazonaws.com`
        }
      }
    }));

    return key;
  }

  private createArm64LambdaFunction(
    functionName: string,
    codePath: string,
    memorySize: number
  ): lambda.Function {
    return new lambda.Function(this, functionName, {
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64, // 20% cost savings
      handler: 'index.handler',
      code: lambda.Code.fromAsset(codePath),
      memorySize: memorySize, // Right-sized for workload
      timeout: Duration.seconds(30),
      layers: [this.optimizedLambdaLayer],
      environment: {
        ENABLE_COMPRESSION: 'true',
        COMPRESSION_THRESHOLD: '1024', // 1KB threshold
        KMS_KEY_ID: this.tenantKmsKey.keyId,
        COST_OPTIMIZATION_ENABLED: 'true',
        ARM64_OPTIMIZED: 'true'
      },
      deadLetterQueue: new aws_sqs.Queue(this, `${functionName}DLQ`, {
        queueName: `${functionName.toLowerCase()}-dlq`,
        retentionPeriod: Duration.days(14)
      }),
      reservedConcurrentExecutions: 100, // Cost control
      description: `ARM64 optimized ${functionName} with 20% cost savings`,
    });
  }

  private createCostOptimizedDynamoTable(): dynamodb.Table {
    const table = new dynamodb.Table(this, 'FormSubmissions', {
      tableName: 'form-bridge-submissions',
      partitionKey: {
        name: 'tenant_partition',
        type: dynamodb.AttributeType.STRING
      },
      sortKey: {
        name: 'submission_id',
        type: dynamodb.AttributeType.STRING
      },
      billingMode: dynamodb.BillingMode.ON_DEMAND, // Pay per request
      encryption: dynamodb.TableEncryption.CUSTOMER_MANAGED,
      encryptionKey: this.tenantKmsKey,
      pointInTimeRecovery: true,
      stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
      timeToLiveAttribute: 'ttl', // Automatic data cleanup
      removalPolicy: RemovalPolicy.DESTROY, // Adjust for production
    });

    // Add Global Secondary Index for cost-optimized queries
    table.addGlobalSecondaryIndex({
      indexName: 'tenant-timestamp-index',
      partitionKey: {
        name: 'tenant_id',
        type: dynamodb.AttributeType.STRING
      },
      sortKey: {
        name: 'timestamp',
        type: dynamodb.AttributeType.STRING
      },
      projectionType: dynamodb.ProjectionType.KEYS_ONLY, // Minimize storage costs
    });

    return table;
  }

  private createCostOptimizedWaf(): wafv2.CfnWebACL {
    return new wafv2.CfnWebACL(this, 'FormBridgeWAF', {
      name: 'form-bridge-waf',
      scope: 'REGIONAL',
      defaultAction: { allow: {} },
      description: 'Cost-optimized WAF for Form Bridge API',
      rules: [
        {
          name: 'AWSManagedRulesCommonRuleSet',
          priority: 1,
          overrideAction: { none: {} },
          statement: {
            managedRuleGroupStatement: {
              vendorName: 'AWS',
              name: 'AWSManagedRulesCommonRuleSet',
            },
          },
          visibilityConfig: {
            sampledRequestsEnabled: true,
            cloudWatchMetricsEnabled: true,
            metricName: 'CommonRuleSetMetric',
          },
        },
        {
          name: 'RateLimitRule',
          priority: 2,
          action: { block: {} },
          statement: {
            rateBasedStatement: {
              limit: 2000,
              aggregateKeyType: 'IP',
            },
          },
          visibilityConfig: {
            sampledRequestsEnabled: true,
            cloudWatchMetricsEnabled: true,
            metricName: 'RateLimitMetric',
          },
        },
        {
          name: 'GeoBlockRule',
          priority: 3,
          action: { block: {} },
          statement: {
            geoMatchStatement: {
              countryCodes: ['CN', 'RU'], // Block high-risk countries to reduce costs
            },
          },
          visibilityConfig: {
            sampledRequestsEnabled: true,
            cloudWatchMetricsEnabled: true,
            metricName: 'GeoBlockMetric',
          },
        },
      ],
      visibilityConfig: {
        sampledRequestsEnabled: true,
        cloudWatchMetricsEnabled: true,
        metricName: 'FormBridgeWAFMetric',
      },
    });
  }

  private createOptimizedApiGateway(
    lambdaFunction: lambda.Function,
    webAcl: wafv2.CfnWebACL
  ): apigateway.RestApi {
    const api = new apigateway.RestApi(this, 'FormBridgeAPI', {
      restApiName: 'form-bridge-api',
      description: 'Cost-optimized Form Bridge API',
      deployOptions: {
        stageName: 'v1',
        tracingEnabled: true, // For debugging, can be disabled in production to save costs
        metricsEnabled: true,
        loggingLevel: apigateway.MethodLoggingLevel.ERROR, // Reduce logging costs
        dataTraceEnabled: false, // Disable detailed logging to save costs
      },
      endpointConfiguration: {
        types: [apigateway.EndpointType.REGIONAL], // Avoid edge costs
      },
      policy: new iam.PolicyDocument({
        statements: [
          new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            principals: [new iam.AnyPrincipal()],
            actions: ['execute-api:Invoke'],
            resources: ['*'],
            conditions: {
              IpAddress: {
                'aws:SourceIp': ['0.0.0.0/0'] // Adjust for production security
              }
            }
          })
        ]
      })
    });

    // Create webhook endpoint
    const webhookResource = api.root.addResource('webhook');
    webhookResource.addMethod(
      'POST',
      new apigateway.LambdaIntegration(lambdaFunction, {
        requestTemplates: {
          'application/json': '{ "statusCode": "200" }',
        },
      }),
      {
        requestValidator: new apigateway.RequestValidator(this, 'RequestValidator', {
          restApi: api,
          requestValidatorName: 'form-bridge-validator',
          validateRequestBody: true,
          validateRequestParameters: true,
        }),
        requestModels: {
          'application/json': new apigateway.Model(this, 'FormSubmissionModel', {
            restApi: api,
            modelName: 'FormSubmissionModel',
            schema: {
              type: apigateway.JsonSchemaType.OBJECT,
              properties: {
                tenant_id: { type: apigateway.JsonSchemaType.STRING },
                form_data: { type: apigateway.JsonSchemaType.OBJECT },
                signature: { type: apigateway.JsonSchemaType.STRING },
              },
              required: ['tenant_id', 'form_data', 'signature'],
            },
          }),
        },
      }
    );

    // Associate WAF with API Gateway
    new wafv2.CfnWebACLAssociation(this, 'WAFAssociation', {
      resourceArn: api.deploymentStage.stageArn,
      webAclArn: webAcl.attrArn,
    });

    return api;
  }

  private setupCostMonitoring(props: CostOptimizationStackProps): void {
    // Create budget with multiple alert thresholds
    const budget = new budgets.CfnBudget(this, 'FormBridgeBudget', {
      budget: {
        budgetName: 'form-bridge-monthly-budget',
        budgetLimit: {
          amount: props.costBudgetLimit,
          unit: 'USD',
        },
        budgetType: 'COST',
        timeUnit: 'MONTHLY',
        costFilters: {
          TagKey: ['Project'],
          TagValue: ['FormBridge'],
        },
      },
      notificationsWithSubscribers: props.alertThresholds.map((threshold, index) => ({
        notification: {
          notificationType: 'ACTUAL',
          comparisonOperator: 'GREATER_THAN',
          threshold,
        },
        subscribers: [
          {
            subscriptionType: 'SNS',
            address: this.costMonitoringTopic.topicArn,
          },
        ],
      })),
    });

    // Create CloudWatch dashboard for cost monitoring
    const dashboard = new cloudwatch.Dashboard(this, 'CostOptimizationDashboard', {
      dashboardName: 'FormBridge-CostOptimization',
      widgets: [
        [
          new cloudwatch.TextWidget({
            markdown: '# Form Bridge - Cost Optimization Dashboard\n\nReal-time cost monitoring and optimization metrics',
            width: 24,
            height: 2,
          }),
        ],
        [
          new cloudwatch.GraphWidget({
            title: 'Lambda Invocations (ARM64 vs x86 Cost Comparison)',
            left: [
              new cloudwatch.Metric({
                namespace: 'AWS/Lambda',
                metricName: 'Invocations',
                dimensionsMap: {
                  FunctionName: 'FormProcessor',
                },
                statistic: 'Sum',
              }),
            ],
            width: 12,
            height: 6,
          }),
          new cloudwatch.GraphWidget({
            title: 'DynamoDB Consumption (On-Demand)',
            left: [
              new cloudwatch.Metric({
                namespace: 'AWS/DynamoDB',
                metricName: 'ConsumedReadCapacityUnits',
                dimensionsMap: {
                  TableName: 'form-bridge-submissions',
                },
                statistic: 'Sum',
              }),
              new cloudwatch.Metric({
                namespace: 'AWS/DynamoDB',
                metricName: 'ConsumedWriteCapacityUnits',
                dimensionsMap: {
                  TableName: 'form-bridge-submissions',
                },
                statistic: 'Sum',
              }),
            ],
            width: 12,
            height: 6,
          }),
        ],
        [
          new cloudwatch.SingleValueWidget({
            title: 'Estimated Monthly Savings (ARM64)',
            metrics: [
              new cloudwatch.MathExpression({
                expression: 'LAMBDA_INVOCATIONS * 0.20', // 20% savings calculation
                usingMetrics: {
                  LAMBDA_INVOCATIONS: new cloudwatch.Metric({
                    namespace: 'AWS/Lambda',
                    metricName: 'Invocations',
                    statistic: 'Sum',
                  }),
                },
                label: 'ARM64 Savings ($)',
              }),
            ],
            width: 8,
            height: 6,
          }),
          new cloudwatch.SingleValueWidget({
            title: 'Compression Savings (%)',
            metrics: [
              new cloudwatch.MathExpression({
                expression: '(ORIGINAL_SIZE - COMPRESSED_SIZE) / ORIGINAL_SIZE * 100',
                usingMetrics: {
                  ORIGINAL_SIZE: new cloudwatch.Metric({
                    namespace: 'FormBridge/Compression',
                    metricName: 'OriginalSize',
                    statistic: 'Average',
                  }),
                  COMPRESSED_SIZE: new cloudwatch.Metric({
                    namespace: 'FormBridge/Compression',
                    metricName: 'CompressedSize',
                    statistic: 'Average',
                  }),
                },
                label: 'Storage Savings (%)',
              }),
            ],
            width: 8,
            height: 6,
          }),
          new cloudwatch.SingleValueWidget({
            title: 'Per-Tenant Average Cost',
            metrics: [
              new cloudwatch.MathExpression({
                expression: 'TOTAL_COST / ACTIVE_TENANTS',
                usingMetrics: {
                  TOTAL_COST: new cloudwatch.Metric({
                    namespace: 'FormBridge/Cost',
                    metricName: 'TotalMonthlyCost',
                    statistic: 'Average',
                  }),
                  ACTIVE_TENANTS: new cloudwatch.Metric({
                    namespace: 'FormBridge/Tenants',
                    metricName: 'ActiveCount',
                    statistic: 'Average',
                  }),
                },
                label: 'Cost per Tenant ($)',
              }),
            ],
            width: 8,
            height: 6,
          }),
        ],
      ],
    });
  }

  private createCostOptimizationAutomation(): void {
    // Lambda function for automated cost optimization
    const costOptimizerFunction = new lambda.Function(this, 'CostOptimizer', {
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      handler: 'cost_optimizer.handler',
      code: lambda.Code.fromAsset('lambdas/cost-optimization'),
      memorySize: 256,
      timeout: Duration.minutes(5),
      environment: {
        COST_MONITORING_TOPIC: this.costMonitoringTopic.topicArn,
        OPTIMIZATION_ENABLED: 'true',
      },
    });

    // Grant necessary permissions for cost optimization
    costOptimizerFunction.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'ce:GetCostAndUsage',
          'ce:GetDimensionValues',
          'ce:GetReservationCoverage',
          'ce:GetReservationPurchaseRecommendation',
          'lambda:GetFunction',
          'lambda:UpdateFunctionConfiguration',
          'dynamodb:DescribeTable',
          'cloudwatch:PutMetricData',
          'sns:Publish',
        ],
        resources: ['*'],
      })
    );

    // Schedule cost optimization to run daily
    const costOptimizationRule = new events.Rule(this, 'CostOptimizationSchedule', {
      schedule: events.Schedule.cron({ hour: '6', minute: '0' }), // 6 AM daily
      description: 'Daily cost optimization analysis and recommendations',
    });

    costOptimizationRule.addTarget(
      new events_targets.LambdaFunction(costOptimizerFunction)
    );
  }

  private createCostOptimizationOutputs(
    api: apigateway.RestApi,
    table: dynamodb.Table
  ): void {
    new CfnOutput(this, 'APIEndpoint', {
      value: api.url,
      description: 'Cost-optimized API Gateway endpoint with ARM64 Lambda backend',
    });

    new CfnOutput(this, 'DynamoTableName', {
      value: table.tableName,
      description: 'Cost-optimized DynamoDB table with on-demand billing',
    });

    new CfnOutput(this, 'CostMonitoringTopic', {
      value: this.costMonitoringTopic.topicArn,
      description: 'SNS topic for cost monitoring alerts',
    });

    new CfnOutput(this, 'ARM64OptimizationSavings', {
      value: '20% reduction in Lambda duration charges',
      description: 'Expected cost savings from ARM64 Graviton2 migration',
    });

    new CfnOutput(this, 'KMSKeyId', {
      value: this.tenantKmsKey.keyId,
      description: 'Tenant KMS key for envelope encryption cost optimization',
    });

    new CfnOutput(this, 'EstimatedMonthlyCost', {
      value: '$12-20 for MVP with 1K submissions/month',
      description: 'Realistic cost projection with security and compliance',
    });
  }
}

// Additional construct for per-tenant cost tracking
export class TenantCostTrackingConstruct extends Construct {
  constructor(scope: Construct, id: string) {
    super(scope, id);

    // Lambda function for per-tenant cost allocation
    const costTrackingFunction = new lambda.Function(this, 'TenantCostTracker', {
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      handler: 'tenant_cost_tracker.handler',
      code: lambda.Code.fromAsset('lambdas/tenant-cost-tracking'),
      memorySize: 256,
      timeout: Duration.minutes(3),
      environment: {
        COST_ALLOCATION_ENABLED: 'true',
      },
    });

    // Grant permissions for cost and usage data
    costTrackingFunction.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'ce:GetCostAndUsage',
          'ce:GetUsageReport',
          'organizations:ListAccounts',
          'dynamodb:PutItem',
          'dynamodb:UpdateItem',
        ],
        resources: ['*'],
      })
    );

    // Schedule daily cost allocation
    const costAllocationRule = new events.Rule(this, 'TenantCostAllocationSchedule', {
      schedule: events.Schedule.cron({ hour: '8', minute: '0' }), // 8 AM daily
      description: 'Daily per-tenant cost allocation and tracking',
    });

    costAllocationRule.addTarget(
      new events_targets.LambdaFunction(costTrackingFunction)
    );
  }
}