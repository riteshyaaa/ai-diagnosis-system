# Changelog

## Unreleased — safety and evidence integrity

- Prevented public self-registration from assigning roles; new accounts are clinician-only.
- Bounded application-level reads on both case-image and direct-inference uploads.
- Removed automatic random-weight model creation and synthetic placeholder evaluation/calibration from registry initialization.
- Made unpromoted model versions unavailable to default inference; promotion now checks artifact presence and checksum.
- Cleared unsupported active-model, checksum, calibrator, and performance claims from the checked-in model metadata.
- Return service-unavailable for missing model artifacts and avoid changing a case to `PROCESSING` before inference succeeds.
- Removed fabricated audit rows and the unsupported 21 CFR Part 11 label from the audit page.
- Updated tests to assert fail-closed inference rather than random-weight clinical-looking output; added upload and role-escalation regression tests.
- Added repository audit and model card; prior baseline test/build checks were blocked because project dependencies are not installed in the execution environment.
