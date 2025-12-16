---
description: Run baseline tests and show results
---

# Run Baseline Tests

Manually run the baseline test suite and display detailed results.

## Purpose

Baseline tests establish the starting state before making changes:
- Verify existing functionality works
- Identify pre-existing failures
- Provide comparison for changes you make
- Ensure you don't break existing features

## Actions

1. **Detect Project Type**
   Check for project configuration files:
   - `package.json` -> Node.js (npm test)
   - `Cargo.toml` -> Rust (cargo test)
   - `go.mod` -> Go (go test ./...)
   - `pyproject.toml` or `setup.py` -> Python (pytest)
   - `pom.xml` -> Java Maven (mvn test)
   - `build.gradle` -> Java Gradle (./gradlew test)

2. **Run Tests**
   Execute the appropriate test command with a reasonable timeout (5 minutes max).
   Capture both stdout and stderr.

3. **Parse Results**
   Extract from output:
   - Total tests run
   - Tests passed
   - Tests failed
   - Tests skipped
   - Duration

4. **Display Results**
   Format output:
   ```
   === BASELINE TEST RESULTS ===

   Project Type: {type}
   Test Command: {command}

   Results:
     Total:   {total} tests
     Passed:  {passed} tests
     Failed:  {failed} tests
     Skipped: {skipped} tests
     Duration: {duration}s

   Status: PASS / FAIL

   {If failures, list them with file locations}
   ```

5. **Log to Progress File**
   Add entry to `claude-progress.txt`:
   ```
   [timestamp] BASELINE: {passed}/{total} tests passed
   ```

6. **Provide Recommendations**
   - If all pass: "Baseline established. Safe to make changes."
   - If failures: "Fix these failures before making other changes, or they may mask new issues."

## Example Output

```
=== BASELINE TEST RESULTS ===

Project Type: python
Test Command: pytest -v

Results:
  Total:   42 tests
  Passed:  40 tests
  Failed:  2 tests
  Skipped: 0 tests
  Duration: 3.45s

Status: FAIL

Failed Tests:
  - tests/test_auth.py::test_login_redirect
  - tests/test_api.py::test_rate_limiting

Recommendation: Review and fix these 2 failing tests before making other changes.
```

## Notes

- Tests are run with output captured, so you'll see the full results
- The command handles test failures gracefully (won't crash on non-zero exit)
- Results are logged to progress file for future reference
- If no test command is detected, suggests setting up tests
