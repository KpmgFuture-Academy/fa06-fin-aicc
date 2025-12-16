"""
Evaluation Report Generator
============================

평가 결과 리포트 생성기
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from ..runners.e2e_runner import PipelineEvaluationResult
from ..metrics.base import EvaluationResult
from ..configs.kpi_thresholds import Priority, EvaluationLevel, BENCHMARK_STANDARDS


class ReportGenerator(ABC):
    """리포트 생성기 기본 클래스"""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def generate(self, result: PipelineEvaluationResult) -> str:
        """리포트 생성"""
        pass

    def save(self, content: str, filename: str) -> Path:
        """리포트 저장"""
        output_path = self.output_dir / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return output_path


class JSONReportGenerator(ReportGenerator):
    """JSON 형식 리포트 생성기"""

    def generate(self, result: PipelineEvaluationResult) -> str:
        return result.to_json(indent=2)

    def save_report(self, result: PipelineEvaluationResult) -> Path:
        timestamp = result.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"evaluation_report_{timestamp}.json"
        content = self.generate(result)
        return self.save(content, filename)


class HTMLReportGenerator(ReportGenerator):
    """HTML 형식 리포트 생성기"""

    def generate(self, result: PipelineEvaluationResult) -> str:
        """HTML 리포트 생성"""
        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E2E Evaluation Report - {result.timestamp.strftime('%Y-%m-%d %H:%M')}</title>
    <style>
        {self._get_styles()}
    </style>
</head>
<body>
    <div class="container">
        {self._generate_header(result)}
        {self._generate_summary(result)}
        {self._generate_module_results(result)}
        {self._generate_benchmark_comparison(result)}
        {self._generate_p0_details(result)}
        {self._generate_footer()}
    </div>
</body>
</html>
"""
        return html

    def save_report(self, result: PipelineEvaluationResult) -> Path:
        timestamp = result.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"evaluation_report_{timestamp}.html"
        content = self.generate(result)
        return self.save(content, filename)

    def _get_styles(self) -> str:
        return """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; color: #333; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }

        .header { background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; }
        .header h1 { font-size: 28px; margin-bottom: 10px; }
        .header .meta { opacity: 0.8; font-size: 14px; }

        .card { background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .card h2 { color: #1e3a5f; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #e0e0e0; }
        .card h3 { color: #2d5a87; margin: 15px 0 10px; }

        .status-badge { display: inline-block; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 14px; }
        .status-pass { background: #4caf50; color: white; }
        .status-fail { background: #f44336; color: white; }
        .status-warning { background: #ff9800; color: white; }

        .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
        .summary-item { text-align: center; padding: 15px; background: #f8f9fa; border-radius: 8px; }
        .summary-value { font-size: 32px; font-weight: bold; color: #1e3a5f; }
        .summary-label { font-size: 12px; color: #666; margin-top: 5px; }

        .metrics-table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        .metrics-table th, .metrics-table td { padding: 12px; text-align: left; border-bottom: 1px solid #e0e0e0; }
        .metrics-table th { background: #f8f9fa; color: #1e3a5f; font-weight: 600; }
        .metrics-table tr:hover { background: #f8f9fa; }

        .priority-p0 { color: #f44336; font-weight: bold; }
        .priority-p1 { color: #ff9800; }
        .priority-p2 { color: #2196f3; }

        .level-world_class { color: #4caf50; }
        .level-excellent { color: #8bc34a; }
        .level-good { color: #ffeb3b; }
        .level-needs_improvement { color: #ff9800; }
        .level-critical { color: #f44336; }

        .progress-bar { height: 8px; background: #e0e0e0; border-radius: 4px; overflow: hidden; }
        .progress-fill { height: 100%; border-radius: 4px; transition: width 0.3s; }
        .progress-pass { background: linear-gradient(90deg, #4caf50, #8bc34a); }
        .progress-fail { background: linear-gradient(90deg, #f44336, #ff5722); }

        .benchmark-comparison { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }
        .benchmark-item { padding: 15px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #1e3a5f; }

        .footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
        """

    def _generate_header(self, result: PipelineEvaluationResult) -> str:
        status_class = "status-pass" if result.overall_passed else "status-fail"
        status_text = "PASSED" if result.overall_passed else "FAILED"

        return f"""
        <div class="header">
            <h1>E2E Evaluation Report</h1>
            <div class="meta">
                <span>Generated: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</span> |
                <span>Mode: {result.config_mode.value.upper()}</span> |
                <span>Duration: {result.total_duration_seconds:.2f}s</span>
            </div>
            <div style="margin-top: 15px;">
                <span class="status-badge {status_class}">{status_text}</span>
            </div>
        </div>
        """

    def _generate_summary(self, result: PipelineEvaluationResult) -> str:
        stats = result.summary.get("overall_stats", {})

        return f"""
        <div class="card">
            <h2>Overview</h2>
            <div class="summary-grid">
                <div class="summary-item">
                    <div class="summary-value">{len(result.module_results)}</div>
                    <div class="summary-label">Modules Evaluated</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">{stats.get('passed_metrics', 0)}/{stats.get('total_metrics', 0)}</div>
                    <div class="summary-label">Metrics Passed</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">{stats.get('pass_rate', 0):.1f}%</div>
                    <div class="summary-label">Overall Pass Rate</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">{stats.get('p0_passed', 0)}/{stats.get('p0_total', 0)}</div>
                    <div class="summary-label">P0 Metrics Passed</div>
                </div>
            </div>
        </div>
        """

    def _generate_module_results(self, result: PipelineEvaluationResult) -> str:
        modules_html = ""

        for module_name, mod_result in result.module_results.items():
            status_class = "status-pass" if mod_result.overall_passed else "status-fail"
            status_text = "PASS" if mod_result.overall_passed else "FAIL"

            metrics_rows = ""
            for metric in mod_result.metrics:
                priority_class = f"priority-{metric.priority.value.lower()}"
                row_class = "" if metric.passed else "style='background: #fff5f5;'"

                metrics_rows += f"""
                <tr {row_class}>
                    <td><span class="{priority_class}">[{metric.priority.value}]</span> {metric.name}</td>
                    <td>{metric.value:.2f} {metric.unit}</td>
                    <td>{metric.target} {metric.unit}</td>
                    <td class="level-{metric.level.value}">{metric.level.value.replace('_', ' ').title()}</td>
                    <td><span class="status-badge {'status-pass' if metric.passed else 'status-fail'}">
                        {'PASS' if metric.passed else 'FAIL'}</span></td>
                </tr>
                """

            modules_html += f"""
            <div class="card">
                <h2>{module_name.upper().replace('_', ' ')}
                    <span class="status-badge {status_class}" style="float: right;">{status_text}</span>
                </h2>
                <div class="progress-bar">
                    <div class="progress-fill {'progress-pass' if mod_result.pass_rate >= 80 else 'progress-fail'}"
                         style="width: {mod_result.pass_rate}%"></div>
                </div>
                <p style="margin-top: 10px; color: #666;">Pass Rate: {mod_result.pass_rate:.1f}%</p>

                <table class="metrics-table">
                    <thead>
                        <tr>
                            <th>Metric</th>
                            <th>Value</th>
                            <th>Target</th>
                            <th>Level</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {metrics_rows}
                    </tbody>
                </table>
            </div>
            """

        return modules_html

    def _generate_benchmark_comparison(self, result: PipelineEvaluationResult) -> str:
        if not result.benchmark_comparison:
            return ""

        items_html = ""
        for module, metrics in result.benchmark_comparison.items():
            for metric_name, data in metrics.items():
                vs_status = "above" if data["vs_benchmark"] == "above" else "below"
                color = "#4caf50" if vs_status == "above" else "#f44336"

                items_html += f"""
                <div class="benchmark-item">
                    <strong>{module} - {metric_name}</strong><br>
                    <span style="font-size: 24px; color: {color};">{data['current']:.2f}</span>
                    <span style="color: #666;"> vs {data['benchmark']:.2f} (benchmark)</span><br>
                    <small style="color: {color};">{vs_status.upper()} benchmark</small>
                </div>
                """

        return f"""
        <div class="card">
            <h2>Industry Benchmark Comparison</h2>
            <div class="benchmark-comparison">
                {items_html}
            </div>
        </div>
        """

    def _generate_p0_details(self, result: PipelineEvaluationResult) -> str:
        p0_summary = result.summary.get("p0_metrics_summary", {})
        if not p0_summary:
            return ""

        rows = ""
        for metric_key, data in p0_summary.items():
            status_class = "status-pass" if data["passed"] else "status-fail"
            rows += f"""
            <tr>
                <td>{metric_key}</td>
                <td>{data['value']:.2f}</td>
                <td>{data['target']}</td>
                <td><span class="status-badge {status_class}">{'PASS' if data['passed'] else 'FAIL'}</span></td>
            </tr>
            """

        return f"""
        <div class="card">
            <h2>P0 (Critical) Metrics Detail</h2>
            <table class="metrics-table">
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                        <th>Target</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        """

    def _generate_footer(self) -> str:
        return f"""
        <div class="footer">
            <p>KPMG 6기 2팀 - 카드사 AICC 자동화 시스템</p>
            <p>Generated by E2E Evaluation Pipeline v1.0</p>
        </div>
        """


class MarkdownReportGenerator(ReportGenerator):
    """Markdown 형식 리포트 생성기"""

    def generate(self, result: PipelineEvaluationResult) -> str:
        stats = result.summary.get("overall_stats", {})

        md = f"""# E2E Evaluation Report

**Generated:** {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**Mode:** {result.config_mode.value.upper()}
**Duration:** {result.total_duration_seconds:.2f}s

## Summary

| Metric | Value |
|--------|-------|
| Overall Status | {'PASSED' if result.overall_passed else 'FAILED'} |
| P0 Status | {'PASSED' if result.p0_passed else 'FAILED'} |
| Modules Evaluated | {len(result.module_results)} |
| Metrics Passed | {stats.get('passed_metrics', 0)}/{stats.get('total_metrics', 0)} |
| Pass Rate | {stats.get('pass_rate', 0):.1f}% |

## Module Results

"""
        for module_name, mod_result in result.module_results.items():
            md += f"""### {module_name.upper().replace('_', ' ')}

**Status:** {'PASS' if mod_result.overall_passed else 'FAIL'} | **Pass Rate:** {mod_result.pass_rate:.1f}%

| Priority | Metric | Value | Target | Status |
|----------|--------|-------|--------|--------|
"""
            for metric in mod_result.metrics:
                status = 'PASS' if metric.passed else 'FAIL'
                md += f"| {metric.priority.value} | {metric.name} | {metric.value:.2f} {metric.unit} | {metric.target} {metric.unit} | {status} |\n"

            md += "\n"

        return md

    def save_report(self, result: PipelineEvaluationResult) -> Path:
        timestamp = result.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"evaluation_report_{timestamp}.md"
        content = self.generate(result)
        return self.save(content, filename)
