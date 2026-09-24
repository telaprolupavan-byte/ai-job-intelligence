"""One evaluator per NERO AI capability (AJI-031).

Each `evaluate_*` function takes the dataset plus the pipeline callable
to evaluate (defaulting to the production adapter in
`services.ai_evaluation.pipelines`), so the scoring logic can be unit
tested with hand-built outputs and no production code in the loop.
"""
