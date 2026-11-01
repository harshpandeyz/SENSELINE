# Independent technical review package

This package is prepared for an external reviewer. No independent metrologist has reviewed or approved SENSELINE to date. The reviewer should compare each task statement, reference, oracle, hidden fixtures, and report generation; this document is not a sign-off.

## Review questions

### Calibration validity (S04/S08)

- Are applicability predicates and the deterministic reason order understandable and internally consistent?
- Are certificate date/range boundaries inclusive as specified? Are malformed/missing fields distinguished from checks that cannot be evaluated?
- Is certificate uncertainty only validated, rather than combined with S05, justified by the missing distribution/coverage/correlation information?
- Does S08 check certificate range against the corrected output value and final unit, and does an unavailable corrected value avoid inventing a range result?

### Measurement uncertainty (S05/S08)

- For Type A, does the implementation calculate the sample standard deviation of the mean, using sample variance divided by sample count?
- For Type B rectangular half-width a, is standard uncertainty a/√3?
- Is combined variance computed as Σ(c_i u_i)^2 + 2Σ(i<j)c_i c_j rho_ij u_i u_j, with symmetry, unit diagonal, bounded correlations, and positive-semidefinite validation?
- Is coverage factor handling consistent with the task's expanded uncertainty U = k u_c?
- Is the fixed three-contributor limit appropriately disclosed?

### Dimensional consistency (S02/S03/S08)

- Are supported affine transforms and dimension families correct for C/F/K, Pa/kPa/bar, and V/mV?
- Does S08 convert the measurement once before calibration? Are gain, offset, and temperature coefficient dimensions stated consistently?
- The S08 environmental interval is explicitly Celsius even for Fahrenheit/Kelvin output; is that contract clear and physically intended?
- S08 uncertainty inputs are specified as post-calibration in final units, sensitivities dimensionless, and covariance in final-unit squared. Is that a useful and unambiguous benchmark assumption?

### Conformity rule (S06/S08)

- Is acceptance based on the complete inclusive uncertainty interval lying within the specification interval?
- Is rejection limited to intervals wholly outside the specification? Are overlaps indeterminate?
- Is the rule appropriately described as a task-specific decision rule rather than a universal metrology recommendation?

## Independent numerical checks

The frozen S08 examples include 68 °F → 20 °C → 20.35 °C after calibration with u_c = 0.1 °C and U = 0.2 °C; a signed count of −50 at 0.1 °C/count with +5 °C compensation yields −4.9 °C; two rectangular contributors with rho = 0.5 yield u_c = 1 and U = 2 in the specified output unit; Celsius input 25 °C to Fahrenheit output gives 77 °F before correction and 78.9 °F after the stated °F/°C compensation. Boundary and simultaneous-failure fixtures are detailed in the task package and tests. These are internal consistency checks, not external approval.

## Technical sources

- NIST, [Technical Note 1297](https://www.nist.gov/pml/nist-technical-note-1297), including [combined standard uncertainty](https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-5-combined-standard-uncertainty) and the [law of propagation of uncertainty](https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-appendix-law-propagation-uncertainty).
- JCGM/BIPM, [Guide to the Expression of Uncertainty in Measurement publications](https://www.bipm.org/en/committees/jc/jcgm/publications).
- ILAC, [G8:09/2019 decision rules and statements of conformity](https://ilac.org/publications-and-resources/ilac-guidance-series/).
- NIST, [metrological traceability policy](https://www.nist.gov/metrology/metrological-traceability).

The benchmark does not claim compliance with ISO/IEC 17025, accreditation, or safety certification. Any reviewer name, date, and conclusion should be recorded only after an actual review is completed.
