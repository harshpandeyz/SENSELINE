# Related work and research positioning

SENSELINE studies measurement integrity in AI-generated software: whether code preserves a sensor reading's physical meaning across decoding, conversion, calibration, uncertainty, validity checks, and a decision. It overlaps with broader engineering problem-solving and embedded-agent evaluation but uses a narrower executable construct. No first-of-kind claim is made, and this is a focused, not systematic, literature review.

## Adjacent engineering and agent benchmarks

| Work | Relationship to SENSELINE |
| --- | --- |
| [EngiBench: A Benchmark for Evaluating Large Language Models on Engineering Problem Solving](https://arxiv.org/abs/2509.17677) | Evaluates engineering problem solving across knowledge retrieval, contextual reasoning, and modeling. SENSELINE evaluates implementation of explicit measurement-processing contracts. |
| [Skilled AI Agents for Embedded and IoT Systems Development / IoT-SkillsBench](https://arxiv.org/abs/2603.19583) | Evaluates embedded and IoT programming tasks with hardware execution. SENSELINE uses synthetic measurements to isolate physical quantity, uncertainty, and conformity semantics. |
| [Closed-loop evaluation of LLM agents for embedded software development](https://arxiv.org/abs/2610.11447) | Studies iterative agent work on simulated embedded firmware. SENSELINE's main construct is cross-layer measurement integrity under independent numeric grading. |
| [Vibe-FDTR: An agent-oriented framework for reproducible frequency-domain thermoreflectance data analysis](https://arxiv.org/abs/2607.28200) | A close measurement-science neighbor that evaluates agent-assisted thermal metrology workflows. SENSELINE instead grades generated implementations across sensor decoding, calibration evidence, temporal validity, uncertainty, and conformity. |

These distinctions describe scope. They do not establish that SENSELINE is novel, superior, or the first benchmark in sensor metrology. Repository content and preprint versions can change; the links identify the cited primary records.

## Measurement-science foundations

The task rules draw on selected ideas in NIST [Technical Note 1297](https://www.nist.gov/pml/nist-technical-note-1297), including combined standard uncertainty and covariance propagation; the JCGM/BIPM [Guide to the Expression of Uncertainty in Measurement publications](https://www.bipm.org/en/committees/jc/jcgm/publications); NIST's [metrological traceability policy](https://www.nist.gov/metrology/metrological-traceability); and ILAC [G8:09/2019 guidance on decision rules and statements of conformity](https://ilac.org/publications-and-resources/ilac-guidance-series/). These authorities inform narrow synthetic contracts, not a general GUM implementation or universal decision rule.

[ISO/IEC 17025:2017](https://www.iso.org/standard/66912.html) is cited as relevant laboratory competence context only. SENSELINE does not assess conformity with ISO/IEC 17025, confer accreditation, or establish real-world safety.
