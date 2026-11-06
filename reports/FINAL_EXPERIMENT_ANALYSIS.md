# FINAL_EXPERIMENT_ANALYSIS

Source: `results/experiment_analysis.json` (91 trials: 14 GENUINE, 58 TOOL_USE, 17 INFRA, 2 BUDGET_BREACH). Primary metrics pool GENUINE trials only; BUDGET_BREACH trials are exploratory budget findings with evidence preserved.

## full|ollama/llama3.2:1b|opencode
Trial classes: {"GENUINE": 0, "TOOL_USE": 24, "INFRA": 0, "BUDGET_BREACH": 0}
No genuine trials: every metric is null (reported as "no eligible executions", never as zero).

## full|ollama/qwen3:8b|opencode
Trial classes: {"GENUINE": 0, "TOOL_USE": 18, "INFRA": 6, "BUDGET_BREACH": 0}
No genuine trials: every metric is null (reported as "no eligible executions", never as zero).

## full|openrouter/nvidia/nemotron-3.5-super-vl:free|opencode
Trial classes: {"GENUINE": 7, "TOOL_USE": 0, "INFRA": 0, "BUDGET_BREACH": 0}
Eligible cases: 216
  functional_correctness: 211/216 = 0.9768518518518519
  schema_compliance: 216/216 = 1.0
  numerical_correctness: 172/172 = 1.0
  physical_unit_correctness: 78/78 = 1.0
  physical_equivalence_correctness: 78/78 = 1.0
  physical_integrity_correctness: 216/216 = 1.0
  semantic_integrity_failures: 0/216 = 0.0
  validity_state_correctness: 216/216 = 1.0
  engineering_decision_correctness: 0/0 = None
  execution_failures: 0/216 = 0.0
  malformed_response_rate: 0/216 = 0.0
  contract_violations: 5/216 = 0.023148148148148147
  end_to_end_correctness: 0/0 = None
  silent_corruption_rate: 0/216 = 0.0
  unsafe_acceptance_rate: 0/0 = None
  calibration_validity_recall: 0/0 = None
  uncertainty_calculation_accuracy: 0/0 = None
  false_rejection_rate: 0/0 = None
  boundary_decision_accuracy: 0/0 = None
  pass_at_3: 1/2 = 0.5
  pass_cubed: 1/2 = 0.5
  macro_average_task_accuracy = 0.9826388888888888
  per-task functional accuracy / SCR:
    S01: acc 91/96=0.9479166666666666, SCR 0/96=0.0
    S02: acc 90/90=1.0, SCR 0/90=0.0
    S03: acc 30/30=1.0, SCR 0/30=0.0

## pilot-history|ollama/llama3.2:1b|opencode
Trial classes: {"GENUINE": 0, "TOOL_USE": 7, "INFRA": 1, "BUDGET_BREACH": 0}
No genuine trials: every metric is null (reported as "no eligible executions", never as zero).

## pilot-history|ollama/qwen3:8b|opencode
Trial classes: {"GENUINE": 2, "TOOL_USE": 6, "INFRA": 3, "BUDGET_BREACH": 0}
Eligible cases: 60
  functional_correctness: 1/60 = 0.016666666666666666
  schema_compliance: 30/60 = 0.5
  numerical_correctness: 0/44 = 0.0
  physical_unit_correctness: 0/0 = None
  physical_equivalence_correctness: 0/0 = None
  physical_integrity_correctness: 16/60 = 0.26666666666666666
  semantic_integrity_failures: 0/60 = 0.0
  validity_state_correctness: 8/60 = 0.13333333333333333
  engineering_decision_correctness: 0/0 = None
  execution_failures: 30/60 = 0.5
  malformed_response_rate: 0/60 = 0.0
  contract_violations: 59/60 = 0.9833333333333333
  end_to_end_correctness: 0/0 = None
  silent_corruption_rate: 0/60 = 0.0
  unsafe_acceptance_rate: 0/0 = None
  calibration_validity_recall: 0/0 = None
  uncertainty_calculation_accuracy: 0/44 = 0.0
  false_rejection_rate: 0/0 = None
  boundary_decision_accuracy: 0/0 = None
  pass_at_3: 0/0 = None
  pass_cubed: 0/0 = None
  macro_average_task_accuracy = 0.016666666666666666
  per-task functional accuracy / SCR:
    S05: acc 1/60=0.016666666666666666, SCR 0/60=0.0

## pilot-history|openrouter/nvidia/nemotron-3.5-super-vl:free|opencode
Trial classes: {"GENUINE": 2, "TOOL_USE": 0, "INFRA": 1, "BUDGET_BREACH": 2}
Eligible cases: 62
  functional_correctness: 61/62 = 0.9838709677419355
  schema_compliance: 62/62 = 1.0
  numerical_correctness: 45/45 = 1.0
  physical_unit_correctness: 0/0 = None
  physical_equivalence_correctness: 0/0 = None
  physical_integrity_correctness: 62/62 = 1.0
  semantic_integrity_failures: 0/62 = 0.0
  validity_state_correctness: 62/62 = 1.0
  engineering_decision_correctness: 0/0 = None
  execution_failures: 0/62 = 0.0
  malformed_response_rate: 0/62 = 0.0
  contract_violations: 1/62 = 0.016129032258064516
  end_to_end_correctness: 0/0 = None
  silent_corruption_rate: 0/62 = 0.0
  unsafe_acceptance_rate: 0/0 = None
  calibration_validity_recall: 0/0 = None
  uncertainty_calculation_accuracy: 22/22 = 1.0
  false_rejection_rate: 0/0 = None
  boundary_decision_accuracy: 0/0 = None
  pass_at_3: 0/0 = None
  pass_cubed: 0/0 = None
  macro_average_task_accuracy = 0.984375
  per-task functional accuracy / SCR:
    S01: acc 31/32=0.96875, SCR 0/32=0.0
    S05: acc 30/30=1.0, SCR 0/30=0.0

## pilot|ollama/llama3.2:1b|opencode
Trial classes: {"GENUINE": 0, "TOOL_USE": 1, "INFRA": 2, "BUDGET_BREACH": 0}
No genuine trials: every metric is null (reported as "no eligible executions", never as zero).

## pilot|ollama/qwen3:8b|opencode
Trial classes: {"GENUINE": 0, "TOOL_USE": 1, "INFRA": 2, "BUDGET_BREACH": 0}
No genuine trials: every metric is null (reported as "no eligible executions", never as zero).

## pilot|openrouter/nvidia/nemotron-3.5-super-vl:free|opencode
Trial classes: {"GENUINE": 3, "TOOL_USE": 0, "INFRA": 0, "BUDGET_BREACH": 0}
Eligible cases: 107
  functional_correctness: 60/107 = 0.5607476635514018
  schema_compliance: 107/107 = 1.0
  numerical_correctness: 55/88 = 0.625
  physical_unit_correctness: 126/126 = 1.0
  physical_equivalence_correctness: 126/126 = 1.0
  physical_integrity_correctness: 74/107 = 0.6915887850467289
  semantic_integrity_failures: 0/107 = 0.0
  validity_state_correctness: 99/107 = 0.9252336448598131
  engineering_decision_correctness: 42/45 = 0.9333333333333333
  execution_failures: 0/107 = 0.0
  malformed_response_rate: 0/107 = 0.0
  contract_violations: 47/107 = 0.4392523364485981
  end_to_end_correctness: 0/45 = 0.0
  silent_corruption_rate: 41/107 = 0.38317757009345793
  unsafe_acceptance_rate: 3/23 = 0.13043478260869565
  calibration_validity_recall: 35/35 = 1.0
  uncertainty_calculation_accuracy: 62/62 = 1.0
  false_rejection_rate: 0/22 = 0.0
  boundary_decision_accuracy: 9/9 = 1.0
  pass_at_3: 0/0 = None
  pass_cubed: 0/0 = None
  macro_average_task_accuracy = 0.6458333333333334
  per-task functional accuracy / SCR:
    S01: acc 30/32=0.9375, SCR 0/32=0.0
    S05: acc 30/30=1.0, SCR 0/30=0.0
    S08: acc 0/45=0.0, SCR 41/45=0.9111111111111111

## supplementary|ollama/qwen2.5-coder:7b|opencode
Trial classes: {"GENUINE": 0, "TOOL_USE": 1, "INFRA": 0, "BUDGET_BREACH": 0}
No genuine trials: every metric is null (reported as "no eligible executions", never as zero).

## supplementary|opencode/beam-free|opencode
Trial classes: {"GENUINE": 0, "TOOL_USE": 0, "INFRA": 1, "BUDGET_BREACH": 0}
No genuine trials: every metric is null (reported as "no eligible executions", never as zero).

## supplementary|opencode/deepseek-v4.1-flash-free|opencode
Trial classes: {"GENUINE": 0, "TOOL_USE": 0, "INFRA": 1, "BUDGET_BREACH": 0}
No genuine trials: every metric is null (reported as "no eligible executions", never as zero).

## Budget-breach findings (excluded from primary metrics)
  [pilot-history] nemotron-3.5-super-vl:free S08 t0 acc=0.7111111111111111 cases=32/45 tokens=None reason=budget enforcer stopped the agent at 82740 tokens (token_budget_exceeded); work cut off before completion run=20261105T204856_382435Z_S08_opencode_trial0
  [pilot-history] nemotron-3.5-super-vl:free S01 t1 acc=0.96875 cases=31/32 tokens=None reason=budget enforcer stopped the agent at 64271 tokens (token_budget_exceeded); work cut off before completion run=20261106T010759_300310Z_S01_opencode_trial1

## Trial roster (all 91, with class + reason)
  [pilot] llama3.2:1b S01 t0 class=INFRA acc=0.0 reason=provider resolution/rate-limit error with no usage metadata
  [pilot] llama3.2:1b S05 t0 class=INFRA acc=0.0 reason=provider resolution/rate-limit error with no usage metadata
  [pilot] llama3.2:1b S08 t0 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [pilot] qwen3:8b S01 t0 class=INFRA acc=0.0 reason=provider resolution/rate-limit error with no usage metadata
  [pilot] qwen3:8b S05 t0 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [pilot] qwen3:8b S08 t0 class=INFRA acc=0.0 reason=provider resolution/rate-limit error with no usage metadata
  [pilot] nemotron-3.5-super-vl:free S01 t0 class=GENUINE acc=0.9375 reason=candidate code produced and graded
  [pilot] nemotron-3.5-super-vl:free S05 t0 class=GENUINE acc=1.0 reason=candidate code produced and graded
  [pilot] nemotron-3.5-super-vl:free S08 t0 class=GENUINE acc=0.0 reason=candidate code produced and graded
  [pilot-history] llama3.2:1b S01 t0 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [pilot-history] llama3.2:1b S05 t0 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [pilot-history] llama3.2:1b S08 t0 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [pilot-history] qwen3:8b S01 t0 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [pilot-history] qwen3:8b S05 t0 class=GENUINE acc=0.03333333333333333 reason=candidate code produced and graded
  [pilot-history] qwen3:8b S08 t0 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [pilot-history] nemotron-3.5-super-vl:free S01 t0 class=INFRA acc=0.0 reason=usage metadata absent (provider or launch failure)
  [pilot-history] llama3.2:1b S01 t0 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [pilot-history] llama3.2:1b S05 t0 class=INFRA acc=0.0 reason=provider resolution/rate-limit error with no usage metadata
  [pilot-history] qwen3:8b S01 t0 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [pilot-history] qwen3:8b S05 t0 class=GENUINE acc=0.0 reason=candidate code produced and graded
  [pilot-history] qwen3:8b S08 t0 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [pilot-history] qwen3:8b S01 t0 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [pilot-history] qwen3:8b S05 t0 class=INFRA acc=0.0 reason=provider resolution/rate-limit error with no usage metadata
  [pilot-history] llama3.2:1b S01 t0 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [pilot-history] llama3.2:1b S05 t0 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [pilot-history] llama3.2:1b S08 t0 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [pilot-history] qwen3:8b S01 t0 class=INFRA acc=0.0 reason=provider resolution/rate-limit error with no usage metadata
  [pilot-history] qwen3:8b S05 t0 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [pilot-history] qwen3:8b S08 t0 class=INFRA acc=0.0 reason=provider resolution/rate-limit error with no usage metadata
  [pilot-history] nemotron-3.5-super-vl:free S01 t0 class=GENUINE acc=0.96875 reason=candidate code produced and graded
  [pilot-history] nemotron-3.5-super-vl:free S05 t0 class=GENUINE acc=1.0 reason=candidate code produced and graded
  [pilot-history] nemotron-3.5-super-vl:free S08 t0 class=BUDGET_BREACH acc=0.7111111111111111 reason=budget enforcer stopped the agent at 82740 tokens (token_budget_exceeded); work cut off before compl
  [pilot-history] nemotron-3.5-super-vl:free S01 t1 class=BUDGET_BREACH acc=0.96875 reason=budget enforcer stopped the agent at 64271 tokens (token_budget_exceeded); work cut off before compl
  [full] qwen3:8b S01 t1 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] qwen3:8b S01 t2 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] qwen3:8b S01 t3 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] qwen3:8b S02 t1 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] qwen3:8b S02 t2 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] qwen3:8b S02 t3 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] qwen3:8b S03 t1 class=INFRA acc=0.0 reason=provider resolution/rate-limit error with no usage metadata
  [full] qwen3:8b S03 t2 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] qwen3:8b S03 t3 class=INFRA acc=0.0 reason=provider resolution/rate-limit error with no usage metadata
  [full] qwen3:8b S04 t1 class=INFRA acc=0.0 reason=provider resolution/rate-limit error with no usage metadata
  [full] qwen3:8b S04 t2 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] qwen3:8b S04 t3 class=INFRA acc=0.0 reason=provider resolution/rate-limit error with no usage metadata
  [full] qwen3:8b S05 t1 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] qwen3:8b S05 t2 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] qwen3:8b S05 t3 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] qwen3:8b S06 t1 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] qwen3:8b S06 t2 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] qwen3:8b S06 t3 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] qwen3:8b S07 t1 class=INFRA acc=0.0 reason=provider resolution/rate-limit error with no usage metadata
  [full] qwen3:8b S07 t2 class=INFRA acc=0.0 reason=usage metadata absent (provider or launch failure)
  [full] qwen3:8b S07 t3 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] qwen3:8b S08 t1 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] qwen3:8b S08 t2 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] qwen3:8b S08 t3 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S01 t1 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S01 t2 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S01 t3 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S02 t1 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S02 t2 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S02 t3 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S03 t1 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S03 t2 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S03 t3 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S04 t1 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S04 t2 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S04 t3 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S05 t1 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S05 t2 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S05 t3 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S06 t1 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S06 t2 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S06 t3 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S07 t1 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S07 t2 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S07 t3 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S08 t1 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S08 t2 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] llama3.2:1b S08 t3 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
  [full] nemotron-3.5-super-vl:free S01 t1 class=GENUINE acc=0.96875 reason=candidate code produced and graded
  [full] nemotron-3.5-super-vl:free S01 t2 class=GENUINE acc=0.9375 reason=candidate code produced and graded
  [full] nemotron-3.5-super-vl:free S01 t3 class=GENUINE acc=0.9375 reason=candidate code produced and graded
  [full] nemotron-3.5-super-vl:free S02 t1 class=GENUINE acc=1.0 reason=candidate code produced and graded
  [full] nemotron-3.5-super-vl:free S02 t2 class=GENUINE acc=1.0 reason=candidate code produced and graded
  [full] nemotron-3.5-super-vl:free S02 t3 class=GENUINE acc=1.0 reason=candidate code produced and graded
  [full] nemotron-3.5-super-vl:free S03 t1 class=GENUINE acc=1.0 reason=candidate code produced and graded
  [supplementary] beam-free S01 t1 class=INFRA acc=0.0 reason=provider quota exhausted before any implementation was produced
  [supplementary] deepseek-v4.1-flash-free S01 t1 class=INFRA acc=0.0 reason=provider quota exhausted before any implementation was produced
  [supplementary] qwen2.5-coder:7b S01 t1 class=TOOL_USE acc=0.0 reason=usage reported but solution.py is starter/empty/missing
