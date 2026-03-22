Please fix the following frontend issues in the chatbot UI:

1. Logo rendering issue
The PSEG logo in the top-left is not displaying correctly (broken or missing). Please fix the image rendering so the logo loads properly across environments (local and Azure Web App). Check static asset paths, public folder usage, and deployment handling.

2. Incorrect chat history shown for new users/devices
When the app is opened on a new device or fresh browser session, old chat history from previous users is briefly visible on first load. This should NOT happen.

Expected behavior:
- A new user/session should start with an empty recent history
- Only the current user's chats should be loaded
- No stale or cached data should be rendered on initial load
- The UI should not require a refresh to correct this behavior

Likely issue:
Stale localStorage/session state or shared backend response is being rendered before proper initialization.

3. Feedback link not working in Help / Info modal
In the Help / Info popup, the footer still shows the placeholder text "Feedback form coming soon", even though the feedback form URL has already been configured in the code and in the Azure Web App environment settings.

Expected behavior:
- Replace "Feedback form coming soon" with a clickable link or button (e.g., "Feedback Form")
- Clicking it should open the configured feedback form URL
- The URL should be dynamically read from the frontend environment configuration
- Ensure it works correctly in the deployed Azure Web App, not just locally

Things to verify:
- Environment variable is correctly exposed to the frontend (e.g., NEXT_PUBLIC_ or REACT_APP_ prefix if required)
- No mismatch between variable name in code and Azure configuration
- UI is not using hardcoded placeholder text anymore
- Link is rendered and clickable in the modal footer

Please fix all three issues and ensure correct behavior on first load without requiring a refresh.
