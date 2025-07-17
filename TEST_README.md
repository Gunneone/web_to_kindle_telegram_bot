# Substack Metadata Extraction Tests

This file contains comprehensive tests for the Substack metadata extraction functionality in the Web to Kindle Telegram Bot.

## Test Coverage

The tests validate metadata extraction for three specific Substack URLs as requested in issue #25:

1. **Win-Win Publication**: https://substack.com/inbox/post/166333070
   - Expected Publication: Win-Win
   - Expected Author: Liv Boeree
   - Expected Title: Can We Save Our Internet From The Bots, AND Preserve Anonymity?

2. **Knowingless Publication**: https://aella.substack.com/p/pt3-the-status-wars-of-apes
   - Expected Publication: Knowingless
   - Expected Author: Aella
   - Expected Title: Pt3: The Status Wars of Apes

3. **Sustainability by Numbers**: https://www.sustainabilitybynumbers.com/p/population-growth-decline-climate
   - Expected Publication: Sustainability by Numbers
   - Expected Author: Hannah Ritchie
   - Expected Title: Population growth or decline will have little impact on climate change

## Test Features

- **Mock HTTP Requests**: Tests use mock HTML content to avoid network dependencies
- **Comprehensive Metadata Validation**: Verifies Title, Author, Publication, URL, and Content fields
- **Edge Case Testing**: Includes tests for missing og:site_name tags and error conditions
- **Content Validation**: Ensures extracted content includes author and publication metadata

## Running the Tests

```bash
# Run all tests with verbose output
python -m unittest test_substack_metadata.py -v

# Run a specific test
python -m unittest test_substack_metadata.TestSubstackMetadataExtraction.test_win_win_metadata_extraction -v

# Run tests quietly
python -m unittest test_substack_metadata.py
```

## Test Structure

- `TestSubstackMetadataExtraction`: Main test class containing all Substack-related tests
- Mock HTML fixtures for each target URL
- Mocked file operations and HTTP requests to ensure isolated testing
- Validation of both successful extraction and error conditions

## Dependencies

Tests require the same dependencies as the main application:
- unittest (built-in Python module)
- unittest.mock (built-in Python module)
- All dependencies from requirements.txt

The tests are designed to be self-contained and do not require external network access or file system modifications during execution.