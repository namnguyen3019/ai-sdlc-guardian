"""AWS Lambda handlers for the Step Functions workflow.

``analyze`` runs the pipeline on a supplied diff; ``store`` persists the
report and publishes metrics. Week 3 adds the webhook receiver and the
GitHub comment publisher.
"""
