"""Amazon Bedrock AI analysis (implemented in Week 2).

Week 1 defines only the interface so the pipeline shape is stable: the AI
analyzer is just another ``BaseAnalyzer`` whose findings land in the
``ai`` category and are scored by the deterministic engine — the LLM never
decides the final score. Repository code passed to the model is untrusted
input; instructions found inside code or comments must never be followed.
"""
