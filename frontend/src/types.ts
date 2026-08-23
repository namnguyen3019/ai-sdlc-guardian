export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface RecentAnalysis {
  analysis_id: string;
  repository: string;
  pr_number: number;
  overall_risk: number;
  risk_level: RiskLevel;
  merge_recommendation: string;
  findings_total: number;
  timestamp: string;
}

export interface DashboardData {
  note?: string;
  totals: { analyses: number; average_risk: number; findings: number };
  risk_level_distribution: Record<RiskLevel, number>;
  findings_by_severity: Record<RiskLevel, number>;
  dimension_means: Record<string, number>;
  risk_trend: { timestamp: string; overall_risk: number }[];
  recent_analyses: RecentAnalysis[];
}

export const LEVELS: RiskLevel[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];

export const LEVEL_COLOR: Record<RiskLevel, string> = {
  LOW: '#3fb950',
  MEDIUM: '#d29922',
  HIGH: '#db6d28',
  CRITICAL: '#f85149',
};
