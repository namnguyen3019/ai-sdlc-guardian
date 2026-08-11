#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { GuardianStack } from '../lib/guardian-stack';

const app = new cdk.App();

new GuardianStack(app, 'AiSdlcGuardianStack', {
  description: 'AI-SDLC Guardian — PR risk analysis platform (storage foundation)',
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});
